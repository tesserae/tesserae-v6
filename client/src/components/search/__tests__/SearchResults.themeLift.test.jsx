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
vi.mock('../../../utils/api', async (importOriginal) => ({
  ...(await importOriginal()),
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
import { mockResponse } from '../../../test/mockResponse';

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
        return Promise.resolve(mockResponse({
          json: () => Promise.resolve({ results: [{ score: 0.9, lift: 0.11, level: 'strong' }] }),
        }));
      }
      return Promise.resolve(mockResponse({ ok: true, json: () => Promise.resolve({}) }));
    });

    render(<SearchResults {...baseProps} results={[ROW]} />);

    expect(await screen.findByText('theme +0.11')).toBeInTheDocument();
    expect(posted.pairs).toEqual([{
      work_a: 'vergil.aeneid.tess', ref_a: 'verg. aen. 1.1',
      work_b: 'lucan.bellum_civile.tess', ref_b: 'lucan. 1.1',
    }]);
  });

  // A Persian card carries one more badge ("form in 3 poems") in the same row,
  // and the theme badge, after a long channels badge, dropped to a line of its
  // own in 2 of the first 50 cards (2026-10-13). The short theme badge now comes
  // first, so it fills the space the long channels badge cannot use.
  it('puts the theme badge before the channels badge on a Persian card', async () => {
    global.fetch = vi.fn((url) => {
      if (String(url).includes('/api/passages/pair-lift')) {
        return Promise.resolve(mockResponse({
          json: () => Promise.resolve({ results: [{ score: 0.9, lift: 0.02, level: 'weak' }] }),
        }));
      }
      return Promise.resolve(mockResponse({ ok: true, json: () => Promise.resolve({}) }));
    });
    const row = {
      ...ROW,
      poetics: { corpus_poems: 3 },
      channels: ['form', 'sound', 'content'],
    };
    render(<SearchResults {...baseProps} language="fa" results={[row]} />);
    const theme = await screen.findByText('theme +0.02');
    const channels = screen.getByText('form + sound + content');
    expect(theme.compareDocumentPosition(channels) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(screen.getByText('form in 3 poems').compareDocumentPosition(theme) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it('renders nothing extra when the pair-lift call fails', async () => {
    global.fetch = vi.fn((url) => {
      if (String(url).includes('/api/passages/pair-lift')) {
        return Promise.reject(new Error('network error'));
      }
      return Promise.resolve(mockResponse({ ok: true, json: () => Promise.resolve({}) }));
    });

    render(<SearchResults {...baseProps} results={[ROW]} />);

    // The result itself still renders immediately -- the lift call never
    // blocks the page.
    expect(screen.getByText('arma virumque cano')).toBeInTheDocument();
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(screen.queryByText(/^theme /)).not.toBeInTheDocument();
  });

  it('does not call pair-lift when there is no source/target text (e.g. rare-word results)', () => {
    global.fetch = vi.fn(() => Promise.resolve(mockResponse({ ok: true, json: () => Promise.resolve({}) })));
    render(<SearchResults {...baseProps} sourceTextInfo={undefined} targetTextInfo={undefined} results={[ROW]} />);
    expect(global.fetch).not.toHaveBeenCalledWith(
      expect.stringContaining('/api/passages/pair-lift'), expect.anything());
  });
});
