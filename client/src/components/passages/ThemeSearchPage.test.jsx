/**
 * Theme Search shows a real author and title, not the file id.
 *
 * The scene index names a work by its filename slug internally
 * ("quintus_smyrnaeus.fall_of_troy"), but the API sends author/title/
 * display_name from get_text_metadata -- the same source Browse Corpus and
 * the Reader's Similar Passages tab use -- so the page should read that
 * instead of the raw work id.
 */
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import ThemeSearchPage from './ThemeSearchPage';

const RESULT = {
  query: 'a hero descends to the underworld',
  confidence: { level: 'high' },
  results: [{
    id: 'quintus_smyrnaeus.fall_of_troy.w1',
    language: 'grc',
    work: 'quintus_smyrnaeus.fall_of_troy',
    author: 'Quintus Smyrnaeus',
    title: 'The Fall of Troy',
    display_name: 'Quintus Smyrnaeus, The Fall of Troy',
    ref_start: '6.357',
    ref_end: '6.360',
    score: 0.9,
    gist: 'A hero descends to the underworld.',
  }],
};

beforeEach(() => {
  global.fetch = vi.fn((url) => {
    const u = String(url);
    if (u.startsWith('/api/languages')) {
      return Promise.resolve({ json: () => Promise.resolve({ languages: [] }) });
    }
    if (u.startsWith('/api/passages/theme-search')) {
      return Promise.resolve({ json: () => Promise.resolve(RESULT) });
    }
    return Promise.resolve({ json: () => Promise.resolve({}) });
  });
});

async function search(text) {
  render(<ThemeSearchPage />);
  fireEvent.change(screen.getByPlaceholderText(/a warrior arms himself/), {
    target: { value: text },
  });
  fireEvent.click(screen.getByRole('button', { name: /search/i }));
  await waitFor(() => expect(global.fetch).toHaveBeenCalledWith(
    expect.stringContaining('/api/passages/theme-search')));
}

describe('results are labelled with a real author and title', () => {
  it('renders the display name the API sends', async () => {
    await search('a hero descends to the underworld');
    expect(await screen.findByText('Quintus Smyrnaeus, The Fall of Troy')).toBeTruthy();
    expect(screen.queryByText(/quintus_smyrnaeus\.fall_of_troy/)).toBeNull();
  });

  it('falls back to the raw work id only when the API sends no display name', async () => {
    global.fetch = vi.fn((url) => {
      const u = String(url);
      if (u.startsWith('/api/languages')) {
        return Promise.resolve({ json: () => Promise.resolve({ languages: [] }) });
      }
      if (u.startsWith('/api/passages/theme-search')) {
        return Promise.resolve({ json: () => Promise.resolve({
          query: 'x', confidence: { level: 'high' },
          results: [{ id: 'w1', language: 'la', work: 'ovid.metamorphoses',
                      ref_start: '4.55', score: 0.8 }],
        }) });
      }
      return Promise.resolve({ json: () => Promise.resolve({}) });
    });
    await search('x');
    expect(await screen.findByText('ovid.metamorphoses')).toBeTruthy();
  });
});
