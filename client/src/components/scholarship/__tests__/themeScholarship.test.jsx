/**
 * The Scholarship option of Theme Search: hidden unless the Scholarship
 * collection is on, exclusive with Coins and Objects, its own list and label.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import ThemeSearchPage from '../../passages/ThemeSearchPage';
import ThemeScholarship, { heading, linkText, workName } from '../ThemeScholarship';
import { PAGE_NEEDS } from '../../../collections/collectionsConfig';
import { setProfile, setCollection } from '../../../collections/collectionsStore';

const LABEL = 'Ranked by a blend of meaning and keyword search over 82,814 commentary notes and article sentences. On fifteen test questions, thirteen had a strongly relevant note in the first ten.';
const THEME = {
  available: true, query: 'catalogue of ships', label: LABEL,
  results: [
    { id: 'servius:vergil.aeneid:1', rank: 1, score: 0.03, meaning_rank: 1, keyword_rank: 2, kind: 'commentary',
      commentator: 'Conington and Nettleship', work: 'vergil.aeneid', ref_start: 'verg. aen. 7.641', ref_end: 'verg. aen. 7.641',
      journal: null, title: null, year: null, snippet: 'This invocation is of course from that in Il. 2. 484.',
      link: { kind: 'reader', url: '/read?work=vergil.aeneid.tess&lang=la&ref=7.641' } },
    { id: 'ejc:1:0', rank: 2, score: 0.02, meaning_rank: 7, keyword_rank: 3, kind: 'article', commentator: null,
      work: 'horace.satires', ref_start: '1.10.77', ref_end: '1.10.77', journal: 'Classical Philology',
      title: 'Notes on Horace', year: 1912, snippet: 'Catalogue of the ships in the Iliad.',
      link: { kind: 'jstor', url: 'https://www.jstor.org/stable/262736' } },
  ],
};

function mockApi(override) {
  const calls = [];
  global.fetch = vi.fn(async (url) => {
    const u = String(url);
    calls.push(u);
    let body = {};
    if (u.startsWith('/api/scholarship/theme')) body = override || THEME;
    else if (u.startsWith('/api/languages')) body = { languages: [] };
    return { ok: true, status: 200, json: async () => body };
  });
  return calls;
}

beforeEach(() => {
  window.localStorage.clear();
  window.sessionStorage.clear();
  window.history.replaceState({}, '', '/theme-search');
  setProfile('literary');
});
afterEach(() => { cleanup(); delete global.fetch; window.history.replaceState({}, '', '/'); });

async function run(text) {
  fireEvent.change(screen.getByPlaceholderText(/a warrior arms himself/), { target: { value: text } });
  fireEvent.click(screen.getByRole('button', { name: /^search/i }));
}

describe('wiring', () => {
  it('is needed by the Scholarship collection', () => {
    expect(PAGE_NEEDS['scholarship-theme']).toEqual(['scholarship']);
  });
});

describe('card text', () => {
  it('names a commentary by commentator, work and reference, an article by journal and year', () => {
    expect(heading(THEME.results[0])).toBe('Conington and Nettleship on Vergil Aeneid, verg. aen. 7.641');
    expect(heading(THEME.results[1])).toBe('Classical Philology, 1912');
    expect(workName('homer.hymns.part.1')).toBe('Homer Hymns');
  });
  it('words the link by where it goes', () => {
    expect(linkText({ kind: 'reader', url: '/read?x' })).toBe('Open the passage in the Reader');
    expect(linkText({ kind: 'jstor', url: 'https://www.jstor.org/stable/1' })).toBe('Open the article on JSTOR');
    expect(linkText({ kind: 'jstor', url: 'https://archive.org/details/x' })).toBe('Open the article');
    expect(linkText(null)).toBeNull();
  });
});

describe('ThemeScholarship', () => {
  it('renders the label and a card for each result with its link', async () => {
    mockApi();
    render(<ThemeScholarship search={{ q: 'catalogue of ships', n: 1 }} />);
    await screen.findByText('This invocation is of course from that in Il. 2. 484.');
    expect(screen.getByTestId('theme-scholarship-label').textContent).toBe(LABEL);
    expect(screen.getAllByTestId('scholarship-match')).toHaveLength(2);
    expect(screen.getByText('Notes on Horace')).toBeTruthy();
    expect(screen.getByRole('link', { name: 'Open the passage in the Reader' }).getAttribute('href'))
      .toBe('/read?work=vergil.aeneid.tess&lang=la&ref=7.641');
    expect(screen.getByRole('link', { name: 'Open the article on JSTOR' }).getAttribute('href'))
      .toBe('https://www.jstor.org/stable/262736');
    expect(screen.getByTestId('scope-box-scholarship_theme')).toBeTruthy();
  });

  it('says so when the files are not installed', async () => {
    mockApi({ available: false, results: [], reason: 'x' });
    render(<ThemeScholarship search={{ q: 'a', n: 1 }} />);
    await screen.findByText(/not installed on this server yet/);
  });

  it('says so when the encoder is down', async () => {
    mockApi({ available: true, unavailable: true, error: 'The query encoder service is not running.', results: [] });
    render(<ThemeScholarship search={{ q: 'a', n: 1 }} />);
    await screen.findByText('The query encoder service is not running.');
  });
});

describe('Theme Search choice', () => {
  it('offers no Scholarship choice when the collection is off', () => {
    mockApi();
    setCollection('scholarship', false);
    render(<ThemeSearchPage />);
    expect(screen.queryByRole('checkbox', { name: 'Scholarship' })).toBeNull();
  });

  it('searches the scholarship on its own, never the passages, and shows cards', async () => {
    const calls = mockApi();
    setCollection('scholarship', true);
    render(<ThemeSearchPage />);
    await userEvent.click(screen.getByRole('checkbox', { name: 'Scholarship' }));
    await run('catalogue of ships');
    await screen.findByText('Catalogue of the ships in the Iliad.');
    expect(calls.some((c) => c.startsWith('/api/scholarship/theme?q=catalogue%20of%20ships'))).toBe(true);
    expect(calls.some((c) => c.startsWith('/api/passages/theme-search'))).toBe(false);
    expect(screen.getByTestId('theme-scholarship-label').textContent).toBe(LABEL);
    await userEvent.click(screen.getByRole('checkbox', { name: 'Scholarship' }));
    expect(screen.queryByTestId('theme-scholarship')).toBeNull();
  });

  it('keeps Scholarship apart from Coins and Objects, in both directions', async () => {
    mockApi();
    setProfile('everything');
    setCollection('scholarship', true);
    setCollection('coins', true);
    setCollection('objects', true);
    render(<ThemeSearchPage />);
    const box = (n) => screen.getByRole('checkbox', { name: n });
    await userEvent.click(box('Coins'));
    await userEvent.click(box('Scholarship'));
    expect(box('Scholarship').checked).toBe(true);
    expect(box('Coins').checked).toBe(false);
    await userEvent.click(box('Objects'));
    expect(box('Objects').checked).toBe(true);
    expect(box('Scholarship').checked).toBe(false);
    await userEvent.click(box('Scholarship'));
    expect(box('Objects').checked).toBe(false);
    await userEvent.click(box('Coins'));
    expect(box('Scholarship').checked).toBe(false);
  });
});


describe('Recent articles under the list', () => {
  const rec = (title, extra = {}) => ({ title, authors: ['A. Scholar'], year: 2020, venue: 'Classical Quarterly', doi: null, oa_url: null, url: null, excerpt: '', score: 1, ...extra });

  function mockRecent(answers) {
    const calls = [];
    global.fetch = vi.fn((url) => {
      const u = String(url);
      calls.push(u);
      const reply = (body) => Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(body) });
      if (u.startsWith('/api/scholarship/theme')) return reply(THEME);
      if (u.startsWith('/api/passages/recent-scholarship')) {
        const svc = new URL(u, 'http://x').searchParams.get('service');
        const a = answers[svc];
        return typeof a === 'function' ? a(reply) : reply(a || { service: svc, available: true, results: [] });
      }
      return reply({});
    });
    return calls;
  }

  it('paints each service as it answers and drops the pending line when all have', async () => {
    let release;
    const gate = new Promise((r) => { release = r; });
    const calls = mockRecent({
      openalex: { service: 'openalex', available: true, results: [rec('Dido in Love', { oa_url: 'https://free.example/d.pdf' })] },
      crossref: (reply) => gate.then(() => reply({ service: 'crossref', available: true, results: [rec('Politics of Passion', { doi: '10.1/pp', year: 2022 })] })),
    });
    render(<ThemeScholarship search={{ q: 'love and politics', n: 1 }} />);
    const box = await screen.findByTestId('theme-recent');
    expect(screen.getAllByTestId('theme-recent-item')).toHaveLength(1);
    expect(screen.getByRole('link', { name: 'Dido in Love' })).toHaveAttribute('href', 'https://free.example/d.pdf');
    expect(box).toHaveTextContent('free copy');
    expect(screen.getByTestId('theme-recent-pending')).toHaveTextContent('Looking up recent articles from Crossref...');
    release();
    await waitFor(() => expect(screen.getAllByTestId('theme-recent-item')).toHaveLength(2));
    await waitFor(() => expect(screen.queryByTestId('theme-recent-pending')).toBeNull());
    expect(screen.getByRole('link', { name: 'Politics of Passion' })).toHaveAttribute('href', 'https://doi.org/10.1/pp');
    const asks = calls.filter((c) => c.startsWith('/api/passages/recent-scholarship'));
    expect(asks).toHaveLength(5);
    expect(asks.every((c) => !c.includes('work='))).toBe(true);
  });

  it('passes the work when the search came from Search One Text', async () => {
    const calls = mockRecent({});
    render(<ThemeScholarship search={{ q: 'love', n: 1, work: 'vergil.aeneid' }} />);
    await screen.findByTestId('theme-scholarship');
    await waitFor(() => expect(calls.filter((c) => c.includes('recent-scholarship'))).toHaveLength(5));
    expect(calls.filter((c) => c.includes('recent-scholarship')).every((c) => c.includes('work=vergil.aeneid'))).toBe(true);
  });

  it('shows nothing at all when every service answered with no items', async () => {
    mockRecent({});
    render(<ThemeScholarship search={{ q: 'love', n: 1 }} />);
    await screen.findByTestId('theme-scholarship');
    await waitFor(() => expect(screen.queryByTestId('theme-recent-pending')).toBeNull());
    expect(screen.queryByTestId('theme-recent')).toBeNull();
  });

  it('Theme Search reads work from the address and hands it to the scholarship search', async () => {
    const calls = mockRecent({ openalex: { service: 'openalex', available: true, results: [rec('Dido in Love')] } });
    window.history.replaceState({}, '', '/theme-search?query=love&in=scholarship&work=vergil.aeneid');
    setCollection('scholarship', true);
    render(<ThemeSearchPage />);
    await screen.findByTestId('theme-recent');
    expect(calls.some((c) => c.includes('recent-scholarship') && c.includes('work=vergil.aeneid'))).toBe(true);
  });
});
