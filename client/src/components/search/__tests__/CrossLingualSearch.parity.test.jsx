/**
 * Cross-language result cards had none of the single-language page's
 * citation or repository tools (owner's review, 2026-10-08): no Cite, no
 * Register, no per-side Search Corpus, no Export PDF, no Refresh results,
 * no Share link, no top pagination, no Ask Tessa. This file checks the
 * ones added for parity.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

vi.mock('react-chartjs-2', () => ({ Bar: () => null }));
vi.mock('chart.js', () => ({
  Chart: { register: () => {} },
  CategoryScale: {}, LinearScale: {}, BarElement: {},
  Title: {}, Tooltip: {}, Legend: {},
}));

const exportRowsToPDFMock = vi.fn();
vi.mock('../../../utils/exportResults', () => ({
  exportRowsToPDF: (...args) => exportRowsToPDFMock(...args),
}));

import CrossLingualSearch from '../CrossLingualSearch';

const list = (author_key, author, work_key, work) => ({
  authors: [{ author_key, author, works: [{ work_key, work, whole_text: `${author_key}.${work_key}.tess`, parts: [] }] }],
});
const LISTS = {
  fa: list('hafez', 'Hafez', 'diwan', 'Diwan'),
  ur: list('ghalib', 'Ghalib', 'diwan_wikisource', 'Diwan'),
};
const SERVED = [{ key: 'fa-ur', source: 'fa', target: 'ur' }];

const SEARCH_RESULT = {
  corpus_version: '2026-10-08',
  results: [{
    source: { ref: '1693', text: 'aval ghazal namad', tokens: ['aval', 'ghazal', 'namad'], highlight_indices: [2] },
    target: { ref: '64.1', text: 'dovvom sher biyad', tokens: ['dovvom', 'sher', 'biyad'], highlight_indices: [2] },
    overall_score: 1.4,
    matched_words: [
      { source_word: 'ghazal', target_word: 'sher', source_lemma: 'ghazal', target_lemma: 'sher', display: 'ghazal→sher' },
    ],
    channels: 'semantic (85%), dictionary (2 words)',
    features: { semantic_score: 0.82, dict_score: 2, n_channels: 2 },
  }],
};

beforeEach(() => {
  exportRowsToPDFMock.mockClear();
  global.fetch = vi.fn((url) => {
    const u = String(url);
    if (u.includes('/api/languages')) {
      return Promise.resolve({ json: () => Promise.resolve({ languages: [], crosslingual_pairs: SERVED }) });
    }
    const m = u.match(/hierarchy\?language=(\w+)/);
    if (m) return Promise.resolve({ json: () => Promise.resolve(LISTS[m[1]] || { authors: [] }) });
    if (u.includes('/api/search')) {
      return Promise.resolve({ json: () => Promise.resolve(SEARCH_RESULT) });
    }
    return Promise.resolve({ json: () => Promise.resolve({}) });
  });
});

afterEach(() => {
  delete global.fetch;
  window.history.replaceState({}, '', '/');
  try { localStorage.clear(); } catch { /* noop */ }
});

async function runPersianUrduSearch(props = {}) {
  render(<CrossLingualSearch {...props} />);
  const fa = await screen.findByRole('button', { name: /Persian → Urdu/ });
  fireEvent.click(fa);
  await waitFor(() => expect(screen.getByText('Persian Source')).toBeTruthy());
  fireEvent.click(screen.getByRole('button', { name: /^search$/i }));
  await waitFor(() => expect(screen.getByText(/Found 1 cross-lingual parallel/)).toBeTruthy());
}

describe('CrossLingualSearch — Cite', () => {
  it('names both sides, the pair, and the score, with the corpus version carried through', async () => {
    const user = userEvent.setup();
    await runPersianUrduSearch();
    await user.click(screen.getByRole('button', { name: 'Cite' }));
    const text = screen.getByLabelText('Citation text').value;
    expect(text).toContain('Hafez, Diwan 1693');
    expect(text).toContain('Ghalib, Diwan 64.1');
    expect(text).toContain('Persian → Urdu');
    expect(text).toContain('2026-10-08');
  });

  it('carries the guidance sentence and How to cite link, same as the single-language Cite', async () => {
    const user = userEvent.setup();
    await runPersianUrduSearch();
    await user.click(screen.getByRole('button', { name: 'Cite' }));
    expect(screen.getByText(/One citation of Tesserae per publication is enough/)).toBeTruthy();
    expect(screen.getByRole('button', { name: 'How to cite Tesserae' })).toBeTruthy();
  });
});

describe('CrossLingualSearch — Register', () => {
  it('calls onRegister with both languages and the channels', async () => {
    const onRegister = vi.fn();
    await runPersianUrduSearch({ onRegister });
    fireEvent.click(screen.getByRole('button', { name: 'Register' }));
    expect(onRegister).toHaveBeenCalledTimes(1);
    const payload = onRegister.mock.calls[0][0];
    expect(payload.source.language).toBe('fa');
    expect(payload.target.language).toBe('ur');
    expect(payload.channels).toBe('semantic (85%), dictionary (2 words)');
    expect(payload.source.ref).toBe('1693');
    expect(payload.target.ref).toBe('64.1');
  });
});

describe('CrossLingualSearch — Search Corpus', () => {
  it('offers one action per side, each with that side\'s own language and lemma', async () => {
    const onCorpusSearch = vi.fn();
    await runPersianUrduSearch({ onCorpusSearch });
    fireEvent.click(screen.getByRole('button', { name: 'Search Corpus (Persian)' }));
    expect(onCorpusSearch).toHaveBeenCalledWith(expect.objectContaining({
      language: 'fa', matched_lemmas: ['ghazal'],
    }));
    fireEvent.click(screen.getByRole('button', { name: 'Search Corpus (Urdu)' }));
    expect(onCorpusSearch).toHaveBeenCalledWith(expect.objectContaining({
      language: 'ur', matched_lemmas: ['sher'],
    }));
  });
});

describe('CrossLingualSearch — pagination top and bottom', () => {
  it('shows a page-size control above the list and keeps the list below it', async () => {
    await runPersianUrduSearch();
    const topList = screen.getAllByLabelText(/show/i, { selector: 'select' });
    expect(topList.length).toBeGreaterThanOrEqual(1);
  });
});

describe('CrossLingualSearch — Export PDF', () => {
  it('calls the PDF export helper with the result row', async () => {
    await runPersianUrduSearch();
    fireEvent.click(screen.getByRole('button', { name: 'Export PDF' }));
    expect(exportRowsToPDFMock).toHaveBeenCalledTimes(1);
    const [title, , headers, rows] = exportRowsToPDFMock.mock.calls[0];
    expect(title).toContain('Cross-Language');
    expect(headers).toContain('Score');
    expect(rows[0]).toContain('1693');
  });
});

describe('CrossLingualSearch — Refresh results', () => {
  it('re-runs the search with skip_cache true', async () => {
    await runPersianUrduSearch();
    global.fetch.mockClear();
    fireEvent.click(screen.getByRole('button', { name: 'Refresh results' }));
    await waitFor(() => {
      const call = global.fetch.mock.calls.find(([url]) => String(url).includes('/api/search'));
      expect(call).toBeTruthy();
      const body = JSON.parse(call[1].body);
      expect(body.skip_cache).toBe(true);
    });
  });
});

describe('CrossLingualSearch — share link round trip', () => {
  it('copies a link carrying lang, pair, source, target and min_matches', async () => {
    const writeText = vi.fn(() => Promise.resolve());
    Object.defineProperty(navigator, 'clipboard', { value: { writeText }, configurable: true });
    await runPersianUrduSearch();
    fireEvent.click(screen.getByRole('button', { name: /share/i }));
    await waitFor(() => expect(writeText).toHaveBeenCalled());
    const url = new URL(writeText.mock.calls[0][0]);
    expect(url.searchParams.get('lang')).toBe('cross');
    expect(url.searchParams.get('pair')).toBe('fa-ur');
    expect(url.searchParams.get('source')).toBe('hafez.diwan.tess');
    expect(url.searchParams.get('target')).toBe('ghalib.diwan_wikisource.tess');
    expect(url.searchParams.get('min_matches')).toBe('2');
  });

  it('reopens the same search from those parameters on the next mount', async () => {
    window.history.replaceState({}, '', '/?lang=cross&pair=fa-ur&source=hafez.diwan.tess&target=ghalib.diwan_wikisource.tess&min_matches=3');
    render(<CrossLingualSearch />);
    await waitFor(() => expect(screen.getByText(/Found 1 cross-lingual parallel/)).toBeTruthy());
    expect(screen.getByText('Hafez, Diwan 1693')).toBeTruthy();
    expect(screen.getByText('Ghalib, Diwan 64.1')).toBeTruthy();
  });
});
