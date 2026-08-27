import { useState } from 'react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

// Chart.js needs a real canvas, which jsdom does not provide. The stub also
// surfaces the chart's own onClick so the chart-filter path stays reachable.
// forwardRef keeps React quiet about the ref SearchResults passes to <Bar>;
// it is pulled in via importActual because vi.mock factories are hoisted
// above this file's imports.
vi.mock('react-chartjs-2', async () => {
  const { forwardRef, createElement } = await vi.importActual('react');
  return {
    Bar: forwardRef(({ options }, ref) =>
      createElement(
        'button',
        {
          ref,
          'data-testid': 'mock-chart-bar',
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

// Every search transport lives in utils/api. Pagination must never reach it.
vi.mock('../../../utils/api', () => ({
  searchTexts: vi.fn(),
  searchTextsStream: vi.fn(),
  searchFusionStream: vi.fn(),
  searchSemanticCross: vi.fn(),
  searchHapax: vi.fn(),
  searchBigrams: vi.fn(),
  wildcardSearch: vi.fn(),
}));

import * as api from '../../../utils/api';
import SearchResults from '../SearchResults';

/**
 * Fixture shaped like a real scorer result (backend/scorer.py:232-240).
 * `source_text` is used as the row identifier because it renders verbatim,
 * whereas `source.ref` is rewritten by formatReference().
 */
const makeResults = (n, tag = 'a') =>
  Array.from({ length: n }, (_, i) => ({
    source: {
      ref: `${tag}.src.${i + 1}`,
      text: `source line ${i + 1}`,
      tokens: ['source', 'line'],
      highlight_indices: [0],
    },
    target: {
      ref: `${tag}.tgt.${i + 1}`,
      text: `target line ${i + 1}`,
      tokens: ['target', 'line'],
      highlight_indices: [0],
    },
    source_text: `${tag}-src-${i + 1}`,
    target_text: `${tag}-tgt-${i + 1}`,
    matched_words: [{ lemma: `lemma${i + 1}`, source_word: 'source', target_word: 'target' }],
    source_distance: 1,
    target_distance: 1,
    overall_score: (n - i) / n,
    base_score: (n - i) / n,
    features: {},
  }));

/**
 * Loci that resolve to two distinct book labels. getDistributionData matches
 * /(\d+)\.\d+/ against the TARGET locus (the default chart view), so these
 * yield "Book 1" (100 results) and "Book 2" (137 results).
 */
const makeBookedResults = (n = 237) =>
  makeResults(n).map((r, i) => ({
    ...r,
    target: { ...r.target, ref: i < 100 ? `1.${i + 1}` : `2.${i + 1}` },
  }));

const baseProps = {
  loading: false,
  error: null,
  pageSize: 50,
  onPageSizeChange: () => {},
  searchRunId: 1,
  sortBy: 'score',
  setSortBy: () => {},
  searchStats: null,
  language: 'la',
};

const renderResults = (props = {}) =>
  render(<SearchResults {...baseProps} results={makeResults(237)} {...props} />);

/**
 * Mirrors App.jsx, which owns pageSize and passes it down. Without a real owner
 * the controlled selector could never change and the tests would prove nothing.
 */
const PageSizeHarness = ({ results = makeResults(237), ...props }) => {
  const [pageSize, setPageSize] = useState(50);
  return (
    <SearchResults
      {...baseProps}
      results={results}
      pageSize={pageSize}
      onPageSizeChange={setPageSize}
      {...props}
    />
  );
};

const selectPageSize = (value) =>
  userEvent.selectOptions(screen.getAllByRole('combobox', { name: 'Show' })[0], value);

/** Result rows carry a leading "N." index cell; count those. */
const countRows = () => screen.getAllByText(/^\d+\.$/).length;
const rowNumbers = () => screen.getAllByText(/^\d+\.$/).map((el) => parseInt(el.textContent, 10));

const nav = () => screen.getAllByRole('navigation', { name: 'Search results pagination' })[0];

/** Put the per-comparison distribution chart on screen, however it got left.
 *
 *  These tests used to press a "Distribution" button. The chart has since
 *  become a standing sidebar with two views, and both changes broke the old
 *  route to it:
 *
 *    - the open/close toggle is now "Show chart" / "Hide chart", and its state
 *      is remembered in sessionStorage, which jsdom keeps for a whole file, so
 *      one test closing the chart decided whether a later one could find it;
 *    - the sidebar opens on "Across the corpus", which needs a backend call
 *      these tests forbid, so it renders nothing. The chart whose bars filter
 *      the results is the other view, "In this comparison".
 *
 *  Asking for the state the test needs, instead of assuming a default, is
 *  independent of both.
 */
async function openChart() {
  const closed = screen.queryByRole('button', { name: 'Show chart' });
  if (closed) await userEvent.click(closed);
  await userEvent.click(screen.getByRole('button', { name: 'In this comparison' }));
}
const nextButton = () => within(nav()).getByRole('button', { name: 'Next' });
const prevButton = () => within(nav()).getByRole('button', { name: 'Previous' });

const expectNoBackendCalls = () => {
  expect(global.fetch).not.toHaveBeenCalled();
  Object.values(api).forEach((fn) => {
    if (typeof fn === 'function' && 'mock' in fn) expect(fn).not.toHaveBeenCalled();
  });
};

beforeEach(() => {
  vi.clearAllMocks();
  global.fetch = vi.fn(() =>
    Promise.resolve({ ok: true, json: () => Promise.resolve({}) })
  );
});

afterEach(() => {
  delete global.fetch;
});

describe('SearchResults — default page', () => {
  it('renders only the first 50 of 237 results by default', () => {
    renderResults();
    expect(countRows()).toBe(50);
    expect(screen.getByText('a-src-1')).toBeInTheDocument();
    expect(screen.getByText('a-src-50')).toBeInTheDocument();
    expect(screen.queryByText('a-src-51')).not.toBeInTheDocument();
  });

  it('summarises the visible range', () => {
    renderResults();
    expect(screen.getByText('Showing 1–50 of 237 results')).toBeInTheDocument();
  });

  it('numbers rows from 1 on the first page', () => {
    renderResults();
    expect(rowNumbers()[0]).toBe(1);
    expect(rowNumbers()[49]).toBe(50);
  });
});

describe('SearchResults — navigation', () => {
  it('shows the next subset when Next is clicked', async () => {
    renderResults();
    await userEvent.click(nextButton());

    expect(countRows()).toBe(50);
    expect(screen.getByText('a-src-51')).toBeInTheDocument();
    expect(screen.getByText('a-src-100')).toBeInTheDocument();
    expect(screen.queryByText('a-src-50')).not.toBeInTheDocument();
    expect(screen.getByText('Showing 51–100 of 237 results')).toBeInTheDocument();
  });

  it('continues row numbering across pages', async () => {
    renderResults();
    await userEvent.click(nextButton());
    expect(rowNumbers()[0]).toBe(51);
    expect(rowNumbers()[49]).toBe(100);
  });

  it('returns to the previous subset when Previous is clicked', async () => {
    renderResults();
    await userEvent.click(nextButton());
    await userEvent.click(prevButton());
    expect(screen.getByText('a-src-1')).toBeInTheDocument();
    expect(screen.getByText('Showing 1–50 of 237 results')).toBeInTheDocument();
  });

  it('renders the remainder on the final page', async () => {
    renderResults();
    await userEvent.click(within(nav()).getByRole('button', { name: 'Go to page 5' }));
    expect(countRows()).toBe(37);
    expect(screen.getByText('a-src-237')).toBeInTheDocument();
    expect(screen.getByText('Showing 201–237 of 237 results')).toBeInTheDocument();
    expect(nextButton()).toBeDisabled();
  });

  it('preserves result ordering across every page', async () => {
    renderResults();
    const seen = [];
    for (let page = 1; page <= 5; page += 1) {
      if (page > 1) {
        await userEvent.click(within(nav()).getByRole('button', { name: `Go to page ${page}` }));
      }
      seen.push(...rowNumbers());
    }
    expect(seen).toEqual(Array.from({ length: 237 }, (_, i) => i + 1));
  });
});

describe('SearchResults — page size', () => {
  it('shows 10 rows when 10 is selected', async () => {
    render(<PageSizeHarness />);
    await selectPageSize('10');
    expect(countRows()).toBe(10);
    expect(screen.getByText('Showing 1–10 of 237 results')).toBeInTheDocument();
  });

  it('shows 20 rows when 20 is selected', async () => {
    render(<PageSizeHarness />);
    await selectPageSize('20');
    expect(countRows()).toBe(20);
    expect(screen.getByText('Showing 1–20 of 237 results')).toBeInTheDocument();
  });

  it('shows at most 100 rows when 100 is selected', async () => {
    render(<PageSizeHarness />);
    await selectPageSize('100');
    expect(countRows()).toBe(100);
    expect(screen.getByText('Showing 1–100 of 237 results')).toBeInTheDocument();
  });

  it('returns to page 1 when the page size changes', async () => {
    render(<PageSizeHarness />);
    await userEvent.click(nextButton());
    expect(screen.getByText('Showing 51–100 of 237 results')).toBeInTheDocument();

    await selectPageSize('20');
    expect(screen.getByText('Showing 1–20 of 237 results')).toBeInTheDocument();
    expect(countRows()).toBe(20);
  });
});

describe('SearchResults — no backend traffic during pagination', () => {
  it('issues no request when moving to the next page', async () => {
    renderResults();
    await userEvent.click(nextButton());
    expectNoBackendCalls();
  });

  it('issues no request when moving to the previous page', async () => {
    renderResults();
    await userEvent.click(nextButton());
    await userEvent.click(prevButton());
    expectNoBackendCalls();
  });

  it('issues no request when selecting a numbered page', async () => {
    renderResults();
    await userEvent.click(within(nav()).getByRole('button', { name: 'Go to page 4' }));
    expectNoBackendCalls();
  });

  it('issues no request when changing the page size', async () => {
    render(<PageSizeHarness />);
    await selectPageSize('100');
    await selectPageSize('10');
    expectNoBackendCalls();
  });
});

describe('SearchResults — reset behaviour', () => {
  it('returns to page 1 when a new search delivers a different result set', async () => {
    const { rerender } = renderResults();
    await userEvent.click(within(nav()).getByRole('button', { name: 'Go to page 4' }));
    expect(screen.getByText('Showing 151–200 of 237 results')).toBeInTheDocument();

    rerender(
      <SearchResults {...baseProps} searchRunId={2} results={makeResults(80, 'b')} />
    );

    expect(screen.getByText('Showing 1–50 of 80 results')).toBeInTheDocument();
    expect(screen.getByText('b-src-1')).toBeInTheDocument();
  });

  it('returns to page 1 when a new search returns the SAME result count', async () => {
    const { rerender } = renderResults();
    await userEvent.click(within(nav()).getByRole('button', { name: 'Go to page 4' }));
    expect(screen.getByText('Showing 151–200 of 237 results')).toBeInTheDocument();

    // Same length, brand new set — only searchRunId distinguishes them.
    rerender(
      <SearchResults {...baseProps} searchRunId={2} results={makeResults(237, 'b')} />
    );

    expect(screen.getByText('Showing 1–50 of 237 results')).toBeInTheDocument();
    expect(screen.getByText('b-src-1')).toBeInTheDocument();
    expect(rowNumbers()[0]).toBe(1);
  });

  it('returns to page 1 when a chart filter is applied', async () => {
    render(<SearchResults {...baseProps} results={makeBookedResults(237)} />);
    await userEvent.click(within(nav()).getByRole('button', { name: 'Go to page 3' }));
    expect(screen.getByText('Showing 101–150 of 237 results')).toBeInTheDocument();

    await openChart();
    await userEvent.click(screen.getByTestId('mock-chart-bar'));

    // Filter narrowed 237 -> the 100 results in Book 1, and the page reset.
    expect(screen.getByText('Showing 1–50 of 100 results')).toBeInTheDocument();
    expect(rowNumbers()[0]).toBe(1);
    expectNoBackendCalls();
  });

  it('returns to page 1 when a chart filter is cleared', async () => {
    render(<SearchResults {...baseProps} results={makeBookedResults(237)} />);
    await openChart();
    await userEvent.click(screen.getByTestId('mock-chart-bar'));
    expect(screen.getByText('Showing 1–50 of 100 results')).toBeInTheDocument();

    await userEvent.click(within(nav()).getByRole('button', { name: 'Go to page 2' }));
    expect(screen.getByText('Showing 51–100 of 100 results')).toBeInTheDocument();

    await userEvent.click(screen.getByRole('button', { name: 'Clear Filter' }));

    expect(screen.getByText('Showing 1–50 of 237 results')).toBeInTheDocument();
    expectNoBackendCalls();
  });

  it('returns to page 1 when the sort order changes', async () => {
    const { rerender } = renderResults();
    await userEvent.click(within(nav()).getByRole('button', { name: 'Go to page 3' }));
    expect(screen.getByText('Showing 101–150 of 237 results')).toBeInTheDocument();

    rerender(
      <SearchResults {...baseProps} results={makeResults(237)} sortBy="source_locus" />
    );

    expect(screen.getByText('Showing 1–50 of 237 results')).toBeInTheDocument();
  });
});

describe('SearchResults — fusion streaming', () => {
  const streaming = {
    loading: true,
    fusionProgress: { phase: 'line', batchIndex: 2, batchTotal: 9, channelsDone: ['lemma', 'exact'] },
  };

  it('shows the live total but holds page 1 while results stream in', () => {
    const { rerender } = render(
      <SearchResults {...baseProps} {...streaming} results={makeResults(120)} />
    );
    expect(screen.getByText('Showing 1–50 of 120 results')).toBeInTheDocument();

    // Next intermediate SSE event delivers a larger set.
    rerender(<SearchResults {...baseProps} {...streaming} results={makeResults(400)} />);
    expect(screen.getByText('Showing 1–50 of 400 results')).toBeInTheDocument();
    expect(rowNumbers()[0]).toBe(1);
    expect(countRows()).toBe(50);
  });

  it('disables navigation until the search completes', () => {
    render(<SearchResults {...baseProps} {...streaming} results={makeResults(237)} />);
    expect(nextButton()).toBeDisabled();
    expect(within(nav()).getByRole('button', { name: 'Go to page 3' })).toBeDisabled();
  });

  it('never renders a slice past the end of a shrinking streamed set', () => {
    const { rerender } = render(
      <SearchResults {...baseProps} {...streaming} results={makeResults(400)} />
    );
    // Re-fusion can drop candidates between events.
    rerender(<SearchResults {...baseProps} {...streaming} results={makeResults(12)} />);
    expect(countRows()).toBe(12);
    expect(screen.queryByRole('navigation')).not.toBeInTheDocument();
  });

  it('becomes interactive once loading finishes', async () => {
    const { rerender } = render(
      <SearchResults {...baseProps} {...streaming} results={makeResults(237)} />
    );
    rerender(<SearchResults {...baseProps} results={makeResults(237)} />);
    expect(nextButton()).toBeEnabled();
    await userEvent.click(nextButton());
    expect(screen.getByText('Showing 51–100 of 237 results')).toBeInTheDocument();
    expectNoBackendCalls();
  });
});

describe('SearchResults — zero results', () => {
  it('renders no pagination and no invalid range', () => {
    const { container } = render(
      <SearchResults {...baseProps} results={[]} />
    );
    expect(container).toBeEmptyDOMElement();
    expect(screen.queryByText(/Showing/)).not.toBeInTheDocument();
    expect(screen.queryByRole('navigation')).not.toBeInTheDocument();
  });

  it('renders no pagination when the total fits on one page', () => {
    render(<SearchResults {...baseProps} results={makeResults(30)} />);
    expect(screen.queryByRole('navigation')).not.toBeInTheDocument();
    expect(screen.getByText('Showing 1–30 of 30 results')).toBeInTheDocument();
    expect(countRows()).toBe(30);
  });
});

describe('SearchResults — export scope', () => {
  it('exports every result, not just the visible page', async () => {
    const createObjectURL = vi.fn(() => 'blob:mock');
    const revokeObjectURL = vi.fn();
    global.URL.createObjectURL = createObjectURL;
    global.URL.revokeObjectURL = revokeObjectURL;
    // Anchor clicks would trigger jsdom navigation; swallow them.
    const clickSpy = vi
      .spyOn(HTMLAnchorElement.prototype, 'click')
      .mockImplementation(() => {});

    let capturedCsv = '';
    const BlobOriginal = global.Blob;
    global.Blob = class extends BlobOriginal {
      constructor(parts, opts) {
        capturedCsv = parts.join('');
        super(parts, opts);
      }
    };

    renderResults();
    await userEvent.click(screen.getByRole('button', { name: 'Export CSV' }));

    const dataRows = capturedCsv.trim().split('\n').slice(1); // drop header
    expect(dataRows).toHaveLength(237);
    expect(capturedCsv).toContain('a-src-1');
    expect(capturedCsv).toContain('a-src-237'); // well past the visible 50

    global.Blob = BlobOriginal;
    clickSpy.mockRestore();
  });
});
