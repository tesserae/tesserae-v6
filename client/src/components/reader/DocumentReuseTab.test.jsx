/**
 * The Reuse tab's documentary group ("In inscriptions and papyri"):
 * inscriptions/papyri that quote or near-quote the selected line, from
 * GET /api/reuse/line's `documents` field (backend/reuse_documents.py),
 * shown only behind the documents_trial session flag (?documents=1 --
 * the same trial LineSearch.jsx's documents collection uses).
 */
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import ResultsPanel from './ResultsPanel';

const UNITS = [
  { ref: 'verg. aen. 1.1', text: 'Arma virumque cano, Troiae qui primus ab oris' },
];

const REUSE_RESPONSE_WITH_DOCUMENTS = {
  available: true,
  quotations: [],
  documents: [
    {
      doc_id: 'edr:GRAFFITO1', ref: 'edr:GRAFFITO1', language: 'la',
      text: 'Arma virumque cano Troiae qui primus ab oris',
      bold_spans: [[0, 45]], shared: 16, jaccard: 1.0, span_len: 1,
      restored: false, tier: 'strict',
      credit: { principal_edition: 'CIL IV 9131' },
      date_not_before: 1, date_not_after: 79,
      ancient_place: 'Pompeii', modern_place: null, region: 'Campania',
      text_type_label: 'graffito', object_type_label: 'wall', material_label: 'plaster',
    },
    {
      doc_id: 'edh:FRAG1', ref: 'edh:FRAG1', language: 'la',
      text: 'arma uirumque', bold_spans: [[0, 4]], shared: 1, jaccard: 0.05,
      span_len: 1, restored: true, tier: 'possible',
      credit: null, date_not_before: null, date_not_after: null,
      ancient_place: null, modern_place: null, region: null,
      text_type_label: null, object_type_label: null, material_label: null,
    },
  ],
  meta: { corpus_version: '2026-10-08' },
};

function mount() {
  render(
    <ResultsPanel
      selection={{ refStart: 'verg. aen. 1.1', refEnd: 'verg. aen. 1.1', startIdx: 0, endIdx: 0 }}
      language="la"
      work="vergil.aeneid"
      units={UNITS}
      onOpenPassage={vi.fn()}
      initialTab="reuse"
    />
  );
}

beforeEach(() => {
  global.fetch = vi.fn(() => Promise.resolve({
    status: 200,
    json: () => Promise.resolve(REUSE_RESPONSE_WITH_DOCUMENTS),
  }));
});

afterEach(() => {
  sessionStorage.clear();
});

describe('behind the documents_trial flag', () => {
  it('does not show the documentary group when the flag is off', async () => {
    mount();
    await waitFor(() => expect(global.fetch).toHaveBeenCalled());
    expect(screen.queryByText(/In inscriptions and papyri/)).toBeNull();
  });

  it('shows the documentary group once ?documents=1 has been seen this session', async () => {
    sessionStorage.setItem('tesserae_documents_trial', '1');
    mount();
    await waitFor(() => expect(screen.getByText(/In inscriptions and papyri/)).toBeTruthy());
  });
});

describe('a strict document hit', () => {
  beforeEach(() => sessionStorage.setItem('tesserae_documents_trial', '1'));

  it('shows the edition, place and date', async () => {
    mount();
    await waitFor(() => expect(screen.getByText('CIL IV 9131')).toBeTruthy());
    expect(screen.getByText(/Pompeii/)).toBeTruthy();
  });

  it('shows the document text', async () => {
    mount();
    await waitFor(() => expect(screen.getByText(/Arma virumque cano Troiae qui primus ab oris/)).toBeTruthy());
  });

  it('links to the /document page', async () => {
    mount();
    await waitFor(() => expect(screen.getByText('CIL IV 9131')).toBeTruthy());
    const link = screen.getByText('CIL IV 9131').closest('a');
    expect(link.getAttribute('href')).toContain('/document?doc=edr%3AGRAFFITO1');
    expect(link.getAttribute('href')).toContain('lang=la');
  });
});

describe('a possible-tier (shared==1) document hit', () => {
  beforeEach(() => sessionStorage.setItem('tesserae_documents_trial', '1'));

  it('sits behind a collapsed "Possible echoes" toggle, not shown directly', async () => {
    mount();
    await waitFor(() => expect(screen.getByText(/Possible echoes/)).toBeTruthy());
    expect(screen.queryByText(/match on restored text/)).toBeNull();
  });

  it('shows the restored-text note once the toggle is opened', async () => {
    mount();
    await waitFor(() => expect(screen.getByText(/Possible echoes/)).toBeTruthy());
    screen.getByText(/Possible echoes/).closest('button').click();
    await waitFor(() => expect(screen.getByText(/match on restored text/)).toBeTruthy());
  });
});

describe('an uncredited document (no metadata.db row)', () => {
  beforeEach(() => sessionStorage.setItem('tesserae_documents_trial', '1'));

  it('falls back to the doc_id as the card title', async () => {
    mount();
    await waitFor(() => expect(screen.getByText(/Possible echoes/)).toBeTruthy());
    screen.getByText(/Possible echoes/).closest('button').click();
    await waitFor(() => expect(screen.getByText('edh:FRAG1')).toBeTruthy());
  });
});
