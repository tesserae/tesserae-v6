/**
 * The Reader's Documents tab: the selected lines are sent to Line Search over
 * the inscriptions and papyri, and the documents that answer are listed as
 * compact cards with the shared words marked and a link to the document.
 */
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import ResultsPanel from './ResultsPanel';
import { resetScholarshipLanguagesCache } from '../../utils/scholarshipLanguages';
import { setCollection } from '../../collections/collectionsStore';

const UNITS = [{ ref: 'tac. ann. 1.1', text: 'Urbem Romam a principio reges habuere' }];
const SELECTION = { refStart: 'tac. ann. 1.1', refEnd: 'tac. ann. 1.1', startIdx: 0, endIdx: 0 };

const ANSWER = {
  results: [{
    collection: 'documents', doc_id: 'edr:E1', locus: 'edr:E1', language: 'la',
    text: 'urbem romam conditam esse',
    matched_words: ['urbem', 'romam'],
    credit: { principal_edition: 'CIL VI 1' },
    date_not_before: 14, date_not_after: 37,
    ancient_place: 'Roma', modern_place: null,
    text_type_label: 'dedication', object_type_label: null, material_label: null,
    matched_restored: false,
  }],
};

let posts;
function mockFetch(answer) {
  posts = [];
  global.fetch = vi.fn((url, init) => {
    if (url === '/api/line-search') {
      posts.push(JSON.parse(init.body));
      return Promise.resolve({ ok: true, json: () => Promise.resolve(answer) });
    }
    return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
  });
}

function mount() {
  render(<ResultsPanel selection={SELECTION} language="la" work="tacitus.annales.part.1.tess"
                       units={UNITS} initialTab="documents" />);
}

beforeEach(() => {
  resetScholarshipLanguagesCache();
  window.localStorage.clear();
  window.sessionStorage.clear();
  setCollection('inscriptions', true);
});
afterEach(() => { cleanup(); delete global.fetch; });

describe('the Documents tab', () => {
  it('posts the selection to Line Search over the documents collection', async () => {
    mockFetch(ANSWER);
    mount();
    await waitFor(() => expect(posts.length).toBe(1));
    expect(posts[0]).toMatchObject({
      query: 'Urbem Romam a principio reges habuere',
      language: 'la', collection: 'documents', search_type: 'lemma', max_results: 30,
    });
  });

  it('shows a card with the edition, date, place, marked words and a link', async () => {
    mockFetch(ANSWER);
    mount();
    expect(await screen.findByText('CIL VI 1')).toBeTruthy();
    expect(screen.getByText(/14 AD.37 AD/)).toBeTruthy();
    expect(screen.getByText(/Roma/)).toBeTruthy();
    const marks = [...document.querySelectorAll('mark')].map((m) => m.textContent);
    expect(marks).toEqual(['urbem', 'romam']);
    const link = screen.getByText('CIL VI 1').closest('a');
    expect(link.getAttribute('href')).toBe('/document?doc=edr%3AE1&lang=la&documents=1');
  });

  it('says so when no document shares two words', async () => {
    mockFetch({ results: [] });
    mount();
    expect(await screen.findByText('No inscription or papyrus shares two words with this selection.')).toBeTruthy();
  });
});
