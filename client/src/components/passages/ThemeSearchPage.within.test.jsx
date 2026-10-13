/**
 * "Search within": the picker's effect on the Theme Search request and on the
 * address, and that leaving it alone changes nothing.
 */
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import ThemeSearchPage, { scopeQuery } from './ThemeSearchPage';

const TEXTS = [
  { id: 'lucan.bellum_civile.tess', author: 'Lucan', title: 'Bellum Civile' },
  { id: 'vergil.aeneid.tess', author: 'Vergil', title: 'Aeneid' },
  { id: 'vergil.georgics.tess', author: 'Vergil', title: 'Georgics' },
  { id: 'cicero.orator.tess', author: 'Cicero', title: 'Orator' },
];
const COVERED = ['lucan.bellum_civile', 'vergil.aeneid', 'vergil.georgics'];

const RESULT = { query: 'a storm', confidence: { level: 'strong' }, results: [] };

function themeCalls() {
  return global.fetch.mock.calls.map((c) => String(c[0]))
    .filter((u) => u.startsWith('/api/passages/theme-search'));
}

beforeEach(() => {
  window.history.replaceState({}, '', '/theme-search');
  global.fetch = vi.fn((url) => {
    const u = String(url);
    const body = u.startsWith('/api/languages') ? { languages: [{ code: 'la' }] }
      : u.startsWith('/api/texts') ? TEXTS
      : u.startsWith('/api/passages/works') ? { works: COVERED }
      : u.startsWith('/api/passages/theme-search') ? RESULT
      : {};
    return Promise.resolve({ json: () => Promise.resolve(body) });
  });
});

async function pick(name, label) {
  fireEvent.click(await screen.findByRole('combobox', { name }));
  fireEvent.pointerDown(within(screen.getByRole('listbox', { name })).getByRole('option', { name: label }));
}

async function runSearch(text = 'a storm') {
  fireEvent.change(screen.getByPlaceholderText(/a warrior arms himself/), { target: { value: text } });
  fireEvent.click(screen.getByRole('button', { name: /^search/i }));
  await waitFor(() => expect(themeCalls().length).toBeGreaterThan(0));
}

describe('scopeQuery', () => {
  it('is empty with nothing chosen', () => {
    expect(scopeQuery({ author: '', work: '' })).toBe('');
    expect(scopeQuery(undefined)).toBe('');
  });
  it('names the work when one is chosen, else the author', () => {
    expect(scopeQuery({ author: 'vergil', work: 'vergil.aeneid' })).toBe('&works=vergil.aeneid');
    expect(scopeQuery({ author: 'vergil', work: '' })).toBe('&author=vergil');
  });
});

describe('Search within picker', () => {
  it('leaves the request unchanged by default', async () => {
    render(<ThemeSearchPage />);
    await runSearch();
    const u = themeCalls()[0];
    expect(u).not.toMatch(/author=|works=/);
    expect(window.location.search).not.toMatch(/author=|works=/);
  });

  it('sends author= for an author and records it in the address', async () => {
    render(<ThemeSearchPage />);
    fireEvent.click(screen.getByRole('button', { name: /narrow to one author or work/i }));
    await pick('Search within author', 'Lucan');
    await runSearch();
    expect(themeCalls()[0]).toContain('&author=lucan');
    expect(themeCalls()[0]).not.toContain('works=');
    await waitFor(() => expect(window.location.search).toContain('author=lucan'));
  });

  it('offers only authors with passage windows', async () => {
    render(<ThemeSearchPage />);
    fireEvent.click(screen.getByRole('button', { name: /narrow to one author or work/i }));
    fireEvent.click(await screen.findByRole('combobox', { name: 'Search within author' }));
    const labels = within(screen.getByRole('listbox', { name: 'Search within author' }))
      .getAllByRole('option').map((o) => o.textContent);
    expect(labels).toEqual(['Whole corpus', 'Lucan', 'Vergil']);
  });

  it('sends works= for a chosen work', async () => {
    render(<ThemeSearchPage />);
    fireEvent.click(screen.getByRole('button', { name: /narrow to one author or work/i }));
    await pick('Search within author', 'Vergil');
    await pick('Search within work', 'Georgics');
    await runSearch();
    expect(themeCalls()[0]).toContain('&works=vergil.georgics');
    expect(themeCalls()[0]).not.toContain('author=');
  });

  it('opens already filled in from a shared link and sends the restriction', async () => {
    window.history.replaceState({}, '', '/theme-search?query=a+storm&author=lucan');
    render(<ThemeSearchPage />);
    await waitFor(() => expect(themeCalls().length).toBeGreaterThan(0));
    expect(themeCalls()[0]).toContain('&author=lucan');
    expect(await screen.findByRole('combobox', { name: 'Search within author' })).toBeTruthy();
  });

  it('clearing returns to a corpus-wide request', async () => {
    window.history.replaceState({}, '', '/theme-search?query=a+storm&author=lucan');
    render(<ThemeSearchPage />);
    await waitFor(() => expect(themeCalls().length).toBe(1));
    fireEvent.click(await screen.findByRole('button', { name: /clear: search the whole corpus/i }));
    await waitFor(() => expect(themeCalls().length).toBe(2));
    expect(themeCalls()[1]).not.toMatch(/author=|works=/);
    await waitFor(() => expect(window.location.search).not.toMatch(/author=|works=/));
  });

  it('shows the restriction and the note in the results header', async () => {
    global.fetch = vi.fn((url) => {
      const u = String(url);
      const body = u.startsWith('/api/texts') ? TEXTS
        : u.startsWith('/api/passages/works') ? { works: COVERED }
        : u.startsWith('/api/passages/theme-search') ? {
          query: 'a storm', restricted: true, confidence: { level: 'restricted' },
          note: 'Confidence is not rated for a narrow to one author or work.',
          results: [{ id: 'w1', language: 'la', work: 'lucan.bellum_civile', author: 'Lucan',
                      title: 'Bellum Civile', display_name: 'Lucan, Bellum Civile',
                      ref_start: '5.560', score: 0.8, gist: 'A storm.' }],
        } : { languages: [] };
      return Promise.resolve({ json: () => Promise.resolve(body) });
    });
    window.history.replaceState({}, '', '/theme-search?query=a+storm&author=lucan');
    render(<ThemeSearchPage />);
    expect(await screen.findByText(/Confidence is not rated/)).toBeTruthy();
    expect(await screen.findByText('In Lucan.')).toBeTruthy();
  });
});
