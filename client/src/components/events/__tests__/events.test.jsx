/**
 * The Events page: list with search and filters, the focus view of one event
 * (tabs, Reader links with the way back), and the Collections gate.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor, within, cleanup, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import EventsPage from '../EventsPage';
import EventList from '../EventList';
import { __resetEventNamesForTests } from '../EventNameBox';
import { dateLabel, centuryLabel, yearLabel, shortPassageRef } from '../eventsFormat';
import { __resetCorpusTextMapCacheForTests } from '../../../utils/textNames';
import { setProfile, setCollection } from '../../../collections/collectionsStore';

const LIST = {
  available: true, total: 2, page: 1, per_page: 20,
  types: ['battle', 'siege'], centuries: [-5, -3],
  events: [
    { id: 'Q1', label: 'Battle of Marathon', type: 'battle', date_start: -490, date_end: -490,
      place: 'Marathon', n_passages: 8, n_documents: 2, n_scholarship: 27 },
    { id: 'Q2', label: 'Siege of Syracuse', type: 'siege', date_start: -213, date_end: -211,
      place: 'Syracuse', n_passages: 1, n_documents: 0, n_scholarship: 0 },
  ],
};

const DETAIL = {
  event: {
    id: 'Q1', label: 'Battle of Marathon', type: 'battle', date_start: -490, date_end: -490,
    place: 'Marathon', lat: 38.15, lon: 23.96, pleiades_id: '580030',
    participants: ['Miltiades', 'Datis'], description: 'Athenian victory over a Persian landing.',
    wikipedia_url: 'https://en.wikipedia.org/wiki/Battle_of_Marathon',
    pleiades_url: 'https://pleiades.stoa.org/places/580030',
  },
  passages: [
    { rank: 1, work: 'herodotus.histories', language: 'grc', ref_start: 'hdt. 6.111.1', ref_end: 'hdt. 6.113.2',
      llm_label: 'yes', names_matched: ['Marathon [place] = Μαραθῶνα'], snippet: 'ἐν τῷ Μαραθῶνι',
      reader_url: '/read?work=herodotus.histories.tess&lang=grc&ref=hdt.%206.111.1', score: 0.1 },
    { rank: 5, work: 'herodotus.histories', language: 'grc', ref_start: 'hdt. 7.1.1', ref_end: 'hdt. 7.1.3',
      llm_label: 'mention', names_matched: [], snippet: 'ἡ ἐν Μαραθῶνι μάχη',
      reader_url: '/read?work=herodotus.histories.tess&lang=grc&ref=hdt.%207.1.1', score: 0.05 },
    { rank: 2, work: 'nepos.vitae', language: 'la', ref_start: 'nep. milt. 5.1', ref_end: 'nep. milt. 5.4',
      llm_label: 'yes', names_matched: [], snippet: 'apud Marathona',
      reader_url: '/read?work=nepos.vitae.tess&lang=la&ref=nep.%20milt.%205.1', score: 0.09 },
  ],
  passage_counts: { yes: 2, mention: 1, no: 4 },
  documents: [
    { doc_id: 'edh:HD1', date_start: -500, date_end: -450, place: 'Rhamnous', distance_km: 12.4,
      text_snippet: 'ΜΑΡΑΘΩΝ', text: 'Augusto / sacrum / Perusia restituta.', edition: 'CIL 11, 01923', matched_forms: ['perusia'],
      view_url: '/document?doc=edh%3AHD1&lang=la&documents=1' },
  ],
  scholarship: [
    { kind: 'article', title: 'Marathon Revisited (Doe, 1990)', page_ref: 'Hdt. 6.111', url: 'https://example.org/a',
      passage_rank: 1, passage_ref: 'hdt. 6.111.1-6.113.2' },
    { kind: 'commentary', title: 'How and Wells: note', page_ref: 'hdt. 6.112.1', url: null },
  ],
  map: [
    { kind: 'event', label: 'Marathon', lat: 38.15, lon: 23.96, n_documents: 0 },
    { kind: 'findspot', label: 'Rhamnous', lat: 38.23, lon: 24.0, n_documents: 1 },
  ],
};

const NAMES = [
  { id: 'Q1', label: 'Battle of Marathon', place: 'Marathon', year_start: -490, year_end: -490, type: 'battle', n_passages: 8, n_documents: 2 },
  { id: 'Q3', label: 'Marathon Campaign', place: 'Attica', year_start: -491, year_end: -490, type: 'campaign', n_passages: 3, n_documents: 0 },
  { id: 'Q4', label: 'Siege of Syracuse', place: 'Syracuse', year_start: -213, year_end: -211, type: 'siege', n_passages: 1, n_documents: 0 },
  { id: 'Q5', label: 'Marathonomachia', place: 'Marathon', year_start: -490, year_end: -490, type: 'battle', n_passages: 0, n_documents: 0 },
  { id: 'Q6', label: 'Battle of Cannae', place: 'Apulia', year_start: -216, year_end: -216, type: 'battle', n_passages: 5, n_documents: 0 },
];

function mockApi(listOverride, detailOverride) {
  const calls = [];
  global.fetch = vi.fn(async (url) => {
    const u = String(url);
    calls.push(u);
    if (u === '/api/events/names') return { ok: true, status: 200, json: async () => NAMES };
    if (u.startsWith('/api/events/')) return { ok: true, status: 200, json: async () => detailOverride || DETAIL };
    if (u.startsWith('/api/events')) return { ok: true, status: 200, json: async () => listOverride || LIST };
    return { ok: true, status: 200, json: async () => ({}) };
  });
  return calls;
}

beforeEach(() => {
  __resetEventNamesForTests();
  window.localStorage.clear();
  window.sessionStorage.clear();
  window.history.replaceState({}, '', '/events');
  setProfile('historical');
});
afterEach(() => { __resetCorpusTextMapCacheForTests(); cleanup(); window.history.replaceState({}, '', '/'); });

describe('formatting', () => {
  it('writes years, ranges and centuries', () => {
    expect(yearLabel(-490)).toBe('490 BCE');
    expect(dateLabel(-213, -211)).toBe('213 to 211 BCE');
    expect(dateLabel(-48, -48)).toBe('48 BCE');
    expect(dateLabel(-5, 3)).toBe('5 BCE to 3 CE');
    expect(centuryLabel(-5)).toBe('5th century BCE');
    expect(centuryLabel(1)).toBe('1st century CE');
    expect(centuryLabel(-2)).toBe('2nd century BCE');
  });
});

describe('the list', () => {
  it('opens alphabetical, says how many empty events are hidden, and can include them', async () => {
    const calls = mockApi({ ...LIST, total_all: 5, sort: 'evidence', show: 'evidence',
      type_counts: { battle: 1, siege: 1 } });
    render(<EventsPage setPageType={() => {}} />);
    expect(await screen.findByText('Battle of Marathon')).toBeTruthy();
    expect(calls[0]).toContain('sort=name');
    expect(calls[0]).not.toContain('show=all');
    expect(screen.getByTestId('events-total').textContent)
      .toBe('2 events with passages or documents · 3 more have neither');
    expect(screen.getByRole('option', { name: 'battle (1)' })).toBeTruthy();
    await userEvent.click(screen.getByLabelText('Include events with no passages or documents'));
    await waitFor(() => expect(calls.some((u) => u.includes('show=all'))).toBe(true));
    await userEvent.selectOptions(screen.getByLabelText('Order'), 'date');
    await waitFor(() => expect(calls.some((u) => u.includes('sort=date'))).toBe(true));
  });

  it('lists the events with dates and counts, and opens one', async () => {
    mockApi();
    render(<EventsPage setPageType={() => {}} />);
    expect(await screen.findByText('Battle of Marathon')).toBeTruthy();
    expect(screen.getByTestId('events-total').textContent).toContain('2 events');
    expect(screen.getByText(/213 to 211 BCE/)).toBeTruthy();
    expect(screen.getByText(/27 scholarship items/)).toBeTruthy();
    await userEvent.click(screen.getByRole('link', { name: 'Battle of Marathon' }));
    expect(window.location.pathname).toBe('/events/Q1');
    expect(await screen.findByRole('heading', { name: 'Battle of Marathon' })).toBeTruthy();
  });

  it('sends the search, type and century to the API and returns to page 1', async () => {
    const calls = mockApi();
    render(<EventList openEvent={() => {}} />);
    await screen.findByText('Battle of Marathon');
    await userEvent.type(screen.getByLabelText(/Search by name/), 'mara');
    await userEvent.click(screen.getByRole('button', { name: 'Search' }));
    await waitFor(() => expect(calls.some((c) => c.includes('q=mara'))).toBe(true));
    await userEvent.selectOptions(screen.getByLabelText('Type'), 'siege');
    await waitFor(() => expect(calls.some((c) => c.includes('type=siege'))).toBe(true));
    await userEvent.selectOptions(screen.getByLabelText('Century'), '-5');
    await waitFor(() => expect(calls.some((c) => c.includes('century=-5'))).toBe(true));
    expect(screen.getByRole('option', { name: '5th century BCE' })).toBeTruthy();
  });

  it('pages when there are more events than a page', async () => {
    const calls = mockApi({ ...LIST, total: 45 });
    render(<EventList openEvent={() => {}} />);
    await screen.findByText('Page 1 of 3');
    await userEvent.click(screen.getByRole('button', { name: 'Next' }));
    await waitFor(() => expect(calls.some((c) => c.includes('page=2'))).toBe(true));
  });

  it('says so when no dossiers are installed or nothing matches', async () => {
    mockApi({ available: false, events: [], total: 0, types: [], centuries: [] });
    render(<EventList openEvent={() => {}} />);
    expect(await screen.findByText(/not installed on this server/)).toBeTruthy();
    cleanup();
    mockApi({ ...LIST, events: [], total: 0 });
    render(<EventList openEvent={() => {}} />);
    expect(await screen.findByText(/No event matches/)).toBeTruthy();
  });
});

describe('the name box suggestions', () => {
  const suggestions = () => within(screen.getByRole('listbox', { hidden: true })).queryAllByRole('option');
  async function typeInto(text) {
    const box = screen.getByLabelText(/Search by name/);
    await userEvent.click(box);
    await userEvent.type(box, text);
    return box;
  }

  it('suggests events as you type, label starts first, then word starts, then the rest', async () => {
    const calls = mockApi();
    render(<EventList openEvent={() => {}} />);
    await screen.findByText('Battle of Marathon');
    const box = await typeInto('marat');
    await waitFor(() => expect(suggestions()).toHaveLength(3));
    const options = suggestions();
    expect(options.map((o) => o.querySelector('.font-bold').textContent)).toEqual(
      ['Marathon Campaign', 'Marathonomachia', 'Battle of Marathon']);
    expect(box.getAttribute('aria-expanded')).toBe('true');
    expect(within(options[1]).getByText('no passages yet')).toBeTruthy();
    expect(within(options[2]).queryByText('no passages yet')).toBeNull();
    expect(options[2].textContent).toContain('490 BCE');
    expect(options[2].textContent).toContain('Marathon');
    expect(calls.filter((u) => u === '/api/events/names')).toHaveLength(1);
  });

  it('opens the whole list on a click, alphabetical, events with passages or documents only', async () => {
    mockApi();
    render(<EventList openEvent={() => {}} />);
    await screen.findByText('Battle of Marathon');
    await userEvent.click(screen.getByLabelText(/Search by name/));
    await waitFor(() => expect(suggestions()).toHaveLength(4));
    expect(suggestions().map((o) => o.querySelector('.font-bold').textContent)).toEqual(
      ['Battle of Cannae', 'Battle of Marathon', 'Marathon Campaign', 'Siege of Syracuse']);
  });

  it('the arrow button opens and closes the list', async () => {
    mockApi();
    render(<EventList openEvent={() => {}} />);
    await screen.findByText('Battle of Marathon');
    await userEvent.click(screen.getByRole('button', { name: 'Show the list of events' }));
    await waitFor(() => expect(suggestions()).toHaveLength(4));
    await userEvent.click(screen.getByRole('button', { name: 'Close the list of events' }));
    expect(suggestions()).toHaveLength(0);
  });

  it('matches places and folds accents from the first character', async () => {
    mockApi();
    render(<EventList openEvent={() => {}} />);
    await screen.findByText('Battle of Marathon');
    await typeInto('á');
    expect(await within(screen.getByRole('listbox')).findByRole('option', { name: /Battle of Cannae/ })).toBeTruthy();
    await userEvent.clear(screen.getByLabelText(/Search by name/));
    await userEvent.type(screen.getByLabelText(/Search by name/), 'apul');
    expect(await within(screen.getByRole('listbox')).findByRole('option', { name: /Battle of Cannae/ })).toBeTruthy();
  });

  it('moves with the arrow keys and opens the highlighted event on Enter', async () => {
    mockApi();
    const open = vi.fn();
    render(<EventList openEvent={open} />);
    await screen.findByText('Battle of Marathon');
    const box = await typeInto('marat');
    await waitFor(() => expect(suggestions().length).toBeGreaterThan(0));
    await userEvent.keyboard('{ArrowDown}{ArrowDown}');
    const second = suggestions()[1];
    expect(box.getAttribute('aria-activedescendant')).toBe(second.id);
    await userEvent.keyboard('{Enter}');
    expect(open).toHaveBeenCalledWith('Q5');
  });

  it('opens an event on a click and closes on Escape', async () => {
    mockApi();
    const open = vi.fn();
    render(<EventList openEvent={open} />);
    await screen.findByText('Battle of Marathon');
    const box = await typeInto('marat');
    await waitFor(() => expect(suggestions().length).toBeGreaterThan(0));
    await userEvent.keyboard('{Escape}');
    expect(suggestions()).toHaveLength(0);
    expect(box.getAttribute('aria-expanded')).toBe('false');
    await userEvent.type(box, 'h');
    await userEvent.click(await within(screen.getByRole('listbox')).findByRole('option', { name: /Marathon Campaign/ }));
    expect(open).toHaveBeenCalledWith('Q3');
  });

  it('says so when nothing matches and still submits the form', async () => {
    const calls = mockApi();
    const open = vi.fn();
    render(<EventList openEvent={open} />);
    await screen.findByText('Battle of Marathon');
    await typeInto('zzzq');
    expect(await screen.findByText(/No event by that name\. Press Search to look through places and descriptions\./)).toBeTruthy();
    await userEvent.keyboard('{Enter}');
    await waitFor(() => expect(calls.some((c) => c.includes('q=zzzq'))).toBe(true));
    expect(open).not.toHaveBeenCalled();
  });

  it('submits the form on Enter when nothing is highlighted', async () => {
    const calls = mockApi();
    const open = vi.fn();
    render(<EventList openEvent={open} />);
    await screen.findByText('Battle of Marathon');
    await typeInto('marat');
    await waitFor(() => expect(suggestions().length).toBeGreaterThan(0));
    await userEvent.keyboard('{Enter}');
    await waitFor(() => expect(calls.some((c) => c.includes('q=marat'))).toBe(true));
    expect(open).not.toHaveBeenCalled();
  });
});

describe('the Inscriptions & Papyri tab', () => {
  beforeEach(() => window.history.replaceState({}, '', '/events/Q1'));

  it('shows two groups in order with the record id and a caption', async () => {
    const mk = (doc_id, group, edition) => ({
      doc_id, group, edition, date_start: -415, date_end: -413, place: 'Gela', distance_km: 3,
      text_snippet: 'x', view_url: `/document?doc=${doc_id}` });
    mockApi(undefined, { ...DETAIL, documents: [
      mk('isicily:ISic020570', 'names', 'I.Sicily 1'),
      mk('isicily:ISic020571', 'dated', 'I.Sicily 20570'),
      mk('isicily:ISic020572', 'dated', 'I.Sicily 20570'),
    ] });
    render(<EventsPage setPageType={() => {}} />);
    await screen.findByRole('heading', { name: 'Battle of Marathon' });
    await userEvent.click(screen.getByRole('tab', { name: /Inscriptions & Papyri/ }));
    const heads = screen.getAllByRole('heading', { level: 4 }).map((h) => h.textContent);
    expect(heads).toEqual(['Name a participant or the place', "Dated within the event's years, nearest first"]);
    expect(screen.getByText('Record ISic020570')).toBeTruthy();
    expect(screen.getByText('Record ISic020572')).toBeTruthy();
    expect(screen.getByText(/dating span of no more than fifty years/)).toBeTruthy();
  });
});

describe('the Inscriptions & Papyri tab when nothing names the event', () => {
  beforeEach(() => window.history.replaceState({}, '', '/events/Q1'));

  it('says so and keeps the regional list behind a disclosure (2026-10-18)', async () => {
    const mk = (doc_id, edition) => ({
      doc_id, group: 'dated', edition, date_start: -425, date_end: -401, place: 'Gela', distance_km: 6,
      text_snippet: 'loom weight', view_url: `/document?doc=${doc_id}` });
    mockApi(undefined, { ...DETAIL, documents: [mk('isicily:ISic020576', 'IGASM2[2] 115'), mk('isicily:ISic020577', 'IGASM2[2] 116')] });
    render(<EventsPage setPageType={() => {}} />);
    await screen.findByRole('heading', { name: 'Battle of Marathon' });
    await userEvent.click(screen.getByRole('tab', { name: /Inscriptions & Papyri/ }));
    expect(screen.getByText(/No inscription or papyrus in the collection names a participant or the place/)).toBeTruthy();
    const details = screen.getByTestId('events-documents-regional');
    expect(details.open).toBe(false);
    expect(details.textContent).toMatch(/2 documents from the region dated within the event's years, none naming/);
    expect(screen.queryByRole('heading', { level: 4 })).toBeNull();
    expect(screen.getByText('Record ISic020576')).toBeTruthy();
  });
});

describe('the Events tab in the navigation', () => {
  beforeEach(() => window.history.replaceState({}, '', '/events/Q1'));

  it('returns from an open event to the list', async () => {
    mockApi();
    render(<EventsPage setPageType={() => {}} />);
    await screen.findByRole('heading', { name: 'Battle of Marathon' });
    window.history.pushState({}, '', '/events');
    act(() => { window.dispatchEvent(new Event('tesserae:events-home')); });
    expect(await screen.findByText('Siege of Syracuse')).toBeTruthy();
    expect(screen.queryByRole('heading', { name: 'Battle of Marathon' })).toBeNull();
    expect(window.location.pathname).toBe('/events');
  });
});

describe('the focus view', () => {
  beforeEach(() => window.history.replaceState({}, '', '/events/Q1'));

  it('shows the header with participants, description and outside links', async () => {
    mockApi();
    render(<EventsPage setPageType={() => {}} />);
    expect(await screen.findByRole('heading', { name: 'Battle of Marathon' })).toBeTruthy();
    expect(screen.getByText(/490 BCE · Marathon · battle/)).toBeTruthy();
    expect(screen.getByText(/Miltiades, Datis/)).toBeTruthy();
    expect(screen.getByText(/Athenian victory/)).toBeTruthy();
    expect(screen.getByRole('link', { name: 'Wikipedia' })).toHaveAttribute('href', DETAIL.event.wikipedia_url);
    expect(screen.getByRole('link', { name: 'Pleiades' })).toHaveAttribute('href', DETAIL.event.pleiades_url);
  });

  it('groups passages by work and links each to the Reader with the way back', async () => {
    mockApi();
    render(<EventsPage setPageType={() => {}} />);
    await screen.findByRole('heading', { name: 'Battle of Marathon' });
    expect(screen.getByRole('heading', { name: 'Herodotus, Histories' })).toBeTruthy();
    expect(screen.getByRole('heading', { name: 'Nepos, Vitae' })).toBeTruthy();
    const links = screen.getAllByRole('link', { name: 'Open in the Reader' });
    expect(links).toHaveLength(3);
    expect(links[0].getAttribute('href')).toBe(
      '/read?work=herodotus.histories.tess&lang=grc&ref=hdt.%206.111.1&event=Q1&eventLabel=Battle%20of%20Marathon');
    expect(screen.getByText(/4 more were judged unrelated/)).toBeTruthy();
    expect(screen.getByText('Mention')).toBeTruthy();
    expect(screen.getAllByText('Narrative')).toHaveLength(2);
    expect(screen.queryByText('Tells of it')).toBeNull();
    expect(screen.queryByText('Mentions it')).toBeNull();
    expect(screen.getByText(/2 Narrative, 1 Mention\./)).toBeTruthy();
  });

  it('prints the work by name and the locus short, from the corpus text map', async () => {
    const detail = {
      ...DETAIL,
      passages: [
        { rank: 1, work: 'thucydides.peloponnesian_war', language: 'grc',
          ref_start: 'thuc. pele. 7.49.3', ref_end: 'thuc. pele. 7.53.2', llm_label: 'yes',
          names_matched: [], snippet: 'x', reader_url: '/read?work=thucydides.peloponnesian_war.tess&lang=grc', score: 0.1 },
        { rank: 2, work: 'obscure_author.lost_work', language: 'la',
          ref_start: 'obs. lost 1.1', ref_end: 'obs. lost 1.1', llm_label: 'mention',
          names_matched: [], snippet: 'y', reader_url: '/read?work=obscure_author.lost_work.tess&lang=la', score: 0.1 },
      ],
      scholarship: [{ kind: 'article', title: 'T', page_ref: 'p', url: null,
                      passage_rank: 1, passage_ref: 'thuc. pele. 7.49.3-7.53.2', scope: 'passage' },
                    { kind: 'article', title: 'Elsewhere article', page_ref: 'p', url: null,
                      passage_rank: null, passage_ref: 'thuc. pele. 6.1-7.87', scope: 'span' }],
    };
    global.fetch = vi.fn(async (url) => {
      const u = String(url);
      if (u.startsWith('/api/texts?language=grc')) {
        return { ok: true, status: 200, json: async () => [
          { id: 'thucydides.peloponnesian_war.tess', author: 'Thucydides', title: 'Peloponnesian War' }] };
      }
      if (u.startsWith('/api/texts')) return { ok: true, status: 200, json: async () => [] };
      if (u.startsWith('/api/events/')) return { ok: true, status: 200, json: async () => detail };
      return { ok: true, status: 200, json: async () => LIST };
    });
    render(<EventsPage setPageType={() => {}} />);
    expect(await screen.findByRole('heading', { name: 'Thucydides, Peloponnesian War' })).toBeTruthy();
    expect(screen.getByText('7.49.3 to 7.53.2')).toBeTruthy();
    expect(screen.queryByText(/thuc\. pele\./)).toBeNull();
    expect(screen.getByRole('heading', { name: 'Obscure Author, Lost Work' })).toBeTruthy();
    await userEvent.click(screen.getByRole('tab', { name: /Scholarship/ }));
    expect(screen.getByRole('link', { name: 'on 7.49.3 to 7.53.2' })).toBeTruthy();
    expect(screen.getByRole('heading', { name: 'Articles citing a leading passage' })).toBeTruthy();
    expect(screen.getByRole('heading', { name: /Articles citing elsewhere within the span/ })).toBeTruthy();
    expect(screen.getByText('within 6.1 to 7.87')).toBeTruthy();
  });

  it('keeps the articles judged to cite the passage for another reason under one line and tags the partly ones', async () => {
    const detail = {
      ...DETAIL,
      scholarship: [
        { kind: 'article', title: 'Great Harbor article', page_ref: 'p', url: null, passage_rank: 1, passage_ref: 'hdt. 6.111.1', scope: 'passage', relevance: 'yes', relevance_reason: 'Discusses the battle itself.' },
        { kind: 'article', title: 'Background article', page_ref: 'p', url: null, passage_rank: 1, passage_ref: 'hdt. 6.111.1', scope: 'passage', relevance: 'partly', relevance_reason: 'Touches it.' },
        { kind: 'article', title: 'Grammar article', page_ref: 'p', url: null, passage_rank: 1, passage_ref: 'hdt. 6.111.1', scope: 'passage', relevance: 'no', relevance_reason: 'Cites it for a Greek word.' },
        { kind: 'article', title: 'Syntax article', page_ref: 'p', url: null, passage_rank: 1, passage_ref: 'hdt. 6.111.1', scope: 'passage', relevance: 'no', relevance_reason: 'Cites it for syntax.' },
      ],
    };
    mockApi(undefined, detail);
    render(<EventsPage setPageType={() => {}} />);
    await screen.findByRole('heading', { name: 'Battle of Marathon' });
    await userEvent.click(screen.getByRole('tab', { name: /Scholarship/ }));
    expect(screen.getByText('Discusses the battle itself.')).toBeTruthy(); // the reason shows under a YES row too (2026-10-19)
    expect(screen.getByText('Great Harbor article')).toBeTruthy();
    expect(screen.getByText('Background article')).toBeTruthy();
    expect(screen.getByText('partly')).toBeTruthy();
    expect(screen.queryByText('Grammar article')).toBeNull();
    const line = screen.getByRole('button', { name: /2 articles cite the passage for another reason/ });
    await userEvent.click(line);
    expect(screen.getByText('Grammar article')).toBeTruthy();
    expect(screen.getByText('Cites it for syntax.')).toBeTruthy();
    await userEvent.click(line);
    expect(screen.queryByText('Grammar article')).toBeNull();
  });

  it('shortens a scholarship passage reference', () => {
    expect(shortPassageRef('thuc. pele. 7.49.3-7.53.2')).toBe('7.49.3 to 7.53.2');
    expect(shortPassageRef('hdt. 6.111.1')).toBe('6.111.1');
  });

  it('shows documents with distance and date, scholarship and the map', async () => {
    mockApi();
    render(<EventsPage setPageType={() => {}} />);
    await screen.findByRole('heading', { name: 'Battle of Marathon' });
    await userEvent.click(screen.getByRole('tab', { name: /Inscriptions & Papyri \(1\)/ }));
    // the card leads with the edition or the type, never the internal id
    expect(screen.getByRole('link', { name: 'Corpus Inscriptionum Latinarum (CIL) 11, 01923' }))
      .toHaveAttribute('href', DETAIL.documents[0].view_url);
    // the text of the inscription itself, with the word that names the place marked
    const mark = screen.getByText('Perusia', { selector: 'mark' });
    expect(mark.parentElement.textContent).toBe('Augusto / sacrum / Perusia restituta.');
    expect(screen.queryByText('edh:HD1')).toBeNull();
    expect(screen.getByText(/12 km from Marathon/)).toBeTruthy();
    expect(screen.getByText(/Rhamnous · 500 to 450 BCE/)).toBeTruthy();

    await userEvent.click(screen.getByRole('tab', { name: /Scholarship/ }));
    expect(screen.getByTestId('about-these-sources')).toHaveAttribute('href', '/scholarship-sources#journals');
    expect(screen.getByRole('link', { name: /Marathon Revisited/ })).toHaveAttribute('href', 'https://example.org/a');
    expect(screen.getByText(/How and Wells: note/)).toBeTruthy();

    await userEvent.click(screen.getByRole('tab', { name: /Map/ }));
    expect(screen.getByRole('region', { name: /Map of the event/ })).toBeTruthy();
    const row = screen.getByRole('link', { name: 'Rhamnous' }).closest('tr');
    expect(within(row).getByText('38.2300, 24.0000')).toBeTruthy();
  });

  it('shows Cite on a commentary row that carries an edition, and nothing new on one that does not', async () => {
    const cited = {
      ...DETAIL,
      scholarship: [
        { kind: 'commentary', title: 'W. W. How and J. Wells on herodotus.histories', page_ref: 'hdt. 6.112.1', url: null,
          commentator: 'W. W. How and J. Wells', work: 'herodotus.histories', ref_start: 'hdt. 6.112.1',
          edition: 'W. W. How and J. Wells, eds., A Commentary on Herodotus (Oxford: Clarendon Press, 1912)', edition_title: 'A Commentary on Herodotus' },
        { kind: 'commentary', title: 'How and Wells: note', page_ref: 'hdt. 6.112.1', url: null },
      ],
    };
    mockApi(undefined, cited);
    render(<EventsPage setPageType={() => {}} />);
    await screen.findByRole('heading', { name: 'Battle of Marathon' });
    await userEvent.click(screen.getByRole('tab', { name: /Scholarship/ }));
    const cites = screen.getAllByRole('button', { name: 'Cite' });
    expect(cites).toHaveLength(1);
    expect(cites[0].closest('li').textContent).toContain('W. W. How and J. Wells on herodotus.histories');
    await userEvent.click(cites[0]);
    expect(await screen.findByText(/A Commentary on Herodotus/)).toBeTruthy();
  });

  it('shows no Cite control on a commentary row without an edition', async () => {
    mockApi();
    render(<EventsPage setPageType={() => {}} />);
    await screen.findByRole('heading', { name: 'Battle of Marathon' });
    await userEvent.click(screen.getByRole('tab', { name: /Scholarship/ }));
    expect(screen.getByText(/How and Wells: note/)).toBeTruthy();
    expect(screen.queryByRole('button', { name: 'Cite' })).toBeNull();
  });

  it('shows the Wikipedia summary with its credit line, or the Wikidata description without one', async () => {
    const withSummary = {
      ...DETAIL,
      event: { ...DETAIL.event, summary: 'The Battle of Marathon was fought in 490 BC.',
               summary_source: 'Wikipedia', summary_url: 'https://en.wikipedia.org/wiki/Battle_of_Marathon',
               summary_licence: 'CC BY-SA 4.0' },
    };
    mockApi(undefined, withSummary);
    render(<EventsPage setPageType={() => {}} />);
    await screen.findByRole('heading', { name: 'Battle of Marathon' });
    expect(screen.getByText('The Battle of Marathon was fought in 490 BC.')).toBeTruthy();
    expect(screen.queryByText(/Athenian victory/)).toBeNull();
    const credit = screen.getByText(/CC BY-SA 4.0/);
    expect(credit.textContent).toBe('From Wikipedia, CC BY-SA 4.0');
    expect(within(credit).getByRole('link', { name: 'Wikipedia' }))
      .toHaveAttribute('href', 'https://en.wikipedia.org/wiki/Battle_of_Marathon');
    cleanup();
    mockApi();
    render(<EventsPage setPageType={() => {}} />);
    await screen.findByRole('heading', { name: 'Battle of Marathon' });
    expect(screen.getByText(/Athenian victory/)).toBeTruthy();
    expect(screen.queryByText(/CC BY-SA 4.0/)).toBeNull();
  });

  it('names the passage under each article and opens the Passages tab at it', async () => {
    mockApi();
    const scroll = vi.fn();
    window.HTMLElement.prototype.scrollIntoView = scroll;
    render(<EventsPage setPageType={() => {}} />);
    await screen.findByRole('heading', { name: 'Battle of Marathon' });
    expect(document.getElementById('passage-1')).not.toBeNull();
    await userEvent.click(screen.getByRole('tab', { name: /Scholarship/ }));
    expect(screen.getByText(/articles that cite one of the event's leading passages/)).toBeTruthy();
    await userEvent.click(screen.getByRole('link', { name: 'on 6.111.1 to 6.113.2' }));
    expect(screen.getByRole('tab', { name: /Passages/, selected: true })).toBeTruthy();
    await waitFor(() => expect(scroll).toHaveBeenCalled());
    expect(scroll.mock.instances[0].id).toBe('passage-1');
  });

  it('goes back to the list', async () => {
    mockApi();
    render(<EventsPage setPageType={() => {}} />);
    await screen.findByRole('heading', { name: 'Battle of Marathon' });
    await userEvent.click(screen.getByRole('link', { name: 'All events' }));
    expect(window.location.pathname).toBe('/events');
    expect(await screen.findByText('Siege of Syracuse')).toBeTruthy();
  });

  it('answers a missing event plainly', async () => {
    global.fetch = vi.fn(async () => ({ ok: false, status: 404, json: async () => ({}) }));
    render(<EventsPage setPageType={() => {}} />);
    expect(await screen.findByText(/not in the dossiers/)).toBeTruthy();
  });

  it('shows every tab whatever the collection switches say (2026-10-20)', async () => {
    setCollection('scholarship', false);
    setCollection('inscriptions', false);
    setCollection('papyri', false);
    mockApi();
    render(<EventsPage setPageType={() => {}} />);
    await screen.findByRole('heading', { name: 'Battle of Marathon' });
    expect(screen.getByRole('tab', { name: /Scholarship/ })).toBeTruthy();
    expect(screen.getByRole('tab', { name: /Inscriptions/ })).toBeTruthy();
    setCollection('scholarship', true);
    setCollection('inscriptions', true);
    setCollection('papyri', true);
  });
});

describe('the Collections gate', () => {
  it('opens for a Literary visitor too (the menu lists it in every view)', async () => {
    setProfile('literary');
    mockApi();
    const setPageType = vi.fn();
    render(<EventsPage setPageType={setPageType} />);
    expect(await screen.findByText('Battle of Marathon')).toBeTruthy();
    expect(setPageType).not.toHaveBeenCalledWith('search');
  });

  it('opens for the Historical and Everything profiles', async () => {
    for (const profile of ['historical', 'everything']) {
      setProfile(profile);
      mockApi();
      const setPageType = vi.fn();
      const { unmount } = render(<EventsPage setPageType={setPageType} />);
      expect(await screen.findByText('Battle of Marathon')).toBeTruthy();
      expect(setPageType).not.toHaveBeenCalled();
      unmount();
    }
  });
});
