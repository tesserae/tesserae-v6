/**
 * The "Across the corpus" chart needs a parallel with two or more shared
 * words. Persian results lead with refrain rows that share one word, so the
 * chart opened on "shares only one word" and looked broken (NC 2026-10-07).
 * It now opens on the first row it can draw, and labels one-word rows.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

vi.mock('react-chartjs-2', async () => {
  const { forwardRef, createElement } = await vi.importActual('react');
  return { Bar: forwardRef((_props, ref) => createElement('div', { ref }, 'chart')) };
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

const row = (i, words) => ({
  source: { ref: `hafez.diwan.${i}`, text: `s${i}`, tokens: ['s'], highlight_indices: [] },
  target: { ref: `iqbal.zabur.${i}`, text: `t${i}`, tokens: ['t'], highlight_indices: [] },
  source_text: `src-${i}`, target_text: `tgt-${i}`,
  matched_words: words.map((w) => ({ lemma: w, source_word: w, target_word: w })),
  overall_score: 1 / i, base_score: 1 / i, features: {},
});

beforeEach(() => {
  try { window.sessionStorage.clear(); } catch { /* ignore */ }
  global.fetch = vi.fn(() => Promise.resolve({ ok: true, json: () => Promise.resolve({ results: [] }) }));
});
afterEach(() => { delete global.fetch; });

describe('corpus chart picks a row it can draw', () => {
  it('opens on the first parallel with two shared words, and labels one-word rows', async () => {
    render(
      <SearchResults loading={false} error={null} pageSize={50} onPageSizeChange={() => {}}
        searchRunId={1} sortBy="score" setSortBy={() => {}} searchStats={null} language="fa"
        results={[row(1, ['انداز']), row(2, ['گفت']), row(3, ['دیر', 'مغان'])]} />,
    );
    const show = screen.queryByRole('button', { name: 'Show chart' });
    if (show) await userEvent.click(show);
    const across = screen.queryByRole('button', { name: 'Across the corpus' });
    if (across) await userEvent.click(across);
    const picker = await screen.findByLabelText('Parallel:', { selector: 'select' }).catch(
      () => screen.getAllByRole('combobox').find((c) => /#1/.test(c.textContent)));
    await waitFor(() => expect(picker.value).toBe('2'));
    expect(picker.options[0].textContent).toContain('one word, no chart');
    expect(picker.options[2].textContent).not.toContain('one word');
    await waitFor(() => {
      const bodies = global.fetch.mock.calls
        .filter(([u]) => String(u) === '/api/line-search')
        .map(([, init]) => JSON.parse(init.body).query);
      expect(bodies).toContain('دیر مغان');
    });
  });
});
