import { describe, it, expect, afterEach, vi } from 'vitest';
import { render, screen } from '@testing-library/react';

// Same stubs as SearchResults.themeLift.test.jsx: Chart.js needs a real
// canvas jsdom doesn't provide, and every search transport lives in
// utils/api, which this file never calls.
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
  language: 'he',
};

const ROW = (formulaFields) => ({
  source: { ref: 'gen. 1.1', text: 'in principio' },
  target: { ref: '1sam. 1.1', text: 'fuit vir' },
  source_text: 'in principio',
  target_text: 'fuit vir',
  fused_score: 3.4,
  matched_words: [],
  features: {},
  ...formulaFields,
});

afterEach(() => {
  delete global.fetch;
});

describe('SearchResults — formula count tag', () => {
  it('shows "in N works" when the result carries a formula_count', () => {
    global.fetch = vi.fn(() => Promise.resolve({ ok: true, json: () => Promise.resolve({}) }));
    render(<SearchResults {...baseProps} results={[ROW({ formula_count: 37 })]} />);
    expect(screen.getByText('in 37 works')).toBeInTheDocument();
  });

  it('uses the singular "work" for a count of exactly 1', () => {
    global.fetch = vi.fn(() => Promise.resolve({ ok: true, json: () => Promise.resolve({}) }));
    render(<SearchResults {...baseProps} results={[ROW({ formula_count: 1 })]} />);
    expect(screen.getByText('in 1 work')).toBeInTheDocument();
  });

  it('renders no tag when formula_count is absent (table had nothing for the pair)', () => {
    global.fetch = vi.fn(() => Promise.resolve({ ok: true, json: () => Promise.resolve({}) }));
    render(<SearchResults {...baseProps} results={[ROW({})]} />);
    expect(screen.queryByText(/^in \d+ works?$/)).not.toBeInTheDocument();
  });

  it('renders no tag when formula_count is null', () => {
    global.fetch = vi.fn(() => Promise.resolve({ ok: true, json: () => Promise.resolve({}) }));
    render(<SearchResults {...baseProps} results={[ROW({ formula_count: null })]} />);
    expect(screen.queryByText(/^in \d+ works?$/)).not.toBeInTheDocument();
  });
});
