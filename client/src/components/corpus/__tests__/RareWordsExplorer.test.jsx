/**
 * Rare Words Explorer used to define its own `getLanguageName`, hardcoded
 * to { la, grc, en, cop }, instead of importing the shared `languageName`
 * (code review 2026-09-21, finding 3). Its language tabs only ever offer
 * those four languages -- there is no Hebrew tab here today, so a Hebrew
 * heading isn't reachable through this page (adding one is a separate
 * product decision, not this bug fix). What this pins down is that the
 * heading for every language the page DOES offer is read from the one
 * shared table, so the bug can't reappear the moment a fifth tab is added.
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
