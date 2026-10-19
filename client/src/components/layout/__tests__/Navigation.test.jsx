import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { cleanup, render, screen, waitFor, fireEvent, within } from '@testing-library/react';
import Navigation from '../Navigation';
import { mockResponse } from '../../../test/mockResponse';

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

const noop = () => {};

const renderNav = (props = {}) =>
  render(
    <Navigation
      pageType="search"
      setPageType={noop}
      activeTab="la"
      setActiveTab={noop}
      {...props}
    />
  );

// The pages about what the texts refer to sit under one menu. Opens it and
// returns the menu element once it is on screen.
const THINGS = { name: /^People, Places & Things/ };
const openThings = async () => {
  fireEvent.click(await screen.findByRole('button', THINGS));
  return screen.getByTestId('things-menu');
};
const thingsNames = (menu) => within(menu).getAllByRole('menuitem').map((b) => b.textContent.replace(/beta$/i, '').trim());

describe('Navigation — selected state is announced, not just colored', () => {
  it('marks the active main tab with aria-current="page" and leaves others unmarked', () => {
    renderNav({ pageType: 'browse' });
    expect(screen.getByRole('button', { name: 'Browse Corpus' })).toHaveAttribute('aria-current', 'page');
    expect(screen.getByRole('button', { name: 'Intertextual Search' })).not.toHaveAttribute('aria-current');
  });

  it('marks the active language tab with aria-current and leaves others unmarked', () => {
    renderNav({ pageType: 'search', activeTab: 'grc' });
    expect(screen.getByRole('button', { name: 'Greek' })).toHaveAttribute('aria-current');
    expect(screen.getByRole('button', { name: 'Latin' })).not.toHaveAttribute('aria-current');
  });

  it('gives the active main tab a heavier font weight, not just a color change', () => {
    renderNav({ pageType: 'browse' });
    const active = screen.getByRole('button', { name: 'Browse Corpus' });
    const inactive = screen.getByRole('button', { name: 'Intertextual Search' });
    expect(active.className).toMatch(/font-semibold/);
    expect(inactive.className).not.toMatch(/font-semibold/);
  });

  it('marks the admin panel button as the current page when locked to admin', () => {
    render(
      <Navigation
        pageType="admin"
        setPageType={noop}
        activeTab="la"
        setActiveTab={noop}
        lockedToAdmin
        onAdminLogout={noop}
      />
    );
    expect(screen.getByRole('button', { name: 'Admin Panel' })).toHaveAttribute('aria-current', 'page');
  });
});

/**
 * The People, Places & Things menu lists every page of the group in every
 * view (the project lead, 2026-10-19). The collection switches decide what a
 * search covers and which Reader tabs show, not which pages the menu offers.
 * The one gate left is the server switch for the documents collection
 * (documents_enabled from /api/languages), which hides Inscriptions & Papyri
 * when the documents index is not installed.
 */
describe('Navigation — the People, Places & Things menu lists every page', () => {
  const originalFetch = global.fetch;
  beforeEach(() => {
    window.localStorage.clear();
    try { window.sessionStorage.clear(); } catch { /* ignore */ }
    window.history.replaceState({}, '', '/');
  });
  afterEach(() => {
    window.localStorage.clear();
    window.history.replaceState({}, '', '/');
    global.fetch = originalFetch;
  });

  function mockLanguages(documentsEnabled) {
    global.fetch = vi.fn(async (url) => {
      if (String(url) === '/api/languages') {
        return mockResponse({
          json: async () => ({
            languages: [{ code: 'la', label: 'Latin' }],
            documents_enabled: documentsEnabled,
          }),
        });
      }
      return mockResponse({ json: async () => ({}) });
    });
  }

  it('lists all five pages in the Literary profile once the server switch is read', async () => {
    mockLanguages(true);
    renderNav();
    await waitFor(() => expect(global.fetch).toHaveBeenCalledWith('/api/languages'));
    const menu = await openThings();
    await waitFor(() => expect(thingsNames(menu)).toEqual(['People & Places', 'Inscriptions & Papyri', 'Events', 'Coins', 'Objects']));
  });

  it.each(['historical', 'archaeological', 'everything'])('lists all five pages in the %s profile', async (profile) => {
    const { setProfile } = await import('../../../collections/collectionsStore');
    setProfile(profile);
    mockLanguages(true);
    renderNav();
    await waitFor(() => expect(global.fetch).toHaveBeenCalledWith('/api/languages'));
    const menu = await openThings();
    await waitFor(() => expect(thingsNames(menu)).toHaveLength(5));
  });

  it('leaves out Inscriptions & Papyri only while the server switch is off', async () => {
    mockLanguages(false);
    renderNav();
    await waitFor(() => expect(global.fetch).toHaveBeenCalledWith('/api/languages'));
    const menu = await openThings();
    expect(thingsNames(menu)).toEqual(['People & Places', 'Events', 'Coins', 'Objects']);
  });

  it('shows no note about collections', async () => {
    mockLanguages(true);
    renderNav();
    const menu = await openThings();
    expect(within(menu).queryByText(/appear here when their collections are on/)).toBeNull();
  });

  it('clicking a member calls setPageType with its code', async () => {
    mockLanguages(true);
    const setPageType = vi.fn();
    renderNav({ setPageType });
    await waitFor(async () => {
      const menu = await openThings();
      fireEvent.click(within(menu).getByRole('menuitem', { name: /Inscriptions & Papyri/ }));
    });
    expect(setPageType).toHaveBeenCalledWith('inscriptions-papyri');
  });
});

describe('Navigation — the People, Places & Things menu', () => {
  beforeEach(() => { window.localStorage.clear(); window.sessionStorage.clear(); });
  afterEach(() => { window.localStorage.clear(); });

  it('is one button with a menu that lists the four pages the server switch does not gate, before /api/languages answers', async () => {
    renderNav();
    const button = screen.getByRole('button', THINGS);
    expect(button).toHaveAttribute('aria-haspopup', 'menu');
    expect(button).toHaveAttribute('aria-expanded', 'false');
    expect(screen.queryByRole('button', { name: /^People & Places/ })).toBeNull();
    const menu = await openThings();
    expect(button).toHaveAttribute('aria-expanded', 'true');
    expect(thingsNames(menu)).toEqual(['People & Places', 'Events', 'Coins', 'Objects']);
    expect(menu.style.position).toBe('fixed');
  });

  it('lists the members in the order of the History view', async () => {
    const { setProfile } = await import('../../../collections/collectionsStore');
    setProfile('historical');
    const { setView } = await import('../../../collections/collectionsStore');
    if (setView) setView('history');
    global.fetch = vi.fn(async () => mockResponse({
      json: async () => ({ languages: [{ code: 'la', label: 'Latin' }], documents_enabled: true }),
    }));
    renderNav();
    await waitFor(async () => {
      const menu = await openThings();
      expect(thingsNames(menu)).toEqual(['Events', 'Inscriptions & Papyri', 'Coins', 'Objects', 'People & Places']);
      fireEvent.click(screen.getByRole('button', THINGS));
    });
  });

  it('clicking a member closes the menu and calls setPageType with its code', async () => {
    const setPageType = vi.fn();
    renderNav({ setPageType });
    const menu = await openThings();
    fireEvent.click(within(menu).getByRole('menuitem', { name: /People & Places/ }));
    expect(setPageType).toHaveBeenCalledWith('mentions');
    expect(screen.queryByTestId('things-menu')).toBeNull();
  });

  it('is highlighted when the open page is one of its members', async () => {
    const { setProfile } = await import('../../../collections/collectionsStore');
    setProfile('everything');
    renderNav({ pageType: 'events' });
    expect(screen.getByRole('button', THINGS).className).toMatch(/text-red-700/);
    cleanup();
    renderNav({ pageType: 'browse' });
    expect(screen.getByRole('button', THINGS).className).not.toMatch(/text-red-700/);
  });

  it('lists its members by their own labels in More when the group falls past the row', async () => {
    const widths = { 'data-tab': 100 };
    const spy = vi.spyOn(HTMLElement.prototype, 'offsetWidth', 'get').mockImplementation(function () {
      return this.hasAttribute('data-tab') || this.hasAttribute('data-more-probe') ? widths['data-tab'] : 0;
    });
    const clientSpy = vi.spyOn(HTMLElement.prototype, 'clientWidth', 'get').mockImplementation(function () {
      return this.className && String(this.className).includes('scroll-hint') ? 350 : 0;
    });
    renderNav();
    await waitFor(() => expect(screen.queryByRole('button', THINGS)).toBeNull());
    fireEvent.click(screen.getByRole('button', { name: /More/ }));
    const more = screen.getByTestId('more-menu');
    const labels = within(more).getAllByRole('menuitem').map((b) => b.textContent.trim());
    expect(labels).toContain('People & Places');
    expect(labels).not.toContain('People, Places & Things');
    spy.mockRestore();
    clientSpy.mockRestore();
  });
});
