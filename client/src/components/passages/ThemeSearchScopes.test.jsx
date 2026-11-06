/**
 * Theme Search as one tab with three scopes (2026-10-25): the scope control,
 * the address, the old /ask-a-work address, and the title.
 */
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import App from '../../App';
import { scopeFromSearch, legacyRedirect } from '../../hooks/routePaths';

const json = (data) => ({ ok: true, status: 200, json: () => Promise.resolve(data), text: () => Promise.resolve(JSON.stringify(data)) });
const TEXTS = [
  { id: 'vergil.aeneid.tess', author: 'Vergil', title: 'Aeneid', work: 'Aeneid', is_part: false, language: 'la' },
];

function routeFetch(url) {
  const u = String(url);
  if (u.startsWith('/api/texts')) return Promise.resolve(json(TEXTS));
  if (u.startsWith('/api/authors')) return Promise.resolve(json([]));
  if (u.startsWith('/api/languages')) return Promise.resolve(json({ languages: [{ code: 'la', label: 'Latin' }] }));
  if (u.startsWith('/api/passages/works')) return Promise.resolve(json({ works: ['vergil.aeneid'] }));
  if (u.startsWith('/api/admin/me')) return Promise.resolve({ ok: false, status: 401, json: () => Promise.resolve({}), text: () => Promise.resolve('{}') });
  if (u.startsWith('/api/auth/user')) return Promise.resolve(json({ user: null }));
  return Promise.resolve(json({}));
}

beforeEach(() => {
  global.fetch = vi.fn(routeFetch);
  window.HTMLElement.prototype.scrollIntoView = vi.fn();
  window.localStorage.clear();
  window.sessionStorage.clear();
  window.history.replaceState({}, '', '/');
});
afterEach(() => {
  window.history.replaceState({}, '', '/');
  window.localStorage.clear();
  window.sessionStorage.clear();
});

const where = () => window.location.pathname + window.location.search;

describe('the scope helpers', () => {
  it('reads scope=, and infers it from older parameters when absent', () => {
    expect(scopeFromSearch('?scope=two')).toBe('two');
    expect(scopeFromSearch('?scope=corpus&query=x')).toBe('corpus');
    expect(scopeFromSearch('')).toBe('one');
    expect(scopeFromSearch('?query=storm')).toBe('corpus');
    expect(scopeFromSearch('?compare=a&with=b')).toBe('two');
    expect(scopeFromSearch('?scope=bogus')).toBe('one');
  });

  it('rewrites /ask-a-work and keeps its parameters', () => {
    expect(legacyRedirect('/ask-a-work?work=vergil.aeneid&lang=la&q=storms&books=1-3'))
      .toBe('/theme-search?work=vergil.aeneid&lang=la&q=storms&books=1-3&scope=one');
    expect(legacyRedirect('/ask-a-work')).toBe('/theme-search?scope=one');
    expect(legacyRedirect('/theme-search?query=x')).toBe('/theme-search?query=x');
  });
});

describe('Theme Search with three scopes', () => {
  it('opens on One text and offers the three scopes side by side', async () => {
    window.history.replaceState({}, '', '/theme-search');
    render(<App />);
    expect(await screen.findByTestId('scope-one')).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByTestId('scope-two')).toHaveAttribute('aria-pressed', 'false');
    expect(screen.getByTestId('scope-corpus')).toHaveAttribute('aria-pressed', 'false');
    expect(screen.getByTestId('scope-one').textContent).toBe('One text');
    expect(screen.getByTestId('scope-two').textContent).toBe('Two texts');
    expect(screen.getByTestId('scope-corpus').textContent).toBe('Whole corpus');
    await waitFor(() => expect(where()).toBe('/theme-search?scope=one'));
    await waitFor(() => expect(document.title).toBe('Theme Search: one text — Tesserae'));
  });

  it('switches the form, the address and the title with the scope', async () => {
    window.history.replaceState({}, '', '/theme-search?scope=one');
    render(<App />);
    await screen.findByTestId('scope-one');
    expect(screen.queryByText('Compare two works')).toBeNull();

    fireEvent.click(screen.getByTestId('scope-two'));
    expect(await screen.findByText('First work')).toBeTruthy();
    expect(where()).toBe('/theme-search?scope=two');
    expect(document.title).toBe('Theme Search: two texts — Tesserae');

    fireEvent.click(screen.getByTestId('scope-corpus'));
    expect(await screen.findByPlaceholderText(/a warrior arms himself/i)).toBeTruthy();
    expect(where()).toBe('/theme-search?scope=corpus');
    expect(document.title).toBe('Theme Search: whole corpus — Tesserae');
    expect(screen.queryByText('First work')).toBeNull();

    fireEvent.click(screen.getByTestId('scope-one'));
    await waitFor(() => expect(where()).toBe('/theme-search?scope=one'));
  });

  it('keeps the typed question when the scope changes between One text and Whole corpus', async () => {
    window.history.replaceState({}, '', '/theme-search?scope=corpus');
    render(<App />);
    const box = await screen.findByPlaceholderText(/a warrior arms himself/i);
    fireEvent.change(box, { target: { value: 'a storm at sea' } });
    fireEvent.click(screen.getByTestId('scope-one'));
    await waitFor(() => expect(screen.getByDisplayValue('a storm at sea')).toBeTruthy());
    fireEvent.click(screen.getByTestId('scope-corpus'));
    await waitFor(() => expect(screen.getByDisplayValue('a storm at sea')).toBeTruthy());
  });

  it('opens an old /ask-a-work address on the one-text scope with its parameters', async () => {
    window.history.replaceState({}, '', '/ask-a-work?work=vergil.aeneid&lang=la&q=storms');
    render(<App />);
    expect(await screen.findByTestId('scope-one')).toHaveAttribute('aria-pressed', 'true');
    expect(window.location.pathname).toBe('/theme-search');
    const p = new URLSearchParams(window.location.search);
    expect(p.get('scope')).toBe('one');
    expect(p.get('work')).toBe('vergil.aeneid');
    expect(p.get('lang')).toBe('la');
    expect(p.get('q')).toBe('storms');
  });

  it('opens older Theme Search addresses on the scope their parameters imply', async () => {
    window.history.replaceState({}, '', '/theme-search?compare=vergil.aeneid&with=lucan.bellum_civile');
    render(<App />);
    expect(await screen.findByTestId('scope-two')).toHaveAttribute('aria-pressed', 'true');
  });
});
