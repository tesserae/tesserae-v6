import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen } from '@testing-library/react';

// Same stubs as SearchResults.pagination.test.jsx: Chart.js needs a real
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
  sourceTextInfo: { id: 'vergil.aeneid.tess', author: 'Vergil', title: 'Aeneid' },
  targetTextInfo: { id: 'lucan.bellum_civile.tess', author: 'Lucan', title: 'Bellum Civile' },
};

const ROW = {
  source: { ref: 'verg. aen. 1.1', text: 'arma virumque cano' },
  target: { ref: 'lucan. 1.1', text: 'bella per emathios' },
  source_text: 'arma virumque cano',
  target_text: 'bella per emathios',
  fused_score: 5.2,
  matched_words: [],
  features: {},
};

afterEach(() => {
  delete global.fetch;
});

describe('SearchResults — theme lift badge', () => {
  it('posts the visible page to /api/passages/pair-lift and shows the lift once it answers', async () => {
    let posted = null;
    global.fetch = vi.fn((url, opts) => {
      if (String(url).includes('/api/passages/pair-lift')) {
        posted = JSON.parse(opts.body);
        return Promise.resolve({
          json: () => Promise.resolve({ results: [{ score: 0.9, lift: 0.11, level: 'strong' }] }),
        });
      }
      return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
    });

    render(<SearchResults {...baseProps} results={[ROW]} />);

    expect(await screen.findByText('theme +0.11')).toBeInTheDocument();
    expect(posted.pairs).toEqual([{
      work_a: 'vergil.aeneid.tess', ref_a: 'verg. aen. 1.1',
      work_b: 'lucan.bellum_civile.tess', ref_b: 'lucan. 1.1',
    }]);
  });

  it('renders nothing extra when the pair-lift call fails', async () => {
    global.fetch = vi.fn((url) => {
      if (String(url).includes('/api/passages/pair-lift')) {
        return Promise.reject(new Error('network error'));
      }
      return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
    });

    render(<SearchResults {...baseProps} results={[ROW]} />);

    // The result itself still renders immediately -- the lift call never
    // blocks the page.
    expect(screen.getByText('arma virumque cano')).toBeInTheDocument();
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(screen.queryByText(/^theme /)).not.toBeInTheDocument();
  });

  it('does not call pair-lift when there is no source/target text (e.g. rare-word results)', () => {
    global.fetch = vi.fn(() => Promise.resolve({ ok: true, json: () => Promise.resolve({}) }));
    render(<SearchResults {...baseProps} sourceTextInfo={undefined} targetTextInfo={undefined} results={[ROW]} />);
    expect(global.fetch).not.toHaveBeenCalledWith(
      expect.stringContaining('/api/passages/pair-lift'), expect.anything());
  });
});
