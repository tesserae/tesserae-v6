import { describe, it, expect, afterEach, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';

// Same stubs as SearchResults.formulaTag.test.jsx: Chart.js needs a real
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
  fetchResultPage: vi.fn(),
  fetchAllResults: vi.fn(),
  wildcardSearch: vi.fn(),
}));

import SearchResults from '../SearchResults';
import { __resetCorpusTextMapCacheForTests } from '../../../utils/textNames';

const baseProps = {
  loading: false,
  error: null,
  pageSize: 50,
  onPageSizeChange: () => {},
  searchRunId: 1,
  sortBy: 'score',
  setSortBy: () => {},
  searchStats: null,
};

afterEach(() => {
  delete global.fetch;
  vi.restoreAllMocks();
  // Each test's /api/texts mock is its own; without this, a later test
  // reusing the same language would see an earlier test's cached (possibly
  // empty) corpus map instead of calling fetch again.
  __resetCorpusTextMapCacheForTests();
});

// Owner's review of the result card (2026-10-08): the channel count ("2
// channels") and the channel names ("form", "sound") both appeared. Now
// there is one blue badge naming the channels, nothing counting them
// separately.
describe('SearchResults — no duplicate channel count', () => {
  it('shows one badge naming the channels, never a separate count', () => {
    global.fetch = vi.fn(() => Promise.resolve({ ok: true, json: () => Promise.resolve([]) }));
    const row = {
      source: { ref: 'hafez. diwan. 1', text: 'a' },
      target: { ref: 'iqbal. zabur_e_ajam. 1', text: 'b' },
      fused_score: 2.1,
      matched_words: [],
      features: {},
      channels: ['form', 'sound'],
    };
    render(<SearchResults {...baseProps} language="fa" results={[row]} />);
    expect(screen.getByText('form + sound')).toBeInTheDocument();
    expect(screen.queryByText(/\d+\s+channels?$/)).not.toBeInTheDocument();
    expect(screen.queryByText('form')).not.toBeInTheDocument();
    expect(screen.queryByText('sound')).not.toBeInTheDocument();
  });
});

// Owner's review: the refrain already names the shared word in its own
// badge, so repeating it again as "Matches: ..." said nothing new.
describe('SearchResults — Matches omitted when it only repeats the refrain', () => {
  const rowWithRadif = (matched_words) => ({
    source: { ref: 'hafez. diwan. 1', text: 'a' },
    target: { ref: 'iqbal. zabur_e_ajam. 1', text: 'b' },
    fused_score: 2.1,
    matched_words,
    features: {},
    poetics: { radif: 'نیامد ما را' },
  });

  it('omits "Matches:" when every matched word is one of the refrain\'s own words', () => {
    global.fetch = vi.fn(() => Promise.resolve({ ok: true, json: () => Promise.resolve([]) }));
    const row = rowWithRadif(['نیامد', 'ما']);
    render(<SearchResults {...baseProps} language="fa" results={[row]} />);
    expect(screen.queryByText(/^Matches:/)).not.toBeInTheDocument();
  });

  it('still shows "Matches:" when a matched word is not part of the refrain', () => {
    global.fetch = vi.fn(() => Promise.resolve({ ok: true, json: () => Promise.resolve([]) }));
    const row = rowWithRadif(['شراب']);
    render(<SearchResults {...baseProps} language="fa" results={[row]} />);
    expect(screen.getByText(/^Matches:/)).toBeInTheDocument();
  });
});

// Finding #4 (owner's review): Persian and Urdu showed the raw internal id
// ("hafez.diwan.5097") where Latin shows "Vergil, Aeneid 1.1". The corpus
// list (/api/texts?language=fa) now backs the citation once it loads.
describe('SearchResults — Persian/Urdu citations resolve via the corpus list', () => {
  it('upgrades a raw Persian locus to "Author, Work reference" once /api/texts answers', async () => {
    global.fetch = vi.fn((url) => {
      if (String(url).includes('/api/texts')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve([
            { id: 'hafez.diwan.tess', author: 'Hafez', title: 'Diwan' },
            { id: 'iqbal.zabur_e_ajam.tess', author: 'Iqbal', title: 'Zabur-e Ajam' },
          ]),
        });
      }
      return Promise.resolve({ ok: true, json: () => Promise.resolve([]) });
    });
    const row = {
      source: { ref: 'hafez.diwan.5097', text: 'a' },
      target: { ref: 'iqbal.zabur_e_ajam.26.1', text: 'b' },
      fused_score: 2.1,
      matched_words: [],
      features: {},
    };
    render(<SearchResults {...baseProps} language="fa" results={[row]} />);
    expect(await screen.findByText('Hafez, Diwan 5097')).toBeInTheDocument();
    expect(await screen.findByText('Iqbal, Zabur-e Ajam 26.1')).toBeInTheDocument();
    expect(screen.queryByText('hafez.diwan.5097')).not.toBeInTheDocument();
  });
});

// Spec D: the refrain-lines popover names each work once and collapses its
// lines, instead of a raw-id tooltip.
describe('SearchResults — refrain-lines popover', () => {
  it('shows the structured refrain-lines explanation on tap, not a raw-id list', async () => {
    global.fetch = vi.fn((url) => {
      if (String(url).includes('/api/texts')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve([
            { id: 'hafez.diwan.tess', author: 'Hafez', title: 'Diwan' },
            { id: 'iqbal.zabur_e_ajam.tess', author: 'Iqbal', title: 'Zabur-e Ajam' },
          ]),
        });
      }
      return Promise.resolve({ ok: true, json: () => Promise.resolve([]) });
    });
    const row = {
      source: { ref: 'hafez.diwan.5097', text: 'a' },
      target: { ref: 'iqbal.zabur_e_ajam.26.1', text: 'b' },
      fused_score: 2.1,
      matched_words: [],
      features: {},
      poetics: {
        radif: 'نیامد',
        source_lines: ['hafez.diwan.5097', 'hafez.diwan.5098', 'hafez.diwan.5100'],
        target_lines: ['iqbal.zabur_e_ajam.26.1', 'iqbal.zabur_e_ajam.26.2', 'iqbal.zabur_e_ajam.26.3'],
      },
    };
    render(<SearchResults {...baseProps} language="fa" results={[row]} />);
    const badge = await screen.findByText('3 + 3 refrain lines');
    fireEvent.click(badge.closest('button'));
    expect(await screen.findByText('one result stands for the set.', { exact: false })).toBeInTheDocument();
    expect(screen.getByText('Hafez, Diwan: lines 5097, 5098, 5100')).toBeInTheDocument();
    expect(screen.getByText('Iqbal, Zabur-e Ajam 26: lines 1 to 3')).toBeInTheDocument();
  });
});
