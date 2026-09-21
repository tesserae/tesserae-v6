/**
 * The `/corpus?theme=1&language=la` deep link (Help, Theme Search) has to
 * survive App's pageType->path canonicalization, which rewrites the address
 * from `/corpus` to the real route, `/browse`. This renders the whole App
 * (there is no client router to render in isolation -- App reads
 * window.location itself, jsdom's real history object, and rewrites it with
 * window.history.pushState) and checks that Browse Corpus ends up with the
 * filter on and Latin selected, and that the rewritten address still carries
 * the query string rather than dropping it.
 */
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import App from './App';

const TEXTS = [
  { id: 'vergil.aeneid.part.1.tess', author: 'Vergil', title: 'Aeneid 1', line_count: 756 },
  { id: 'vergil.aeneid.part.2.tess', author: 'Vergil', title: 'Aeneid 2', line_count: 620 },
  { id: 'cicero.orator.tess', author: 'Cicero', title: 'Orator', line_count: 236 },
];

const LANGUAGES = {
  languages: [
    { code: 'la', label: 'Latin' },
    { code: 'grc', label: 'Greek' },
    { code: 'en', label: 'English' },
    { code: 'cop', label: 'Coptic' },
  ],
};

function jsonResponse(data, { ok = true, status = ok ? 200 : 401 } = {}) {
  const text = JSON.stringify(data);
  return { ok, status, json: () => Promise.resolve(data), text: () => Promise.resolve(text) };
}

// Covers every endpoint the App shell fetches at mount (Header, Navigation,
// UpdateBanner, AssistantDock, the admin-session check, useCorpus) plus the
// ones Browse Corpus fetches for itself. Order matters: more specific routes
// first, a permissive default last so an endpoint this test doesn't care
// about (e.g. a stray poll) can't throw and take the render down with it.
function routeFetch(url) {
  if (url.startsWith('/api/texts?language=')) return Promise.resolve(jsonResponse(TEXTS));
  if (url.startsWith('/api/authors')) return Promise.resolve(jsonResponse([]));
  if (url.startsWith('/api/passages/works')) {
    return Promise.resolve(jsonResponse({ language: 'la', works: ['vergil.aeneid'] }));
  }
  if (url.startsWith('/api/passages/translations')) return Promise.resolve(jsonResponse({ works: {} }));
  if (url.startsWith('/api/text-descriptions')) return Promise.resolve(jsonResponse({ descriptions: {} }));
  if (url.startsWith('/api/stats')) return Promise.resolve(jsonResponse({}));
  if (url.startsWith('/api/auth/user')) return Promise.resolve(jsonResponse({ user: null }));
  if (url.startsWith('/api/admin/me')) return Promise.resolve(jsonResponse({}, { ok: false }));
  if (url.startsWith('/api/languages')) return Promise.resolve(jsonResponse(LANGUAGES));
  if (url.startsWith('/api/version')) return Promise.resolve(jsonResponse({ bundle: null }));
  if (url.startsWith('/api/assistant/status')) return Promise.resolve(jsonResponse({ available: false }));
  return Promise.resolve(jsonResponse({}));
}

beforeEach(() => {
  global.fetch = vi.fn(routeFetch);
});

afterEach(() => {
  vi.unstubAllGlobals();
  window.history.replaceState({}, '', '/');
});

describe('the /corpus deep link into Browse Corpus', () => {
  it('opens with the Theme Search filter on and Latin selected, and the rewritten address keeps the query string', async () => {
    window.history.pushState({}, '', '/corpus?theme=1&language=la');

    render(<App />);

    await waitFor(() =>
      expect(screen.getByText('Works covered by Theme Search: 1 of 2 in Latin')).toBeTruthy());
    expect(screen.getByLabelText('Show only works covered by Theme Search').checked).toBe(true);

    // The pageType->path effect rewrites /corpus to the real route, /browse,
    // on mount. It has to carry window.location.search along rather than
    // drop it, or the deep link would work only for the first render and
    // vanish the moment the address bar updates (a reload, a copied link).
    await waitFor(() => {
      expect(window.location.pathname).toBe('/browse');
      expect(window.location.search).toBe('?theme=1&language=la');
    });
  });
});

// --------------------------------------------------------------------------
// The assistant dock was rendered twice in App.jsx, once before the footer
// and once after (2026-08 to 2026-09-21): two docks asked the assistant
// service for their own status on every page load, shared one sessionStorage
// key for the conversation, and drew the floating button on top of itself.
describe('the assistant is mounted once', () => {
  it('asks the assistant service for its status once per page load', async () => {
    render(<App />);
    await waitFor(() => expect(global.fetch).toHaveBeenCalled());
    const statusCalls = global.fetch.mock.calls
      .map(([url]) => String(url))
      .filter((url) => url.startsWith('/api/assistant/status'));
    expect(statusCalls.length).toBeLessThanOrEqual(1);
  });
});
