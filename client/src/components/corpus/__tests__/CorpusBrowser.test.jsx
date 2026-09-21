/**
 * Browse Corpus: the "Theme Search" coverage badge.
 *
 * Theme Search and Similar Passages run over the passage index, which
 * covers most but not all of the corpus. A work with no passage windows
 * never appears in either feature, and nothing on the site said so. This
 * mirrors the existing "EN" translation badge test-shape: stub
 * /api/passages/works and check the badge lands on a covered work and not
 * on an uncovered one.
 */
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import CorpusBrowser from '../CorpusBrowser';

const TEXTS = [
  { id: 'vergil.aeneid.part.1.tess', author: 'Vergil', title: 'Aeneid 1', line_count: 756 },
  { id: 'vergil.aeneid.part.2.tess', author: 'Vergil', title: 'Aeneid 2', line_count: 620 },
  { id: 'cicero.orator.tess', author: 'Cicero', title: 'Orator', line_count: 236 },
];

function mockFetch(url) {
  if (url.startsWith('/api/texts')) {
    return Promise.resolve({ json: () => Promise.resolve(TEXTS) });
  }
  if (url.startsWith('/api/passages/translations')) {
    return Promise.resolve({ json: () => Promise.resolve({ language: 'la', works: {} }) });
  }
  if (url.startsWith('/api/passages/works')) {
    return Promise.resolve({
      json: () => Promise.resolve({ language: 'la', works: ['vergil.aeneid'] }),
    });
  }
  if (url.startsWith('/api/text-descriptions')) {
    return Promise.resolve({ json: () => Promise.resolve({ descriptions: {} }) });
  }
  if (url.startsWith('/api/stats')) {
    return Promise.resolve({ json: () => Promise.resolve({}) });
  }
  return Promise.resolve({ json: () => Promise.resolve({}) });
}

beforeEach(() => {
  global.fetch = vi.fn(mockFetch);
});

afterEach(() => {
  vi.unstubAllGlobals();
  window.history.replaceState({}, '', '/');
});

// Corpus Browser used to define its own `getLanguageName`, hardcoded to
// { la, grc, en, cop }, instead of importing the shared `languageName`
// (code review 2026-09-21, finding 3). Its language tabs only ever offer
// those four languages, so a Hebrew heading is not reachable through this
// page today -- that gap is real, but it's a separate product decision
// (whether to add a Hebrew tab here at all), not this bug. What the fix
// does guarantee is that the heading for every language this page DOES
// offer comes from the one shared table, so the bug can't reappear the
// moment a fifth tab is added.
describe('the corpus heading names the language from the shared table', () => {
  it('shows "Greek Corpus" for the Greek tab, not a raw or stale name', async () => {
    render(<CorpusBrowser />);
    await waitFor(() => expect(screen.getByText('Vergil')).toBeTruthy());
    fireEvent.click(screen.getByRole('button', { name: 'Greek' }));
    await waitFor(() => expect(screen.getByText('Greek Corpus')).toBeTruthy());
  });
});

// The era filter used to be a second, hand-written table (finding 4) that
// had drifted from utils/eras.js: English's "18th Century" matched no work
// (the backend tags that period "Neoclassical" or "Augustan"). It's now
// derived from the shared table, so the two can't drift apart again.
describe('the era filter comes from the shared era table', () => {
  it('offers "Neoclassical" for English, not the old, unmatched "18th Century"', async () => {
    window.history.replaceState({}, '', '/corpus?language=en');
    render(<CorpusBrowser />);
    await waitFor(() => expect(screen.getByDisplayValue('All Eras')).toBeTruthy());
    const eraSelect = screen.getByDisplayValue('All Eras');
    const labels = [...eraSelect.options].map((o) => o.textContent);
    expect(labels).toContain('Neoclassical');
    expect(labels).not.toContain('18th Century');
  });
});

describe('the Theme Search coverage badge', () => {
  it('marks a covered work and leaves an uncovered one alone', async () => {
    render(<CorpusBrowser />);

    await waitFor(() => expect(screen.getByText('Vergil')).toBeTruthy());
    fireEvent.click(screen.getByText('Vergil'));
    fireEvent.click(screen.getByText('Cicero'));

    await waitFor(() => expect(screen.getAllByText('Theme Search').length).toBe(2));
    // Two Vergil parts collapse to one covered work, so both rows get the
    // badge; Cicero's single work does not.
    expect(screen.queryAllByTitle('Covered by Theme Search and Similar Passages').length).toBe(2);
  });

  it('shows a coverage count under the corpus heading', async () => {
    render(<CorpusBrowser />);

    await waitFor(() =>
      expect(screen.getByText(/1 of 2 works are covered by Theme Search/)).toBeTruthy());
  });

  it('can show only the covered works', async () => {
    render(<CorpusBrowser />);
    await waitFor(() => expect(screen.getByText('Cicero')).toBeTruthy());
    fireEvent.click(screen.getByLabelText('Show only works covered by Theme Search'));
    await waitFor(() => expect(screen.queryByText('Cicero')).toBeNull());
    expect(screen.getByText('Vergil')).toBeTruthy();
  });

  it('a URL of ?theme=1&language=la opens straight to the covered-only list', async () => {
    window.history.replaceState({}, '', '/corpus?theme=1&language=la');
    render(<CorpusBrowser />);

    await waitFor(() => expect(screen.getByText('Vergil')).toBeTruthy());
    // The filter is already on: Cicero (uncovered) never shows.
    expect(screen.queryByText('Cicero')).toBeNull();
    expect(screen.getByLabelText('Show only works covered by Theme Search').checked).toBe(true);
  });

  it('shows the "Works covered by Theme Search" heading and a Copy list button when the filter is on', async () => {
    window.history.replaceState({}, '', '/corpus?theme=1&language=la');
    render(<CorpusBrowser />);

    await waitFor(() =>
      expect(screen.getByText('Works covered by Theme Search: 1 of 2 in Latin')).toBeTruthy());
    expect(screen.getByText('Copy list')).toBeTruthy();
    expect(screen.getByText('Download list')).toBeTruthy();
  });

  it('shows no heading or list buttons when the filter is off', async () => {
    render(<CorpusBrowser />);

    await waitFor(() => expect(screen.getByText('Vergil')).toBeTruthy());
    expect(screen.queryByText(/Works covered by Theme Search:/)).toBeNull();
    expect(screen.queryByText('Copy list')).toBeNull();
  });

  it('a failed works fetch costs only the badges, not the page', async () => {
    global.fetch = vi.fn((url) => {
      if (url.startsWith('/api/passages/works')) {
        return Promise.reject(new Error('network down'));
      }
      return mockFetch(url);
    });

    render(<CorpusBrowser />);

    await waitFor(() => expect(screen.getByText('Vergil')).toBeTruthy());
    fireEvent.click(screen.getByText('Vergil'));
    await waitFor(() => expect(screen.getByText('Aeneid 1')).toBeTruthy());
    expect(screen.queryByText('Theme Search')).toBeNull();
  });

  // Right after a deploy reload, the passage index can still be loading on
  // this server and /api/passages/works comes back slow, empty, or failed.
  // The old code read that as "zero coverage" and printed "0 of 2 works are
  // covered by Theme Search" -- indistinguishable from a real gap. Now it
  // says the count is still loading instead of asserting a false zero.
  describe('when the works fetch cannot yet answer', () => {
    it('shows "coverage is loading" rather than "0 of N" on a failed fetch', async () => {
      global.fetch = vi.fn((url) => {
        if (url.startsWith('/api/passages/works')) {
          return Promise.reject(new Error('network down'));
        }
        return mockFetch(url);
      });

      render(<CorpusBrowser />);

      await waitFor(() =>
        expect(screen.getByText(/Theme Search coverage is loading/)).toBeTruthy());
      expect(screen.queryByText(/0 of 2 works are covered/)).toBeNull();
    });

    it('shows "coverage is loading" rather than "0 of N" on an empty works list', async () => {
      global.fetch = vi.fn((url) => {
        if (url.startsWith('/api/passages/works')) {
          return Promise.resolve({ json: () => Promise.resolve({ language: 'la', works: [] }) });
        }
        return mockFetch(url);
      });

      render(<CorpusBrowser />);

      await waitFor(() =>
        expect(screen.getByText(/Theme Search coverage is loading/)).toBeTruthy());
      expect(screen.queryByText(/0 of 2 works are covered/)).toBeNull();
    });

    it('recovers to the real count once a retry succeeds', async () => {
      vi.useFakeTimers();
      let calls = 0;
      global.fetch = vi.fn((url) => {
        if (url.startsWith('/api/passages/works')) {
          calls += 1;
          if (calls < 2) {
            return Promise.resolve({ json: () => Promise.resolve({ language: 'la', works: [] }) });
          }
          return Promise.resolve({
            json: () => Promise.resolve({ language: 'la', works: ['vergil.aeneid'] }),
          });
        }
        return mockFetch(url);
      });

      render(<CorpusBrowser />);

      // First attempt fires immediately and comes back empty: "loading".
      await act(() => vi.advanceTimersByTimeAsync(0));
      expect(screen.getByText(/Theme Search coverage is loading/)).toBeTruthy();

      // Retry at +3s succeeds, so the real count takes over.
      await act(() => vi.advanceTimersByTimeAsync(3000));
      expect(screen.getByText(/1 of 2 works are covered by Theme Search/)).toBeTruthy();

      vi.useRealTimers();
    });
  });
});

// Hebrew as a Corpus Browser tab (added 2026-09-21). The live corpus is 39
// Hebrew Bible books, one author ("Hebrew Bible"), one era ("Biblical").
const HEBREW_TEXTS = [
  { id: 'hebrew_bible.genesis.tess', author: 'Hebrew Bible', title: 'Genesis', era: 'Biblical', line_count: 1533 },
  { id: 'hebrew_bible.exodus.tess', author: 'Hebrew Bible', title: 'Exodus', era: 'Biblical', line_count: 1213 },
];

function mockFetchWithHebrew(url) {
  if (url.startsWith('/api/texts?language=he')) {
    return Promise.resolve({ json: () => Promise.resolve(HEBREW_TEXTS) });
  }
  return mockFetch(url);
}

describe('the Hebrew tab', () => {
  it('appears in the language tabs, after English and before Coptic', () => {
    render(<CorpusBrowser />);
    const tabs = screen.getAllByRole('button').map((b) => b.textContent);
    const order = ['Latin', 'Greek', 'English', 'Hebrew', 'Coptic'].filter((l) => tabs.includes(l));
    expect(order).toEqual(['Latin', 'Greek', 'English', 'Hebrew', 'Coptic']);
  });

  it('asks the API for language=he when chosen, and renders a Hebrew work name', async () => {
    global.fetch = vi.fn(mockFetchWithHebrew);
    render(<CorpusBrowser />);

    await waitFor(() => expect(screen.getByText('Latin Corpus')).toBeTruthy());
    fireEvent.click(screen.getByText('Hebrew'));

    await waitFor(() =>
      expect(global.fetch).toHaveBeenCalledWith(expect.stringContaining('/api/texts?language=he')));
    await waitFor(() => expect(screen.getByText('Hebrew Corpus')).toBeTruthy());

    fireEvent.click(screen.getByText('Hebrew Bible'));
    await waitFor(() => expect(screen.getByText('Genesis')).toBeTruthy());
    expect(screen.getByText('Exodus')).toBeTruthy();
  });

  it('offers a Biblical era option, not the Latin era list, once Hebrew is chosen', async () => {
    global.fetch = vi.fn(mockFetchWithHebrew);
    render(<CorpusBrowser />);

    await waitFor(() => expect(screen.getByText('Latin Corpus')).toBeTruthy());
    fireEvent.click(screen.getByText('Hebrew'));

    await waitFor(() => expect(screen.getByText('Hebrew Corpus')).toBeTruthy());
    const eraSelect = screen.getByDisplayValue('All Eras');
    const optionLabels = Array.from(eraSelect.querySelectorAll('option')).map((o) => o.textContent);
    expect(optionLabels).toEqual(['All Eras', 'Biblical', 'Unknown']);
    // The Latin-only "Republic"/"Augustan" options must not leak into Hebrew's list.
    expect(optionLabels).not.toContain('Republic');
  });
});
