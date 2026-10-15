/**
 * The Reuse tab with the inscriptions and papyri switched off: the server's
 * document hits are named in one line, and "Show them" switches them on.
 */
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import ResultsPanel from './ResultsPanel';
import { resetScholarshipLanguagesCache } from '../../utils/scholarshipLanguages';
import { setCollection, getSnapshot } from '../../collections/collectionsStore';

const UNITS = [{ ref: 'verg. aen. 1.1', text: 'Arma virumque cano, Troiae qui primus ab oris' }];
const SELECTION = { refStart: 'verg. aen. 1.1', refEnd: 'verg. aen. 1.1', startIdx: 0, endIdx: 0 };
const DOC = {
  collection: 'documents', doc_id: 'edr:aEDR175604', ref: 'edr:aEDR175604', language: 'la', source: 'edr',
  text: 'Arma virumque cano, Troiae qui primus ab oris', bold_spans: [[0, 4]], tier: 'strict', shared: 16,
  ancient_place: 'Pompeii', modern_place: 'Pompei (Napoli)', date_not_before: 1, date_not_after: 79,
  credit: { licence_name: 'CC BY 4.0' }, text_type_label: 'other', object_type_label: 'building', material_label: 'plaster',
};
const REUSE = { available: true, quotations: [], documents: [DOC, { ...DOC, doc_id: 'edr:x2', ref: 'edr:x2' }], meta: {} };

function mockFetch() {
  global.fetch = vi.fn((url) => {
    if (String(url).startsWith('/api/reuse/line')) return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(REUSE) });
    return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve({}) });
  });
}

beforeEach(() => {
  resetScholarshipLanguagesCache();
  window.localStorage.clear();
  window.sessionStorage.clear();
  setCollection('inscriptions', false);
  setCollection('papyri', false);
});
afterEach(() => { cleanup(); delete global.fetch; });

describe('Reuse with the documents switched off', () => {
  it('names the hidden document hits and switches them on', async () => {
    mockFetch();
    render(<ResultsPanel selection={SELECTION} language="la" work="vergil.aeneid.part.1.tess"
                         units={UNITS} initialTab="reuse" />);
    const note = await screen.findByTestId('reuse-documents-hidden');
    expect(note.textContent).toContain('2 inscriptions and papyri also quote this line.');
    expect(screen.queryByText('In inscriptions and papyri')).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: 'Show them' }));
    expect(getSnapshot().on.inscriptions).toBe(true);
    expect(getSnapshot().on.papyri).toBe(true);
    await waitFor(() => expect(screen.getByText('In inscriptions and papyri')).toBeInTheDocument());
    expect(screen.queryByTestId('reuse-documents-hidden')).toBeNull();
  });
});
