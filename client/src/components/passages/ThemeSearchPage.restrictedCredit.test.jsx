/**
 * Theme Comparison's pair card (CompareSideCard) must show a restricted
 * work's licence credit line beneath the passage, same as _naming
 * (backend/passage_index.py) attaches it to every 'a'/'b' side it builds.
 */
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import ThemeSearchPage from './ThemeSearchPage';

const AUTHORS_LA = {
  authors: [
    { author: 'Held Author', works: [{ work_key: 'history', work: 'History',
      author_key: 'held_author', id: 'heldwork.history.tess', title: 'History', is_part: false }] },
    { author: 'Ordinary Poet', works: [{ work_key: 'poem', work: 'Poem',
      author_key: 'ordinary_poet', id: 'ordinary.poem.tess', title: 'Poem', is_part: false }] },
  ],
};

const COMPARE_RESULT = {
  work_a: { work: 'heldwork.history', display_name: 'Held Author, History' },
  work_b: { work: 'ordinary.poem', display_name: 'Ordinary Poet, Poem' },
  scale: 'fine', n_a: 10, n_b: 10,
  pairs: [{
    score: 0.9, lift: 0.1, strong: true,
    a: { id: 'a1', work: 'heldwork.history', language: 'la', ref_start: '1.1', ref_end: '1.5',
         gist: 'A held passage.', display_name: 'Held Author, History',
         reader_url: '/read?work=heldwork.history.tess',
         restricted: true, credit: 'Source: Test Licence Holder (example.invalid)' },
    b: { id: 'b1', work: 'ordinary.poem', language: 'la', ref_start: '5.1', ref_end: '5.4',
         gist: 'An ordinary passage.', display_name: 'Ordinary Poet, Poem',
         reader_url: '/read?work=ordinary.poem.tess' },
  }],
  confidence: { top: 0.9, baseline: 0.8, head_lift: 0.07, level: 'strong' },
};

function fakeResponse(data) {
  return Promise.resolve({
    ok: true, json: () => Promise.resolve(data), text: () => Promise.resolve(JSON.stringify(data)),
  });
}

function mockFetchFor(extra) {
  return vi.fn((url) => {
    const u = String(url);
    if (u.startsWith('/api/languages')) return fakeResponse({ languages: [] });
    if (u.startsWith('/api/authors')) return fakeResponse(AUTHORS_LA);
    if (u.startsWith('/api/texts')) return fakeResponse([]);
    if (extra) {
      const hit = extra(u);
      if (hit) return hit;
    }
    return fakeResponse({});
  });
}

function openComparePane() {
  render(<ThemeSearchPage />);
  fireEvent.click(screen.getByRole('button', { name: 'Compare two works' }));
}

function pickWork(sideLabel, authorName, workId) {
  const authorInput = screen.getByLabelText(`${sideLabel} author`);
  fireEvent.focus(authorInput);
  fireEvent.pointerDown(screen.getByRole('button', { name: authorName }));
  const workSelect = screen.getByLabelText(`${sideLabel} Work`);
  fireEvent.change(workSelect, { target: { value: workId } });
}

beforeEach(() => {
  window.history.replaceState(null, '', '/theme-search');
});

describe('Theme Comparison pair card shows a restricted work\'s credit', () => {
  it('shows the restricted side\'s credit line beneath its pair card', async () => {
    global.fetch = mockFetchFor((u) => {
      if (u.startsWith('/api/passages/compare')) {
        return Promise.resolve({ json: () => Promise.resolve(COMPARE_RESULT) });
      }
      return null;
    });
    openComparePane();
    await screen.findByLabelText('First work author');

    pickWork('First work', 'Held Author', 'heldwork.history.tess');
    pickWork('Second work', 'Ordinary Poet', 'ordinary.poem.tess');
    fireEvent.click(screen.getByRole('button', { name: 'Compare', exact: true }));

    expect(await screen.findByText('A held passage.')).toBeTruthy();
    expect(screen.getByText('Source: Test Licence Holder (example.invalid)')).toBeTruthy();
    // The unrestricted side carries no credit line.
    const credits = screen.queryAllByText(/^Source: /);
    expect(credits).toHaveLength(1);
  });
});
