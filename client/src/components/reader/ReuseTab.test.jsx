/**
 * The Reuse tab: lines from other works that verbatim-repeat the selected
 * line, from the corpus-wide reuse table (GET /api/reuse/line).
 */
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import ResultsPanel from './ResultsPanel';

const UNITS = [
  { ref: 'verg. aen. 1.1', text: 'Arma virumque cano, Troiae qui primus ab oris' },
  { ref: 'verg. aen. 1.2', text: 'Italiam fato profugus' },
];

const REUSE_RESPONSE = {
  available: true,
  quotations: [
    {
      work: 'macrobius.saturnalia', ref: 'macro. sat. 5.2.8', language: 'la',
      text: 'Troiae qui primus ab oris, quoted at length', shared: 10,
      jaccard: 0.2, span_len: 1, year: 400,
    },
    {
      work: 'servius.commentary', ref: 'serv. 1.1', language: 'la',
      text: 'a note on arma virumque', shared: 4, jaccard: 0.15, span_len: 1, year: 400,
    },
  ],
  meta: { corpus_version: '2026-08-16' },
};

function mount(props = {}) {
  const onOpenPassage = vi.fn();
  render(
    <ResultsPanel
      selection={{ refStart: 'verg. aen. 1.1', refEnd: 'verg. aen. 1.1', startIdx: 0, endIdx: 0 }}
      language="la"
      work="vergil.aeneid"
      units={UNITS}
      onOpenPassage={onOpenPassage}
      initialTab="reuse"
      {...props}
    />
  );
  return { onOpenPassage };
}

beforeEach(() => {
  global.fetch = vi.fn(() => Promise.resolve({
    status: 200,
    json: () => Promise.resolve(REUSE_RESPONSE),
  }));
});

describe('the tab asks for the selected line, not the whole work', () => {
  it('fetches /api/reuse/line with the selected ref', async () => {
    mount();
    await waitFor(() => expect(global.fetch).toHaveBeenCalled());
    const url = global.fetch.mock.calls[0][0];
    expect(url).toContain('/api/reuse/line');
    expect(url).toContain('work=vergil.aeneid');
    expect(url).toContain('ref=verg.%20aen.%201.1');
    expect(url).toContain('language=la');
  });

  it('one fetch per selected line for a multi-line selection', async () => {
    mount({ selection: { refStart: 'verg. aen. 1.1', refEnd: 'verg. aen. 1.2', startIdx: 0, endIdx: 1 } });
    await waitFor(() => expect(global.fetch.mock.calls.length).toBe(2));
  });
});

describe('results are grouped by work and shown with their text', () => {
  it('shows both quoting works with their line text', async () => {
    mount();
    await waitFor(() => expect(screen.getByText(/Macrobius/)).toBeTruthy());
    expect(screen.getByText(/Troiae qui primus ab oris, quoted at length/)).toBeTruthy();
    expect(screen.getByText(/Servius/)).toBeTruthy();
  });

  it('clicking a result opens it in the Reader', async () => {
    const { onOpenPassage } = mount();
    await waitFor(() => expect(screen.getByText(/Macrobius/)).toBeTruthy());
    screen.getByText(/Troiae qui primus ab oris, quoted at length/).closest('button').click();
    expect(onOpenPassage).toHaveBeenCalledWith(
      expect.objectContaining({ work: 'macrobius.saturnalia', ref_start: 'macro. sat. 5.2.8' })
    );
  });

  it('states what the table is, once, at the top of the tab', async () => {
    mount();
    await waitFor(() => expect(screen.getByText(/word-triples/)).toBeTruthy());
  });
});

describe('a language with no reuse table', () => {
  it('reads as "not built", not an error', async () => {
    global.fetch = vi.fn(() => Promise.resolve({ status: 404, json: () => Promise.resolve({ error: 'no table' }) }));
    mount({ language: 'grc' });
    await waitFor(() => expect(screen.getByText(/no reuse table/i)).toBeTruthy());
  });
});

describe('a line nothing else repeats', () => {
  it('says so plainly rather than showing an empty list', async () => {
    global.fetch = vi.fn(() => Promise.resolve({
      status: 200,
      json: () => Promise.resolve({ available: true, quotations: [] }),
    }));
    mount();
    await waitFor(() => expect(screen.getByText(/no other work/i)).toBeTruthy());
  });
});
