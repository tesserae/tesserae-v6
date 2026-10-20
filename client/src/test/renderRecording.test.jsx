/**
 * The front end's golden check (cleaning job H4, 2026-10-13).
 *
 * Renders SearchResults in each of its modes and App on every page the router
 * knows, with fetch answering from fixed fixtures (renderFixtures.js), and
 * snapshots the HTML. The snapshots were recorded on main BEFORE the files
 * were split; a split that changes any of them has changed what a visitor
 * sees. Generated ids and dates are normalized first. The chart library is
 * stubbed as in the other SearchResults tests (jsdom has no canvas).
 */
import { useState } from 'react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor, act, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

vi.mock('react-chartjs-2', async () => {
  const { forwardRef, createElement } = await vi.importActual('react');
  return {
    Bar: forwardRef(({ data, options }, ref) =>
      createElement('button', {
        ref,
        'data-testid': 'mock-chart-bar',
        'data-labels': JSON.stringify(data?.labels || []),
        'data-counts': JSON.stringify(data?.datasets?.[0]?.data || []),
        'data-colors': JSON.stringify(data?.datasets?.[0]?.backgroundColor || ''),
        'data-title': JSON.stringify(options?.plugins?.title?.text || ''),
        onClick: () => options?.onClick?.(null, [{ index: 0 }]),
      }, 'chart bar 0')),
    Line: forwardRef(() => null),
    Doughnut: forwardRef(() => null),
    Pie: forwardRef(() => null),
  };
});
vi.mock('chart.js', () => ({
  Chart: { register: () => {} },
  CategoryScale: {}, LinearScale: {}, BarElement: {}, Title: {}, Tooltip: {}, Legend: {},
  PointElement: {}, LineElement: {}, ArcElement: {}, Filler: {},
}));

import SearchResults from '../components/search/SearchResults';
import App from '../App';
import { makeRows, SOURCE_INFO, TARGET_INFO, LINE_SEARCH_REPLY } from './renderFixtures';

const json = (data, ok = true) => ({
  ok, status: ok ? 200 : 401,
  json: () => Promise.resolve(data),
  text: () => Promise.resolve(JSON.stringify(data)),
});

// Fixed replies for every endpoint these screens ask for. Anything not listed
// gets an empty object, as in the other App tests.
const TEXTS = [
  { id: 'vergil.aeneid.part.1.tess', author: 'Vergil', title: 'Aeneid 1', line_count: 756, language: 'la' },
  { id: 'lucan.bellum_civile.part.1.tess', author: 'Lucan', title: 'Civil War 1', line_count: 700, language: 'la' },
];
const routeFetch = (url, init) => {
  const u = String(url);
  if (u.startsWith('/api/line-search')) return Promise.resolve(json(LINE_SEARCH_REPLY));
  if (u.startsWith('/api/passages/pair-lift')) return Promise.resolve(json({ results: [] }));
  if (u.startsWith('/api/requests')) return Promise.resolve(json({ open: [{ number: 7, title: 'A fixed open request', labels: [] }], done: [] }));
  if (u.startsWith('/api/texts?language=')) return Promise.resolve(json(TEXTS));
  if (u.startsWith('/api/authors')) return Promise.resolve(json([]));
  if (u.startsWith('/api/languages')) {
    return Promise.resolve(json({ languages: [{ code: 'la', label: 'Latin' }, { code: 'grc', label: 'Greek' }, { code: 'en', label: 'English' }, { code: 'cop', label: 'Coptic' }] }));
  }
  if (u.startsWith('/api/admin/me')) return Promise.resolve(json({}, false));
  if (u.startsWith('/api/auth/user')) return Promise.resolve(json({ user: null }));
  if (u.startsWith('/api/version')) return Promise.resolve(json({ bundle: null }));
  if (u.startsWith('/api/assistant/status')) return Promise.resolve(json({ available: false }));
  // The things pages open in every view since 2026-10-20, so they render here:
  // empty lists, and a record that is not found.
  if (/^\/api\/(events|coins|objects)\/[^/?]+/.test(u)) return Promise.resolve(json({ error: 'Not found' }, false));
  if (u.startsWith('/api/events')) return Promise.resolve(json({ events: [], total: 0, total_all: 0, types: [], centuries: [], type_counts: {} }));
  if (u.startsWith('/api/coins')) return Promise.resolve(json({ coins: [], results: [], total: 0, facets: {} }));
  if (u.startsWith('/api/objects')) return Promise.resolve(json({ objects: [], results: [], total: 0, facets: {} }));
  void init;
  return Promise.resolve(json({}));
};

// Dates and generated ids out, one tag per line in.
const normalize = (html) => html
  .replace(/\d{4}-\d{2}-\d{2}/g, 'DATE')
  .replace(/:r[0-9a-z]+:/g, ':rID:')
  .replace(/Exported [^<·]*·/g, 'Exported TIME ·')
  .replace(/></g, '>\n<');

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const settle = async (container, { max = 30 } = {}) => {
  let last = null;
  let same = 0;
  for (let i = 0; i < max && same < 3; i += 1) {
    await act(async () => { await sleep(20); });
    const now = container.innerHTML;
    same = now === last ? same + 1 : 0;
    last = now;
  }
};

beforeEach(() => {
  global.fetch = vi.fn(routeFetch);
  window.localStorage.clear();
  window.sessionStorage.clear();
  window.history.replaceState({}, '', '/');
});
afterEach(() => {
  vi.restoreAllMocks();
  window.localStorage.clear();
  window.sessionStorage.clear();
  window.history.replaceState({}, '', '/');
});

const ALL = makeRows();
const byLocus = [...ALL].sort((a, b) => String(a.source_locus).localeCompare(String(b.source_locus)));

const Harness = ({ rows = ALL, sortBy: initialSort = 'score', pageSize: initialSize = 50, language = 'la', ...rest }) => {
  const [pageSize, setPageSize] = useState(initialSize);
  const [sortBy, setSortBy] = useState(initialSort);
  return (
    <SearchResults
      results={rows}
      loading={false}
      error={null}
      pageSize={pageSize}
      onPageSizeChange={setPageSize}
      searchRunId={1}
      sortBy={sortBy}
      setSortBy={setSortBy}
      searchStats={{ total_matches: 4821, elapsed_time: 3.2, source_lines: 756, target_lines: 700, corpus_version: 'v-fixed' }}
      language={language}
      sourceTextInfo={SOURCE_INFO}
      targetTextInfo={TARGET_INFO}
      onRegister={() => {}}
      onCorpusSearch={() => {}}
      onOpenHelp={() => {}}
      onRerunFresh={() => {}}
      {...rest}
    />
  );
};

const hideChart = () => window.sessionStorage.setItem('tess_show_dist_chart', 'false');

describe('SearchResults render recording', () => {
  it('sorted by score, chart hidden', async () => {
    hideChart();
    const { container } = render(<Harness />);
    await settle(container);
    expect(normalize(container.innerHTML)).toMatchSnapshot();
  });

  it('sorted by locus, chart hidden', async () => {
    hideChart();
    const { container } = render(<Harness rows={byLocus} sortBy="source_locus" />);
    await settle(container);
    expect(normalize(container.innerHTML)).toMatchSnapshot();
  });

  it('paged: page 1 and page 2 of 10', async () => {
    hideChart();
    const { container } = render(<Harness pageSize={10} />);
    await settle(container);
    expect(normalize(container.innerHTML)).toMatchSnapshot('page 1');
    fireEvent.click(screen.getAllByRole('button', { name: /^Next/ })[0]);
    await settle(container);
    expect(normalize(container.innerHTML)).toMatchSnapshot('page 2');
  });

  it('chart open, In this comparison, source and target views, and a bar filter', async () => {
    const { container } = render(<Harness />);
    await settle(container);
    await userEvent.click(screen.getByRole('button', { name: 'In this comparison' }));
    await settle(container);
    expect(normalize(container.innerHTML)).toMatchSnapshot('target view');
    await userEvent.click(screen.getByRole('button', { name: 'Source' }));
    await settle(container);
    expect(normalize(container.innerHTML)).toMatchSnapshot('source view');
    await userEvent.click(screen.getByTestId('mock-chart-bar'));
    await settle(container);
    expect(normalize(container.innerHTML)).toMatchSnapshot('after a bar is clicked');
  });

  it('chart open, server mode with the server aggregates', async () => {
    const resultSet = {
      id: 'a'.repeat(32), total: 237, pageSize: 50, firstPage: ALL,
      aggregates: { distribution: {
        target: { mode: 'book', labels: ['Book 1', 'Book 2'], counts: [100, 137] },
        source: { mode: 'line', band: 25, labels: ['1–25', '26–50'], counts: [200, 37] },
      } },
    };
    const { container } = render(<Harness resultSet={resultSet} />);
    await settle(container);
    await userEvent.click(screen.getByRole('button', { name: 'In this comparison' }));
    await settle(container);
    expect(normalize(container.innerHTML)).toMatchSnapshot();
  });

  it('corpus panel: timeline, era, work, and a clicked author', async () => {
    const { container } = render(<Harness />);
    await settle(container);
    expect(normalize(container.innerHTML)).toMatchSnapshot('timeline');
    await userEvent.click(screen.getByRole('button', { name: 'Era' }));
    await settle(container);
    expect(normalize(container.innerHTML)).toMatchSnapshot('era');
    await userEvent.click(screen.getByRole('button', { name: 'Work' }));
    await settle(container);
    expect(normalize(container.innerHTML)).toMatchSnapshot('work');
    await userEvent.click(screen.getByTestId('mock-chart-bar'));
    await settle(container);
    expect(normalize(container.innerHTML)).toMatchSnapshot('work, first bar clicked, instances listed');
  });

  it('corpus panel on a pair that shares one word', async () => {
    const one = ALL.slice(10, 11);
    const { container } = render(<Harness rows={one.map((r) => ({ ...r, matched_words: [r.matched_words[0]] }))} />);
    await settle(container);
    expect(normalize(container.innerHTML)).toMatchSnapshot();
  });

  it('export CSV file contents', async () => {
    hideChart();
    let blob = null;
    window.URL.createObjectURL = (b) => { blob = b; return 'blob:fixed'; };
    window.URL.revokeObjectURL = () => {};
    vi.spyOn(window.HTMLAnchorElement.prototype, 'click').mockImplementation(function click() { void this; });
    const { container } = render(<Harness />);
    await settle(container);
    await userEvent.click(screen.getByRole('button', { name: 'Export CSV' }));
    await waitFor(() => expect(blob).not.toBeNull());
    const text = await new Promise((resolve) => { const fr = new FileReader(); fr.onload = () => resolve(fr.result); fr.readAsText(blob); });
    expect(text).toMatchSnapshot();
  });

  it('export PDF document, Latin and Coptic', async () => {
    hideChart();
    for (const language of ['la', 'cop', 'fa']) {
      const written = [];
      vi.spyOn(window, 'open').mockImplementation(() => ({ document: { open() {}, write: (h) => written.push(h), close() {} } }));
      const { container, unmount } = render(<Harness language={language} />);
      await settle(container);
      await userEvent.click(screen.getByRole('button', { name: 'Export PDF' }));
      await waitFor(() => expect(written.length).toBe(1));
      expect(normalize(written[0])).toMatchSnapshot(language);
      unmount();
      vi.restoreAllMocks();
    }
  });

  it.each(['grc', 'cop', 'fa', 'ur', 'he', 'en'])('language %s, first ten rows', async (language) => {
    hideChart();
    const { container } = render(<Harness language={language} rows={ALL.slice(17, 30)} pageSize={50} />);
    await settle(container);
    expect(normalize(container.innerHTML)).toMatchSnapshot();
  });

  it('streaming: partial results with a progress banner, then paused', async () => {
    hideChart();
    const progress = { phase: 'window', batchTotal: 8, batchIndex: 3, currentChannel: 'lemma', totalMatches: 1200, resultCount: 30 };
    const { container } = render(<Harness loading fusionProgress={progress} progressText="Searching..." elapsedTime={42} />);
    await settle(container);
    expect(normalize(container.innerHTML)).toMatchSnapshot('partial');
    await userEvent.click(screen.getByRole('button', { name: 'Pause' }));
    await settle(container);
    expect(normalize(container.innerHTML)).toMatchSnapshot('paused');
  });

  it('loading, queued, error and empty states', async () => {
    const states = [
      ['loading', { rows: [], loading: true, matchType: 'fusion', elapsedTime: 12, progressText: 'Reading texts' }],
      ['queued', { rows: [], loading: true, isQueued: true, queuedMessage: 'Position 2' }],
      ['error', { rows: [], error: 'Something broke' }],
      ['empty', { rows: [] }],
    ];
    for (const [name, props] of states) {
      const { container, unmount } = render(<Harness {...props} />);
      await settle(container);
      expect(normalize(container.innerHTML)).toMatchSnapshot(name);
      unmount();
    }
  });
});

describe('App render recording', () => {
  const PATHS = ['/', '/read', '/document', '/theme-search', '/ask-a-work', '/inscriptions-papyri', '/events', '/events/e1', '/coins', '/coins/c1',
    '/objects', '/objects/o1', '/browse', '/corpus', '/repository', '/line-search', '/string-search', '/visualize', '/downloads', '/about', '/help',
    '/privacy', '/research', '/blog-archive', '/text-credits', '/requests', '/admin', '/no-such-page'];

  it.each(PATHS)('page %s', async (path) => {
    window.history.replaceState({}, '', path);
    const { container } = render(<App />);
    await settle(container, { max: 60 });
    // The blog archive loads its posts through a dynamic import, which on a
    // busy machine can outlast the settle window and leave an empty list in
    // the recording (2026-10-16). Wait for the first post, then settle again.
    if (path === '/blog-archive') {
      await screen.findByText('A Greek to Latin Dictionary', {}, { timeout: 15000 });
      await settle(container, { max: 60 });
    }
    expect(window.location.pathname).toMatchSnapshot('address after load');
    expect(normalize(container.innerHTML)).toMatchSnapshot();
  });

  it('page / in History view', async () => {
    window.localStorage.setItem('tesserae_view', 'history');
    const { container } = render(<App />);
    await settle(container, { max: 60 });
    expect(window.location.pathname).toMatchSnapshot('address after load');
    expect(normalize(container.innerHTML)).toMatchSnapshot();
  });
});
