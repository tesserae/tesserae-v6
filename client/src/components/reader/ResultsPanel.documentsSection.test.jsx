/**
 * The "Inscriptions and papyri" section under the Reader's Verbal parallels:
 * the same request as the literary list (query, refs, rare_focus) over the
 * documents collection, listed as compact cards under the same rules.
 */
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import { cleanup, render, screen, waitFor, fireEvent } from '@testing-library/react';
import ResultsPanel from './ResultsPanel';
import { resetScholarshipLanguagesCache } from '../../utils/scholarshipLanguages';
import { setCollection } from '../../collections/collectionsStore';

const UNITS = [{ ref: 'tac. ann. 1.1', text: 'Urbem Romam a principio reges habuere' }];
const SELECTION = { refStart: 'tac. ann. 1.1', refEnd: 'tac. ann. 1.1', startIdx: 0, endIdx: 0 };

const ROW = {
  collection: 'documents', doc_id: 'edr:E1', locus: 'edr:E1', language: 'la',
  text: 'urbem romam conditam esse',
  matched_words: ['urbem', 'romam'],
  credit: { principal_edition: 'CIL VI 1' },
  date_not_before: 14, date_not_after: 37,
  ancient_place: 'Roma', modern_place: null,
  text_type_label: 'dedication', object_type_label: null, material_label: null,
  matched_restored: false,
};

let posts;
function mockFetch(answer) {
  posts = [];
  global.fetch = vi.fn((url, init) => {
    if (url === '/api/line-search') {
      const body = JSON.parse(init.body);
      posts.push(body);
      const d = body.collection === 'documents' ? answer : { results: [] };
      return Promise.resolve({ ok: true, json: () => Promise.resolve(d) });
    }
    return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
  });
}
const docPosts = () => posts.filter((p) => p.collection === 'documents');

function mount() {
  render(<ResultsPanel selection={SELECTION} language="la" work="tacitus.annales.part.1.tess"
                       units={UNITS} initialTab="verbal" />);
}

beforeEach(() => {
  resetScholarshipLanguagesCache();
  window.localStorage.clear();
  window.sessionStorage.clear();
  setCollection('inscriptions', true);
});
afterEach(() => { cleanup(); delete global.fetch; });

describe('Inscriptions and papyri under Verbal parallels', () => {
  it('sends the literary request body plus the documents collection, without the exclusions', async () => {
    mockFetch({ results: [ROW], total: 1 });
    mount();
    await waitFor(() => expect(docPosts().length).toBe(1));
    expect(docPosts()[0]).toMatchObject({
      query: 'Urbem Romam a principio reges habuere', language: 'la', search_type: 'lemma',
      collection: 'documents', rare_focus: true, refs: ['tac. ann. 1.1'], max_results: 20, limit: 20,
    });
    for (const k of ['exclude_text_id', 'exclude_locus', 'exclude_author']) {
      expect(docPosts()[0][k]).toBeUndefined();
    }
    const literary = posts.find((p) => !p.collection);
    expect(literary).toMatchObject({ rare_focus: true, refs: ['tac. ann. 1.1'] });
  });

  it('shows the heading with its count, and a card with date, place, marked words and a link', async () => {
    mockFetch({ results: [ROW], total: 1 });
    mount();
    expect(await screen.findByText('CIL VI 1')).toBeTruthy();
    expect(screen.getByRole('heading', { name: /Inscriptions and papyri/ })).toBeTruthy();
    expect(screen.getByText(/14 AD.37 AD/)).toBeTruthy();
    const marks = [...document.querySelectorAll('mark')].map((m) => m.textContent);
    expect(marks).toEqual(['urbem', 'romam']);
    expect(screen.getByText('CIL VI 1').closest('a').getAttribute('href'))
      .toBe('/document?doc=edr%3AE1&lang=la&documents=1');
  });

  it('is absent when the documents collections are off', async () => {
    setCollection('inscriptions', false);
    setCollection('papyri', false);
    mockFetch({ results: [ROW], total: 1 });
    mount();
    await waitFor(() => expect(posts.length).toBeGreaterThan(0));
    expect(screen.queryByTestId('verbal-documents')).toBeNull();
    expect(docPosts().length).toBe(0);
  });

  it('says so when no document shares a distinctive word', async () => {
    mockFetch({ results: [], total: 0 });
    mount();
    expect(await screen.findByText('No inscription or papyrus shares a distinctive word with this selection.')).toBeTruthy();
  });

  it('shows a loading line while the request runs', async () => {
    posts = [];
    global.fetch = vi.fn((url, init) => {
      const body = init?.body ? JSON.parse(init.body) : {};
      if (body.collection === 'documents') return new Promise(() => {});
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ results: [] }) });
    });
    mount();
    expect(await screen.findByTestId('documents-loading')).toBeTruthy();
  });

  it('counts the hidden commonplace matches', async () => {
    mockFetch({ results: [ROW], total: 3, rare_focus: { hidden: 2, common_lemmas: ['quis', 'ipse'] } });
    mount();
    const note = await screen.findByTestId('documents-hidden');
    expect(note).toHaveTextContent('2 inscriptions or papyri sharing only common words (quis, ipse) not shown.');
  });

  it('names the words a passage-sized selection was matched on', async () => {
    mockFetch({ results: [ROW], total: 1, query_reduced: { from_lemmas: 20, to_lemmas: ['brutus', 'libertas'],
      note: 'x' } });
    mount();
    expect(await screen.findByTestId('documents-reduced'))
      .toHaveTextContent('matched on its most distinctive words (brutus, libertas)');
  });

  it('Show more raises the limit', async () => {
    mockFetch({ results: [ROW], total: 40 });
    mount();
    fireEvent.click(await screen.findByText('Show more inscriptions and papyri'));
    await waitFor(() => expect(docPosts().some((p) => p.limit === 35)).toBe(true));
  });

  it('is not a tab any more', async () => {
    mockFetch({ results: [], total: 0 });
    mount();
    expect(screen.queryByRole('button', { name: 'Documents' })).toBeNull();
  });
});
