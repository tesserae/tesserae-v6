import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import Navigation from '../Navigation';

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

describe('Navigation — selected state is announced, not just colored', () => {
  it('marks the active main tab with aria-current="page" and leaves others unmarked', () => {
    renderNav({ pageType: 'browse' });
    expect(screen.getByRole('button', { name: 'Browse Corpus' })).toHaveAttribute('aria-current', 'page');
    expect(screen.getByRole('button', { name: 'Search' })).not.toHaveAttribute('aria-current');
  });

  it('marks the active language tab with aria-current and leaves others unmarked', () => {
    renderNav({ pageType: 'search', activeTab: 'grc' });
    expect(screen.getByRole('button', { name: 'Greek' })).toHaveAttribute('aria-current');
    expect(screen.getByRole('button', { name: 'Latin' })).not.toHaveAttribute('aria-current');
  });

  it('gives the active main tab a heavier font weight, not just a color change', () => {
    renderNav({ pageType: 'browse' });
    const active = screen.getByRole('button', { name: 'Browse Corpus' });
    const inactive = screen.getByRole('button', { name: 'Search' });
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
        return {
          json: async () => ({
            languages: [{ code: 'la', label: 'Latin' }],
            documents_enabled: documentsEnabled,
          }),
        };
      }
      return { json: async () => ({}) };
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

  it('appears, beside Theme Search, once both the trial flag and the server switch are on', async () => {
    window.sessionStorage.setItem('tesserae_documents_trial', '1');
    mockLanguages(true);
    renderNav();
    const tab = await screen.findByRole('button', { name: /Inscriptions & Papyri/ });
    expect(tab).toBeTruthy();
    const buttons = screen.getAllByRole('button').map((b) => b.textContent);
    const themeIdx = buttons.findIndex((t) => t.includes('Theme Search'));
    const docsIdx = buttons.findIndex((t) => t.includes('Inscriptions & Papyri'));
    expect(docsIdx).toBe(themeIdx + 1);
  });

  it('turns on from ?documents=1 in the URL, without a prior session flag', async () => {
    window.history.pushState({}, '', '/?documents=1');
    mockLanguages(true);
    renderNav();
    expect(await screen.findByRole('button', { name: /Inscriptions & Papyri/ })).toBeTruthy();
  });

  it('clicking it calls setPageType with its code', async () => {
    window.sessionStorage.setItem('tesserae_documents_trial', '1');
    mockLanguages(true);
    const setPageType = vi.fn();
    renderNav({ setPageType });
    const tab = await screen.findByRole('button', { name: /Inscriptions & Papyri/ });
    tab.click();
    expect(setPageType).toHaveBeenCalledWith('inscriptions-papyri');
  });
});

describe('Navigation — the "Events" item follows Collections', () => {
  beforeEach(() => { window.localStorage.clear(); window.sessionStorage.clear(); });
  afterEach(() => { window.localStorage.clear(); });

  it('is absent in the Literary profile', () => {
    renderNav();
    expect(screen.queryByRole('button', { name: /Events/ })).toBeNull();
  });

  it.each(['historical', 'everything'])('appears in the %s profile', async (profile) => {
    const { setProfile } = await import('../../../collections/collectionsStore');
    setProfile(profile);
    renderNav();
    expect(await screen.findByRole('button', { name: /Events/ })).toBeTruthy();
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
    expect(await screen.findByRole('button', { name: /^Coins/ })).toBeTruthy();
    cleanup();
    setProfile('everything');
    renderNav();
    expect(await screen.findByRole('button', { name: /^Coins/ })).toBeTruthy();
    cleanup();
    setProfile('historical');
    setCollection('coins', true);
    renderNav();
    expect(await screen.findByRole('button', { name: /^Coins/ })).toBeTruthy();
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
    expect(await screen.findByRole('button', { name: /^Objects/ })).toBeTruthy();
  });

  it('appears when Objects is switched on by name, after Coins', async () => {
    const { setProfile, setCollection } = await import('../../../collections/collectionsStore');
    setProfile('historical');
    setCollection('objects', true);
    renderNav();
    expect(await screen.findByRole('button', { name: /^Objects/ })).toBeTruthy();
    setCollection('coins', true);
    cleanup();
    renderNav();
    const names = (await screen.findAllByRole('button')).map((b) => b.textContent.trim());
    const coins = names.findIndex((n) => /^Coins/.test(n));
    const objects = names.findIndex((n) => /^Objects/.test(n));
    expect(coins).toBeGreaterThan(-1);
    expect(objects).toBe(coins + 1);
  });
});
