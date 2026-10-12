import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { render, waitFor } from '@testing-library/react';
import ThemeSearchPage from './ThemeSearchPage';

// `in=scholarship` in the address opens the page on the scholarship search
// and does not run the passage search (2026-10-12).
describe('the scholarship search from the address', () => {
  beforeEach(() => {
    window.history.replaceState({}, '', '/theme-search?query=Vergil%2C%20Aeneid%3A%20Dido&in=scholarship');
    global.fetch = vi.fn((u) => Promise.resolve({ ok: true, json: () => Promise.resolve(
      String(u).startsWith('/api/scholarship/theme') ? { available: true, label: 'Scholarship', query: 'x', results: [] }
        : String(u).startsWith('/api/languages') ? { languages: [], scholarship: true } : {}) }));
  });
  afterEach(() => { window.history.replaceState({}, '', '/'); });
  it('does not run the passage search', async () => {
    render(<ThemeSearchPage />);
    await waitFor(() => expect(global.fetch).toHaveBeenCalled());
    await new Promise((r) => setTimeout(r, 50));
    const urls = global.fetch.mock.calls.map((c) => String(c[0]));
    expect(urls.some((u) => u.startsWith('/api/passages/theme-search'))).toBe(false);
  });
});
