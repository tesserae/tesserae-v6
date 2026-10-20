/**
 * The Mentions page: the search list, the entity view with
 * mentions grouped by work, and the row of a shared name.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, cleanup } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import MentionsPage, { MentionRow, headingOf, sharedLabel, sortedCounts, MENTIONS_NOTE } from '../MentionsPage';

const SEARCH = {
  available: true, total: 1,
  results: [{ id: 'ln:E2', label: 'Ares/Mars', type: 'deity', mention_counts: { en: 2, grc: 4, la: 9 },
              mentions_total: 15, label_shared: true, label_shared_with: [] }],
};
const ENTITY = {
  id: 'ln:E2', label: 'Ares/Mars', type: 'deity', identifiers: {}, mention_counts: { la: 1 },
  label_shared: true, label_shared_with: [],
  works: [{ work: 'vergil.aeneid', title: 'Aeneid', author: 'Vergil', language: 'la', count: 1 }],
  corpus_names: [{ id: 'nm:marsi', label: 'Marsi', mention_counts: { la: 6 }, mentions_total: 6, adjective: true }],
  document_counts: { la: 3 },
};
const DOCUMENTS = {
  total: 1,
  results: [{ doc_id: 'edr:aEDR020542', language: 'la', locus: 'edr:aEDR020542', text: 'Publicum Coloniae Rusellanorum',
              matched_form: 'rusellanorum', match_kind: 'adjective_stem', adjective: true,
              credit: { principal_edition: 'EDR020542', source_name: 'Epigraphic Database Roma', source_url: 'https://example.org/edr',
                        licence_name: 'CC BY-SA 4.0' },
              date_not_before: 1, date_not_after: 100, ancient_place: 'Rusellae', text_type_label: 'tessera' }],
};
const MENTIONS = {
  total: 1,
  results: [{ window_id: 'vergil.aeneid:fine:1', work: 'vergil.aeneid', language: 'la', ref_start: 'verg. aen. 1.1',
              ref_end: 'verg. aen. 1.2', locus: '1.1', text: 'Troia fuit, et Mars ferox.', token: 'Mars',
              shared_with: ['Mars (Roman family)', 'Marsi'] }],
};

function stubFetch() {
  global.fetch = vi.fn((url) => {
    const u = String(url);
    const body = u.includes('/documents') ? DOCUMENTS : u.includes('/mentions') ? MENTIONS
      : u.includes('/search') ? (global.__search || SEARCH) : (global.__entity || ENTITY);
    return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(body) });
  });
}

beforeEach(() => {
  window.sessionStorage.clear();
  window.history.replaceState({}, '', '/mentions');
  stubFetch();
});
afterEach(() => { cleanup(); vi.restoreAllMocks(); });

describe('the page', () => {
  it('shows the title, the gray note and a search box', () => {
    render(<MentionsPage setPageType={() => {}} />);
    expect(screen.getByRole('heading', { name: 'People & Places' })).toBeInTheDocument();
    expect(screen.getByTestId('mentions-note').textContent).toBe(MENTIONS_NOTE);
    expect(screen.getByLabelText('A place, person or god')).toBeInTheDocument();
  });

  it('lists matches with counts in Latin, Greek, English order, then opens one', async () => {
    const user = userEvent.setup();
    render(<MentionsPage setPageType={() => {}} />);
    await user.type(screen.getByLabelText('A place, person or god'), 'mars{enter}');
    const item = await screen.findByTestId('entity-result');
    expect(item.textContent).toMatch(/God · Latin 9 lines · Greek 4 lines · English 2 lines/);
    await user.click(screen.getByRole('link', { name: 'Ares/Mars' }));
    expect(await screen.findByRole('heading', { name: 'Ares/Mars' })).toBeInTheDocument();
    await user.click(await screen.findByRole('button', { name: /Vergil, Aeneid/ }));
    const row = await screen.findByTestId('mention-row');
    expect(row.querySelector('mark').textContent).toBe('Mars');
    expect(row.querySelector('a').getAttribute('href')).toBe(
      '/read?work=vergil.aeneid.tess&lang=la&ref=verg.+aen.+1.1&refEnd=verg.+aen.+1.2&tab=similar');
    expect(screen.getByTestId('shared-label').textContent).toBe('name shared with Mars (Roman family) and Marsi');
  });
});

describe('stage 2b', () => {
  afterEach(() => { delete global.__search; });

  it('puts corpus names under a gray heading below the list entities', async () => {
    global.__search = { available: true, total: 2, results: [
      SEARCH.results[0],
      { id: 'nm:rusel', label: 'Rusellanum', type: 'name', source: 'corpus', mention_counts: { la: 6 }, mentions_total: 6 }] };
    const user = userEvent.setup();
    render(<MentionsPage setPageType={() => {}} />);
    await user.type(screen.getByLabelText('A place, person or god'), 'rusel{enter}');
    expect((await screen.findByTestId('corpus-heading')).textContent).toBe('Names in the corpus');
    const items = screen.getAllByTestId('entity-result');
    expect(items).toHaveLength(2);
    expect(items[1].textContent).toMatch(/Rusellanum/);
    expect(items[1].textContent).toMatch(/Name in the corpus · Latin 6 lines/);
  });

  it('offers near spellings when nothing matches', async () => {
    global.__search = { available: true, total: 0, results: [],
                        suggestions: [{ id: 'pl:413288', label: 'Rusellae', type: 'place', distance: 1 }] };
    const user = userEvent.setup();
    render(<MentionsPage setPageType={() => {}} />);
    await user.type(screen.getByLabelText('A place, person or god'), 'russelae{enter}');
    const box = await screen.findByTestId('suggestions');
    expect(box.textContent).toBe('Did you mean Rusellae?');
    expect(screen.getByRole('link', { name: 'Rusellae' })).toBeInTheDocument();
  });

  it('names the corpus forms, marks adjectives, and lists inscriptions with their credit', async () => {
    window.history.replaceState({}, '', '/mentions?e=ln:E2');
    const user = userEvent.setup();
    render(<MentionsPage setPageType={() => {}} />);
    const line = await screen.findByTestId('corpus-names');
    expect(line.textContent).toBe('Named in the corpus as Marsi (6) (adjective)');
    await user.click(await screen.findByRole('button', { name: /Inscriptions and papyri/ }));
    const row = await screen.findByTestId('document-row');
    expect(row.textContent).toMatch(/Text: Epigraphic Database Roma, CC BY-SA 4.0/);
    expect(row.querySelector('mark').textContent).toBe('Rusellanorum');
    expect(row.querySelector('a').getAttribute('href')).toBe('/document?doc=edr%3AaEDR020542&lang=la&documents=1');
  });

  it('counts lines and shows the line locus of a row', async () => {
    const user = userEvent.setup();
    window.history.replaceState({}, '', '/mentions?e=ln:E2');
    render(<MentionsPage setPageType={() => {}} />);
    expect((await screen.findByRole('button', { name: /Vergil, Aeneid/ })).textContent).toMatch(/1 line/);
    expect(MENTIONS_NOTE).toMatch(/matched by the name's forms alone, without the model's check\.$/);
    await user.click(screen.getByRole('button', { name: /Vergil, Aeneid/ }));
    expect((await screen.findByTestId('mention-row')).textContent).toMatch(/^1\.1/);
  });
});

describe('a row', () => {
  it('carries the gray label only when the name is shared', () => {
    const base = MENTIONS.results[0];
    const { rerender } = render(<ul><MentionRow r={{ ...base, shared_with: [] }} /></ul>);
    expect(screen.queryByTestId('shared-label')).toBeNull();
    rerender(<ul><MentionRow r={{ ...base, shared_with: ['Argos'] }} /></ul>);
    expect(screen.getByTestId('shared-label').textContent).toBe('name shared with Argos');
  });

  it('words the label and orders the counts', () => {
    expect(sharedLabel(['A', 'B', 'C'])).toBe('name shared with A, B and C');
    expect(sharedLabel([])).toBe('');
    expect(sortedCounts({ en: 1, la: 2, grc: 3, cop: 4 }).map(([k]) => k)).toEqual(['la', 'grc', 'en', 'cop']);
  });
});

describe('stage 3a', () => {
  const PROMOTED = { id: 'pn:sarpe', label: 'Sarpedon', display_label: 'Sarpedon', display_label_grc: 'Σαρπηδών',
                     type: 'person', source: 'promoted', description: 'Son of Zeus and Europa, king of Lycia.',
                     provenance: 'Named in the corpus, identified by a language model',
                     mention_counts: { la: 69, grc: 100 }, mentions_total: 169 };
  afterEach(() => { delete global.__search; delete global.__entity; });

  it('pairs the Latin heading with the Greek form', () => {
    expect(headingOf(PROMOTED)).toBe('Sarpedon · Σαρπηδών');
    expect(headingOf({ label: 'Troy' })).toBe('Troy');
    expect(headingOf({ label: 'Troy', display_label: 'Troy', display_label_grc: 'Troy' })).toBe('Troy');
  });

  it('shows type, description and the model note in the result row, and the heading in the entity view', async () => {
    global.__search = { available: true, total: 1, results: [PROMOTED] };
    global.__entity = { ...PROMOTED, identifiers: {}, label_shared: false, works: [], corpus_names: [], document_counts: {} };
    const user = userEvent.setup();
    render(<MentionsPage setPageType={() => {}} />);
    await user.type(screen.getByLabelText('A place, person or god'), 'sarpedon{enter}');
    const item = await screen.findByTestId('entity-result');
    expect(item.textContent).toMatch(/^Sarpedon · Σαρπηδών/);
    expect(item.textContent).toMatch(/Person · Latin 69 lines · Greek 100 lines/);
    expect(screen.getByTestId('result-description').textContent).toBe('Son of Zeus and Europa, king of Lycia.');
    expect(screen.getByTestId('result-provenance').textContent).toBe('Named in the corpus, identified by a language model');
    expect(screen.queryByTestId('corpus-heading')).toBeNull();          // a promoted entity sits with the list entries
    await user.click(screen.getByRole('link', { name: 'Sarpedon · Σαρπηδών' }));
    expect(await screen.findByRole('heading', { name: 'Sarpedon · Σαρπηδών' })).toBeInTheDocument();
    expect(screen.getByTestId('entity-provenance').textContent).toBe('Named in the corpus, identified by a language model');
  });
});

describe('stage 3b', () => {
  afterEach(() => { delete global.__search; });

  it('lists near spellings under their own heading, between the list entries and the corpus names', async () => {
    global.__search = {
      available: true, total: 2,
      results: [
        { id: 'nm:rhode', label: 'Rhodes', type: 'name', source: 'corpus', mention_counts: { la: 3 }, mentions_total: 3 },
      ],
      near_spellings: [
        { id: 'pl:590031', label: 'Rhodos (island)', type: 'place', source: 'list', mention_counts: { grc: 221, la: 160 },
          mentions_total: 381, distance: 1 }],
    };
    const user = userEvent.setup();
    render(<MentionsPage setPageType={() => {}} />);
    await user.type(screen.getByLabelText('A place, person or god'), 'rhodes{enter}');
    expect((await screen.findByTestId('near-heading')).textContent).toBe('Near spellings');
    const items = screen.getAllByTestId('entity-result');
    expect(items).toHaveLength(2);
    expect(items[0].textContent).toMatch(/Rhodos \(island\)/);          // the near spelling comes before the corpus name
    expect(items[1].textContent).toMatch(/Rhodes/);
    expect(screen.getByTestId('corpus-heading').textContent).toBe('Names in the corpus');
  });

  it('draws no heading when the search offers none', async () => {
    const user = userEvent.setup();
    render(<MentionsPage setPageType={() => {}} />);
    await user.type(screen.getByLabelText('A place, person or god'), 'mars{enter}');
    await screen.findAllByTestId('entity-result');
    expect(screen.queryByTestId('near-heading')).toBeNull();
  });
});

describe('a link from the Reader', () => {
  it('reads ?q= on load and runs the search at once', async () => {
    window.history.replaceState({}, '', '/mentions?q=Troy');
    render(<MentionsPage setPageType={() => {}} />);
    expect(screen.getByLabelText('A place, person or god').value).toBe('Troy');
    expect(await screen.findByTestId('entity-result')).toBeInTheDocument();
    expect(global.fetch.mock.calls.some(([u]) => String(u) === '/api/entities/search?q=Troy')).toBe(true);
  });
});

describe('named by its adjective', () => {
  const PLACE = {
    id: 'pl:413288', label: 'Rusellae', type: 'place', identifiers: {}, mention_counts: {}, label_shared: false,
    works: [], corpus_names: [], document_counts: {},
    adjective_names: [{ entity_id: 'nm:rusel', label: 'Rusellanum', count: 2,
                        forms: [{ form: 'Rusellanum', count: 1 }, { form: 'Rusellani', count: 1 }] }],
  };
  afterEach(() => { delete global.__entity; });

  it('shows the heading, the sentence and a group whose lines load from the mentions route', async () => {
    global.__entity = PLACE;
    window.history.replaceState({}, '', '/mentions?e=pl:413288');
    const user = userEvent.setup();
    render(<MentionsPage setPageType={() => {}} />);
    expect(await screen.findByRole('heading', { name: 'Named by its adjective' })).toBeInTheDocument();
    expect(screen.getByTestId('adjective-names').textContent).toMatch(
      /These lines refer to Rusellae only through an adjective formed from its name, such as Rusellanum\./);
    const group = screen.getByRole('button', { name: /Rusellanum/ });
    expect(group.textContent).toMatch(/2 lines/);
    await user.click(group);
    const row = await screen.findByTestId('mention-row');
    expect(row.querySelector('a').getAttribute('href')).toMatch(/^\/read\?work=vergil\.aeneid\.tess/);
    expect(row.textContent).toMatch(/vergil\.aeneid/);        // the work is named on each row, the lines come from many works
    const urls = global.fetch.mock.calls.map((c) => String(c[0]));
    expect(urls.some((u) => u.startsWith('/api/entities/nm%3Arusel/mentions?adjective_of=pl%3A413288'))).toBe(true);
  });

  it('shows nothing for a place with no adjectives or an entity without the field', async () => {
    window.history.replaceState({}, '', '/mentions?e=pl:413288');
    global.__entity = { ...PLACE, adjective_names: [] };
    const { unmount } = render(<MentionsPage setPageType={() => {}} />);
    await screen.findByRole('heading', { name: 'Rusellae' });
    expect(screen.queryByTestId('adjective-names')).toBeNull();
    expect(screen.queryByText('Named by its adjective')).toBeNull();
    unmount();
    const bare = { ...PLACE };
    delete bare.adjective_names;
    global.__entity = bare;
    render(<MentionsPage setPageType={() => {}} />);
    await screen.findByRole('heading', { name: 'Rusellae' });
    expect(screen.queryByTestId('adjective-names')).toBeNull();
  });
});
