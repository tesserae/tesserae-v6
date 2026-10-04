import { useState } from 'react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, within, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

// Same chart stubs as SearchResults.pagination.test.jsx: no canvas in jsdom,
// and the stub's click reaches the chart's own onClick (bar 0).
vi.mock('react-chartjs-2', async () => {
  const { forwardRef, createElement } = await vi.importActual('react');
  return {
    Bar: forwardRef(({ data, options }, ref) =>
      createElement(
        'button',
        {
          ref,
          'data-testid': 'mock-chart-bar',
          'data-labels': JSON.stringify(data?.labels || []),
          'data-counts': JSON.stringify(data?.datasets?.[0]?.data || []),
          onClick: () => options?.onClick?.(null, [{ index: 0 }]),
        },
        'chart bar 0'
      )
    ),
  };
});
vi.mock('chart.js', () => ({
  Chart: { register: () => {} },
  CategoryScale: {}, LinearScale: {}, BarElement: {},
  Title: {}, Tooltip: {}, Legend: {},
}));

vi.mock('../../../utils/api', () => ({
  fetchResultPage: vi.fn(),
  fetchAllResults: vi.fn(),
}));

import * as api from '../../../utils/api';
import SearchResults from '../SearchResults';

const TOTAL = 237;
const ALL = Array.from({ length: TOTAL }, (_, i) => ({
  source: { ref: `s.${i + 1}`, text: `source line ${i + 1}`, tokens: [], highlight_indices: [] },
  target: { ref: i < 100 ? `1.${i + 1}` : `2.${i + 1}`, text: `target line ${i + 1}`, tokens: [], highlight_indices: [] },
  source_text: `src-${i + 1}`,
  target_text: `tgt-${i + 1}`,
  matched_words: [],
  overall_score: (TOTAL - i) / TOTAL,
}));

// A stand-in for GET /api/search-results/<id>: filter, sort, then slice the
// full list, the order backend/result_pages.query_page applies.
const fakeServer = (id, q) => {
  let rows = ALL;
  if (q.filter_book) rows = rows.filter((r) => `Book ${r.target.ref.split('.')[0]}` === q.filter_book);
  if (q.sort === 'target_locus') rows = [...rows].reverse();
  return Promise.resolve({ results: rows.slice(q.offset, q.offset + q.limit), total: rows.length, offset: q.offset, limit: q.limit });
};

const resultSet = {
  id: 'a'.repeat(32),
  total: TOTAL,
  pageSize: 50,
  firstPage: ALL.slice(0, 50),
  aggregates: { distribution: {
    target: { mode: 'book', labels: ['Book 1', 'Book 2'], counts: [100, 137] },
    source: { mode: 'line', band: 25, labels: ['1–25'], counts: [TOTAL] },
  } },
};

const Harness = (props) => {
  const [pageSize, setPageSize] = useState(50);
  const [sortBy, setSortBy] = useState('score');
  return (
    <SearchResults
      results={resultSet.firstPage}
      resultSet={resultSet}
      loading={false}
      error={null}
      pageSize={pageSize}
      onPageSizeChange={setPageSize}
      searchRunId={1}
      sortBy={sortBy}
      setSortBy={setSortBy}
      searchStats={null}
      language="la"
      {...props}
    />
  );
};

const rowNumbers = () => screen.getAllByText(/^\d+\.$/).map((el) => parseInt(el.textContent, 10));
const nav = () => screen.getAllByRole('navigation', { name: 'Search results pagination' })[0];

async function openComparisonChart() {
  const closed = screen.queryByRole('button', { name: 'Show chart' });
  if (closed) await userEvent.click(closed);
  await userEvent.click(screen.getByRole('button', { name: 'In this comparison' }));
}

beforeEach(() => {
  vi.clearAllMocks();
  api.fetchResultPage.mockImplementation(fakeServer);
  api.fetchAllResults.mockImplementation(() => Promise.resolve(ALL));
  global.fetch = vi.fn(() => Promise.resolve({ ok: true, json: () => Promise.resolve({}) }));
});

afterEach(() => {
  delete global.fetch;
});

describe('SearchResults — server-held result set', () => {
  it('shows the first page from the search response without another request', () => {
    render(<Harness />);
    expect(rowNumbers()).toHaveLength(50);
    expect(screen.getByText('src-1')).toBeInTheDocument();
    expect(screen.getByText(`Showing 1–50 of ${TOTAL} results`)).toBeInTheDocument();
    expect(screen.getByRole('status')).toHaveTextContent(`${TOTAL} Parallels Found`);
    expect(api.fetchResultPage).not.toHaveBeenCalled();
  });

  it('fetches the next page from the server and renders only that page', async () => {
    render(<Harness />);
    await userEvent.click(within(nav()).getByRole('button', { name: 'Next' }));
    await waitFor(() => expect(screen.getByText('src-51')).toBeInTheDocument());
    expect(api.fetchResultPage).toHaveBeenCalledWith(
      resultSet.id, { offset: 50, limit: 50, sort: 'score' }, expect.anything());
    expect(screen.queryByText('src-1')).not.toBeInTheDocument();
    expect(rowNumbers()[0]).toBe(51);
    expect(rowNumbers()).toHaveLength(50);
  });

  it('asks the server for a new page size instead of slicing locally', async () => {
    render(<Harness />);
    await userEvent.selectOptions(screen.getAllByRole('combobox', { name: 'Show' })[0], '10');
    await waitFor(() => expect(rowNumbers()).toHaveLength(10));
    expect(api.fetchResultPage).toHaveBeenLastCalledWith(
      resultSet.id, { offset: 0, limit: 10, sort: 'score' }, expect.anything());
  });

  it('sends the sort to the server, which sorts the whole list before slicing', async () => {
    render(<Harness />);
    await userEvent.selectOptions(screen.getByDisplayValue('Score'), 'target_locus');
    await waitFor(() => expect(screen.getByText(`src-${TOTAL}`)).toBeInTheDocument());
    expect(api.fetchResultPage).toHaveBeenLastCalledWith(
      resultSet.id, { offset: 0, limit: 50, sort: 'target_locus' }, expect.anything());
  });

  it('draws the chart from server aggregates and filters through the server', async () => {
    render(<Harness />);
    await openComparisonChart();
    const bar = screen.getByTestId('mock-chart-bar');
    expect(JSON.parse(bar.dataset.counts)).toEqual([100, 137]);
    await userEvent.click(bar);
    await waitFor(() => expect(screen.getByText(/Filtering to Book 1 \(100 results\)/)).toBeInTheDocument());
    expect(api.fetchResultPage).toHaveBeenLastCalledWith(
      resultSet.id,
      { offset: 0, limit: 50, sort: 'score', filter_view: 'target', filter_book: 'Book 1' },
      expect.anything());
  });

  it('exports every stored row, fetched only when Export is clicked', async () => {
    let csv = '';
    const BlobOriginal = global.Blob;
    global.Blob = class extends BlobOriginal {
      constructor(parts, opts) { csv = parts.join(''); super(parts, opts); }
    };
    global.URL.createObjectURL = vi.fn(() => 'blob:mock');
    global.URL.revokeObjectURL = vi.fn();
    const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});

    render(<Harness />);
    expect(api.fetchAllResults).not.toHaveBeenCalled();
    await userEvent.click(screen.getByRole('button', { name: 'Export CSV' }));
    await waitFor(() => expect(csv).not.toBe(''));
    expect(api.fetchAllResults).toHaveBeenCalledWith(resultSet.id);
    expect(csv.trim().split('\n').slice(1)).toHaveLength(TOTAL);
    expect(csv).toContain(`s.${TOTAL}`);

    global.Blob = BlobOriginal;
    click.mockRestore();
  });

  it('shows an error when a page cannot be loaded', async () => {
    api.fetchResultPage.mockImplementation(() => Promise.reject(new Error('Result set not found or expired')));
    render(<Harness />);
    await userEvent.click(within(nav()).getByRole('button', { name: 'Next' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('expired');
  });
});
