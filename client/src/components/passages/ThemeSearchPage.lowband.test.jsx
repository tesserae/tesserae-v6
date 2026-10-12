/**
 * A low confidence band shows the list (2026-10-11). Only a degenerate band,
 * where nothing in the corpus resembles the query, holds it behind a link.
 */
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import ThemeSearchPage from './ThemeSearchPage';

function answer(confidence, note) {
  return {
    query: 'establishment of democracy',
    results: [
      { work: 'thucydides.peleponnesian_war.part.8', ref_start: 'thuc. pele. 8.63.3', ref_end: 'thuc. pele. 8.63.3',
        score: 0.835, strong: false, gist: 'The collapse of Athenian democracy at Samos.', language: 'grc',
        author: 'Thucydides', title: 'Peloponnesian War' },
    ],
    strong_matches: 0,
    confidence,
    note,
  };
}

let payload;
beforeEach(() => {
  global.fetch = vi.fn((url) => {
    const u = String(url);
    if (u.startsWith('/api/languages')) {
      return Promise.resolve({ json: () => Promise.resolve({ languages: [{ code: 'la' }, { code: 'grc' }] }) });
    }
    if (u.startsWith('/api/passages/theme-search')) {
      return Promise.resolve({ ok: true, json: () => Promise.resolve(payload) });
    }
    return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
  });
});

async function search() {
  render(<ThemeSearchPage />);
  const box = await screen.findByPlaceholderText(/warrior arms himself/i);
  fireEvent.change(box, { target: { value: 'establishment of democracy' } });
  fireEvent.click(screen.getByRole('button', { name: /^search$/i }));
}

describe('the low band and the list', () => {
  it('a low band shows the passages and a caution', async () => {
    payload = answer({ level: 'low', coherence: 0.91, head_lift: 0.06, degenerate: false },
      'Low confidence: the top passages do not stand far above the rest of the corpus.');
    await search();
    await waitFor(() => expect(screen.getByText(/Low confidence\./)).toBeTruthy());
    expect(screen.getByText(/collapse of Athenian democracy/)).toBeTruthy();
    expect(screen.queryByRole('button', { name: /nearest passages anyway/ })).toBeNull();
    expect(screen.queryByText('weak neighbor')).toBeNull();
  });

  it('a degenerate band holds the list behind a link', async () => {
    payload = answer({ level: 'low', coherence: 0.997, head_lift: 0.01, degenerate: true },
      'The corpus does not appear to contain passages of this kind.');
    await search();
    await waitFor(() => expect(screen.getByText(/Weak match\./)).toBeTruthy());
    expect(screen.queryByText(/collapse of Athenian democracy/)).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: /nearest passages anyway/ }));
    expect(await screen.findByText(/collapse of Athenian democracy/)).toBeTruthy();
  });
});
