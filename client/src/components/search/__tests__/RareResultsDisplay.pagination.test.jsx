import { useState } from 'react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

// Chart.js needs a real canvas, which jsdom does not provide.
vi.mock('react-chartjs-2', () => ({ Bar: () => <div data-testid="mock-chart" /> }));
vi.mock('chart.js', () => ({
  Chart: { register: () => {} },
  CategoryScale: {}, LinearScale: {}, BarElement: {},
  Title: {}, Tooltip: {}, Legend: {},
}));

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
import RareResultsDisplay from '../RareResultsDisplay';

/** Shaped like /api/hapax-search results (backend/blueprints/hapax.py:1732-1741). */
const makeHapax = (n, tag = 'h') =>
  Array.from({ length: n }, (_, i) => ({
    lemma: `${tag}lemma${i + 1}`,
    display_form: `${tag}word${i + 1}`,
    corpus_count: i + 1,
    rarity: (n - i) / n,
    is_proper_noun: false,
    source_occurrences: 1,
    target_occurrences: 1,
    source_locations: [{ ref: `src.${i + 1}`, text: `source ${i + 1}`, text_id: 'a.tess' }],
    target_locations: [{ ref: `tgt.${i + 1}`, text: `target ${i + 1}`, text_id: 'b.tess' }],
  }));

/** Shaped like /api/rare-bigram-search results. */
const makeBigrams = (n, tag = 'b') =>
  Array.from({ length: n }, (_, i) => ({
    bigram: `${tag}pair${i + 1}`,
    display_form: `${tag}pair${i + 1}`,
    word1: `${tag}one${i + 1}`,
    word2: `${tag}two${i + 1}`,
    rarity: (n - i) / n,
    source_occurrences: 1,
    target_occurrences: 1,
    source_locations: [{ ref: `src.${i + 1}`, text: `source ${i + 1}`, text_id: 'a.tess' }],
    target_locations: [{ ref: `tgt.${i + 1}`, text: `target ${i + 1}`, text_id: 'b.tess' }],
  }));

const baseProps = {
  loading: false,
  error: null,
  pageSize: 50,
  onPageSizeChange: () => {},
  searchRunId: 1,
  searchMode: 'hapax',
  sourceText: 'vergil.aeneid.part.1.tess',
  targetText: 'lucan.bellum_civile.part.1.tess',
  language: 'la',
};

const PageSizeHarness = ({ results = makeHapax(237), ...props }) => {
  const [pageSize, setPageSize] = useState(50);
  return (
    <RareResultsDisplay
      {...baseProps}
      results={results}
      pageSize={pageSize}
      onPageSizeChange={setPageSize}
      {...props}
    />
  );
};

const countRows = () => screen.getAllByText(/^\d+\.$/).length;
const rowNumbers = () => screen.getAllByText(/^\d+\.$/).map((el) => parseInt(el.textContent, 10));

const nav = () => screen.getAllByRole('navigation', { name: 'Search results pagination' })[0];
const nextButton = () => within(nav()).getByRole('button', { name: 'Next' });
const goToPage = (n) => userEvent.click(within(nav()).getByRole('button', { name: `Go to page ${n}` }));
const selectPageSize = (v) =>
  userEvent.selectOptions(screen.getAllByRole('combobox', { name: 'Show' })[0], v);

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

describe('RareResultsDisplay — default page', () => {
  it('renders only the first 50 rare words by default', () => {
    render(<RareResultsDisplay {...baseProps} results={makeHapax(237)} />);
    expect(countRows()).toBe(50);
    expect(screen.getByText('Showing 1–50 of 237 rare words')).toBeInTheDocument();
  });

  it('labels rare pairs distinctly', () => {
    render(
      <RareResultsDisplay {...baseProps} searchMode="bigram" results={makeBigrams(237)} />
    );
    expect(screen.getByText('Showing 1–50 of 237 rare pairs')).toBeInTheDocument();
  });
});

describe('RareResultsDisplay — page size', () => {
  it.each([
    ['10', 10],
    ['20', 20],
    ['100', 100],
  ])('shows %s rows when %s is selected', async (value, expected) => {
    render(<PageSizeHarness />);
    await selectPageSize(value);
    expect(countRows()).toBe(expected);
  });

  it('offers exactly 10, 20, 50 and 100', () => {
    render(<PageSizeHarness />);
    const values = within(screen.getAllByRole('combobox', { name: 'Show' })[0])
      .getAllByRole('option')
      .map((o) => o.value);
    expect(values).toEqual(['10', '20', '50', '100']);
  });

  it('returns to page 1 when the page size changes', async () => {
    render(<PageSizeHarness />);
    await userEvent.click(nextButton());
    expect(screen.getByText('Showing 51–100 of 237 rare words')).toBeInTheDocument();
    await selectPageSize('10');
    expect(screen.getByText('Showing 1–10 of 237 rare words')).toBeInTheDocument();
  });
});

describe('RareResultsDisplay — navigation is local', () => {
  it('pages without any backend request', async () => {
    render(<PageSizeHarness />);
    await userEvent.click(nextButton());
    await goToPage(4);
    await userEvent.click(within(nav()).getByRole('button', { name: 'Previous' }));
    await selectPageSize('20');
    expectNoBackendCalls();
  });

  it('renders the correct remainder on the final page', async () => {
    render(<RareResultsDisplay {...baseProps} results={makeHapax(237)} />);
    await goToPage(5);
    expect(countRows()).toBe(37);
    expect(screen.getByText('Showing 201–237 of 237 rare words')).toBeInTheDocument();
    expect(nextButton()).toBeDisabled();
  });

  it('preserves sorted order across every page', async () => {
    render(<RareResultsDisplay {...baseProps} results={makeHapax(237)} />);
    const seen = [];
    for (let page = 1; page <= 5; page += 1) {
      if (page > 1) await goToPage(page);
      seen.push(...rowNumbers());
    }
    expect(seen).toEqual(Array.from({ length: 237 }, (_, i) => i + 1));
  });

  it('continues row numbering across pages', async () => {
    render(<RareResultsDisplay {...baseProps} results={makeHapax(237)} />);
    await userEvent.click(nextButton());
    expect(rowNumbers()[0]).toBe(51);
    expect(rowNumbers()[49]).toBe(100);
  });
});

describe('RareResultsDisplay — reset behaviour', () => {
  it('returns to page 1 for a new rare-word search', async () => {
    const { rerender } = render(
      <RareResultsDisplay {...baseProps} results={makeHapax(237)} />
    );
    await goToPage(4);
    expect(screen.getByText('Showing 151–200 of 237 rare words')).toBeInTheDocument();

    rerender(
      <RareResultsDisplay {...baseProps} searchRunId={2} results={makeHapax(237, 'x')} />
    );
    expect(screen.getByText('Showing 1–50 of 237 rare words')).toBeInTheDocument();
    expect(rowNumbers()[0]).toBe(1);
  });

  it('returns to page 1 for a new rare-pair search', async () => {
    const { rerender } = render(
      <RareResultsDisplay {...baseProps} searchMode="bigram" results={makeBigrams(237)} />
    );
    await goToPage(3);
    expect(screen.getByText('Showing 101–150 of 237 rare pairs')).toBeInTheDocument();

    rerender(
      <RareResultsDisplay
        {...baseProps}
        searchMode="bigram"
        searchRunId={2}
        results={makeBigrams(237, 'y')}
      />
    );
    expect(screen.getByText('Showing 1–50 of 237 rare pairs')).toBeInTheDocument();
  });

  it('returns to page 1 when switching between rare words and rare pairs', async () => {
    const { rerender } = render(
      <RareResultsDisplay {...baseProps} results={makeHapax(237)} />
    );
    await goToPage(4);
    expect(screen.getByText('Showing 151–200 of 237 rare words')).toBeInTheDocument();

    rerender(
      <RareResultsDisplay {...baseProps} searchMode="bigram" results={makeBigrams(237)} />
    );
    expect(screen.getByText('Showing 1–50 of 237 rare pairs')).toBeInTheDocument();
  });
});

describe('RareResultsDisplay — sort reset', () => {
  // The Sort control renders only for rare pairs (RareResultsDisplay.jsx:417).
  // It has no accessible name, so pick it out by its option values.
  const sortSelect = () =>
    screen.getAllByRole('combobox').find((s) =>
      [...s.options].some((o) => o.value === 'rarity')
    );

  it('returns to page 1 when the rare-pair sort order changes', async () => {
    render(<RareResultsDisplay {...baseProps} searchMode="bigram" results={makeBigrams(237)} />);
    await goToPage(3);
    expect(screen.getByText('Showing 101–150 of 237 rare pairs')).toBeInTheDocument();

    await userEvent.selectOptions(sortSelect(), 'occurrence');

    expect(screen.getByText('Showing 1–50 of 237 rare pairs')).toBeInTheDocument();
    expect(rowNumbers()[0]).toBe(1);
    expectNoBackendCalls();
  });
});

describe('RareResultsDisplay — export scope', () => {
  it('exports every rare word, not just the visible page', async () => {
    global.URL.createObjectURL = vi.fn(() => 'blob:mock');
    global.URL.revokeObjectURL = vi.fn();
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

    render(<RareResultsDisplay {...baseProps} results={makeHapax(237)} />);
    expect(countRows()).toBe(50);

    await userEvent.click(screen.getByRole('button', { name: 'Export CSV' }));

    const dataRows = capturedCsv.trim().split('\n').slice(1); // drop header
    expect(dataRows).toHaveLength(237);
    expect(capturedCsv).toContain('hlemma1');
    expect(capturedCsv).toContain('hlemma237'); // well past the visible 50

    global.Blob = BlobOriginal;
    clickSpy.mockRestore();
  });
});

describe('RareResultsDisplay — edge cases', () => {
  it('shows the empty-state message and no pagination for zero results', () => {
    render(<RareResultsDisplay {...baseProps} results={[]} />);
    expect(screen.getByText(/No shared rare words found/)).toBeInTheDocument();
    expect(screen.queryByText(/Showing/)).not.toBeInTheDocument();
    expect(screen.queryByRole('navigation')).not.toBeInTheDocument();
  });

  it('shows the summary but no navigation when everything fits on one page', () => {
    render(<RareResultsDisplay {...baseProps} results={makeHapax(30)} />);
    expect(screen.queryByRole('navigation')).not.toBeInTheDocument();
    expect(screen.getByText('Showing 1–30 of 30 rare words')).toBeInTheDocument();
    expect(countRows()).toBe(30);
  });
});
