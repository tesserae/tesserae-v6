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
 * "Inscriptions & Papyri" (the documents trial's own main-menu item) is
 * gated on BOTH the client's ?documents=1 session flag (useDocumentsTrial)
 * and the server switch (documents_enabled from /api/languages) -- the
 * same two-part gate LineSearch.jsx's own documents control already uses.
 * Mirrors the mock-fetch pattern LineSearch.documentsCollection.test.jsx
 * uses for the identical gate.
 */
describe('Navigation — the "Inscriptions & Papyri" item (documents trial)', () => {
  const originalFetch = global.fetch;
  beforeEach(() => {
    try { window.sessionStorage.clear(); } catch { /* ignore */ }
    window.history.replaceState({}, '', '/');
  });
  afterEach(() => {
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

  it('is absent when the server switch is on but the client never opted in', async () => {
    mockLanguages(true);
    renderNav();
    await waitFor(() => expect(global.fetch).toHaveBeenCalledWith('/api/languages'));
    expect(screen.queryByRole('button', { name: /Inscriptions & Papyri/ })).toBeNull();
  });

  it('is absent when the client opted in but the server switch is off', async () => {
    window.sessionStorage.setItem('tesserae_documents_trial', '1');
    mockLanguages(false);
    renderNav();
    await waitFor(() => expect(global.fetch).toHaveBeenCalledWith('/api/languages'));
    expect(screen.queryByRole('button', { name: /Inscriptions & Papyri/ })).toBeNull();
  });

  it('appears in the People, Places & Things menu, after People & Places, once both the trial flag and the server switch are on', async () => {
    window.sessionStorage.setItem('tesserae_documents_trial', '1');
    mockLanguages(true);
    renderNav();
    const menu = await openThings();
    await waitFor(() => expect(thingsNames(menu)).toEqual(['People & Places', 'Inscriptions & Papyri', 'Events']));
  });

  it('turns on from ?documents=1 in the URL, without a prior session flag', async () => {
    window.history.pushState({}, '', '/?documents=1');
    mockLanguages(true);
    renderNav();
    await waitFor(async () => {
      const menu = await openThings();
      expect(within(menu).getByRole('menuitem', { name: /Inscriptions & Papyri/ })).toBeTruthy();
    });
  });

  it('clicking it calls setPageType with its code', async () => {
    window.sessionStorage.setItem('tesserae_documents_trial', '1');
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

describe('Navigation — the "Events" item follows Collections', () => {
  beforeEach(() => { window.localStorage.clear(); window.sessionStorage.clear(); });
  afterEach(() => { window.localStorage.clear(); });

  it('is absent in the Literary profile', () => {
    renderNav();
    expect(screen.queryByRole('button', { name: /^Events/ })).toBeNull();
  });

  it.each(['historical', 'everything'])('appears in the %s profile', async (profile) => {
    const { setProfile } = await import('../../../collections/collectionsStore');
    setProfile(profile);
    renderNav();
    expect(within(await openThings()).getByRole('menuitem', { name: /Events/ })).toBeTruthy();
  });
});

describe('Navigation — the "Coins" item follows Collections', () => {
  beforeEach(() => { window.localStorage.clear(); window.sessionStorage.clear(); });
  afterEach(() => { window.localStorage.clear(); });

  it.each(['literary', 'historical'])('is absent in the %s profile', async (profile) => {
    const { setProfile } = await import('../../../collections/collectionsStore');
    setProfile(profile);
    renderNav();
    expect(screen.queryByRole('button', { name: /^Coins/ })).toBeNull();
  });

  it('appears in the Archaeological and Everything profiles and when Coins is switched on by name', async () => {
    const { setProfile, setCollection } = await import('../../../collections/collectionsStore');
    setProfile('archaeological');
    renderNav();
    expect(within(await openThings()).getByRole('menuitem', { name: /^Coins/ })).toBeTruthy();
    cleanup();
    setProfile('everything');
    renderNav();
    expect(within(await openThings()).getByRole('menuitem', { name: /^Coins/ })).toBeTruthy();
    cleanup();
    setProfile('historical');
    setCollection('coins', true);
    renderNav();
    expect(within(await openThings()).getByRole('menuitem', { name: /^Coins/ })).toBeTruthy();
  });
});

describe('Navigation — the "Objects" item follows Collections', () => {
  beforeEach(() => { window.localStorage.clear(); window.sessionStorage.clear(); });
  afterEach(() => { window.localStorage.clear(); });

  it.each(['literary', 'historical'])('is absent in the %s profile', async (profile) => {
    const { setProfile } = await import('../../../collections/collectionsStore');
    setProfile(profile);
    renderNav();
    expect(screen.queryByRole('button', { name: /^Objects/ })).toBeNull();
  });

  it.each(['archaeological', 'everything'])('appears in the %s profile', async (profile) => {
    const { setProfile } = await import('../../../collections/collectionsStore');
    setProfile(profile);
    renderNav();
    expect(within(await openThings()).getByRole('menuitem', { name: /^Objects/ })).toBeTruthy();
  });

  it('appears when Objects is switched on by name, after Coins', async () => {
    const { setProfile, setCollection } = await import('../../../collections/collectionsStore');
    setProfile('historical');
    setCollection('objects', true);
    renderNav();
    expect(within(await openThings()).getByRole('menuitem', { name: /^Objects/ })).toBeTruthy();
    setCollection('coins', true);
    cleanup();
    renderNav();
    const names = thingsNames(await openThings());
    const coins = names.findIndex((n) => /^Coins/.test(n));
    const objects = names.findIndex((n) => /^Objects/.test(n));
    expect(coins).toBeGreaterThan(-1);
    expect(objects).toBe(coins + 1);
  });
});

describe('Navigation — the People, Places & Things menu', () => {
  beforeEach(() => { window.localStorage.clear(); window.sessionStorage.clear(); });
  afterEach(() => { window.localStorage.clear(); });

  it('is one button with a menu that lists People & Places alone in the default profile, with the muted line', async () => {
    renderNav();
    const button = screen.getByRole('button', THINGS);
    expect(button).toHaveAttribute('aria-haspopup', 'menu');
    expect(button).toHaveAttribute('aria-expanded', 'false');
    expect(screen.queryByRole('button', { name: /^People & Places/ })).toBeNull();
    const menu = await openThings();
    expect(button).toHaveAttribute('aria-expanded', 'true');
    expect(thingsNames(menu)).toEqual(['People & Places']);
    expect(menu.style.position).toBe('fixed');
    expect(within(menu).getByText('Inscriptions, coins and objects appear here when their collections are on.')).toBeTruthy();
  });

  it('lists the available members in the order of the view when the documents collections are on', async () => {
    const { setProfile } = await import('../../../collections/collectionsStore');
    setProfile('historical');
    global.fetch = vi.fn(async () => mockResponse({
      json: async () => ({ languages: [{ code: 'la', label: 'Latin' }], documents_enabled: true }),
    }));
    renderNav();
    await waitFor(async () => {
      const menu = await openThings();
      expect(thingsNames(menu)).toEqual(['People & Places', 'Inscriptions & Papyri', 'Events']);
      fireEvent.click(screen.getByRole('button', THINGS));
    });
  });

  it('shows no muted line when every member is available', async () => {
    const { setProfile } = await import('../../../collections/collectionsStore');
    setProfile('everything');
    global.fetch = vi.fn(async () => mockResponse({
      json: async () => ({ languages: [{ code: 'la', label: 'Latin' }], documents_enabled: true }),
    }));
    renderNav();
    await waitFor(async () => {
      const menu = await openThings();
      expect(thingsNames(menu)).toHaveLength(5);
      fireEvent.click(screen.getByRole('button', THINGS));
    });
    const menu = await openThings();
    expect(within(menu).queryByText(/appear here when/)).toBeNull();
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
