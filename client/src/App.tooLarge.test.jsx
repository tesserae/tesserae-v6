/**
 * A pair above the server's size limit (backend/compare_limit.py): the page
 * shows the choice panel instead of running, choosing a book compares that
 * book now, and the status page address opens the status page.
 */
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import App from './App';

const TEXTS = [
  { id: 'vergil.aeneid.tess', author: 'Vergil', author_key: 'vergil', title: 'Aeneid', language: 'la' },
  { id: 'vergil.aeneid.part.1.tess', author: 'Vergil', author_key: 'vergil', title: 'Aeneid 1', language: 'la' },
  { id: 'vergil.aeneid.part.2.tess', author: 'Vergil', author_key: 'vergil', title: 'Aeneid 2', language: 'la' },
  { id: 'ovid.metamorphoses.tess', author: 'Ovid', author_key: 'ovid', title: 'Metamorphoses', language: 'la' },
  { id: 'ovid.metamorphoses.part.1.tess', author: 'Ovid', author_key: 'ovid', title: 'Metamorphoses 1', language: 'la' },
];

const TOO_LARGE = {
  too_large: true, line_pairs: 118712416, limit: 12000000, email_notice: false,
  download_job_url: '/api/comparisons/jobs',
  books: [
    { side: 'source', work: 'vergil.aeneid.tess', id: 'vergil.aeneid.part.1.tess', label: 'Book 1', lines: 756 },
    { side: 'source', work: 'vergil.aeneid.tess', id: 'vergil.aeneid.part.2.tess', label: 'Book 2', lines: 804 },
    { side: 'target', work: 'ovid.metamorphoses.tess', id: 'ovid.metamorphoses.part.1.tess', label: 'Book 1', lines: 778 },
  ],
};

const json = (data, ok = true) => ({
  ok, status: ok ? 200 : 401, json: () => Promise.resolve(data), text: () => Promise.resolve(JSON.stringify(data)),
});

function routeFetch(url) {
  if (url.startsWith('/api/fusion-estimate')) {
    const q = new URLSearchParams(url.split('?')[1]);
    // Only the pair of whole works is over the limit.
    if (q.get('source') === 'vergil.aeneid.tess' && q.get('target') === 'ovid.metamorphoses.tess') {
      return Promise.resolve(json({ pairs: 118712416, in_parts: true, too_large: TOO_LARGE }));
    }
    return Promise.resolve(json({ pairs: 588168, in_parts: false, estimated_seconds: 60 }));
  }
  if (url.startsWith('/api/texts?language=')) return Promise.resolve(json(TEXTS));
  if (url.startsWith('/api/authors')) return Promise.resolve(json([]));
  if (url.startsWith('/api/languages')) {
    return Promise.resolve(json({ languages: [{ code: 'la', label: 'Latin' }] }));
  }
  if (url.startsWith('/api/admin/me')) return Promise.resolve(json({}, false));
  if (url.startsWith('/api/auth/user')) return Promise.resolve(json({ user: null }));
  if (url.startsWith('/api/comparisons/jobs/')) {
    return Promise.resolve(json({ id: 'abc123', status: 'queued', position: 1, source: 'a', target: 'b',
      language: 'la', retention_days: 14 }));
  }
  return Promise.resolve(json({}));
}

const estimateCalls = () => global.fetch.mock.calls
  .map(([url]) => String(url)).filter((u) => u.startsWith('/api/fusion-estimate'));

beforeEach(() => {
  global.fetch = vi.fn(routeFetch);
  window.localStorage.clear();
  window.sessionStorage.clear();
});
afterEach(() => {
  vi.unstubAllGlobals();
  window.history.replaceState({}, '', '/');
  window.localStorage.clear();
  window.sessionStorage.clear();
});

describe('a pair above the size limit', () => {
  it('shows the choice panel, and choosing a book runs that book against the other work', async () => {
    window.history.pushState({}, '', '/?source=vergil.aeneid.tess&target=ovid.metamorphoses.tess&lang=la');
    render(<App />);
    const region = await screen.findByRole('region', { name: 'Comparison too large' });
    expect(region).toHaveTextContent('119 million line pairs');
    expect(screen.getByRole('button', { name: 'Prepare the whole comparison as a download' })).toBeInTheDocument();

    fireEvent.change(screen.getByRole('combobox', { name: 'Source book' }),
      { target: { value: 'vergil.aeneid.part.2.tess' } });

    await waitFor(() => expect(estimateCalls().some((u) => u.includes('source=vergil.aeneid.part.2.tess')
      && u.includes('target=ovid.metamorphoses.tess'))).toBe(true));
    await waitFor(() => expect(screen.queryByRole('region', { name: 'Comparison too large' })).toBeNull());
  });

  it('the server answering the search itself with too_large shows the same panel, not an error', async () => {
    const base = routeFetch;
    global.fetch = vi.fn((url, init) => {
      if (String(url).startsWith('/api/fusion-estimate')) return Promise.resolve(json({ pairs: 5, in_parts: false }));
      if (String(url) === '/api/search-fusion') {
        return Promise.resolve({ ...json(TOO_LARGE), headers: { get: () => 'application/json' } });
      }
      return base(String(url), init);
    });
    window.history.pushState({}, '', '/?source=vergil.aeneid.tess&target=ovid.metamorphoses.tess&lang=la');
    render(<App />);
    await screen.findByRole('region', { name: 'Comparison too large' });
    expect(screen.queryByText(/Search failed/)).toBeNull();
  });
});

describe('a large pair under the size limit', () => {
  it('starts the search on the first click and shows the estimate line', async () => {
    const base = routeFetch;
    global.fetch = vi.fn((url, init) => {
      if (String(url).startsWith('/api/fusion-estimate')) {
        return Promise.resolve(json({ pairs: 23000000, in_parts: true, parts: 8, estimated_seconds: 180 }));
      }
      if (String(url) === '/api/search-fusion') return new Promise(() => {});   // stays running
      return base(String(url), init);
    });
    window.history.pushState({}, '', '/?source=vergil.aeneid.tess&target=ovid.metamorphoses.tess&lang=la');
    render(<App />);
    const region = await screen.findByRole('region', { name: 'Large comparison' });
    expect(region).toHaveTextContent('about 23 million line pairs, about 3 minutes. The results fill in part by part.');
    expect(screen.queryByRole('button', { name: 'Run the full comparison' })).toBeNull();
    expect(global.fetch.mock.calls.some(([u]) => String(u) === '/api/search-fusion')
      || global.fetch.mock.calls.some(([u]) => String(u).includes('search-fusion'))).toBe(true);
    expect(screen.getByRole('button', { name: 'Compare chosen books instead' })).toBeInTheDocument();
  });
});

describe('the status page address', () => {
  it('opens the status page for /comparisons/<id>', async () => {
    window.history.pushState({}, '', '/comparisons/abc123');
    render(<App />);
    expect(await screen.findByRole('heading', { name: 'Prepared comparison' })).toBeInTheDocument();
    await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent('next in line'));
    expect(window.location.pathname).toBe('/comparisons/abc123');
  });
});
