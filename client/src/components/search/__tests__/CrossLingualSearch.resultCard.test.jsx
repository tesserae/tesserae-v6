/**
 * Owner's review of the live Persian -> Urdu cross-language page
 * (result card tidy, second pass, 2026-10-08):
 *  - citations showed bare refs ("1693", "64.1") with no author or work,
 *    on both sides, because the state that freezes the chosen texts'
 *    names at search time was declared but never set;
 *  - a refrain-and-rhyme result marked the refrain in yellow but never
 *    the rhyme word in rose;
 *  - the settings-bar description was fixed to SPhilBERTa for every pair,
 *    including Persian/Urdu, which does not use it;
 *  - badge order mixed the evidence badges with the wrong color (amber)
 *    for the semantic badge and the channel count ahead of the form
 *    badges.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';

vi.mock('react-chartjs-2', () => ({ Bar: () => null }));
vi.mock('chart.js', () => ({
  Chart: { register: () => {} },
  CategoryScale: {}, LinearScale: {}, BarElement: {},
  Title: {}, Tooltip: {}, Legend: {},
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
  results: [{
    source: {
      ref: '1693',
      text: 'aval ghazal namad',
      tokens: ['aval', 'ghazal', 'namad'],
      highlight_indices: [2],
    },
    target: {
      ref: '64.1',
      text: 'dovvom sher biyad',
      tokens: ['dovvom', 'sher', 'biyad'],
      highlight_indices: [2],
    },
    overall_score: 1.4,
    matched_words: [],
    poetics: { radif: 'namad', qafia: 'ghaz' },
    features: { semantic_score: 0.82, dict_score: 3, n_channels: 2 },
  }],
};

beforeEach(() => {
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

async function runPersianUrduSearch() {
  render(<CrossLingualSearch />);
  const fa = await screen.findByRole('button', { name: /Persian → Urdu/ });
  fireEvent.click(fa);
  await waitFor(() => expect(screen.getByText('Persian Source')).toBeTruthy());
  fireEvent.click(screen.getByRole('button', { name: /^search$/i }));
  await waitFor(() => expect(screen.getByText(/Found 1 cross-lingual parallel/)).toBeTruthy());
}

describe('CrossLingualSearch — citations name the author and work', () => {
  it('shows "Hafez, Diwan 1693" and "Ghalib, Diwan 64.1", not the bare refs', async () => {
    await runPersianUrduSearch();
    expect(await screen.findByText('Hafez, Diwan 1693')).toBeInTheDocument();
    expect(await screen.findByText('Ghalib, Diwan 64.1')).toBeInTheDocument();
    expect(screen.queryByText('1693')).not.toBeInTheDocument();
  });
});

describe('CrossLingualSearch — rhyme highlight', () => {
  it('marks the rhyme word in rose alongside the refrain in yellow', async () => {
    await runPersianUrduSearch();
    const marks = document.querySelectorAll('mark');
    const rose = [...marks].filter((m) => m.className.includes('bg-rose-200'));
    const yellow = [...marks].filter((m) => m.className.includes('bg-yellow-200'));
    expect(rose.map((m) => m.textContent)).toContain('ghazal');
    expect(yellow.map((m) => m.textContent)).toContain('namad');
  });
});

describe('CrossLingualSearch — per-pair settings description', () => {
  it('describes the Persian/Urdu pair by its own channels, not SPhilBERTa', async () => {
    render(<CrossLingualSearch />);
    const fa = await screen.findByRole('button', { name: /Persian → Urdu/ });
    fireEvent.click(fa);
    await waitFor(() => expect(screen.getByText('Persian Source')).toBeTruthy());
    expect(screen.queryByText(/SPhilBERTa/)).not.toBeInTheDocument();
    expect(screen.getByText(/multilingual-e5/)).toBeInTheDocument();
  });
});

describe('CrossLingualSearch — badge order and evidence color', () => {
  it('orders Score, Refrain, Rhyme, channel count, then semantic percentage, all evidence in blue', async () => {
    await runPersianUrduSearch();
    const channelBadge = screen.getByText('2 channels: semantic + vocabulary');
    const semanticBadge = screen.getByText('Semantic: 82%');
    const refrainBadge = screen.getByText('Refrain:', { exact: false });
    const rhymeBadge = screen.getByText('Rhyme:', { exact: false });

    // Order in the DOM: refrain/rhyme (the form badges) before the channel
    // and semantic badges (the evidence group), and the channel badge
    // before the semantic percentage within that group.
    expect(refrainBadge.compareDocumentPosition(rhymeBadge) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(rhymeBadge.compareDocumentPosition(channelBadge.closest('button')) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(channelBadge.closest('button').compareDocumentPosition(semanticBadge.closest('button')) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();

    expect(channelBadge.closest('button').className).toContain('bg-blue-100');
    expect(semanticBadge.closest('button').className).toContain('bg-blue-100');
    expect(semanticBadge.closest('button').className).not.toContain('bg-amber-100');
  });
});
