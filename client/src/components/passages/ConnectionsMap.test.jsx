/**
 * The connections map: a labeled canvas heatmap over /api/passages/map,
 * drilling down to /api/passages/map/cell (work pairs behind one cell) and
 * /api/passages/map/pair (passage pairs behind one work pair), plus a
 * "start from one work" picker over /api/passages/works +
 * /api/passages/map/work.
 *
 * jsdom does not implement a real canvas 2D context, so the draw pass
 * itself is not exercised here (LabeledHeatmap guards it with
 * `if (!ctx) return`); what is pinned down is the data flow -- which
 * endpoint each control fetches, that click/hover coordinate math resolves
 * to the right grid cell once row/column label margins are accounted for,
 * and that the response reaches the screen.
 */
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import ConnectionsMap, { columnLabelsNeedRotation } from './ConnectionsMap';

const MAP_PAYLOAD = {
  view: 'author', languages: null, translations: false, top: 50,
  labels: ['Homer (grc)', 'Vergil (la)'],
  ids: ['homer::grc', 'vergil::la'],
  entity_languages: ['grc', 'la'],
  counts: [[0, 6], [6, 0]],
  normalised: [[0, 1], [1, 0]],
  legend: { low: 6, mid: 6, high: 6 },
  translation_pairs_hidden: 1,
  index_fingerprint: 'abc',
};

// Every map response now carries cache_built_at whether or not the backend
// cache is stale (NC, 2026-09-20) -- see mapBuiltFooterText in
// ConnectionsMap.jsx.
const BUILT_MAP_PAYLOAD = { ...MAP_PAYLOAD, cache_built_at: '2026-09-18T21:50:00' };

// `stale` itself still comes back from the API for an operator to read; this
// fixture carries it specifically to prove it never leaks into the UI (see
// 'never shows the word "stale" anywhere in the page' below).
const STALE_MAP_PAYLOAD = {
  ...BUILT_MAP_PAYLOAD,
  stale: {
    cache_built_at: '2026-09-18T21:50:00', cache_window_count: 603594,
    current_window_count: 603592, window_diff: 2,
  },
};

const CELL_PAYLOAD = {
  view: 'author', a: 'homer::grc', b: 'vergil::la',
  work_pairs: [
    { work_a: 'homer.iliad', work_b: 'vergil.aeneid', count: 6, is_translation: false },
  ],
  count: 1,
  // The second heatmap (NC, 2026-09-19): Homer's one work against Vergil's.
  works_matrix: {
    ids_a: ['homer.iliad'], labels_a: ['Homer, iliad'],
    ids_b: ['vergil.aeneid'], labels_b: ['Vergil, aeneid'],
    counts: [[6]], normalised: [[1]],
  },
};

// A century/genre-view cell has no works_matrix -- the flat list stays.
const CELL_PAYLOAD_NO_MATRIX = {
  view: 'genre', a: 'epic', b: 'didactic',
  work_pairs: [
    { work_a: 'homer.iliad', work_b: 'vergil.aeneid', count: 6, is_translation: false },
  ],
  count: 1,
  works_matrix: null,
};

// The third heatmap: books x books for one work pair.
const BOOKS_PAYLOAD = {
  work_a: 'homer.iliad', work_b: 'vergil.aeneid',
  ids_a: ['b1'], labels_a: ['1'],
  ids_b: ['b1'], labels_b: ['1'],
  counts: [[6]], normalised: [[1]],
};

const PAIR_PAYLOAD = {
  work_a: 'homer.iliad', work_b: 'vergil.aeneid', count: 1,
  pairs: [
    {
      score: 0.91,
      window_a: { window_id: 'grc-1', work: 'homer.iliad', title: 'Iliad', language: 'grc',
                  ref_start: '1.1', ref_end: '1.10', gist: 'Achilles rages.',
                  author_display: 'Homer',
                  reader_url: '/read?work=homer.iliad.tess&lang=grc&ref=1.1&refEnd=1.10&tab=similar' },
      window_b: { window_id: 'la-1', work: 'vergil.aeneid', title: 'Aeneid', language: 'la',
                  ref_start: '1.1', ref_end: '1.10', gist: 'Arms and the man.',
                  author_display: 'Vergil',
                  reader_url: '/read?work=vergil.aeneid.tess&lang=la&ref=1.1&refEnd=1.10&tab=similar' },
    },
  ],
};

const WORKS_PAYLOAD = { works: ['homer.iliad', 'vergil.aeneid'] };

const WORK_ROW_PAYLOAD = {
  work: 'homer.iliad', language: 'grc', author_display: 'Homer',
  window_count: 200, total_links: 15, count: 1,
  connections: [{ work: 'vergil.aeneid', language: 'la', author_display: 'Vergil',
                  count: 6, is_translation: false }],
};

function mockFetch(mapPayload = MAP_PAYLOAD, pairPayload = PAIR_PAYLOAD) {
  return vi.fn((url) => {
    if (url.startsWith('/api/passages/map/cell')) {
      const payload = url.includes('view=genre') || url.includes('view=century')
        ? CELL_PAYLOAD_NO_MATRIX : CELL_PAYLOAD;
      return Promise.resolve({ json: () => Promise.resolve(payload) });
    }
    if (url.startsWith('/api/passages/map/books')) {
      return Promise.resolve({ json: () => Promise.resolve(BOOKS_PAYLOAD) });
    }
    if (url.startsWith('/api/passages/map/pair')) {
      return Promise.resolve({ json: () => Promise.resolve(pairPayload) });
    }
    if (url.startsWith('/api/passages/map/work')) {
      return Promise.resolve({ json: () => Promise.resolve(WORK_ROW_PAYLOAD) });
    }
    if (url.startsWith('/api/passages/works')) {
      return Promise.resolve({ json: () => Promise.resolve(WORKS_PAYLOAD) });
    }
    if (url.startsWith('/api/passages/map')) {
      return Promise.resolve({ json: () => Promise.resolve(mapPayload) });
    }
    return Promise.resolve({ json: () => Promise.resolve({}) });
  });
}

// The cells canvas is SEPARATE from the (sticky) row-label canvas and from
// the frozen column-label strip, so its own coordinate space starts at x=0
// for column 0 and y=0 for row 0: no ROW_MARGIN and (since 2026-09-19, when
// the labels moved to their own strip) no column-margin offset either.
function cellCenter(cellSize, i, j) {
  return { clientX: j * cellSize + cellSize / 2,
           clientY: i * cellSize + cellSize / 2 };
}

beforeEach(() => {
  global.fetch = mockFetch();
  // jsdom returns an all-zero rect by default. LabeledHeatmap sets
  // canvas.width/height directly (the pixel buffer size) in its draw
  // effect, so returning THAT as the bounding rect keeps the test's
  // client-to-canvas scale factor at exactly 1, matching a real browser
  // where the canvas is never CSS-resized away from its pixel size.
  HTMLElement.prototype.getBoundingClientRect = function () {
    const w = this.width || 100;
    const h = this.height || 100;
    return { left: 0, top: 0, width: w, height: h, right: w, bottom: h };
  };
  // src/test/setup.js already stubs HTMLElement.prototype.scrollIntoView
  // with a no-op (jsdom implements neither) -- that stub sits CLOSER in the
  // prototype chain than Element.prototype for any HTMLElement instance, so
  // it must be the one replaced with a spy here, not Element.prototype.
  // A real matrix at a high "Top" setting can run to thousands of pixels
  // tall, so a click near row 0 appends its result far below the reader's
  // current scroll position -- indistinguishable from the click doing
  // nothing. The spy lets the fix (each drill-down section scrolling
  // itself into view once its data lands) be asserted on.
  window.HTMLElement.prototype.scrollIntoView = vi.fn();
});

afterEach(() => { vi.unstubAllGlobals(); });

describe('loading the map', () => {
  it('fetches /api/passages/map and shows the entity labels', async () => {
    render(<ConnectionsMap />);
    await waitFor(() => expect(screen.getByLabelText(/Connections map, author view/)).toBeTruthy());
    expect(global.fetch).toHaveBeenCalledWith(expect.stringContaining('/api/passages/map?'));
  });

  it('notes how many translation-pair links are hidden', async () => {
    render(<ConnectionsMap />);
    await waitFor(() => expect(screen.getByText(/translation-pair link hidden/)).toBeTruthy());
  });

  it('shows a legend under the grid with the low, middle and high counts', async () => {
    render(<ConnectionsMap />);
    await waitFor(() => expect(screen.getByLabelText(/Connections map/)).toBeTruthy());
    // Every fixture count is 6, so the ramp collapses to a single figure.
    expect(screen.getByText(/6 links in each cell/)).toBeTruthy();
  });

  it('shows no legend when every cell is empty', async () => {
    global.fetch = mockFetch({ ...MAP_PAYLOAD, counts: [[0, 0], [0, 0]], normalised: [[0, 0], [0, 0]],
                              legend: { low: 0, mid: 0, high: 0 } });
    render(<ConnectionsMap />);
    await waitFor(() => expect(screen.getByLabelText(/Connections map/)).toBeTruthy());
    expect(screen.queryByText(/percentile rank/)).toBeNull();
  });

  it('shows a "Map built <date>." footer under the grid, no warning tone', async () => {
    // NC, 2026-09-20: no notion of "stale" in front of users at all -- a
    // plain grey one-liner under the grid stating the cache's build date,
    // whether or not the backend happened to fall back to an older cache.
    global.fetch = mockFetch(BUILT_MAP_PAYLOAD);
    render(<ConnectionsMap />);
    const footer = await screen.findByText('Map built 2026-09-18.');
    expect(footer.closest('p').className).toContain('text-gray-400');
    expect(footer.closest('p').className).not.toMatch(/amber|yellow|red/);
  });

  it('places the build-date footer under the grid, after the translation-pairs note', async () => {
    global.fetch = mockFetch(BUILT_MAP_PAYLOAD);
    render(<ConnectionsMap />);
    const grid = await screen.findByLabelText(/Connections map, author view/);
    const footer = await screen.findByText('Map built 2026-09-18.');
    expect(grid.compareDocumentPosition(footer) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it('omits the build-date text (but keeps the Refresh map button) when cache_built_at is missing', async () => {
    render(<ConnectionsMap />);
    await waitFor(() => expect(screen.getByLabelText(/Connections map/)).toBeTruthy());
    expect(screen.queryByText(/Map built/)).toBeNull();
    expect(screen.getByRole('button', { name: 'Refresh map' })).toBeTruthy();
  });

  it('clicking "Refresh map" issues a fetch whose URL contains refresh=1', async () => {
    render(<ConnectionsMap />);
    await waitFor(() => expect(screen.getByLabelText(/Connections map/)).toBeTruthy());
    fireEvent.click(screen.getByRole('button', { name: 'Refresh map' }));
    await waitFor(() => expect(global.fetch).toHaveBeenCalledWith(
      expect.stringMatching(/^\/api\/passages\/map\?.*refresh=1/)));
  });

  it('shows "Refreshing..." and disables the button while the refresh request is in flight', async () => {
    render(<ConnectionsMap />);
    await waitFor(() => expect(screen.getByLabelText(/Connections map/)).toBeTruthy());
    let resolveRefresh;
    global.fetch = vi.fn(() => new Promise((resolve) => { resolveRefresh = resolve; }));
    fireEvent.click(screen.getByRole('button', { name: 'Refresh map' }));
    const refreshingButton = await screen.findByRole('button', { name: 'Refreshing...' });
    expect(refreshingButton).toBeDisabled();
    resolveRefresh({ json: () => Promise.resolve(BUILT_MAP_PAYLOAD) });
    await waitFor(() => expect(screen.getByRole('button', { name: 'Refresh map' })).toBeTruthy());
  });

  it('never renders the word "stale" anywhere in the document, even when the API sends `stale`', async () => {
    global.fetch = mockFetch(STALE_MAP_PAYLOAD);
    render(<ConnectionsMap />);
    await waitFor(() => expect(screen.getByLabelText(/Connections map/)).toBeTruthy());
    await screen.findByText('Map built 2026-09-18.');
    expect(document.body.textContent.toLowerCase()).not.toContain('stale');
  });

  it('switching to the work view refetches with view=work', async () => {
    render(<ConnectionsMap />);
    await waitFor(() => expect(screen.getByLabelText(/Connections map/)).toBeTruthy());
    fireEvent.click(screen.getByRole('button', { name: 'Works' }));
    await waitFor(() => expect(global.fetch).toHaveBeenCalledWith(expect.stringContaining('view=work')));
  });
});

// --------------------------------------------------------------------------
// "Show the N most connected authors" (NC, 2026-09-19): a bare "Top 50"
// read as a ranking when the grid does not display one at all -- the N is a
// selection, but the rows/columns are then shown in date order.
// --------------------------------------------------------------------------

describe('the "most connected" control', () => {
  it('names the current view (authors by default)', async () => {
    render(<ConnectionsMap />);
    await waitFor(() => expect(screen.getByLabelText(/Connections map/)).toBeTruthy());
    expect(screen.getByText(/Show the/)).toBeTruthy();
    expect(screen.getByText(/most connected authors/)).toBeTruthy();
  });

  it('switches to "works" when the Works view is chosen', async () => {
    render(<ConnectionsMap />);
    await waitFor(() => expect(screen.getByLabelText(/Connections map/)).toBeTruthy());
    fireEvent.click(screen.getByRole('button', { name: 'Works' }));
    await waitFor(() => expect(screen.getByText(/most connected works/)).toBeTruthy());
  });

  it('has a hover note that entries are shown in date order, not by strength', async () => {
    render(<ConnectionsMap />);
    await waitFor(() => expect(screen.getByLabelText(/Connections map/)).toBeTruthy());
    const label = screen.getByText(/Show the/).closest('label');
    expect(label).toHaveAttribute('title', expect.stringContaining('oldest to newest'));
    expect(label.getAttribute('title')).toContain('not by how connected they are');
  });

  it('gives genres their own honest note -- alphabetical, not date order', async () => {
    render(<ConnectionsMap />);
    await waitFor(() => expect(screen.getByLabelText(/Connections map/)).toBeTruthy());
    fireEvent.click(screen.getByRole('button', { name: 'Genres' }));
    await waitFor(() => expect(screen.getByText(/most connected genres/)).toBeTruthy());
    const label = screen.getByText(/Show the/).closest('label');
    expect(label).toHaveAttribute('title', 'Shown alphabetically.');
  });
  it('checking "Show translation pairs" refetches with translations=1', async () => {
    render(<ConnectionsMap />);
    await waitFor(() => expect(screen.getByLabelText(/Connections map/)).toBeTruthy());
    fireEvent.click(screen.getByLabelText('Show translation pairs'));
    await waitFor(() => expect(global.fetch).toHaveBeenCalledWith(expect.stringContaining('translations=1')));
  });
});

// --------------------------------------------------------------------------
// "All languages" is a button (NC, 2026-09-19): selected by default, mutually
// exclusive with the individual language buttons.
// --------------------------------------------------------------------------

describe('the "All languages" button', () => {
  it('is a real button, pressed by default', async () => {
    render(<ConnectionsMap />);
    await waitFor(() => expect(screen.getByLabelText(/Connections map/)).toBeTruthy());
    const allButton = screen.getByRole('button', { name: 'All languages' });
    expect(allButton).toHaveAttribute('aria-pressed', 'true');
  });

  it('picking a specific language deselects "All languages"', async () => {
    render(<ConnectionsMap />);
    await waitFor(() => expect(screen.getByLabelText(/Connections map/)).toBeTruthy());
    fireEvent.click(screen.getByText('Latin'));
    await waitFor(() => expect(global.fetch).toHaveBeenCalledWith(expect.stringContaining('languages=la')));
    expect(screen.getByRole('button', { name: 'All languages' })).toHaveAttribute('aria-pressed', 'false');
  });

  it('clicking "All languages" again clears any chosen language and refetches with none', async () => {
    render(<ConnectionsMap />);
    await waitFor(() => expect(screen.getByLabelText(/Connections map/)).toBeTruthy());
    fireEvent.click(screen.getByText('Latin'));
    await waitFor(() => expect(global.fetch).toHaveBeenCalledWith(expect.stringContaining('languages=la')));
    global.fetch.mockClear();
    fireEvent.click(screen.getByRole('button', { name: 'All languages' }));
    await waitFor(() => expect(global.fetch).toHaveBeenCalledWith(expect.stringContaining('/api/passages/map?')));
    const call = global.fetch.mock.calls.map((c) => c[0]).find((u) => u.startsWith('/api/passages/map?'));
    expect(call).not.toContain('languages=');
    expect(screen.getByRole('button', { name: 'All languages' })).toHaveAttribute('aria-pressed', 'true');
  });
});

describe('hovering and clicking the grid (margin-aware coordinates)', () => {
  it('hovering a cell shows a tooltip naming both axes and the count', async () => {
    render(<ConnectionsMap />);
    const canvas = await screen.findByLabelText(/Connections map/);
    // 2 labels -> cellSize is clamped to MAX_CELL (28). Row 0 (Homer) x
    // column 1 (Vergil): count 6, percentile rank 1 (the top of the scale).
    fireEvent.mouseMove(canvas, cellCenter(28, 0, 1));
    expect(await screen.findByText('Homer (grc)')).toBeTruthy();
    expect(screen.getByText('Vergil (la)')).toBeTruthy();
    expect(screen.getByText('6 links')).toBeTruthy();   // the tooltip, exact; the legend says 'in each cell'
  });

  it('moving off the grid clears the tooltip', async () => {
    render(<ConnectionsMap />);
    const canvas = await screen.findByLabelText(/Connections map/);
    fireEvent.mouseMove(canvas, cellCenter(28, 0, 1));
    await screen.findByText('Homer (grc)');
    fireEvent.mouseLeave(canvas);
    await waitFor(() => expect(screen.queryByText('Homer (grc)')).toBeNull());
  });

  it('clicking an author cell fetches the pair and shows a nested works heatmap below the grid', async () => {
    render(<ConnectionsMap />);
    const canvas = await screen.findByLabelText(/Connections map, author view/);
    // Row 0 is Homer (id homer::grc), column 1 is Vergil (id vergil::la);
    // the click lands on the SAME grid canvas cellFromEvent hit-tests, at
    // the same cellSize (28, clamped for a 2-label matrix) the component
    // itself computes -- not a coordinate guessed independently of it.
    fireEvent.click(canvas, cellCenter(28, 0, 1));
    await waitFor(() => expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/passages/map/cell')));
    const cellCall = global.fetch.mock.calls.map((c) => c[0]).find((u) => u.startsWith('/api/passages/map/cell'));
    expect(cellCall).toContain('a=homer%3A%3Agrc');
    expect(cellCall).toContain('b=vergil%3A%3Ala');

    // A SECOND heatmap, not a plain list (NC, 2026-09-19): rows Homer's
    // works, columns Vergil's works.
    const worksCanvas = await screen.findByLabelText(/Works of Homer \(grc\) by works of Vergil \(la\)/);
    expect(canvas.compareDocumentPosition(worksCanvas) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(window.HTMLElement.prototype.scrollIntoView).toHaveBeenCalled();
  });

  it('clicking the diagonal (a work against itself) does nothing', async () => {
    render(<ConnectionsMap />);
    const canvas = await screen.findByLabelText(/Connections map/);
    fireEvent.click(canvas, cellCenter(28, 0, 0));   // row 0, col 0: same entity
    expect(global.fetch).not.toHaveBeenCalledWith(expect.stringContaining('/api/passages/map/cell'));
  });

  it('hovering the diagonal shows the "same author, other works" note instead of a plain count', async () => {
    render(<ConnectionsMap />);
    const canvas = await screen.findByLabelText(/Connections map, author view/);
    fireEvent.mouseMove(canvas, cellCenter(28, 0, 0));
    expect(await screen.findByText(/same author, other works: 0 links \(same-work matches are excluded\)/))
      .toBeTruthy();
  });

  it('clicking above the grid (over the rotated column-label area) does nothing', async () => {
    render(<ConnectionsMap />);
    const canvas = await screen.findByLabelText(/Connections map/);
    fireEvent.click(canvas, { clientX: 20, clientY: -1 });   // above the cells canvas: labels sit on their own strip now
    expect(global.fetch).not.toHaveBeenCalledWith(expect.stringContaining('/api/passages/map/cell'));
  });

  it('shows a breadcrumb line above each nested grid, comma-separated with the level name', async () => {
    render(<ConnectionsMap />);
    const canvas = await screen.findByLabelText(/Connections map, author view/);
    fireEvent.click(canvas, cellCenter(28, 0, 1));
    // "Homer (grc) x Vergil (la), works" -- NC's own example format, comma
    // before the level name, so it reads as a breadcrumb trail.
    expect(await screen.findByText('Work by work: Homer (grc) × Vergil (la)')).toBeTruthy();
  });

  it('scrolls each new drill-down grid to the START of the viewport, not merely into view', async () => {
    render(<ConnectionsMap />);
    const canvas = await screen.findByLabelText(/Connections map, author view/);
    fireEvent.click(canvas, cellCenter(28, 0, 1));
    await screen.findByLabelText(/Works of Homer \(grc\) by works of Vergil \(la\)/);
    expect(window.HTMLElement.prototype.scrollIntoView).toHaveBeenCalledWith(
      expect.objectContaining({ block: 'start' }));
  });

  it('drills all the way through works -> books -> passage pairs, with Reader links', async () => {
    render(<ConnectionsMap />);
    const canvas = await screen.findByLabelText(/Connections map, author view/);
    fireEvent.click(canvas, cellCenter(28, 0, 1));
    const worksCanvas = await screen.findByLabelText(/Works of Homer \(grc\) by works of Vergil \(la\)/);
    window.HTMLElement.prototype.scrollIntoView.mockClear();

    // The nested works matrix is 1x1 (Homer, iliad x Vergil, aeneid).
    fireEvent.click(worksCanvas, cellCenter(28, 0, 0));
    await waitFor(() => expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/passages/map/books')));
    const booksCall = global.fetch.mock.calls.map((c) => c[0]).find((u) => u.startsWith('/api/passages/map/books'));
    expect(booksCall).toContain('work_a=homer.iliad');
    expect(booksCall).toContain('work_b=vergil.aeneid');

    const booksCanvas = await screen.findByLabelText(/Books of Homer, iliad by books of Vergil, aeneid/);
    expect(worksCanvas.compareDocumentPosition(booksCanvas) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(await screen.findByText('Book by book: Homer, iliad × Vergil, aeneid')).toBeTruthy();
    expect(window.HTMLElement.prototype.scrollIntoView).toHaveBeenCalledWith(
      expect.objectContaining({ block: 'start' }));
    window.HTMLElement.prototype.scrollIntoView.mockClear();

    // The books grid is also 1x1 (book 1 x book 1).
    fireEvent.click(booksCanvas, cellCenter(28, 0, 0));
    await waitFor(() => expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/passages/map/pair')));
    const pairCall = global.fetch.mock.calls.map((c) => c[0]).find((u) => u.startsWith('/api/passages/map/pair'));
    expect(pairCall).toContain('work_a=homer.iliad');
    expect(pairCall).toContain('work_b=vergil.aeneid');
    expect(pairCall).toContain('book_a=b1');
    expect(pairCall).toContain('book_b=b1');

    expect(await screen.findByText('Achilles rages.')).toBeTruthy();
    expect(screen.getByText('Arms and the man.')).toBeTruthy();
    // Author and work in full, then the reference (NC, 2026-09-19) --
    // "Homer, Iliad 1.1", not "Homer, Iliad, hom. il. 1.1" (NC, 2026-09-19:
    // strip the abbreviation, show only the locus, space not comma).
    expect(screen.getByText('Homer, Iliad 1.1')).toBeTruthy();
    expect(screen.getByText('Vergil, Aeneid 1.1')).toBeTruthy();
    expect(screen.getByText('Passages: Homer, Iliad × Vergil, Aeneid')).toBeTruthy();
    const links = screen.getAllByRole('link');
    expect(links.some((a) => a.getAttribute('href').includes('tab=similar'))).toBe(true);
    // The passage-pair list gets its own scroll-into-view too, since it
    // renders below the (already scrolled-to) books grid.
    expect(window.HTMLElement.prototype.scrollIntoView).toHaveBeenCalled();
  });

  it('strips the abbreviation from the displayed locus, keeping it only in the link title', async () => {
    // "Homer, Iliad 18.427", not "Homer, Iliad, hom. il. 18.427" -- the
    // abbreviation belongs in the citation (the link's title attribute),
    // not the display text (NC, 2026-09-19).
    const abbreviatedPair = {
      ...PAIR_PAYLOAD,
      pairs: [{
        ...PAIR_PAYLOAD.pairs[0],
        window_a: { ...PAIR_PAYLOAD.pairs[0].window_a, ref_start: 'hom. il. 18.427' },
        window_b: { ...PAIR_PAYLOAD.pairs[0].window_b, ref_start: 'verg. a. 18.427' },
      }],
    };
    global.fetch = mockFetch(MAP_PAYLOAD, abbreviatedPair);
    render(<ConnectionsMap />);
    const canvas = await screen.findByLabelText(/Connections map, author view/);
    fireEvent.click(canvas, cellCenter(28, 0, 1));
    const worksCanvas = await screen.findByLabelText(/Works of Homer \(grc\) by works of Vergil \(la\)/);
    fireEvent.click(worksCanvas, cellCenter(28, 0, 0));
    const booksCanvas = await screen.findByLabelText(/Books of Homer, iliad by books of Vergil, aeneid/);
    fireEvent.click(booksCanvas, cellCenter(28, 0, 0));

    const link = await screen.findByText('Homer, Iliad 18.427');
    expect(link.closest('a')).toHaveAttribute('title', 'hom. il. 18.427');
    const otherLink = screen.getByText('Vergil, Aeneid 18.427');
    expect(otherLink.closest('a')).toHaveAttribute('title', 'verg. a. 18.427');
  });

  it('a Works-view cell skips straight to the books grid, no intermediate list', async () => {
    render(<ConnectionsMap />);
    await waitFor(() => expect(screen.getByLabelText(/Connections map/)).toBeTruthy());
    fireEvent.click(screen.getByRole('button', { name: 'Works' }));
    const canvas = await screen.findByLabelText(/Connections map, work view/);
    global.fetch.mockClear();
    fireEvent.click(canvas, cellCenter(28, 0, 1));
    await waitFor(() => expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/passages/map/books')));
    // No /map/cell fetch at all for the Works view's own top grid.
    expect(global.fetch).not.toHaveBeenCalledWith(expect.stringContaining('/api/passages/map/cell'));
    expect(await screen.findByLabelText(/Books of/)).toBeTruthy();
  });

  it('a century/genre cell still shows the flat work-pairs list, not a nested heatmap', async () => {
    render(<ConnectionsMap />);
    await waitFor(() => expect(screen.getByLabelText(/Connections map/)).toBeTruthy());
    fireEvent.click(screen.getByRole('button', { name: 'Genres' }));
    const canvas = await screen.findByLabelText(/Connections map, genre view/);
    fireEvent.click(canvas, cellCenter(28, 0, 1));
    await waitFor(() => expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/passages/map/cell')));
    expect(await screen.findByText(/homer\.iliad.*vergil\.aeneid/)).toBeTruthy();
    expect(screen.queryByLabelText(/Works of/)).toBeNull();
  });
});

describe('starting from one work', () => {
  it('typing in the work picker shows matching options from /api/passages/works', async () => {
    render(<ConnectionsMap />);
    await waitFor(() => expect(global.fetch).toHaveBeenCalledWith(expect.stringContaining('/api/passages/works')));
    fireEvent.change(screen.getByPlaceholderText(/Start from one work/), { target: { value: 'homer' } });
    expect(await screen.findByText('homer.iliad')).toBeTruthy();
  });

  it('picking a work fetches its row, names the row, and hides the full-map canvas', async () => {
    render(<ConnectionsMap />);
    await waitFor(() => expect(global.fetch).toHaveBeenCalledWith(expect.stringContaining('/api/passages/works')));
    fireEvent.change(screen.getByPlaceholderText(/Start from one work/), { target: { value: 'homer' } });
    fireEvent.click(await screen.findByText('homer.iliad'));
    await waitFor(() => expect(global.fetch).toHaveBeenCalledWith(expect.stringContaining('/api/passages/map/work?work=homer.iliad')));
    // The row is named with the same author display name the API returned
    // (Browse Corpus's own display names), not the raw "homer.iliad" slug.
    expect(await screen.findByText(/Homer, iliad \(grc\)/)).toBeTruthy();
    expect(screen.getByLabelText(/Connections for Homer, iliad/)).toBeTruthy();
    expect(screen.queryByLabelText(/Connections map, author view/)).toBeNull();
  });

  it('the one-work row is a labeled 1xN grid whose single column can be clicked', async () => {
    render(<ConnectionsMap />);
    await waitFor(() => expect(global.fetch).toHaveBeenCalledWith(expect.stringContaining('/api/passages/works')));
    fireEvent.change(screen.getByPlaceholderText(/Start from one work/), { target: { value: 'homer' } });
    fireEvent.click(await screen.findByText('homer.iliad'));
    const canvas = await screen.findByLabelText(/Connections for Homer, iliad/);
    // 1 connection -> cellSize clamps to MAX_CELL (28); row 0, col 0.
    fireEvent.click(canvas, cellCenter(28, 0, 0));
    await waitFor(() => expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/passages/map/pair?work_a=homer.iliad&work_b=vergil.aeneid')));
  });
});

// --------------------------------------------------------------------------
// Column label orientation (NC, 2026-09-19): "every grid must draw its
// labels with the same LabeledHeatmap code path and the same upright font
// as the top grid" -- a handful of short labels (a books grid's "1", "2")
// draws upright rather than rotated 45 degrees, so it does not read as
// italic; a grid with many/long labels (the top grid's authors and works)
// still rotates, exactly as before.
// --------------------------------------------------------------------------

describe('column label orientation', () => {
  const stubCtx = (widthOf) => ({ measureText: (s) => ({ width: widthOf(s) }) });

  it('does not rotate a few short labels that fit their own column width', () => {
    const ctx = stubCtx(() => 8);   // "1", "2" measure far narrower than the cell
    expect(columnLabelsNeedRotation(['1', '2'], 28, (s) => s, ctx)).toBe(false);
  });

  it('rotates when a label would overflow its own column width', () => {
    const ctx = stubCtx(() => 60);   // "Vergil, Aeneid" measures wider than a 28px cell
    expect(columnLabelsNeedRotation(['Vergil, Aeneid'], 28, (s) => s, ctx)).toBe(true);
  });

  it('falls back to a plain label count with no measuring context available', () => {
    expect(columnLabelsNeedRotation(['a', 'b'], 28, (s) => s, null)).toBe(false);
    expect(columnLabelsNeedRotation(Array(10).fill('a'), 28, (s) => s, null)).toBe(true);
  });
});

// --------------------------------------------------------------------------
// Crisp labels on a high-resolution screen (NC, 2026-09-19): a canvas's
// backing store must be sized by devicePixelRatio, not just its CSS size, or
// the browser upscales a 1x bitmap and every label blurs. sizeCanvasForDPR
// sets canvas.width/height (the DOM sets these unconditionally, even without
// a working 2D context, so this holds in jsdom too) and canvas.style.width/
// height separately -- this checks the backing store is the ratio times the
// CSS size, not that anything is actually painted (a real 2D context is not
// available in jsdom; see the file-level comment above).
// --------------------------------------------------------------------------

describe('canvas sizing for devicePixelRatio', () => {
  it('sizes the backing store to CSS size times devicePixelRatio on a 2x screen', async () => {
    vi.stubGlobal('devicePixelRatio', 2);
    render(<ConnectionsMap />);
    const gridCanvas = await screen.findByLabelText(/Connections map, author view/);
    const rowCanvas = gridCanvas.previousSibling;

    for (const canvas of [gridCanvas, rowCanvas]) {
      const cssWidth = parseFloat(canvas.style.width);
      const cssHeight = parseFloat(canvas.style.height);
      expect(cssWidth).toBeGreaterThan(0);
      expect(canvas.width).toBe(Math.round(cssWidth * 2));
      expect(canvas.height).toBe(Math.round(cssHeight * 2));
    }
  });

  it('sizes the backing store 1:1 with CSS size on an ordinary screen', async () => {
    vi.stubGlobal('devicePixelRatio', 1);
    render(<ConnectionsMap />);
    const gridCanvas = await screen.findByLabelText(/Connections map, author view/);
    expect(gridCanvas.width).toBe(Math.round(parseFloat(gridCanvas.style.width)));
  });
});
