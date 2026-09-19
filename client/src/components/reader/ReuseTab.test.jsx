/**
 * The Reuse tab: lines from other works that verbatim-repeat the selected
 * line, from the corpus-wide reuse table (GET /api/reuse/line).
 */
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
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

// TIERED (2026-09-19): strict pairs (tier 'strict' or absent, kept by the
// original jaccard/containment rules) list first with no heading; possible
// pairs (tier 'possible', kept only by the rare-single-ngram rule -- one
// rare shared phrase, weaker evidence) sit behind a collapsed section a
// reader opens on purpose.
const TIERED_RESPONSE = {
  available: true,
  quotations: [
    {
      work: 'macrobius.saturnalia', ref: 'macro. sat. 5.2.8', language: 'la',
      text: 'Troiae qui primus ab oris, quoted at length', shared: 10,
      jaccard: 0.2, span_len: 1, year: 400, tier: 'strict',
    },
    {
      work: 'seneca.epistulae', ref: 'sen. ep. 113.25', language: 'la',
      text: 'arma virumque cano, buried in an unrelated sentence', shared: 1,
      jaccard: 0.03, span_len: 1, year: 65, tier: 'possible',
    },
  ],
  meta: { corpus_version: '2026-08-16' },
};

describe('tiered results: strict shown directly, possible collapsed', () => {
  it('shows the strict result immediately, with no heading above it', async () => {
    global.fetch = vi.fn(() => Promise.resolve({ status: 200, json: () => Promise.resolve(TIERED_RESPONSE) }));
    mount();
    await waitFor(() => expect(screen.getByText(/Macrobius/)).toBeTruthy());
    expect(screen.queryByText(/^strict$/i)).toBeNull();
  });

  it('does not show the possible result until the section is expanded', async () => {
    global.fetch = vi.fn(() => Promise.resolve({ status: 200, json: () => Promise.resolve(TIERED_RESPONSE) }));
    mount();
    await waitFor(() => expect(screen.getByText(/Macrobius/)).toBeTruthy());
    expect(screen.queryByText(/Seneca/)).toBeNull();
    expect(screen.getByText(/Possible echoes/)).toBeTruthy();
  });

  it('reveals the possible result on clicking the collapsed section', async () => {
    global.fetch = vi.fn(() => Promise.resolve({ status: 200, json: () => Promise.resolve(TIERED_RESPONSE) }));
    mount();
    await waitFor(() => expect(screen.getByText(/Macrobius/)).toBeTruthy());
    fireEvent.click(screen.getByText(/Possible echoes/));
    expect(screen.getByText(/Seneca/)).toBeTruthy();
    expect(screen.getByText(/arma virumque cano, buried in an unrelated sentence/)).toBeTruthy();
  });

  it('names the possible count in the collapsed section label', async () => {
    global.fetch = vi.fn(() => Promise.resolve({ status: 200, json: () => Promise.resolve(TIERED_RESPONSE) }));
    mount();
    await waitFor(() => expect(screen.getByText(/Macrobius/)).toBeTruthy());
    expect(screen.getByText(/Possible echoes.*1/)).toBeTruthy();
  });

  it('clicking a possible result still opens it in the Reader', async () => {
    global.fetch = vi.fn(() => Promise.resolve({ status: 200, json: () => Promise.resolve(TIERED_RESPONSE) }));
    const { onOpenPassage } = mount();
    await waitFor(() => expect(screen.getByText(/Macrobius/)).toBeTruthy());
    fireEvent.click(screen.getByText(/Possible echoes/));
    screen.getByText(/arma virumque cano, buried in an unrelated sentence/).closest('button').click();
    expect(onOpenPassage).toHaveBeenCalledWith(
      expect.objectContaining({ work: 'seneca.epistulae', ref_start: 'sen. ep. 113.25' })
    );
  });

  it('shows only the collapsed section when every pair is possible', async () => {
    global.fetch = vi.fn(() => Promise.resolve({
      status: 200,
      json: () => Promise.resolve({ available: true, quotations: [TIERED_RESPONSE.quotations[1]] }),
    }));
    mount();
    await waitFor(() => expect(screen.getByText(/Possible echoes/)).toBeTruthy());
    expect(screen.queryByText(/no other work/i)).toBeNull();
  });
});
