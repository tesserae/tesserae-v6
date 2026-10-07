/**
 * The corpus chart counts every work the search found (by_work_all), not
 * only the first 500 lines it returned (NC 2026-10-07: the Persian timeline
 * left out Hafez and Iqbal, the two poets compared).
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

const barData = [];
vi.mock('react-chartjs-2', async () => {
  const { forwardRef, createElement } = await vi.importActual('react');
  return { Bar: forwardRef(({ data }, ref) => { barData.push(data); return createElement('div', { ref }, 'chart'); }) };
});
vi.mock('chart.js', () => ({
  Chart: { register: () => {} },
  CategoryScale: {}, LinearScale: {}, BarElement: {}, Title: {}, Tooltip: {}, Legend: {},
}));
vi.mock('../../../utils/api', () => ({
  searchTexts: vi.fn(), searchTextsStream: vi.fn(), searchFusionStream: vi.fn(),
  searchSemanticCross: vi.fn(), searchHapax: vi.fn(), searchBigrams: vi.fn(),
  fetchResultPage: vi.fn(), fetchAllResults: vi.fn(), wildcardSearch: vi.fn(),
}));

import SearchResults from '../SearchResults';

const row = {
  source: { ref: 'hafez.diwan.1545', text: 's', tokens: ['s'], highlight_indices: [] },
  target: { ref: 'iqbal.zabur.15.1', text: 't', tokens: ['t'], highlight_indices: [] },
  source_text: 'src-1', target_text: 'tgt-1',
  matched_words: [{ lemma: 'من' }, { lemma: 'است' }],
  overall_score: 1, base_score: 1, features: {},
};

beforeEach(() => {
  barData.length = 0;
  try { window.sessionStorage.clear(); } catch { /* ignore */ }
  global.fetch = vi.fn(() => Promise.resolve({ ok: true, json: () => Promise.resolve({
    capped: true, lines_all: 4759,
    results: [{ author: 'Saeb', work: 'Diwan', era: 'Safavid', year: 1676, locus: '1', text: 'x' }],
    by_work_all: [
      { work_id: 'hafez.diwan', author: 'Hafez', work: 'Diwan', era: 'Timurid', year: 1390, count: 71 },
      { work_id: 'saeb.diwan', author: 'Saeb', work: 'Diwan of Saeb', era: 'Safavid', year: 1676, count: 2082 },
      { work_id: 'iqbal.zabur', author: 'Iqbal', work: 'Zabur', era: 'Modern', year: 1938, count: 22 },
    ],
  }) }));
});
afterEach(() => { delete global.fetch; });

describe('corpus chart counts every work', () => {
  it('draws authors the 500-line list never reached, with their full counts', async () => {
    render(
      <SearchResults loading={false} error={null} pageSize={50} onPageSizeChange={() => {}}
        searchRunId={1} sortBy="score" setSortBy={() => {}} searchStats={null} language="fa"
        results={[row]} />,
    );
    const show = screen.queryByRole('button', { name: 'Show chart' });
    if (show) await userEvent.click(show);
    const across = screen.queryByRole('button', { name: 'Across the corpus' });
    if (across) await userEvent.click(across);
    await userEvent.click(await screen.findByRole('button', { name: 'Era' }));
    await waitFor(() => {
      const last = barData[barData.length - 1];
      expect(last.labels).toEqual(expect.arrayContaining(['Timurid', 'Safavid', 'Modern']));
      const byLabel = Object.fromEntries(last.labels.map((l, i) => [l, last.datasets[0].data[i]]));
      expect(byLabel.Timurid).toBe(71);
      expect(byLabel.Safavid).toBe(2082);
    });
    expect(screen.getByText(/4,759 corpus lines across 3 works/)).toBeTruthy();
  });
});
