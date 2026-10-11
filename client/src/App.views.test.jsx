/**
 * The Literature and History views at the level of the whole app: what a
 * plain visit to the site opens, the Phrase Search defaults, and the Start
 * here order.
 */
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor, fireEvent, act } from '@testing-library/react';
import App from './App';

const LATIN = [
  { id: 'vergil.aeneid.part.1.tess', author: 'Vergil', title: 'Aeneid 1', line_count: 756, language: 'la' },
  { id: 'lucan.bellum_civile.part.1.tess', author: 'Lucan', title: 'Civil War 1', line_count: 700, language: 'la' },
  { id: 'livy.ab_urbe_condita.part.1.books_1-10.tess', author: 'Livy', title: 'Books 1-10', line_count: 900, language: 'la' },
  { id: 'tacitus.annales.part.1.tess', author: 'Tacitus', title: 'Annals 1', line_count: 800, language: 'la' },
];
const GREEK = [
  { id: 'homer.iliad.part.1.tess', author: 'Homer', title: 'Iliad 1', line_count: 600, language: 'grc' },
  { id: 'apollonius_rhodius.argonautica.part.1.tess', author: 'Apollonius', title: 'Argonautica 1', line_count: 500, language: 'grc' },
  { id: 'herodotus.histories.part.1.tess', author: 'Herodotus', title: 'Histories 1', line_count: 900, language: 'grc' },
  { id: 'thucydides.peleponnesian_war.part.1.tess', author: 'Thucydides', title: 'War 1', line_count: 700, language: 'grc' },
];

const json = (data) => ({ ok: true, status: 200, json: () => Promise.resolve(data), text: () => Promise.resolve(JSON.stringify(data)) });

function routeFetch(url) {
  if (url.startsWith('/api/texts?language=grc')) return Promise.resolve(json(GREEK));
  if (url.startsWith('/api/texts?language=')) return Promise.resolve(json(LATIN));
  if (url.startsWith('/api/authors')) return Promise.resolve(json([]));
  if (url.startsWith('/api/languages')) {
    return Promise.resolve(json({ languages: [{ code: 'la', label: 'Latin' }, { code: 'grc', label: 'Greek' }] }));
  }
  if (url.startsWith('/api/admin/me')) return Promise.resolve({ ok: false, status: 401, json: () => Promise.resolve({}), text: () => Promise.resolve('{}') });
  if (url.startsWith('/api/auth/user')) return Promise.resolve(json({ user: null }));
  return Promise.resolve(json({}));
}

beforeEach(() => {
  global.fetch = vi.fn(routeFetch);
  window.localStorage.clear();
  window.sessionStorage.clear();
  window.history.replaceState({}, '', '/');
});
afterEach(() => {
  vi.unstubAllGlobals();
  window.history.replaceState({}, '', '/');
  window.localStorage.clear();
  window.sessionStorage.clear();
});

describe('what a plain visit opens', () => {
  it('opens the Search page in Literature view', async () => {
    render(<App />);
    await waitFor(() => expect(global.fetch).toHaveBeenCalled());
    expect(window.location.pathname).toBe('/');
    expect(screen.getByRole('button', { name: 'Literature' })).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByRole('button', { name: 'Latin' })).toHaveAttribute('aria-current');
  });

  it('opens the Reader on Tacitus, Annals 1, in History view', async () => {
    window.localStorage.setItem('tesserae_view', 'history');
    render(<App />);
    await waitFor(() => expect(window.location.pathname).toBe('/read'));
    const params = new URLSearchParams(window.location.search);
    expect(params.get('work')).toBe('tacitus.annales.part.1.tess');
    expect(params.get('lang')).toBe('la');
    expect(screen.getByRole('button', { name: 'History' })).toHaveAttribute('aria-pressed', 'true');
    await waitFor(() => expect(global.fetch.mock.calls.some(
      ([u]) => String(u).startsWith('/api/text/tacitus.annales.part.1.tess'),
    )).toBe(true));
  });

  it('opens History from ?view=history', async () => {
    window.history.replaceState({}, '', '/?view=history');
    render(<App />);
    await waitFor(() => expect(window.location.pathname).toBe('/read'));
  });

  it('leaves an address with a search of its own alone, even in History view', async () => {
    window.localStorage.setItem('tesserae_view', 'history');
    window.history.replaceState({}, '', '/?lang=la&tab=parallel');
    render(<App />);
    await waitFor(() => expect(global.fetch).toHaveBeenCalled());
    expect(window.location.pathname).toBe('/');
  });

  it('switching the view from the switch goes to the new view\'s home', async () => {
    render(<App />);
    await waitFor(() => expect(global.fetch).toHaveBeenCalled());
    fireEvent.click(screen.getByRole('button', { name: 'History' }));
    await waitFor(() => expect(window.location.pathname).toBe('/read'));
    fireEvent.click(screen.getByRole('button', { name: 'Literature' }));
    await waitFor(() => expect(window.location.pathname).toBe('/'));
  });
});

describe('the Phrase Search defaults follow the view', () => {
  const sourceAfter = async (expected) => {
    await waitFor(() => expect(window.sessionStorage.getItem('tesserae_sourceText')).toBe(expected));
  };

  it('Latin in Literature view: Vergil against Lucan', async () => {
    render(<App />);
    await sourceAfter('vergil.aeneid.part.1.tess');
    expect(window.sessionStorage.getItem('tesserae_targetText')).toBe('lucan.bellum_civile.part.1.tess');
  });

  it('Latin in History view: Livy against Tacitus', async () => {
    window.localStorage.setItem('tesserae_view', 'history');
    window.history.replaceState({}, '', '/?lang=la');
    render(<App />);
    await sourceAfter('livy.ab_urbe_condita.part.1.books_1-10.tess');
    expect(window.sessionStorage.getItem('tesserae_targetText')).toBe('tacitus.annales.part.1.tess');
  });

  it('Greek in History view: Herodotus against Thucydides', async () => {
    window.localStorage.setItem('tesserae_view', 'history');
    window.history.replaceState({}, '', '/?lang=grc');
    render(<App />);
    await sourceAfter('herodotus.histories.part.1.tess');
    expect(window.sessionStorage.getItem('tesserae_targetText')).toBe('thucydides.peleponnesian_war.part.1.tess');
  });

  it('Greek in Literature view: Homer against Apollonius', async () => {
    window.history.replaceState({}, '', '/?lang=grc');
    render(<App />);
    await sourceAfter('homer.iliad.part.1.tess');
  });

  it('an unpicked pair follows a change of view, back on the Search page', async () => {
    window.history.replaceState({}, '', '/?lang=la');
    render(<App />);
    await sourceAfter('vergil.aeneid.part.1.tess');
    fireEvent.click(screen.getByRole('button', { name: 'History' }));
    await waitFor(() => expect(window.location.pathname).toBe('/read'));
    fireEvent.click(screen.getByRole('button', { name: 'Search' }));
    await sourceAfter('livy.ab_urbe_condita.part.1.books_1-10.tess');
  });
});

describe('the Start here order follows the view', () => {
  const labels = () => screen.getAllByRole('link').map((a) => a.textContent.split(':')[0])
    .filter((t) => /Search|Reader|Inscriptions|Rare|Collections/.test(t));

  it('Literature: Phrase Search first, Collections answer last', async () => {
    window.history.replaceState({}, '', '/?lang=la&view=literature');
    render(<App />);
    // A query in the address suppresses the panel, so open it as the header link does.
    act(() => { window.dispatchEvent(new Event('tesserae:open-start-here')); });
    await waitFor(() => expect(screen.getByText('What are you trying to do?')).toBeTruthy());
    const l = labels();
    expect(l[0]).toBe('Phrase Search');
    expect(l[l.length - 1]).toBe('Collections');
  });

  it('History: the Collections answer first, relabelled', async () => {
    window.history.replaceState({}, '', '/?lang=la&view=history');
    render(<App />);
    act(() => { window.dispatchEvent(new Event('tesserae:open-start-here')); });
    await waitFor(() => expect(screen.getByText('What are you trying to do?')).toBeTruthy());
    expect(labels()[0]).toBe('Inscriptions, papyri, events and coins');
  });
});
