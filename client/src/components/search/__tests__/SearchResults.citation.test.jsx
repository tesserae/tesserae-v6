import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen } from '@testing-library/react';

// Same stubs as SearchResults.restrictedCredit.test.jsx: Chart.js needs a
// real canvas jsdom doesn't provide, and every search transport lives in
// utils/api, which this file never needs to call.
vi.mock('react-chartjs-2', async () => {
  const { forwardRef, createElement } = await vi.importActual('react');
  return {
    Bar: forwardRef((props, ref) => createElement('button', { ref }, 'chart bar')),
  };
});
vi.mock('chart.js', () => ({
  Chart: { register: () => {} },
  CategoryScale: {}, LinearScale: {}, BarElement: {},
  Title: {}, Tooltip: {}, Legend: {},
}));
vi.mock('../../../utils/api', () => ({
  searchTexts: vi.fn(),
  searchTextsStream: vi.fn(),
  searchFusionStream: vi.fn(),
  searchSemanticCross: vi.fn(),
  searchHapax: vi.fn(),
  searchBigrams: vi.fn(),
  fetchResultPage: vi.fn(),
  fetchAllResults: vi.fn(),
  wildcardSearch: vi.fn(),
}));

import SearchResults from '../SearchResults';

const baseProps = {
  loading: false,
  error: null,
  pageSize: 50,
  onPageSizeChange: () => {},
  searchRunId: 1,
  sortBy: 'score',
  setSortBy: () => {},
  searchStats: null,
  language: 'grc',
};

afterEach(() => {
  delete global.fetch;
});

// Issue #566: the server now builds the full "<Author>, <Work title> <locus>"
// citation itself and attaches it to each side as `citation`. The browser
// must show that string when present, and fall back to the old tag-parsing
// formatReference() only for a result that predates the field (an old cached
// search, a saved parallel from before this shipped).
describe('SearchResults — server-built citation (issue #566)', () => {
  it('renders the server citation when the result carries one', () => {
    global.fetch = vi.fn(() => Promise.resolve({ ok: true, json: () => Promise.resolve({}) }));
    const row = {
      source: {
        ref: 'Ach. Tat. 1.1.0',
        text: 'source wording',
        citation: 'Achilles Tatius, Leucippe and Clitophon 1.1.0',
      },
      target: {
        ref: 'hld. 2.3',
        text: 'target wording',
        citation: 'Heliodorus, Aethiopica 2.3',
      },
      fused_score: 2.4,
      matched_words: [],
      features: {},
    };
    render(<SearchResults {...baseProps} results={[row]} />);
    expect(screen.getByText('Achilles Tatius, Leucippe and Clitophon 1.1.0')).toBeInTheDocument();
    expect(screen.getByText('Heliodorus, Aethiopica 2.3')).toBeInTheDocument();
    // The raw tag -- what the old tag-parsing fallback would have produced
    // for an unmapped abbreviation ("Ach..Tat..1.1.0") -- must not appear.
    expect(screen.queryByText(/Ach\.\.Tat\.\./)).not.toBeInTheDocument();
  });

  it('falls back to formatReference when a result has no citation field', () => {
    global.fetch = vi.fn(() => Promise.resolve({ ok: true, json: () => Promise.resolve({}) }));
    const row = {
      source: { ref: 'verg. aen. 1.1', text: 'arma virumque cano' },
      target: { ref: 'ov. met. 1.1', text: 'in noua fert animus' },
      fused_score: 1.8,
      matched_words: [],
      features: {},
    };
    render(<SearchResults {...baseProps} language="la" results={[row]} />);
    // formatReference knows these well-tabled Latin abbreviations, so the
    // fallback still renders a real citation rather than the raw tag. The
    // same string also appears in the sidebar's parallel picker, so there
    // can be more than one match.
    expect(screen.getAllByText(/Vergil, Aeneid 1\.1/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Ovid, Metamorphoses 1\.1/).length).toBeGreaterThan(0);
  });
});
