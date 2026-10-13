import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import ScopeBox, { resetScopeCounts } from '../ScopeBox';
import { SEARCH_SCOPE } from '../../../data/searchScope';

function serve(body, ok = true) {
  global.fetch = vi.fn(() => Promise.resolve({ ok, json: () => Promise.resolve(body) }));
}

beforeEach(() => {
  window.localStorage.clear();
  resetScopeCounts();
});
afterEach(() => {
  delete global.fetch;
  vi.restoreAllMocks();
});

describe('ScopeBox', () => {
  it('is closed by default and shows the one line', () => {
    render(<ScopeBox id="coins" />);
    expect(screen.getByText('What this search does.')).toBeTruthy();
    expect(screen.getByText(SEARCH_SCOPE.coins.does, { exact: false })).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Details' }).getAttribute('aria-expanded')).toBe('false');
    expect(screen.queryByText('Limits')).toBeNull();
  });

  it('opens on Details with four headings, the measured rows and the Help link', async () => {
    serve({ texts: {} });
    const seen = [];
    window.addEventListener('tesserae:open-help', (e) => seen.push(e.detail.section), { once: true });
    render(<ScopeBox id="parallel" />);
    fireEvent.click(screen.getByRole('button', { name: 'Details' }));
    for (const h of ['Scope', 'Texts and collections', 'Limits', 'Measured performance']) {
      expect(screen.getByText(h)).toBeTruthy();
    }
    for (const m of SEARCH_SCOPE.parallel.measured) {
      expect(screen.getByText(m.against)).toBeTruthy();
    }
    expect(screen.getByText(/Every figure was measured against a published list/)).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: 'More in Help' }));
    expect(seen).toEqual(['fusion-search']);
    await waitFor(() => expect(global.fetch).toHaveBeenCalled());
  });

  it('remembers the state per search', () => {
    const { unmount } = render(<ScopeBox id="coins" />);
    fireEvent.click(screen.getByRole('button', { name: 'Details' }));
    expect(window.localStorage.getItem('tesserae_scope_coins')).toBe('1');
    unmount();
    serve({});
    render(<ScopeBox id="coins" />);
    expect(screen.getByText('Limits')).toBeTruthy();
    render(<ScopeBox id="objects" />);
    expect(screen.getAllByText('Limits')).toHaveLength(1);
  });

  it('survives a storage error', () => {
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => { throw new Error('blocked'); });
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => { throw new Error('blocked'); });
    serve({});
    render(<ScopeBox id="events" />);
    fireEvent.click(screen.getByRole('button', { name: 'Details' }));
    expect(screen.getByText('Limits')).toBeTruthy();
  });

  it('shows live counts when the fetch answers', async () => {
    serve({ texts: { la: 1234, grc: 56 }, coins: 99 });
    render(<ScopeBox id="line" />);
    fireEvent.click(screen.getByRole('button', { name: 'Details' }));
    await waitFor(() => expect(screen.getByText(/Works held now: Latin 1,234, Greek 56\./)).toBeTruthy());
  });

  it('shows the dated line when the fetch fails or has no figure', async () => {
    global.fetch = vi.fn(() => Promise.reject(new Error('down')));
    render(<ScopeBox id="theme" />);
    fireEvent.click(screen.getByRole('button', { name: 'Details' }));
    await waitFor(() => expect(global.fetch).toHaveBeenCalled());
    expect(screen.getByText(SEARCH_SCOPE.theme.covers)).toBeTruthy();
  });

  it('renders nothing for an unknown search', () => {
    const { container } = render(<ScopeBox id="nope" />);
    expect(container.firstChild).toBeNull();
  });
});
