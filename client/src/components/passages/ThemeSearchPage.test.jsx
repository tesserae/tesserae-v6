/**
 * Theme Search shows a real author and title, not the file id.
 *
 * The scene index names a work by its filename slug internally
 * ("quintus_smyrnaeus.fall_of_troy"), but the API sends author/title/
 * display_name from get_text_metadata -- the same source Browse Corpus and
 * the Reader's Similar Passages tab use -- so the page should read that
 * instead of the raw work id.
 */
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import ThemeSearchPage from './ThemeSearchPage';

const RESULT = {
  query: 'a hero descends to the underworld',
  confidence: { level: 'high' },
  results: [{
    id: 'quintus_smyrnaeus.fall_of_troy.w1',
    language: 'grc',
    work: 'quintus_smyrnaeus.fall_of_troy',
    author: 'Quintus Smyrnaeus',
    title: 'The Fall of Troy',
    display_name: 'Quintus Smyrnaeus, The Fall of Troy',
    ref_start: '6.357',
    ref_end: '6.360',
    score: 0.9,
    gist: 'A hero descends to the underworld.',
  }],
};

beforeEach(() => {
  global.fetch = vi.fn((url) => {
    const u = String(url);
    if (u.startsWith('/api/languages')) {
      return Promise.resolve({ json: () => Promise.resolve({ languages: [] }) });
    }
    if (u.startsWith('/api/passages/theme-search')) {
      return Promise.resolve({ json: () => Promise.resolve(RESULT) });
    }
    return Promise.resolve({ json: () => Promise.resolve({}) });
  });
});

async function search(text) {
  render(<ThemeSearchPage />);
  fireEvent.change(screen.getByPlaceholderText(/a warrior arms himself/), {
    target: { value: text },
  });
  fireEvent.click(screen.getByRole('button', { name: /^search/i }));   // the submit ("Search" or "Searching…"), not the Theme Search tab
  await waitFor(() => expect(global.fetch).toHaveBeenCalledWith(
    expect.stringContaining('/api/passages/theme-search')));
}

describe('results are labelled with a real author and title', () => {
  it('renders the display name the API sends', async () => {
    await search('a hero descends to the underworld');
    expect(await screen.findByText('Quintus Smyrnaeus, The Fall of Troy')).toBeTruthy();
    expect(screen.queryByText(/quintus_smyrnaeus\.fall_of_troy/)).toBeNull();
  });

  it('falls back to the raw work id only when the API sends no display name', async () => {
    global.fetch = vi.fn((url) => {
      const u = String(url);
      if (u.startsWith('/api/languages')) {
        return Promise.resolve({ json: () => Promise.resolve({ languages: [] }) });
      }
      if (u.startsWith('/api/passages/theme-search')) {
        return Promise.resolve({ json: () => Promise.resolve({
          query: 'x', confidence: { level: 'high' },
          results: [{ id: 'w1', language: 'la', work: 'ovid.metamorphoses',
                      ref_start: '4.55', score: 0.8 }],
        }) });
      }
      return Promise.resolve({ json: () => Promise.resolve({}) });
    });
    await search('x');
    expect(await screen.findByText('ovid.metamorphoses')).toBeTruthy();
  });
});

describe('the per-result language badge (code review 2026-09-21, finding 3)', () => {
  it('labels a Hebrew result "Hebrew", not the raw code "he"', async () => {
    global.fetch = vi.fn((url) => {
      const u = String(url);
      if (u.startsWith('/api/languages')) {
        return Promise.resolve({ json: () => Promise.resolve({ languages: [] }) });
      }
      if (u.startsWith('/api/passages/theme-search')) {
        return Promise.resolve({ json: () => Promise.resolve({
          query: 'x', confidence: { level: 'high' },
          results: [{ id: 'w1', language: 'he', work: 'genesis',
                      display_name: 'Genesis', ref_start: '1.1', score: 0.9 }],
        }) });
      }
      return Promise.resolve({ json: () => Promise.resolve({}) });
    });
    await search('x');
    await waitFor(() => expect(screen.getByText('Genesis')).toBeTruthy());
    // "Hebrew" also appears as a language-picker checkbox label, so this
    // checks that it appears (not raw "he" anywhere), rather than that it
    // appears exactly once.
    expect(screen.getAllByText('Hebrew').length).toBeGreaterThan(0);
    expect(screen.queryByText('he')).toBeNull();
  });
});

/**
 * The "N of M works" coverage line under the language row used to render
 * only when exactly one covered language (Latin, Greek, English, Coptic)
 * was picked -- with the default "All languages" nothing pointed at the
 * covered-works list at all. Now one line always shows: the existing
 * per-language sentence for one covered language, a fixed sentence for one
 * language Browse Corpus doesn't index, and a summed sentence otherwise
 * (the default, or several languages picked together).
 */
describe('the covered-works line under the language row', () => {
  // la: 10 texts, 8 covered. grc: 5 texts, 5 covered. en: 4 texts, 2
  // covered. cop: 3 texts, 3 covered. Sum: 18 of 4 languages.
  const TOTALS = { la: 10, grc: 5, en: 4, cop: 3 };
  const COVERED = { la: 8, grc: 5, en: 2, cop: 3 };

  function mockFetch() {
    return vi.fn((url) => {
      const u = String(url);
      if (u.startsWith('/api/languages')) {
        return Promise.resolve({ json: () => Promise.resolve({ languages: [] }) });
      }
      const textsMatch = u.match(/^\/api\/texts\?language=(\w+)/);
      if (textsMatch) {
        const lang = textsMatch[1];
        const n = TOTALS[lang] || 0;
        const texts = Array.from({ length: n }, (_, i) => (
          { id: `${lang}${i}.tess`, author: 'Author', title: `Work ${i}` }
        ));
        return Promise.resolve({ json: () => Promise.resolve(texts) });
      }
      const worksMatch = u.match(/^\/api\/passages\/works\?language=(\w+)/);
      if (worksMatch) {
        const lang = worksMatch[1];
        const n = COVERED[lang] || 0;
        const works = Array.from({ length: n }, (_, i) => `${lang}${i}`);
        return Promise.resolve({ json: () => Promise.resolve({ works }) });
      }
      if (u.startsWith('/api/passages/theme-search')) {
        return Promise.resolve({ json: () => Promise.resolve(RESULT) });
      }
      return Promise.resolve({ json: () => Promise.resolve({}) });
    });
  }

  beforeEach(() => {
    global.fetch = mockFetch();
    // The page writes the current query and languages into the address bar
    // (replaceState) so a search survives a reload. jsdom's window.location
    // isn't reset between tests in this file, so without this a later test's
    // fresh mount reads an earlier test's leftover ?query=&languages= and
    // starts already mid-search with a language picked.
    window.history.replaceState(null, '', '/');
  });

  it('with all languages (the default), sums coverage over the four Browse Corpus indexes', async () => {
    render(<ThemeSearchPage />);
    expect(await screen.findByText(/Theme Search covers 18 works in 4 languages\./)).toBeTruthy();
    const link = screen.getByRole('link', { name: 'See the list.' });
    expect(link.getAttribute('href')).toBe('/corpus?theme=1&language=la');

    // Picking several languages together (not exactly one) keeps the same
    // summed sentence rather than something that doesn't parse.
    fireEvent.click(screen.getByText('Latin'));
    fireEvent.click(screen.getByText('Greek'));
    expect(await screen.findByText(/Theme Search covers 18 works in 4 languages\./)).toBeTruthy();
  });

  it('with one covered language selected, keeps the per-language sentence', async () => {
    render(<ThemeSearchPage />);
    await screen.findByText(/Theme Search covers 18 works in 4 languages\./);
    fireEvent.click(screen.getByText('Latin'));
    expect(await screen.findByText(/Searches 8 of 10 works in Latin\./)).toBeTruthy();
    const link = screen.getByRole('link', { name: 'See the list of covered works' });
    expect(link.getAttribute('href')).toBe('/corpus?theme=1&language=la');
    expect(screen.queryByText(/Theme Search covers/)).toBeNull();
  });

  it("while a picked covered language's count is still loading, shows a loading sentence with a link", async () => {
    render(<ThemeSearchPage />);
    await screen.findByText(/Theme Search covers 18 works in 4 languages\./);
    fireEvent.click(screen.getByText('Greek'));
    // Synchronously after the click, before the /api/texts and
    // /api/passages/works fetches for Greek have resolved, the count for
    // this language is unknown. This is the state the old gate
    // (`coverage && coverage.total > 0`) rendered nothing for at all.
    expect(screen.getByText(/Theme Search coverage is loading\./)).toBeTruthy();
    const link = screen.getByRole('link', { name: 'See the list of covered works' });
    expect(link.getAttribute('href')).toBe('/corpus?theme=1&language=grc');
    // Once it resolves, it settles into the normal per-language sentence.
    expect(await screen.findByText(/Searches 5 of 5 works in Greek\./)).toBeTruthy();
  });

  it('when a picked covered language resolves to zero indexed works, shows the fixed sentence', async () => {
    global.fetch = vi.fn((url) => {
      const u = String(url);
      if (u.startsWith('/api/languages')) {
        return Promise.resolve({ json: () => Promise.resolve({ languages: [] }) });
      }
      // English has zero indexed texts in this snapshot; the other three
      // covered languages still have some.
      const totals = { la: 10, grc: 5, en: 0, cop: 3 };
      const covered = { la: 8, grc: 5, en: 0, cop: 3 };
      const textsMatch = u.match(/^\/api\/texts\?language=(\w+)/);
      if (textsMatch) {
        const lang = textsMatch[1];
        const n = totals[lang] || 0;
        const texts = Array.from({ length: n }, (_, i) => (
          { id: `${lang}${i}.tess`, author: 'Author', title: `Work ${i}` }
        ));
        return Promise.resolve({ json: () => Promise.resolve(texts) });
      }
      const worksMatch = u.match(/^\/api\/passages\/works\?language=(\w+)/);
      if (worksMatch) {
        const lang = worksMatch[1];
        const n = covered[lang] || 0;
        const works = Array.from({ length: n }, (_, i) => `${lang}${i}`);
        return Promise.resolve({ json: () => Promise.resolve({ works }) });
      }
      return Promise.resolve({ json: () => Promise.resolve({}) });
    });
    render(<ThemeSearchPage />);
    // 8 + 5 + 0 + 3 = 16.
    await screen.findByText(/Theme Search covers 16 works in 4 languages\./);
    fireEvent.click(screen.getByText('English'));
    expect(await screen.findByText(
      /Theme Search covers works in Latin, Greek, English and Coptic;/
    )).toBeTruthy();
    const link = screen.getByRole('link', { name: 'see the list' });
    expect(link.getAttribute('href')).toBe('/corpus?theme=1&language=la');
    expect(screen.queryByText(/Searches \d+ of \d+ works/)).toBeNull();
  });

  it('with one language Browse Corpus does not cover selected, shows the fixed sentence', async () => {
    render(<ThemeSearchPage />);
    await screen.findByText(/Theme Search covers 18 works in 4 languages\./);
    fireEvent.click(screen.getByText('Hebrew'));
    expect(await screen.findByText(
      /Theme Search covers works in Latin, Greek, English and Coptic;/
    )).toBeTruthy();
    const link = screen.getByRole('link', { name: 'see the list' });
    expect(link.getAttribute('href')).toBe('/corpus?theme=1&language=la');
    expect(screen.queryByText(/Searches \d+ of \d+ works/)).toBeNull();
  });
});
