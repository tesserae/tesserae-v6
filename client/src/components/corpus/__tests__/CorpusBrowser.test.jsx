/**
 * Browse Corpus: the "Theme Search" coverage badge.
 *
 * Theme Search and Similar Passages run over the passage index, which
 * covers most but not all of the corpus. A work with no passage windows
 * never appears in either feature, and nothing on the site said so. This
 * mirrors the existing "EN" translation badge test-shape: stub
 * /api/passages/works and check the badge lands on a covered work and not
 * on an uncovered one.
 */
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import CorpusBrowser from '../CorpusBrowser';

const TEXTS = [
  { id: 'vergil.aeneid.part.1.tess', author: 'Vergil', title: 'Aeneid 1', line_count: 756 },
  { id: 'vergil.aeneid.part.2.tess', author: 'Vergil', title: 'Aeneid 2', line_count: 620 },
  { id: 'cicero.orator.tess', author: 'Cicero', title: 'Orator', line_count: 236 },
];

function mockFetch(url) {
  if (url.startsWith('/api/texts')) {
    return Promise.resolve({ json: () => Promise.resolve(TEXTS) });
  }
  if (url.startsWith('/api/passages/translations')) {
    return Promise.resolve({ json: () => Promise.resolve({ language: 'la', works: {} }) });
  }
  if (url.startsWith('/api/passages/works')) {
    return Promise.resolve({
      json: () => Promise.resolve({ language: 'la', works: ['vergil.aeneid'] }),
    });
  }
  if (url.startsWith('/api/text-descriptions')) {
    return Promise.resolve({ json: () => Promise.resolve({ descriptions: {} }) });
  }
  if (url.startsWith('/api/stats')) {
    return Promise.resolve({ json: () => Promise.resolve({}) });
  }
  return Promise.resolve({ json: () => Promise.resolve({}) });
}

beforeEach(() => {
  global.fetch = vi.fn(mockFetch);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('the Theme Search coverage badge', () => {
  it('marks a covered work and leaves an uncovered one alone', async () => {
    render(<CorpusBrowser />);

    await waitFor(() => expect(screen.getByText('Vergil')).toBeTruthy());
    fireEvent.click(screen.getByText('Vergil'));
    fireEvent.click(screen.getByText('Cicero'));

    await waitFor(() => expect(screen.getAllByText('Theme Search').length).toBe(2));
    // Two Vergil parts collapse to one covered work, so both rows get the
    // badge; Cicero's single work does not.
    expect(screen.queryAllByTitle('Covered by Theme Search and Similar Passages').length).toBe(2);
  });

  it('shows a coverage count under the corpus heading', async () => {
    render(<CorpusBrowser />);

    await waitFor(() =>
      expect(screen.getByText(/1 of 2 works are covered by Theme Search/)).toBeTruthy());
  });

  it('can show only the covered works', async () => {
    render(<CorpusBrowser />);
    await waitFor(() => expect(screen.getByText('Cicero')).toBeTruthy());
    fireEvent.click(screen.getByLabelText('Show only works covered by Theme Search'));
    await waitFor(() => expect(screen.queryByText('Cicero')).toBeNull());
    expect(screen.getByText('Vergil')).toBeTruthy();
  });

  it('a failed works fetch costs only the badges, not the page', async () => {
    global.fetch = vi.fn((url) => {
      if (url.startsWith('/api/passages/works')) {
        return Promise.reject(new Error('network down'));
      }
      return mockFetch(url);
    });

    render(<CorpusBrowser />);

    await waitFor(() => expect(screen.getByText('Vergil')).toBeTruthy());
    fireEvent.click(screen.getByText('Vergil'));
    await waitFor(() => expect(screen.getByText('Aeneid 1')).toBeTruthy());
    expect(screen.queryByText('Theme Search')).toBeNull();
  });
});
