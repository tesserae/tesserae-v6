import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen } from '@testing-library/react';

// Same stubs as SearchResults.themeLift.test.jsx: Chart.js needs a real
// canvas jsdom doesn't provide, and every search transport lives in
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
  language: 'la',
};

const ROW = {
  source: { ref: 'held. hist. 1.1', text: 'held wording' },
  target: { ref: 'ordinary. 1.1', text: 'ordinary wording' },
  source_text: 'held wording',
  target_text: 'ordinary wording',
  fused_score: 3.1,
  matched_words: [],
  features: {},
};

afterEach(() => {
  delete global.fetch;
});

describe('SearchResults — restricted-text credit line', () => {
  it('shows the credit beneath a restricted source passage', () => {
    global.fetch = vi.fn(() => Promise.resolve({ ok: true, json: () => Promise.resolve({}) }));
    render(<SearchResults {...baseProps} results={[ROW]}
      sourceTextInfo={{ id: 'heldwork.history.tess', author: 'Held Author', title: 'History',
                        restricted: true, credit: 'Source: Test Licence Holder (example.invalid)' }}
      targetTextInfo={{ id: 'ordinary.poem.tess', author: 'Ordinary Poet', title: 'Poem' }}
    />);
    expect(screen.getByText('Source: Test Licence Holder (example.invalid)')).toBeInTheDocument();
  });

  it('shows no credit line when neither side is restricted', () => {
    global.fetch = vi.fn(() => Promise.resolve({ ok: true, json: () => Promise.resolve({}) }));
    render(<SearchResults {...baseProps} results={[ROW]}
      sourceTextInfo={{ id: 'ordinary.poem.tess', author: 'Ordinary Poet', title: 'Poem' }}
      targetTextInfo={{ id: 'another.poem.tess', author: 'Another Poet', title: 'Poem' }}
    />);
    expect(screen.queryByText(/^Source: /)).not.toBeInTheDocument();
  });
});
