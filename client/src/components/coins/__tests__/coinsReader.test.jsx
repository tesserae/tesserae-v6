/**
 * The Reader's Coins tab (name links first, then related imagery with its
 * hit rate) and the Coins option of Theme Search (its own list, never mixed
 * into the passage ranking). Both follow the Coins collection.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor, cleanup, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import ResultsPanel from '../../reader/ResultsPanel';
import ThemeSearchPage from '../../passages/ThemeSearchPage';
import { READER_TABS } from '../../../collections/collectionsConfig';
import { setProfile, setCollection } from '../../../collections/collectionsStore';
import { resetScholarshipLanguagesCache } from '../../../utils/scholarshipLanguages';

const UNITS = [{ ref: 'aug. 94.4', text: 'Cum Augusto natus' }, { ref: 'aug. 94.5', text: 'et Tiberium' }];
const SELECTION = { refStart: 'aug. 94.4', refEnd: 'aug. 94.5', startIdx: 0, endIdx: 1 };

const MATCH = (over = {}) => ({
  description: 'Obverse: Head. Reverse: Capricorn right, holding globe.',
  obverse_description: 'Head', reverse_description: 'Capricorn right, holding globe',
  score: 0.84, confidence: { level: 'higher', score: 0.84, tested_rate: '7 in 10' },
  n_types: 3, authorities: ['Augustus'], authorities_total: 1, date_start: -18, date_end: -17,
  mint: 'Colonia Patricia', denomination: 'Aureus', coin_id: 'ocre:ric.1(2).aug.125',
  coin_url: '/coins/ocre%3Aric.1(2).aug.125', ...over,
});
const FOR_PASSAGE = {
  available: true, query: 'gist', related: [MATCH(), MATCH({
    description: 'Obverse: Head. Reverse: Ship.', reverse_description: 'Ship under sail',
    confidence: { level: 'usual', score: 0.8, tested_rate: '1 in 4' }, n_types: 1, coin_id: 'ocre:b',
    coin_url: '/coins/ocre%3Ab' })],
  hit_rate_label: 'About one match in three is right. These are coin types whose description is close.',
  name_links: [{ name: 'Augustus', label: 'Augustus', n_types: 889, coins_url: '/coins?person=Augustus' }],
  name_links_note: 'A name link means the same person is named on the coin and in the passage. It is not an echo of the passage.',
};
const THEME = {
  available: true, query: 'goat', label: 'Ranked by how close each coin description is in meaning to your words.',
  results: [MATCH({ description: 'Obverse: x. Reverse: Infant on goat.', reverse_description: 'Infant on goat' })],
};

function mockApi(over = {}) {
  const calls = [];
  global.fetch = vi.fn(async (url) => {
    const u = String(url);
    calls.push(u);
    const body = (() => {
      if (u.startsWith('/api/coins/for-passage')) return over.forPassage || FOR_PASSAGE;
      if (u.startsWith('/api/coins/theme')) return over.theme || THEME;
      if (u.startsWith('/api/languages')) return { languages: [] };
      return {};
    })();
    return { ok: true, status: 200, json: async () => body };
  });
  return calls;
}

function panel(props = {}) {
  return render(<ResultsPanel selection={SELECTION} language="la" work="suetonius.de_vita_caesarum"
                              units={UNITS} initialTab="coins" {...props} />);
}

beforeEach(() => {
  resetScholarshipLanguagesCache();
  window.localStorage.clear();
  window.sessionStorage.clear();
});
afterEach(() => { cleanup(); delete global.fetch; });

describe('the Coins tab follows the collection', () => {
  it('is registered in READER_TABS and needs coins', () => {
    expect(READER_TABS.find((t) => t.id === 'coins').needs).toEqual(['coins']);
  });
  it('is absent in the Literary profile and in Everything', () => {
    mockApi();
    setProfile('literary');
    panel({ initialTab: undefined });
    expect(screen.queryByRole('button', { name: 'Coins' })).toBeNull();
    cleanup();
    setProfile('everything');
    panel({ initialTab: undefined });
    expect(screen.queryByRole('button', { name: 'Coins' })).toBeNull();
  });
  it('appears when Coins is on', () => {
    mockApi();
    setProfile('archaeological');
    panel({ initialTab: undefined });
    expect(screen.getByRole('button', { name: 'Coins' })).toBeTruthy();
  });
});

describe('the tab', () => {
  beforeEach(() => setProfile('archaeological'));

  it('asks for the selection and shows name links before related imagery', async () => {
    const calls = mockApi();
    panel();
    await screen.findByText('Named on coins');
    const u = calls.find((c) => c.startsWith('/api/coins/for-passage'));
    expect(u).toContain('work=suetonius.de_vita_caesarum');
    expect(u).toContain('lang=la');
    expect(u).toContain('ref=aug.+94.4');
    expect(u).toContain('ref_end=aug.+94.5');
    const link = screen.getByRole('link', { name: 'Augustus' });
    expect(link.getAttribute('href')).toBe('/coins?person=Augustus');
    expect(screen.getByText(/889 coin types/)).toBeTruthy();
    expect(screen.getByText(/It is not an echo of the passage/)).toBeTruthy();
    const headings = screen.getAllByRole('heading', { level: 4 }).map((h) => h.textContent);
    expect(headings).toEqual(['Named on coins', 'Related imagery']);
    expect(screen.getByTitle(/a name link, not an echo/i)).toBeTruthy();
  });

  it('shows each related coin with its confidence, the hit rate and a link to the coin', async () => {
    mockApi();
    panel();
    await screen.findByText('Capricorn right, holding globe');
    expect(screen.getByTestId('coins-hit-rate').textContent).toMatch(/one match in three/);
    expect(screen.getByText('Closer match')).toBeTruthy();
    expect(screen.getByText('Usual match')).toBeTruthy();
    expect(screen.getAllByText(/Augustus · 18 to 17 BCE · Colonia Patricia · Aureus/).length).toBe(2);
    expect(screen.getByRole('link', { name: 'Open the earliest' }).getAttribute('href')).toBe('/coins/ocre%3Aric.1(2).aug.125');
    expect(screen.getByRole('link', { name: 'Open the coin type' }).getAttribute('href')).toBe('/coins/ocre%3Ab');
  });

  it('says so for a Greek passage, an empty answer and a missing collection', async () => {
    mockApi({ forPassage: { ...FOR_PASSAGE, name_links: [], related: [], note: 'No passage window with a description covers this reference.' } });
    panel({ language: 'grc' });
    expect(await screen.findByText('Names are matched in Latin passages only.')).toBeTruthy();
    expect(screen.getByText(/No passage window with a description/)).toBeTruthy();
    cleanup();
    mockApi({ forPassage: { available: false, related: [], name_links: [] } });
    panel();
    expect(await screen.findByText(/not installed on this server/)).toBeTruthy();
    cleanup();
    mockApi({ forPassage: { unavailable: true, error: 'The query encoder service is not running.', related: [], name_links: [] } });
    panel();
    expect(await screen.findByText(/encoder service is not running/)).toBeTruthy();
  });

  it('asks for a selection when there is none', () => {
    mockApi();
    panel({ selection: null });
    expect(screen.getByText(/Select a line or a span/)).toBeTruthy();
  });
});

describe('Theme Search', () => {
  async function run(text) {
    fireEvent.change(screen.getByPlaceholderText(/a warrior arms himself/), { target: { value: text } });
    fireEvent.click(screen.getByRole('button', { name: /^search/i }));
  }

  it('offers no Coins choice unless the collection is on', () => {
    mockApi();
    setProfile('historical');
    render(<ThemeSearchPage />);
    expect(screen.queryByText('Coins')).toBeNull();
  });

  it('searches the coin descriptions on their own, never the passages', async () => {
    const calls = mockApi();
    setProfile('historical');
    setCollection('coins', true);
    render(<ThemeSearchPage />);
    await userEvent.click(screen.getByRole('checkbox', { name: 'Coins' }));
    await run('an infant riding a goat');
    await screen.findByText('Infant on goat');
    expect(calls.some((c) => c.startsWith('/api/coins/theme?q=an%20infant%20riding%20a%20goat'))).toBe(true);
    expect(calls.some((c) => c.startsWith('/api/passages/theme-search'))).toBe(false);
    expect(screen.getByTestId('theme-coins-label').textContent).toMatch(/Ranked by how close/);
    expect(screen.getByRole('link', { name: 'Open the earliest' })).toBeTruthy();
    // switching Coins off returns to the passage search
    await userEvent.click(screen.getByRole('checkbox', { name: 'Coins' }));
    expect(screen.queryByTestId('theme-coins')).toBeNull();
  });
});
