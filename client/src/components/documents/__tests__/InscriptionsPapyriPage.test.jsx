/**
 * The Inscriptions & Papyri page (route /inscriptions-papyri): shares its
 * documents-collection search logic with LineSearch.jsx via
 * useDocumentsSearch.js (see LineSearch.documentsCollection.test.jsx and
 * LineSearch.documentsPolish.test.jsx for that logic's own coverage).
 * This suite covers what is specific to the page itself: the redirect
 * when the documents trial is off, the top-level sections rendering when
 * it is on, and the example-search buttons (DOCUMENT_EXAMPLE_SEARCHES,
 * shared with LineSearch.jsx).
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

vi.mock('react-chartjs-2', () => ({ Bar: () => null }));
vi.mock('chart.js', () => ({
  Chart: { register: () => {} },
  CategoryScale: {}, LinearScale: {}, BarElement: {}, Title: {}, Tooltip: {}, Legend: {},
}));

import InscriptionsPapyriPage from '../InscriptionsPapyriPage';

const BROWSE_RESPONSE = {
  kind_counts: [{ value: 'inscriptions', label: 'Inscriptions (Latin, Greek)', count: 4 }],
  region_counts: [{ value: 'Dalmatia', count: 2 }],
  findspot_counts: [],
  century_counts: [{ label: '2nd century AD', count: 1 }],
  filters: { text_types: [], materials: [], objects: [], languages: [] },
  documents: [],
  total: 4,
  page: 1,
  page_size: 50,
};

const documentHit = (overrides = {}) => ({
  collection: 'documents',
  doc_id: 'edh:HD047322',
  locus: 'edh:HD047322',
  text: 'Dis Manibus',
  tokens: ['Dis', 'Manibus'],
  matched_words: ['Dis', 'Manibus'],
  matched_lemmas: ['deus', 'manus'],
  restored_indices: [],
  fragment_indices: [],
  credit: { source_name: 'Epigraphic Database Heidelberg', principal_edition: 'AE 2001, 2169.' },
  date_not_before: 101, date_not_after: 300,
  ancient_place: null, modern_place: 'Rome', region: 'Roma',
  text_type_label: 'funerary inscription', object_type_label: 'stele', material_label: 'marble',
  ...overrides,
});

function mockFetch({ documentsEnabled = true, lineSearchResponse } = {}) {
  const calls = [];
  global.fetch = vi.fn(async (url, init) => {
    const u = String(url);
    if (u === '/api/languages') {
      return { json: async () => ({ languages: [{ code: 'la', label: 'Latin' }], documents_enabled: documentsEnabled }) };
    }
    if (u.startsWith('/api/documents/browse')) {
      return { ok: true, status: 200, json: async () => BROWSE_RESPONSE };
    }
    if (u === '/api/line-search') {
      const body = init && init.body ? JSON.parse(init.body) : {};
      calls.push(body);
      const response = typeof lineSearchResponse === 'function' ? lineSearchResponse(body) : (lineSearchResponse || { results: [] });
      return { json: async () => response };
    }
    return { json: async () => ({}) };
  });
  global.fetch.calls = calls;
  return calls;
}

function setUrl(search = '') {
  window.history.pushState({}, '', `/inscriptions-papyri${search}`);
}

beforeEach(() => {
  try { window.sessionStorage.clear(); } catch { /* ignore */ }
  setUrl();
});
afterEach(() => {
  delete global.fetch;
  window.history.replaceState({}, '', '/');
});

describe('redirect when the documents trial is not active', () => {
  it('calls setPageType("search") and renders nothing', async () => {
    mockFetch({ documentsEnabled: true });
    const setPageType = vi.fn();
    const { container } = render(<InscriptionsPapyriPage setPageType={setPageType} />);
    await waitFor(() => expect(setPageType).toHaveBeenCalledWith('search'));
    expect(container.textContent).toBe('');
  });

  it('does not redirect once ?documents=1 has set the trial flag', async () => {
    setUrl('?documents=1');
    mockFetch({ documentsEnabled: true });
    const setPageType = vi.fn();
    render(<InscriptionsPapyriPage setPageType={setPageType} />);
    await waitFor(() => expect(screen.getByText('Inscriptions & Papyri')).toBeTruthy());
    expect(setPageType).not.toHaveBeenCalled();
  });
});

describe('top-level sections, with the trial active', () => {
  beforeEach(() => { setUrl('?documents=1'); });

  it('renders the description, example buttons, search box and browse view', async () => {
    mockFetch({ documentsEnabled: true });
    render(<InscriptionsPapyriPage />);
    await waitFor(() => expect(screen.getByText('Inscriptions & Papyri')).toBeTruthy());
    // Description.
    expect(screen.getByText(/Search and browse the documentary corpus/)).toBeTruthy();
    // Example buttons (Latin tab is the page's default language).
    await waitFor(() => expect(screen.getByText('Try a documents example:')).toBeTruthy());
    expect(screen.getByRole('button', { name: '"arma virumque cano"' })).toBeTruthy();
    // Search box.
    expect(screen.getByPlaceholderText('Enter word or phrase...')).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Search' })).toBeTruthy();
    // The Documents/Both toggle (no Literature option on this page).
    expect(screen.getByRole('button', { name: 'Documents' })).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Both' })).toBeTruthy();
    expect(screen.queryByRole('button', { name: 'Literature' })).toBeNull();
    // Browse view (DocumentsBrowser), below the search.
    await waitFor(() => expect(screen.getByText(/Inscriptions \(Latin, Greek\)/)).toBeTruthy());
  });

  it('has an "About this page" link that opens Help at the documents section', async () => {
    mockFetch({ documentsEnabled: true });
    const handler = vi.fn();
    window.addEventListener('tesserae:open-help', handler);
    render(<InscriptionsPapyriPage />);
    await waitFor(() => expect(screen.getByText('Inscriptions & Papyri')).toBeTruthy());
    await userEvent.click(screen.getByRole('button', { name: 'About this page' }));
    expect(handler).toHaveBeenCalled();
    expect(handler.mock.calls[0][0].detail).toEqual({ section: 'documents' });
    window.removeEventListener('tesserae:open-help', handler);
  });
});

describe('example-search buttons', () => {
  beforeEach(() => { setUrl('?documents=1'); });

  it('clicking an example fills the query, sends the right params, and shows document results', async () => {
    const calls = mockFetch({
      documentsEnabled: true,
      lineSearchResponse: { collection: 'both', total: 1, documents_total: 1, results: [documentHit()] },
    });
    render(<InscriptionsPapyriPage />);
    await waitFor(() => expect(screen.getByText('Try a documents example:')).toBeTruthy());

    await userEvent.click(screen.getByRole('button', { name: '"arma virumque cano"' }));

    await waitFor(() => expect(calls.length).toBeGreaterThan(0));
    const body = calls[calls.length - 1];
    expect(body.query).toBe('arma virumque cano');
    expect(body.collection).toBe('both');
    expect(body.search_type).toBe('lemma');
    expect(screen.getByDisplayValue('arma virumque cano')).toBeTruthy();
    await waitFor(() => expect(screen.getByText(/Found 1 documents/)).toBeTruthy());
  });

  it('the exact-match example sends search_type exact', async () => {
    const calls = mockFetch({
      documentsEnabled: true,
      lineSearchResponse: { collection: 'both', total: 1, documents_total: 1, results: [documentHit()] },
    });
    render(<InscriptionsPapyriPage />);
    await waitFor(() => expect(screen.getByText('Try a documents example:')).toBeTruthy());
    await userEvent.click(screen.getByRole('button', { name: '"conticuere omnes"' }));
    await waitFor(() => expect(calls.length).toBeGreaterThan(0));
    expect(calls[calls.length - 1].search_type).toBe('exact');
  });

  it('shows the Greek example only on the Greek language choice', async () => {
    mockFetch({ documentsEnabled: true });
    render(<InscriptionsPapyriPage />);
    await waitFor(() => expect(screen.getByText('Try a documents example:')).toBeTruthy());
    expect(screen.queryByRole('button', { name: /ἀθάνατος/ })).toBeNull();
    await userEvent.selectOptions(screen.getByDisplayValue('Latin'), 'grc');
    await waitFor(() => expect(screen.getByRole('button', { name: /ἀθάνατος/ })).toBeTruthy());
  });
});

describe('returning from the document view (the back link\'s own deep link)', () => {
  it('restores the query, language, collection and filters, and re-runs the search', async () => {
    const calls = mockFetch({
      documentsEnabled: true,
      lineSearchResponse: { collection: 'documents', total: 1, results: [documentHit()] },
    });
    setUrl('?documents=1&q=dis+manibus&lang=la&type=lemma&collection=documents&region=Roma&date_from=100');
    render(<InscriptionsPapyriPage />);

    await waitFor(() => expect(calls.length).toBeGreaterThan(0));
    const body = calls[calls.length - 1];
    expect(body.query).toBe('dis manibus');
    expect(body.collection).toBe('documents');
    expect(body.region).toBe('Roma');
    expect(body.date_from).toBe(100);
    expect(screen.getByDisplayValue('dis manibus')).toBeTruthy();
    await waitFor(() => expect(screen.getByText(/Found 1 documents/)).toBeTruthy());
  });
});

describe('a typed search', () => {
  beforeEach(() => { setUrl('?documents=1'); });

  it('sends collection=documents by default and renders the result', async () => {
    const calls = mockFetch({
      documentsEnabled: true,
      lineSearchResponse: { collection: 'documents', total: 1, results: [documentHit()] },
    });
    render(<InscriptionsPapyriPage />);
    await waitFor(() => expect(screen.getByPlaceholderText('Enter word or phrase...')).toBeTruthy());
    await userEvent.type(screen.getByPlaceholderText('Enter word or phrase...'), 'dis manibus');
    await userEvent.click(screen.getByRole('button', { name: 'Search' }));

    await waitFor(() => expect(calls.length).toBeGreaterThan(0));
    expect(calls[calls.length - 1].collection).toBe('documents');
    await waitFor(() => expect(screen.getByText(/Found 1 documents/)).toBeTruthy());
  });
});
