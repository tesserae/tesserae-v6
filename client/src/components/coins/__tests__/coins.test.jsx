/**
 * The Coins page: list with search and filters, one coin type, and the
 * Collections gate.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor, cleanup } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import CoinsPage from '../CoinsPage';
import CoinList from '../CoinList';
import { coinDate, signedYear } from '../coinsFormat';
import { PROFILES, PAGE_NEEDS, profileSwitches } from '../../../collections/collectionsConfig';
import { setProfile } from '../../../collections/collectionsStore';

const COIN = {
  id: 'ocre:ric.1(2).aug.125', source: 'ocre', title: 'RIC I (second edition) Augustus 125',
  uri: 'http://numismatics.org/ocre/id/ric.1(2).aug.125',
  type_url: 'http://numismatics.org/ocre/id/ric.1(2).aug.125',
  authority: 'Augustus', issuer: null, portrait: 'Augustus', mint: 'Colonia Patricia',
  mint_pleiades_id: '256155', pleiades_url: 'https://pleiades.stoa.org/places/256155', region: null,
  denomination: 'Aureus', material: 'Gold', date_start: -18, date_end: -17,
  obverse_legend: 'AVGVSTVS', reverse_legend: 'S P Q R',
  obverse_description: 'Head of Augustus, bare, right', reverse_description: 'Capricorn right, holding globe',
  credit: 'Type record: OCRE (American Numismatic Society), ODbL',
};
const COIN2 = { ...COIN, id: 'crro:rrc-1.1', source: 'crro', title: 'RRC 1/1', authority: 'anonymous',
  mint: null, pleiades_url: null, date_start: -326, date_end: -242, obverse_legend: null,
  credit: 'Type record: CRRO (American Numismatic Society), ODbL',
  type_url: 'http://numismatics.org/crro/id/rrc-1.1' };

const LIST = {
  available: true, total: 2, page: 1, per_page: 24, sort: 'date',
  coins: [COIN2, COIN],
  facets: {
    authority: [{ value: 'Augustus', count: 1 }, { value: 'anonymous', count: 1 }],
    mint: [{ value: 'Colonia Patricia', count: 1 }],
    denomination: [{ value: 'Aureus', count: 1 }],
    material: [{ value: 'Gold', count: 1 }],
    source: [{ value: 'ocre', count: 1 }, { value: 'crro', count: 1 }],
  },
};

function mockApi(listOverride) {
  const calls = [];
  global.fetch = vi.fn(async (url) => {
    const u = String(url);
    calls.push(u);
    if (u.startsWith('/api/coins/')) return { ok: true, status: 200, json: async () => ({ coin: COIN }) };
    if (u.startsWith('/api/coins')) return { ok: true, status: 200, json: async () => listOverride || LIST };
    return { ok: true, status: 200, json: async () => ({}) };
  });
  return calls;
}

beforeEach(() => {
  window.localStorage.clear();
  window.sessionStorage.clear();
  window.history.replaceState({}, '', '/coins');
  setProfile('archaeological');
});
afterEach(() => { cleanup(); window.history.replaceState({}, '', '/'); });

describe('collections wiring', () => {
  it('the Archaeological and Everything profiles have coins on, Literary off', () => {
    expect(PROFILES.find((p) => p.id === 'everything').on).toContain('coins');
    expect(profileSwitches('everything').coins).toBe(true);
    expect(profileSwitches('archaeological').coins).toBe(true);
    expect(profileSwitches('literary').coins).toBe(false);
    expect(PAGE_NEEDS.coins).toEqual(['coins']);
  });
  it('formats dates and year boxes', () => {
    expect(coinDate({ date_start: -18, date_end: -17 })).toBe('18 to 17 BCE');
    expect(coinDate({ date_start: null })).toBe('undated');
    expect(signedYear('44', 'BCE')).toBe(-44);
    expect(signedYear('14', 'CE')).toBe(14);
    expect(signedYear('', 'CE')).toBeNull();
  });
});

describe('the list', () => {
  it('shows each coin with both legends, descriptions, mint link, credit and type page link', async () => {
    mockApi();
    render(<CoinsPage setPageType={() => {}} />);
    expect(await screen.findByText('RIC I (second edition) Augustus 125')).toBeTruthy();
    expect(screen.getByTestId('coins-total').textContent).toContain('2 coin types');
    expect(screen.getByText('AVGVSTVS')).toBeTruthy();
    expect(screen.getAllByText('S P Q R').length).toBe(2);
    expect(screen.getAllByText('Head of Augustus, bare, right').length).toBe(2);
    expect(screen.getAllByText('Capricorn right, holding globe').length).toBe(2);
    expect(screen.getByRole('link', { name: 'Colonia Patricia' }).getAttribute('href'))
      .toBe('https://pleiades.stoa.org/places/256155');
    expect(screen.getByText('Type record: OCRE (American Numismatic Society), ODbL')).toBeTruthy();
    expect(screen.getByText('Type record: CRRO (American Numismatic Society), ODbL')).toBeTruthy();
    const links = screen.getAllByRole('link', { name: 'Type page and specimens' });
    expect(links[1].getAttribute('href')).toBe(COIN.type_url);
    expect(screen.getAllByText('none recorded').length).toBeGreaterThan(0);  // CRRO card has no obverse legend
  });

  it('sends the search, filters and dates to the API and returns to page 1', async () => {
    const calls = mockApi();
    render(<CoinList openCoin={() => {}} />);
    await screen.findByText('RRC 1/1');
    await userEvent.type(screen.getByLabelText(/Search legends/), 'capricorn');
    await userEvent.type(screen.getByLabelText('From'), '30');
    await userEvent.type(screen.getByLabelText('To'), '10');
    await userEvent.selectOptions(screen.getByLabelText('To era'), 'BCE');
    await userEvent.click(screen.getByRole('button', { name: 'Search' }));
    await waitFor(() => expect(calls.some((c) => c.includes('q=capricorn') && c.includes('date_from=-30') && c.includes('date_to=-10'))).toBe(true));
    await userEvent.selectOptions(screen.getByLabelText('Authority'), 'Augustus');
    await waitFor(() => expect(calls.some((c) => c.includes('authority=Augustus'))).toBe(true));
    await userEvent.selectOptions(screen.getByLabelText('Source'), 'crro');
    await waitFor(() => expect(calls.some((c) => c.includes('source=crro'))).toBe(true));
    expect(screen.getByRole('option', { name: 'OCRE (Empire) (1)' })).toBeTruthy();
  });

  it('pages, and says so when nothing is installed or nothing matches', async () => {
    const calls = mockApi({ ...LIST, total: 100 });
    render(<CoinList openCoin={() => {}} />);
    await screen.findByText('Page 1 of 5');
    await userEvent.click(screen.getByRole('button', { name: 'Next' }));
    await waitFor(() => expect(calls.some((c) => c.includes('page=2'))).toBe(true));
    cleanup();
    mockApi({ available: false, coins: [], total: 0, facets: {} });
    render(<CoinList openCoin={() => {}} />);
    expect(await screen.findByText(/not installed on this server/)).toBeTruthy();
    cleanup();
    mockApi({ ...LIST, coins: [], total: 0 });
    render(<CoinList openCoin={() => {}} />);
    expect(await screen.findByText(/No coin type matches/)).toBeTruthy();
  });
});

describe('a name link from the Reader', () => {
  it('opens the list kept to that person, and can be cleared', async () => {
    window.history.replaceState({}, '', '/coins?person=Augustus');
    const calls = mockApi();
    render(<CoinsPage setPageType={() => {}} />);
    await screen.findByText('RRC 1/1');
    expect(calls[0]).toContain('person=Augustus');
    expect(screen.getByTestId('coins-person').textContent).toMatch(/naming Augustus/);
    await userEvent.click(screen.getByRole('button', { name: 'Show all coins' }));
    await waitFor(() => expect(calls.some((c) => !c.includes('person='))).toBe(true));
    expect(screen.queryByTestId('coins-person')).toBeNull();
  });
});

describe('one coin type', () => {
  it('opens from the list and fetches the type by its encoded id', async () => {
    const calls = mockApi();
    render(<CoinsPage setPageType={() => {}} />);
    await userEvent.click(await screen.findByRole('link', { name: 'RIC I (second edition) Augustus 125' }));
    expect(window.location.pathname).toBe('/coins/ocre%3Aric.1(2).aug.125');
    expect(await screen.findByText(/Images are not held here/)).toBeTruthy();
    expect(calls.some((c) => c === '/api/coins/ocre%3Aric.1(2).aug.125')).toBe(true);
    expect(screen.getByText('Obverse portrait')).toBeTruthy();
  });
});

describe('the Collections gate', () => {
  it('sends a visitor with coins off back to Search', async () => {
    mockApi();
    setProfile('literary');
    const setPageType = vi.fn();
    const { container } = render(<CoinsPage setPageType={setPageType} />);
    await waitFor(() => expect(setPageType).toHaveBeenCalledWith('search'));
    expect(container.textContent).toBe('');
  });
});
