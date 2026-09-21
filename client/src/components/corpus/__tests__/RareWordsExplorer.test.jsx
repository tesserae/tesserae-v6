/**
 * Rare Words Explorer: two things this file pins down.
 *
 * One, the page used to define its own `getLanguageName`, hardcoded to
 * Latin, Greek, English and Coptic, instead of importing the shared table
 * (code review 2026-09-21, finding 3). The heading for every language the
 * page offers is now read from that one table, so the bug cannot reappear
 * the moment another tab is added.
 *
 * Two, Hebrew is now one of those tabs (NC asked for it on 2026-09-21).
 * Hebrew is a fully supported search language with its own index, and the
 * tabs had simply never included it. These tests check that the tab appears
 * in the right place, that choosing it asks the API for language=he, and
 * that a Hebrew word's row renders.
 *
 * The tests stub /api/rare-lemmata-full rather than depend on the live
 * cache. Which Hebrew lemmas qualify as rare is a separate rule, covered in
 * tests/test_rare_words_hebrew.py against regenerate_rare_words_cache().
 */
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import RareWordsExplorer from '../RareWordsExplorer';

beforeEach(() => {
  global.fetch = vi.fn((url) => {
    const u = String(url);
    if (u.startsWith('/api/rare-lemmata-full')) {
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ words: [], total: 0 }) });
    }
    return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
  });
});

describe('the heading names the language from the shared table', () => {
  it('shows "Rare Words Explorer (Latin)" by default', async () => {
    render(<RareWordsExplorer />);
    await waitFor(() =>
      expect(screen.getByText('Rare Words Explorer (Latin)')).toBeTruthy());
  });

  it('shows "Rare Words Explorer (Coptic)" after switching tabs, not the raw code', async () => {
    render(<RareWordsExplorer />);
    await waitFor(() =>
      expect(screen.getByText('Rare Words Explorer (Latin)')).toBeTruthy());
    fireEvent.click(screen.getByRole('button', { name: 'Coptic' }));
    await waitFor(() =>
      expect(screen.getByText('Rare Words Explorer (Coptic)')).toBeTruthy());
    expect(screen.queryByText('Rare Words Explorer (cop)')).toBeNull();
  });
});

// Hebrew joined this page on 2026-09-21 (NC asked for it). This block
// brings its own stub: the shared one above answers every language with an
// empty list, which is all the heading tests need, while these have to tell
// a Latin answer from a Hebrew one.
const LATIN_WORDS = { words: [{ lemma: 'exiguus', display: 'exiguus', count: 3 }], total: 1 };
const HEBREW_WORDS = { words: [{ lemma: 'מהפכה', display: 'מהפכה', count: 10 }], total: 1 };

describe('the Hebrew tab', () => {
  beforeEach(() => {
    global.fetch = vi.fn((url) => {
      const u = String(url);
      if (u.startsWith('/api/rare-lemmata-full')) {
        const body = u.includes('language=he') ? HEBREW_WORDS : LATIN_WORDS;
        return Promise.resolve({ ok: true, json: () => Promise.resolve(body) });
      }
      return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
    });
  });

  it('appears in the language tabs, after English and before Coptic', async () => {
    render(<RareWordsExplorer />);
    await waitFor(() => expect(screen.getByText('exiguus')).toBeTruthy());
    const tabs = screen.getAllByRole('button').filter((b) =>
      ['Latin', 'Greek', 'English', 'Hebrew', 'Coptic'].includes(b.textContent));
    expect(tabs.map((b) => b.textContent)).toEqual(['Latin', 'Greek', 'English', 'Hebrew', 'Coptic']);
  });

  it('asks the API for language=he when chosen, and renders a Hebrew word row', async () => {
    render(<RareWordsExplorer />);
    await waitFor(() => expect(screen.getByText('exiguus')).toBeTruthy());

    fireEvent.click(screen.getByRole('button', { name: 'Hebrew' }));

    await waitFor(() => expect(
      global.fetch.mock.calls.some(([u]) => String(u).includes('language=he'))).toBe(true));
    await waitFor(() =>
      expect(screen.getByText('Rare Words Explorer (Hebrew)')).toBeTruthy());
    await waitFor(() => expect(screen.getByText('מהפכה')).toBeTruthy());
  });
});
