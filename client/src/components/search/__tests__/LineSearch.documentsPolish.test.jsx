/**
 * Stage 4 (the owner's review of the live documents trial, 2026-10-08):
 * one-click example searches, the document results sort control and
 * distribution chart, server-side paging, and the "Filter by Text"
 * section's Documents-only hide / Both relabel. Sibling to
 * LineSearch.documentsCollection.test.jsx, which already covers the
 * Literature/Documents/Both control and the basic document hit card.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

// A real (if simplified) Bar stand-in, so chart data passed down can be
// inspected -- the sibling suite's `() => null` stub cannot tell us
// whether the right labels/counts reached the chart.
vi.mock('react-chartjs-2', () => ({
  Bar: ({ data, options }) => (
    <div data-testid="bar-chart" data-title={options?.plugins?.title?.text}>
      {(data?.labels || []).map((label, i) => (
        <span key={label} data-testid="bar-point">{label}:{data.datasets[0].data[i]}</span>
      ))}
    </div>
  ),
}));
vi.mock('chart.js', () => ({
  Chart: { register: () => {} },
  CategoryScale: {}, LinearScale: {}, BarElement: {}, Title: {}, Tooltip: {}, Legend: {},
}));

import LineSearch from '../LineSearch';

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

const literatureHit = {
  text_id: 'vergil.aeneid.tess', author: 'Vergil', work: 'Aeneid', locus: '1.1',
  text: 'arma virumque cano', era: 'Augustan', year: -19,
  is_poetry: true, matched_words: ['arma', 'virum'], matched_lemmas: ['arma', 'vir'],
};

function mockFetch({ documentsEnabled, lineSearchResponse, trial = documentsEnabled }) {
  if (trial) window.sessionStorage.setItem('tesserae_documents_trial', '1');
  const calls = [];
  global.fetch = vi.fn(async (url, init) => {
    const u = String(url);
    if (u === '/api/languages') {
      return { json: async () => ({ languages: [{ code: 'la', label: 'Latin' }, { code: 'grc', label: 'Greek' }],
                                     crosslingual_pairs: [], documents_enabled: documentsEnabled }) };
    }
    if (u.startsWith('/api/texts')) {
      return { json: async () => ({ texts: [] }) };
    }
    if (u === '/api/line-search') {
      const body = init && init.body ? JSON.parse(init.body) : {};
      calls.push(body);
      const response = typeof lineSearchResponse === 'function'
        ? lineSearchResponse(body)
        : lineSearchResponse;
      return { json: async () => response };
    }
    return { json: async () => ({}) };
  });
  global.fetch.calls = calls;
  return calls;
}

beforeEach(() => {
  try { window.sessionStorage.clear(); } catch { /* ignore */ }
});
afterEach(() => { delete global.fetch; });

async function switchToSearchMode() {
  await userEvent.click(screen.getByRole('button', { name: 'Input Search Text' }));
}

describe('stage 4: example search buttons', () => {
  it('are not shown when the documents control is unavailable', async () => {
    mockFetch({ documentsEnabled: false, lineSearchResponse: { results: [] } });
    render(<LineSearch language="la" />);
    await switchToSearchMode();
    await waitFor(() => expect(global.fetch).toHaveBeenCalledWith('/api/languages'));
    expect(screen.queryByText('Try a documents example:')).toBeNull();
  });

  it('show the three Latin examples on the Latin tab', async () => {
    mockFetch({ documentsEnabled: true, lineSearchResponse: { results: [] } });
    render(<LineSearch language="la" />);
    await switchToSearchMode();
    await waitFor(() => expect(screen.getByText('Try a documents example:')).toBeTruthy());
    expect(screen.getByRole('button', { name: '"arma virumque cano"' })).toBeTruthy();
    expect(screen.getByRole('button', { name: '"conticuere omnes"' })).toBeTruthy();
    expect(screen.getByRole('button', { name: '"sit tibi terra levis"' })).toBeTruthy();
  });

  it('show the Greek example on the Greek tab', async () => {
    mockFetch({ documentsEnabled: true, lineSearchResponse: { results: [] } });
    render(<LineSearch language="grc" />);
    await switchToSearchMode();
    await waitFor(() => expect(screen.getByText('Try a documents example:')).toBeTruthy());
    expect(screen.getByRole('button', { name: /ἀθάνατος/ })).toBeTruthy();
  });

  it('clicking an example fills the query, picks the collection/search type, and runs the search', async () => {
    const calls = mockFetch({
      documentsEnabled: true,
      lineSearchResponse: { collection: 'both', total: 1, documents_total: 1,
        results: [literatureHit, documentHit()] },
    });
    render(<LineSearch language="la" />);
    await switchToSearchMode();
    await waitFor(() => expect(screen.getByText('Try a documents example:')).toBeTruthy());

    await userEvent.click(screen.getByRole('button', { name: '"arma virumque cano"' }));

    await waitFor(() => expect(calls.length).toBeGreaterThan(0));
    const body = calls[calls.length - 1];
    expect(body.query).toBe('arma virumque cano');
    expect(body.collection).toBe('both');
    expect(body.search_type).toBe('lemma');
    // The query box itself reflects the example (not left showing a stale
    // or empty box while results from a different query render).
    expect(screen.getByDisplayValue('arma virumque cano')).toBeTruthy();
  });

  it('the exact-match example sends search_type exact', async () => {
    const calls = mockFetch({
      documentsEnabled: true,
      lineSearchResponse: { collection: 'both', total: 1, documents_total: 4,
        results: [literatureHit, documentHit()] },
    });
    render(<LineSearch language="la" />);
    await switchToSearchMode();
    await waitFor(() => expect(screen.getByText('Try a documents example:')).toBeTruthy());
    await userEvent.click(screen.getByRole('button', { name: '"conticuere omnes"' }));
    await waitFor(() => expect(calls.length).toBeGreaterThan(0));
    expect(calls[calls.length - 1].search_type).toBe('exact');
  });
});

describe('stage 4: document results sort control', () => {
  it('is absent when there are no document results', async () => {
    mockFetch({ documentsEnabled: true, lineSearchResponse: { collection: 'documents', total: 0, results: [] } });
    render(<LineSearch language="la" />);
    await switchToSearchMode();
    await waitFor(() => expect(screen.getByText('Search in')).toBeTruthy());
    await userEvent.click(screen.getByRole('button', { name: 'Documents' }));
    await userEvent.type(screen.getByPlaceholderText('Enter word or phrase...'), 'dis manibus');
    await userEvent.click(screen.getByRole('button', { name: 'Search Lines' }));
    await waitFor(() => expect(global.fetch).toHaveBeenCalled());
    expect(screen.queryByText('Sort')).toBeNull();
  });

  it('defaults to Relevance and offers Oldest/Newest/Region', async () => {
    mockFetch({
      documentsEnabled: true,
      lineSearchResponse: { collection: 'documents', total: 1, results: [documentHit()] },
    });
    render(<LineSearch language="la" />);
    await switchToSearchMode();
    await waitFor(() => expect(screen.getByText('Search in')).toBeTruthy());
    await userEvent.click(screen.getByRole('button', { name: 'Documents' }));
    await userEvent.type(screen.getByPlaceholderText('Enter word or phrase...'), 'dis manibus');
    await userEvent.click(screen.getByRole('button', { name: 'Search Lines' }));

    await waitFor(() => expect(screen.getByText(/Found 1 documents/)).toBeTruthy());
    const select = screen.getByLabelText('Sort');
    expect(select.value).toBe('relevance');
    const optionLabels = Array.from(select.options).map(o => o.textContent);
    expect(optionLabels).toEqual(['Relevance', 'Oldest first', 'Newest first', 'Region']);
  });

  it('changing the sort re-queries with offset 0 and the new sort, without re-running the literary search', async () => {
    const calls = mockFetch({
      documentsEnabled: true,
      lineSearchResponse: (body) => ({
        collection: body.collection, total: body.collection === 'both' ? 1 : undefined,
        documents_total: 1, sort: body.sort,
        results: body.collection === 'both' ? [literatureHit, documentHit()] : [documentHit()],
      }),
    });
    render(<LineSearch language="la" />);
    await switchToSearchMode();
    await waitFor(() => expect(screen.getByText('Search in')).toBeTruthy());
    await userEvent.click(screen.getByRole('button', { name: 'Both' }));
    await userEvent.type(screen.getByPlaceholderText('Enter word or phrase...'), 'dis manibus');
    await userEvent.click(screen.getByRole('button', { name: 'Search Lines' }));
    await waitFor(() => expect(screen.getByText(/Found 1 documents/)).toBeTruthy());

    const beforeCallCount = calls.length;
    await userEvent.selectOptions(screen.getByLabelText('Sort'), 'oldest');

    await waitFor(() => expect(calls.length).toBe(beforeCallCount + 1));
    const sortCall = calls[calls.length - 1];
    expect(sortCall.sort).toBe('oldest');
    expect(sortCall.offset).toBe(0);
    expect(sortCall.query).toBe('dis manibus');
    // The literary result from the original search is still on screen --
    // a sort change on the documents list never re-fetches literature.
    expect(screen.getByText('Vergil')).toBeTruthy();
  });
});

describe('stage 4: document distribution chart', () => {
  it('renders a century and a region chart from documents_by_century/by_source_region', async () => {
    mockFetch({
      documentsEnabled: true,
      lineSearchResponse: {
        collection: 'documents', total: 2,
        documents_by_century: [{ century: '2nd c. AD', count: 2 }],
        documents_by_source_region: [{ source: 'edh', region: 'Roma', count: 2 }],
        results: [documentHit(), documentHit({ doc_id: 'edh:HD000002' })],
      },
    });
    render(<LineSearch language="la" />);
    await switchToSearchMode();
    await waitFor(() => expect(screen.getByText('Search in')).toBeTruthy());
    await userEvent.click(screen.getByRole('button', { name: 'Documents' }));
    await userEvent.type(screen.getByPlaceholderText('Enter word or phrase...'), 'dis manibus');
    await userEvent.click(screen.getByRole('button', { name: 'Search Lines' }));

    await waitFor(() => expect(screen.getAllByTestId('bar-chart').length).toBe(2));
    const charts = screen.getAllByTestId('bar-chart');
    const titles = charts.map(c => c.getAttribute('data-title'));
    expect(titles).toContain('By Century');
    expect(titles).toContain('By Region');
    expect(screen.getByText('2nd c. AD:2')).toBeTruthy();
    expect(screen.getByText('Roma:2')).toBeTruthy();
  });

  it('is absent when no distribution data comes back', async () => {
    mockFetch({
      documentsEnabled: true,
      lineSearchResponse: { collection: 'documents', total: 1, results: [documentHit()] },
    });
    render(<LineSearch language="la" />);
    await switchToSearchMode();
    await waitFor(() => expect(screen.getByText('Search in')).toBeTruthy());
    await userEvent.click(screen.getByRole('button', { name: 'Documents' }));
    await userEvent.type(screen.getByPlaceholderText('Enter word or phrase...'), 'dis manibus');
    await userEvent.click(screen.getByRole('button', { name: 'Search Lines' }));

    await waitFor(() => expect(screen.getByText(/Found 1 documents/)).toBeTruthy());
    expect(screen.queryByTestId('bar-chart')).toBeNull();
    expect(screen.queryByText('Show Distribution')).toBeNull();
  });
});

describe('stage 4: "Filter by Text" hide/relabel per collection', () => {
  it('stays "Filter by Text (Optional)" under plain Literature', async () => {
    mockFetch({ documentsEnabled: true, lineSearchResponse: { results: [] } });
    render(<LineSearch language="la" />);
    await switchToSearchMode();
    await waitFor(() => expect(screen.getByText('Search in')).toBeTruthy());
    expect(screen.getByText('Filter by Text (Optional)')).toBeTruthy();
  });

  it('is hidden entirely under Documents', async () => {
    mockFetch({ documentsEnabled: true, lineSearchResponse: { results: [] } });
    render(<LineSearch language="la" />);
    await switchToSearchMode();
    await waitFor(() => expect(screen.getByText('Search in')).toBeTruthy());
    await userEvent.click(screen.getByRole('button', { name: 'Documents' }));
    expect(screen.queryByText('Filter by Text (Optional)')).toBeNull();
    expect(screen.queryByText('Filter the literature (optional)')).toBeNull();
    expect(screen.queryByLabelText('Author')).toBeNull();
  });

  it('is relabeled "Filter the literature (optional)" under Both, and stays functional', async () => {
    mockFetch({ documentsEnabled: true, lineSearchResponse: { results: [] } });
    render(<LineSearch language="la" />);
    await switchToSearchMode();
    await waitFor(() => expect(screen.getByText('Search in')).toBeTruthy());
    await userEvent.click(screen.getByRole('button', { name: 'Both' }));
    expect(screen.getByText('Filter the literature (optional)')).toBeTruthy();
    expect(screen.queryByText('Filter by Text (Optional)')).toBeNull();
    expect(screen.getByLabelText('Author')).toBeTruthy();
  });

  it('never sends author/work/line filters when the collection is Documents-only', async () => {
    const calls = mockFetch({ documentsEnabled: true, lineSearchResponse: { results: [] } });
    render(<LineSearch language="la" />);
    await switchToSearchMode();
    await waitFor(() => expect(screen.getByText('Search in')).toBeTruthy());
    await userEvent.click(screen.getByRole('button', { name: 'Documents' }));
    await userEvent.type(screen.getByPlaceholderText('Enter word or phrase...'), 'dis manibus');
    await userEvent.click(screen.getByRole('button', { name: 'Search Lines' }));

    await waitFor(() => expect(calls.length).toBeGreaterThan(0));
    const body = calls[calls.length - 1];
    expect(body.author).toBeUndefined();
    expect(body.work).toBeUndefined();
    expect(body.line_start).toBeUndefined();
    expect(body.line_end).toBeUndefined();
  });
});
