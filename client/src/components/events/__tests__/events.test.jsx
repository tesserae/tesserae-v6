/**
 * The Events page: list with search and filters, the focus view of one event
 * (tabs, Reader links with the way back), and the Collections gate.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor, within, cleanup } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import EventsPage from '../EventsPage';
import EventList from '../EventList';
import { dateLabel, centuryLabel, yearLabel } from '../eventsFormat';
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
      text_snippet: 'ΜΑΡΑΘΩΝ', view_url: '/document?doc=edh%3AHD1&lang=la&documents=1' },
  ],
  scholarship: [
    { kind: 'article', title: 'Marathon Revisited (Doe, 1990)', page_ref: 'Hdt. 6.111', url: 'https://example.org/a' },
    { kind: 'commentary', title: 'How and Wells: note', page_ref: 'hdt. 6.112.1', url: null },
  ],
  map: [
    { kind: 'event', label: 'Marathon', lat: 38.15, lon: 23.96, n_documents: 0 },
    { kind: 'findspot', label: 'Rhamnous', lat: 38.23, lon: 24.0, n_documents: 1 },
  ],
};

function mockApi(listOverride) {
  const calls = [];
  global.fetch = vi.fn(async (url) => {
    const u = String(url);
    calls.push(u);
    if (u.startsWith('/api/events/')) return { ok: true, status: 200, json: async () => DETAIL };
    if (u.startsWith('/api/events')) return { ok: true, status: 200, json: async () => listOverride || LIST };
    return { ok: true, status: 200, json: async () => ({}) };
  });
  return calls;
}

beforeEach(() => {
  window.localStorage.clear();
  window.sessionStorage.clear();
  window.history.replaceState({}, '', '/events');
  setProfile('historical');
});
afterEach(() => { cleanup(); window.history.replaceState({}, '', '/'); });

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
  it('asks for the most-evidence order first, says how many empty events are hidden, and can include them', async () => {
    const calls = mockApi({ ...LIST, total_all: 5, sort: 'evidence', show: 'evidence',
      type_counts: { battle: 1, siege: 1 } });
    render(<EventsPage setPageType={() => {}} />);
    expect(await screen.findByText('Battle of Marathon')).toBeTruthy();
    expect(calls[0]).toContain('sort=evidence');
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
    expect(screen.getByRole('heading', { name: 'herodotus: histories' })).toBeTruthy();
    expect(screen.getByRole('heading', { name: 'nepos: vitae' })).toBeTruthy();
    const links = screen.getAllByRole('link', { name: 'Open in the Reader' });
    expect(links).toHaveLength(3);
    expect(links[0].getAttribute('href')).toBe(
      '/read?work=herodotus.histories.tess&lang=grc&ref=hdt.%206.111.1&event=Q1&eventLabel=Battle%20of%20Marathon');
    expect(screen.getByText(/4 more were judged unrelated/)).toBeTruthy();
    expect(screen.getByText('Mentions it')).toBeTruthy();
  });

  it('shows documents with distance and date, scholarship and the map', async () => {
    mockApi();
    render(<EventsPage setPageType={() => {}} />);
    await screen.findByRole('heading', { name: 'Battle of Marathon' });
    await userEvent.click(screen.getByRole('tab', { name: /Inscriptions & Papyri \(1\)/ }));
    // the card leads with the edition or the type, never the internal id
    expect(screen.getByRole('link', { name: 'Document' })).toHaveAttribute('href', DETAIL.documents[0].view_url);
    expect(screen.queryByText('edh:HD1')).toBeNull();
    expect(screen.getByText(/12 km from Marathon/)).toBeTruthy();
    expect(screen.getByText(/Rhamnous · 500 to 450 BCE/)).toBeTruthy();

    await userEvent.click(screen.getByRole('tab', { name: /Scholarship/ }));
    expect(screen.getByRole('link', { name: /Marathon Revisited/ })).toHaveAttribute('href', 'https://example.org/a');
    expect(screen.getByText(/How and Wells: note/)).toBeTruthy();

    await userEvent.click(screen.getByRole('tab', { name: /Map/ }));
    expect(screen.getByRole('region', { name: /Map of the event/ })).toBeTruthy();
    const row = screen.getByRole('link', { name: 'Rhamnous' }).closest('tr');
    expect(within(row).getByText('38.2300, 24.0000')).toBeTruthy();
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

  it('hides the Scholarship tab when Scholarship is off, and the documents tab when both are', async () => {
    setCollection('scholarship', false);
    mockApi();
    const { unmount } = render(<EventsPage setPageType={() => {}} />);
    await screen.findByRole('heading', { name: 'Battle of Marathon' });
    expect(screen.queryByRole('tab', { name: /Scholarship/ })).toBeNull();
    expect(screen.getByRole('tab', { name: /Inscriptions/ })).toBeTruthy();
    unmount();
    setCollection('scholarship', true);
    setCollection('inscriptions', false);
    setCollection('papyri', false);
    render(<EventsPage setPageType={() => {}} />);
    await screen.findByRole('heading', { name: 'Battle of Marathon' });
    expect(screen.queryByRole('tab', { name: /Inscriptions/ })).toBeNull();
    expect(screen.getByRole('tab', { name: /Scholarship/ })).toBeTruthy();
  });
});

describe('the Collections gate', () => {
  it('sends a Literary visitor to Search and shows nothing', async () => {
    setProfile('literary');
    mockApi();
    const setPageType = vi.fn();
    const { container } = render(<EventsPage setPageType={setPageType} />);
    await waitFor(() => expect(setPageType).toHaveBeenCalledWith('search'));
    expect(container.textContent).toBe('');
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
