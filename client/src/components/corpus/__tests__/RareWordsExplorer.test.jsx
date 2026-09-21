/**
<<<<<<< HEAD
 * Rare Words Explorer used to define its own `getLanguageName`, hardcoded
 * to { la, grc, en, cop }, instead of importing the shared `languageName`
 * (code review 2026-09-21, finding 3). Its language tabs only ever offer
 * those four languages -- there is no Hebrew tab here today, so a Hebrew
 * heading isn't reachable through this page (adding one is a separate
 * product decision, not this bug fix). What this pins down is that the
 * heading for every language the page DOES offer is read from the one
 * shared table, so the bug can't reappear the moment a fifth tab is added.
=======
 * Rare Words Explorer: the Hebrew tab (added 2026-09-21).
 *
 * Hebrew is a fully supported search language (40 .tess files, its own
 * index) but the Explorer's tabs hardcoded to Latin/Greek/English/Coptic.
 * These tests check the tab shows up in the right place, that choosing it
 * queries the API for language=he, and that a Hebrew word's row renders.
 *
 * These tests stub /api/rare-lemmata-full directly rather than depend on
 * the live cache. The cache builder's own Hebrew extraction rule (which
 * lemmas qualify as rare) is covered separately in
 * tests/test_rare_words_hebrew.py, against backend/blueprints/hapax.py's
 * regenerate_rare_words_cache().
>>>>>>> 8e002bc6 (Fix stale comments left behind by the Hebrew rare-words backend fix)
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

// Hebrew joined this page on 2026-09-21 (NC asked for it). Merged in from
// the Hebrew branch after the shared-language-name work landed first.
describe('the Hebrew tab', () => {
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

    fireEvent.click(screen.getByText('Hebrew'));

    await waitFor(() =>
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining('language=he'),
        expect.anything()
      ));
    await waitFor(() => expect(screen.getByText('Rare Words Explorer (Hebrew)')).toBeTruthy());
    await waitFor(() => expect(screen.getByText(HEBREW_WORDS.words[0].lemma)).toBeTruthy());
  });
});
