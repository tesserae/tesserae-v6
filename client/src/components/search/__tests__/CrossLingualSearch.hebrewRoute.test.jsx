/**
 * The Hebrew-Greek route control added 2026-09-30 (backend: hebrew_greek_route
 * in backend/blueprints/search.py, see backend/lxx_pivot.py for why the pivot
 * exists). The control must appear only for the Hebrew -> Greek pair, must
 * send the chosen route to /api/search, and must label a result that carries
 * a `route` field.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';

vi.mock('react-chartjs-2', () => ({ Bar: () => null }));
vi.mock('chart.js', () => ({
  Chart: { register: () => {} },
  CategoryScale: {}, LinearScale: {}, BarElement: {},
  Title: {}, Tooltip: {}, Legend: {},
}));

import CrossLingualSearch from '../CrossLingualSearch';

const HE_HIERARCHY = {
  authors: [{
    author_key: 'hebrew_bible', author: 'Hebrew Bible',
    works: [{ work_key: 'ruth', work: 'Ruth', whole_text: 'hebrew_bible.ruth', parts: [] }],
  }],
};
const GRC_HIERARCHY = {
  authors: [{
    author_key: 'homer', author: 'Homer',
    works: [{
      work_key: 'iliad', work: 'Iliad', whole_text: null,
      parts: [{ id: 'homer.iliad.part.1.tess', display: 'Book 1' }],
    }],
  }],
};
const EMPTY_HIERARCHY = { authors: [] };

const SEARCH_RESULT = {
  results: [{
    source: { ref: '2.3', text: 'source line', tokens: [], highlight_indices: [] },
    target: { ref: '1.1', text: 'target line', tokens: [], highlight_indices: [] },
    overall_score: 1.2,
    matched_words: [],
    features: {},
    route: 'direct',
  }],
};

beforeEach(() => {
  global.fetch = vi.fn((url) => {
    const u = String(url);
    if (u.includes('language=he')) {
      return Promise.resolve({ json: () => Promise.resolve(HE_HIERARCHY) });
    }
    if (u.includes('language=grc')) {
      return Promise.resolve({ json: () => Promise.resolve(GRC_HIERARCHY) });
    }
    if (u.includes('/api/texts/hierarchy')) {
      return Promise.resolve({ json: () => Promise.resolve(EMPTY_HIERARCHY) });
    }
    if (u.includes('/api/search')) {
      return Promise.resolve({ json: () => Promise.resolve(SEARCH_RESULT) });
    }
    return Promise.resolve({ json: () => Promise.resolve({}) });
  });
});

async function switchToHebrewGreek() {
  render(<CrossLingualSearch />);
  await waitFor(() => expect(global.fetch).toHaveBeenCalled());
  fireEvent.click(screen.getByRole('button', { name: 'Hebrew → Greek' }));
  await waitFor(() => expect(screen.getByTitle(/How to answer a Hebrew to Greek search/i)).toBeTruthy());
}

describe('Hebrew-Greek route control', () => {
  it('is hidden for a non-Hebrew-Greek pair', () => {
    render(<CrossLingualSearch />);
    expect(screen.queryByTitle(/How to answer a Hebrew to Greek search/i)).toBeNull();
  });

  it('appears for Hebrew -> Greek, defaults to the Septuagint route', async () => {
    await switchToHebrewGreek();
    const select = screen.getByTitle(/How to answer a Hebrew to Greek search/i);
    expect(select.value).toBe('septuagint');
  });

  it('sends the chosen route to /api/search and labels a routed result', async () => {
    await switchToHebrewGreek();
    const select = screen.getByTitle(/How to answer a Hebrew to Greek search/i);
    fireEvent.change(select, { target: { value: 'both' } });

    fireEvent.click(screen.getByRole('button', { name: /^search$/i }));

    await waitFor(() => {
      const call = global.fetch.mock.calls.find(([url]) => String(url).includes('/api/search'));
      expect(call).toBeTruthy();
      const body = JSON.parse(call[1].body);
      expect(body.hebrew_greek_route).toBe('both');
      expect(body.source_language).toBe('he');
      expect(body.target_language).toBe('grc');
    });

    expect(await screen.findByText('Direct')).toBeTruthy();
  });
});
