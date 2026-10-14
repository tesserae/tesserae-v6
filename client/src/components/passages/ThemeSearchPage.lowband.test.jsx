/**
 * A low confidence band shows the list (2026-10-11). Only a degenerate band,
 * where nothing in the corpus resembles the query, holds it behind a link.
 */
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import ThemeSearchPage from './ThemeSearchPage';
import { mockResponse } from '../../test/mockResponse';

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
      return Promise.resolve(mockResponse({ json: () => Promise.resolve({ languages: [{ code: 'la' }, { code: 'grc' }] }) }));
    }
    if (u.startsWith('/api/passages/theme-search')) {
      return Promise.resolve(mockResponse({ ok: true, json: () => Promise.resolve(payload) }));
    }
    return Promise.resolve(mockResponse({ ok: true, json: () => Promise.resolve({}) }));
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
      'No passage stands far above the rest of the corpus on this subject.');
    await search();
    await waitFor(() => expect(screen.getByText(/Closest passages\./)).toBeTruthy());
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

describe('words no passage description contains', () => {
  it('no known words: the label, the note, no list, no link, no export', async () => {
    payload = answer({ level: 'low', coherence: 0.892, head_lift: 0.037, degenerate: false,
                       vocab_checked: true, unknown_words: ['xqzv', 'plorf', 'wibble'], no_known_words: true },
      'None of these words appears in any passage description: xqzv, plorf, wibble. There is nothing for Theme Search to match. Check the spelling, or describe the scene in other words.');
    await search();
    await waitFor(() => expect(screen.getByText(/Nothing to search for\./)).toBeTruthy());
    expect(screen.getByText(/None of these words appears in any passage description/)).toBeTruthy();
    expect(screen.queryByText(/collapse of Athenian democracy/)).toBeNull();
    expect(screen.queryByRole('button', { name: /nearest passages anyway/ })).toBeNull();
    expect(screen.queryByText(/Show more results/)).toBeNull();
  });

  it('some unknown words: the list is shown with the sentence inside the banner', async () => {
    payload = answer({ level: 'moderate', coherence: 0.9, head_lift: 0.08, degenerate: false,
                       vocab_checked: true, unknown_words: ['potatoes'], no_known_words: false },
      'Moderate confidence: the corpus holds passages of this kind. The word potatoes appears in no passage description, so it did not help the search.');
    await search();
    await waitFor(() => expect(screen.getByText(/The word potatoes appears in no passage description/)).toBeTruthy());
    expect(screen.getByText(/collapse of Athenian democracy/)).toBeTruthy();
    expect(screen.queryByText(/Nothing to search for/)).toBeNull();
  });
});
