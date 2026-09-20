import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

/**
 * The corpus connections map: a picture of Theme Search's own connections
 * (same passage index, same description embeddings) aggregated by author,
 * work, century or genre, drawn as a canvas heatmap.
 *
 * Nothing here computes a new relationship. Every cell is the same signal
 * Similar Passages already answers one passage at a time -- descriptions
 * that came out close in the embedding -- rolled up to a scale a single
 * passage lookup cannot show. See backend/connections_map.py and
 * scripts/build_connections_map.py for how the underlying cache is built.
 *
 * Reds and greys only, no blue anywhere: the site-wide color rule.
 *
 * ROW AND COLUMN LABELS (NC, after looking at the first version): a grid of
 * colored cells with nothing naming the rows or columns cannot be read at
 * all, whatever the color scale shows. LabeledHeatmap below draws the
 * author/work/century/genre display names -- the same names Browse Corpus
 * shows, via backend/utils.format_display_name, not raw file slugs -- down
 * the left edge and along the top (rotated 45 degrees to fit more of them
 * in less vertical space), sized so a cell is never smaller than 14px even
 * at the deepest "Top" setting, and it is the same component whether the
 * grid is the full NxN matrix or the single row "start from one work" view.
 *
 * TWO CANVASES, NOT ONE (NC's second look, 2026-09-19): the grid is wider
 * than the page at any real "Top" setting, and a single canvas scrolled
 * horizontally took the row names off screen with it -- exactly the labels
 * a reader needs while reading a column deep in the grid. The row-label
 * canvas is a separate, narrow canvas held `position: sticky; left: 0`
 * inside the same scrolling container, so it stays put while only the
 * column-label-and-cells canvas scrolls under it. The column canvas also
 * carries right padding sized to the longest rotated label, and the pair
 * gets a shared top padding for the same label's rotated height, so the
 * last column's name is never cut off at the scrolled-right edge either.
 */

// Production language tab order (Latin, Greek, English, then the others),
// same convention client/src/components/layout/Navigation.jsx uses.
const LANGUAGES = [
  ['la', 'Latin'], ['grc', 'Greek'], ['en', 'English'],
  ['cop', 'Coptic'], ['he', 'Hebrew'],
];

const VIEWS = [
  ['author', 'Authors'], ['work', 'Works'],
  ['century', 'Centuries'], ['genre', 'Genres'],
];

// "Top 50" read as a ranking, when the grid does not show a ranking at all
// (NC, 2026-09-19): the Top N control still CHOOSES the N most-connected
// entities, but the rows/columns are then displayed in date order (see
// backend/connections_map.py get_map's own chronological sort), so a plain
// number label looked like the rows would be sorted by strength. The noun
// matches the current view, and the hover note says how they are actually
// ordered on screen -- genres sort alphabetically, not by date, so that
// case gets its own honest note rather than a copy-pasted "date order".
const VIEW_NOUN = { author: 'authors', work: 'works', century: 'centuries', genre: 'genres' };
const ORDER_NOTE = {
  author: 'Shown oldest to newest, not by how connected they are.',
  work: 'Shown oldest to newest, not by how connected they are.',
  century: 'Shown oldest to newest.',
  genre: 'Shown alphabetically.',
};

// A single red ramp over a grey ground. index.js light-mode background is
// white, so 0 renders as a pale grey and the strongest cell as the site's
// own red-700, matching every other emphasis color on the page.
function cellColor(v) {
  if (!v || v <= 0) return '#f3f4f6';               // gray-100
  const t = Math.min(1, Math.max(0, v));
  // Interpolate gray-200 (#e5e7eb) -> red-700 (#b91c1c).
  const from = [229, 231, 235];
  const to = [185, 28, 28];
  const rgb = from.map((c, i) => Math.round(c + (to[i] - c) * t));
  return `rgb(${rgb.join(',')})`;
}

// A small legend under every grid (NC, 2026-09-19): colour is each cell's
// count on a LOG scale (backend.connections_map._log_scale), so each step
// of shade stands for roughly the same ratio of links and only the largest
// counts go fully dark. A linear count/max scale had left nearly every cell
// pale (Homer x Quintus Smyrnaeus, over 20,000 links, flattened the rest);
// percentile rank then painted the top fifth of cells in the darkest shade,
// which read as mostly dark red. The legend names the raw counts at the low,
// middle and high ends of the ramp.
function fmtCount(n) {
  return Number.isInteger(n) ? String(n) : n.toFixed(1);
}

function ColorLegend({ legend }) {
  if (!legend || !legend.high) return null;
  if (legend.mode === 'lift') {
    return (
      <div className="mt-2 flex flex-wrap items-center gap-2 text-[11px] text-gray-500">
        <span>1&times;</span>
        <div
          className="h-2 w-28 rounded-sm border border-gray-200"
          style={{ background: `linear-gradient(to right, ${cellColor(0.05)}, `
            + `${cellColor(0.5)}, ${cellColor(1)})` }}
          aria-hidden="true"
        />
        <span>{legend.high.toFixed(1)}&times;</span>
        <span className="text-gray-400">
          &middot; links relative to what the two sizes alone would predict: 1&times; is
          chance, the typical connected cell is {legend.mid.toFixed(1)}&times;, the strongest{' '}
          {legend.high.toFixed(1)}&times;
        </span>
      </div>
    );
  }
  if (legend.low === legend.high) {
    // One cell, or every cell alike: a ramp from 5057 to 5057 says nothing.
    return <div className="mt-2 text-[11px] text-gray-500">{fmtCount(legend.high)} links in each cell</div>;
  }
  return (
    <div className="mt-2 flex flex-wrap items-center gap-2 text-[11px] text-gray-500">
      <span>{fmtCount(legend.low)}</span>
      <div
        className="h-2 w-28 rounded-sm border border-gray-200"
        style={{ background: `linear-gradient(to right, ${cellColor(0.02)}, `
          + `${cellColor(0.5)}, ${cellColor(1)})` }}
        aria-hidden="true"
      />
      <span>{fmtCount(legend.high)}</span>
      <span className="text-gray-400">
        &middot; low {fmtCount(legend.low)}, middle {fmtCount(legend.mid)}, high{' '}
        {fmtCount(legend.high)} links &mdash; log scale, so only the largest counts go fully dark
      </span>
    </div>
  );
}

function readerLinkForWindow(w, other) {
  if (!w) return '#';
  const params = new URLSearchParams({
    work: w.work.endsWith('.tess') ? w.work : `${w.work}.tess`,
    lang: w.language || 'la',
    ref: w.ref_start || '',
    refEnd: w.ref_end || w.ref_start || '',
    tab: 'similar',
    q: other ? `connections map: ${other.author_display || other.work}` : '',
  });
  return `/read?${params.toString()}`;
}

// Author and work in full, then the reference (NC, 2026-09-19): the
// passage-pair list must read as a citation, not a raw work-id slug. `title`
// is the backend's format_display_name-formatted title (falls back to the
// raw work id for a payload from before that field existed).
function passageLabel(w) {
  if (!w) return '';
  const title = w.title || w.work;
  return w.author_display ? `${w.author_display}, ${title}` : title;
}

// The abbreviation belongs in a citation, not the display text (NC,
// 2026-09-19): "Homer, Iliad 18.427", not "Homer, Iliad, hom. il. 18.427".
// Same trailing-locus pattern backend/connections_map.py's _book_of uses,
// so a ref this can't parse (no trailing digits at all) falls back to
// showing it whole rather than silently dropping it.
function locusOnly(ref) {
  if (!ref) return '';
  const m = /(\d+(?:\.\d+)*)\s*$/.exec(ref);
  return m ? m[1] : ref;
}

// Build-date footer (NC, 2026-09-20): the backend can silently fall back to
// an older cache (a corpus edit changes the passage index's fingerprint long
// before a ~40-minute rebuild can catch up -- see backend/connections_map.py
// _resolve_path()), and that used to surface here as a "stale" notice. The
// owner does not want any notion of staleness in front of users: every map
// response now carries `cache_built_at` (an ISO-ish timestamp,
// "2026-09-18T21:50:00") regardless of whether the cache is current, and
// this reads only the date, phrased as a plain fact rather than a warning.
// The `stale` field itself still comes back from the API for an operator to
// read; it is never surfaced here.
function mapBuiltFooterText(cacheBuiltAt) {
  if (!cacheBuiltAt) return null;
  const date = (cacheBuiltAt || '').split('T')[0];
  return date ? `Map built ${date}.` : null;
}

// The backend bakes "Name (lang)" into author/century labels (see
// backend/connections_map.py _entity()); work and genre labels carry no
// language suffix. Split it apart so the language can be drawn small and
// only where it actually disambiguates two identically-named entities.
function splitLabel(label) {
  const m = /^(.*) \(([a-z]{2,3})\)$/.exec(label || '');
  return m ? { base: m[1], lang: m[2] } : { base: label || '', lang: null };
}

function truncateToWidth(ctx, text, maxWidth) {
  if (ctx.measureText(text).width <= maxWidth) return text;
  let lo = 0, hi = text.length;
  while (lo < hi) {
    const mid = Math.ceil((lo + hi) / 2);
    const candidate = `${text.slice(0, mid)}…`;
    if (ctx.measureText(candidate).width <= maxWidth) lo = mid; else hi = mid - 1;
  }
  return lo > 0 ? `${text.slice(0, lo)}…` : '…';
}

// Row-label canvas width and a floor for the column-label canvas's top
// margin; both grow the column side dynamically (see colGeometry below) to
// fit whatever the longest actual label turns out to be.
const ROW_MARGIN = 190;
const COL_MARGIN_MIN = 90;
const MIN_CELL = 14;   // never smaller than this -- the owner's ask, verbatim
const MAX_CELL = 28;
const LABEL_FONT = '11px sans-serif';
const LABEL_CAP = 220;   // widest a label is allowed to measure before truncation kicks in

// One fill colour and one font for every label, row or column (NC,
// 2026-09-19: the row-label canvas and the rotated column labels on the
// grid canvas must not diverge -- both read off these same four constants,
// nowhere else).
const LABEL_COLOR = '#374151';           // gray-700
const LABEL_COLOR_ACTIVE = '#111827';    // gray-900
const LABEL_FONT_ACTIVE = `bold ${LABEL_FONT}`;

function cellSizeFor(n) {
  return Math.max(MIN_CELL, Math.min(MAX_CELL, 900 / Math.max(1, n)));
}

// A throwaway canvas purely for ctx.measureText, independent of anything
// that gets drawn on screen -- lets the column margin and right padding be
// sized to the ACTUAL longest label rather than a guessed constant.
let _measureCtx = null;
function measureCtx() {
  if (!_measureCtx && typeof document !== 'undefined') {
    const c = document.createElement('canvas');
    _measureCtx = c.getContext('2d');
  }
  return _measureCtx;
}

// Crisp labels on a high-resolution screen (NC, 2026-09-19): sized only by
// their CSS pixel dimensions, a canvas's backing store is that many DEVICE
// pixels regardless of the screen's actual pixel density, so on a 2x/3x
// display the browser upscales a 1x bitmap and every label blurs -- while
// the surrounding page text, drawn by the browser's own text layout, stays
// sharp. Sizing the backing store by devicePixelRatio and scaling the
// context by the same factor keeps every existing draw call's coordinates
// in CSS-pixel units (nothing else in this component needs to change) while
// the actual bitmap is rendered at full device resolution.
function sizeCanvasForDPR(canvas, cssWidth, cssHeight) {
  const dpr = (typeof window !== 'undefined' && window.devicePixelRatio) || 1;
  canvas.width = Math.round(cssWidth * dpr);
  canvas.height = Math.round(cssHeight * dpr);
  canvas.style.width = `${cssWidth}px`;
  canvas.style.height = `${cssHeight}px`;
  const ctx = canvas.getContext('2d');
  // jsdom has no real 2D context (see the draw effects below); nothing to
  // scale when there is nothing to draw with.
  if (ctx) ctx.scale(dpr, dpr);
  return ctx;
}

/**
 * A labeled heatmap: row names down the left (a separate, sticky canvas so
 * they stay on screen while the grid scrolls horizontally), column names
 * along the top of the scrolling canvas (rotated 45deg), colored cells,
 * hover highlights the row+column band and reports both names to the
 * caller for a tooltip. Used for the full NxN matrix AND for the
 * single-row "start from one work" view -- same drawing code, same label
 * treatment, so a reader learns the grid once.
 */
// The diagonal (NC, 2026-09-19): a same-author or same-work cell is drawn
// hatched and grey rather than colored by its count, because a reader who
// sees a hot cell on the diagonal reads it as "these two correlate", when a
// same-author cell in fact counts only links between that author's OWN
// different works (same-work windows are excluded from the underlying data
// by construction) and a same-work cell is always empty by construction.
// Detected generically, by id equality between the row and column entity at
// (i, j) -- true for the main square matrix (rowIds===colIds) and equally
// true for a nested grid opened from an author-against-itself cell (both
// axes list that author's own works), and never true for a rectangular grid
// comparing two distinct entities' works, where it needs no special case.
function isDiagonalCell(rowIds, colIds, i, j) {
  return !!(rowIds && colIds && rowIds[i] !== undefined && rowIds[i] === colIds[j]);
}

// Column labels rotate 45 degrees only when they need to (NC, 2026-09-19:
// forcing a slant on labels that don't need it -- a books grid's "1", "2"
// -- reads as italic, not as an ordinary upright heading). Pure and exported
// so it can be tested without a real canvas: `ctx` is anything with a
// `measureText` (a real 2D context, or a stub in a test); with none at all
// (e.g. jsdom, before a real context exists) it falls back to a plain count,
// since the top grid's own column count (tens of authors/works) always
// needs rotation regardless of measurement.
export function columnLabelsNeedRotation(colLabels, cellSize, colTextFn, ctx) {
  if (!ctx) return colLabels.length > 6;
  return colLabels.some((label) => ctx.measureText(colTextFn(label)).width > cellSize - 4);
}

function drawHatch(ctx, x, y, size) {
  ctx.save();
  ctx.fillStyle = '#e5e7eb';   // gray-200
  ctx.fillRect(x, y, size, size);
  ctx.beginPath();
  ctx.rect(x, y, size, size);
  ctx.clip();
  ctx.strokeStyle = '#9ca3af';  // gray-400
  ctx.lineWidth = 1;
  for (let off = -size; off < size * 2; off += 5) {
    ctx.beginPath();
    ctx.moveTo(x + off, y);
    ctx.lineTo(x + off + size, y + size);
    ctx.stroke();
  }
  ctx.restore();
}

// Colour relative to size (NC, 2026-09-19: "are the scores normalized?" -- they
// were not). For each cell, the observed link count over what the two sizes
// alone would predict: row total x column total / grand total, the
// independence expectation. 1x means "as much as chance"; the ramp runs on a
// log2 scale from 1x up to the strongest cell, and cells at or under 1x stay
// pale. Big authors no longer light up a whole row just by being big.
function liftScale(counts) {
  const n = counts?.length || 0;
  if (!n) return { normalised: counts || [], legend: null, lift: null };
  const m = counts[0].length;
  const rowSum = counts.map((r) => r.reduce((a, b) => a + b, 0));
  const colSum = Array.from({ length: m }, (_, j) => counts.reduce((a, r) => a + (r[j] || 0), 0));
  const total = rowSum.reduce((a, b) => a + b, 0);
  const lift = counts.map((r, i) => r.map((v, j) =>
    (v > 0 && rowSum[i] > 0 && colSum[j] > 0 && total > 0) ? (v * total) / (rowSum[i] * colSum[j]) : 0));
  const vals = lift.flat().filter((v) => v > 0).sort((a, b) => a - b);
  if (!vals.length) return { normalised: lift, legend: null, lift };
  const hi = vals[vals.length - 1];
  const mid = vals[vals.length >> 1];
  const denom = Math.log2(Math.max(hi, 2));
  const normalised = lift.map((r) => r.map((v) => (v <= 1 ? (v > 0 ? 0.05 : 0) : Math.min(1, Math.log2(v) / denom))));
  return { normalised, legend: { low: 1, mid, high: hi, mode: 'lift' }, lift };
}

function LabeledHeatmap({
  rowLabels, colLabels, rowIds, colIds, normalised, cellSize, onHover, onCellClick, ariaLabel,
  outlineCell,
}) {
  const rowCanvasRef = useRef(null);
  const gridCanvasRef = useRef(null);
  const headerCanvasRef = useRef(null);
  const [hover, setHover] = useState(null);   // {i, j} in grid coordinates
  // Frozen column labels (NC, 2026-09-19: "the top label row needs to be
  // frozen so that when you scroll down the graph the column labels remain
  // visible"). The labels live on their own strip above the scroll box,
  // stuck under the site's menu bar while the page scrolls, and slid
  // sideways by the same amount as the grid.
  const [scrollLeft, setScrollLeft] = useState(0);
  const [navHeight, setNavHeight] = useState(56);
  useEffect(() => {
    const nav = document.querySelector('nav');
    if (nav) setNavHeight(Math.round(nav.getBoundingClientRect().height));
  }, []);

  const nRows = rowLabels.length;
  const nCols = colLabels.length;

  // A base name shared by two entities (same author, different language;
  // "1st c. CE" in both Latin and Greek) needs the language shown to tell
  // them apart. A name that appears once needs no such clutter.
  const ambiguousBases = useMemo(() => {
    // A Set first: rowLabels and colLabels are literally the SAME array for
    // the square matrix view, and counting that array twice would mark
    // every label ambiguous regardless of whether anything actually
    // collides. Distinct labels (different language) still count separately.
    const uniqueLabels = new Set([...rowLabels, ...colLabels]);
    const count = {};
    for (const l of uniqueLabels) {
      const { base } = splitLabel(l);
      count[base] = (count[base] || 0) + 1;
    }
    return count;
  }, [rowLabels, colLabels]);

  // In a nested works grid every column reads "Plutarch, <title>": the author
  // is already in the heading, and the repeated prefix made the slanted
  // titles collide and run off the right edge (NC, 2026-09-19). When every
  // column label shares the same "Author, " prefix it is dropped from the
  // column labels only; row labels keep it (there is room).
  const commonColPrefix = useMemo(() => {
    if (colLabels.length < 2) return '';
    const heads = colLabels.map((l) => {
      const i = String(l).indexOf(', ');
      return i > 0 ? String(l).slice(0, i + 2) : null;
    });
    return heads.every((h) => h && h === heads[0]) ? heads[0] : '';
  }, [colLabels]);
  const colText = useCallback((label) => {
    const { base, lang } = splitLabel(label);
    const shown = commonColPrefix && base.startsWith(commonColPrefix) ? base.slice(commonColPrefix.length) : base;
    return lang && ambiguousBases[base] > 1 ? `${shown} (${lang})` : shown;
  }, [ambiguousBases, commonColPrefix]);

  // The rotated column labels can run past the canvas's own right edge and
  // (if long enough) need more than the default vertical room too. Both are
  // sized here from the ACTUAL longest label, measured once, rather than a
  // constant that is sometimes too little and sometimes wastes space.
  const { colMargin, rightPad } = useMemo(() => {
    const mctx = measureCtx();
    if (!mctx || !colLabels.length) return { colMargin: COL_MARGIN_MIN, rightPad: 40 };
    mctx.font = LABEL_FONT;
    let maxW = 0;
    for (const label of colLabels) {
      maxW = Math.max(maxW, mctx.measureText(colText(label)).width);
    }
    maxW = Math.min(maxW, LABEL_CAP);
    const rad = Math.PI / 4;   // the labels are rotated 45 degrees
    return {
      colMargin: Math.max(COL_MARGIN_MIN, Math.ceil(maxW * Math.sin(rad) + 26)),
      rightPad: Math.max(40, Math.ceil(maxW * Math.cos(rad) + 16)),
    };
  }, [colLabels, colText]);

  const gridWidth = nCols * cellSize + rightPad;
  const rowsHeight = nRows * cellSize;           // the row canvas and the cells canvas
  const totalHeight = rowsHeight;                // (labels are on the header strip now)

  // ---- row-label canvas (sticky; never scrolls) --------------------------
  useEffect(() => {
    const canvas = rowCanvasRef.current;
    if (!canvas) return;
    const ctx = sizeCanvasForDPR(canvas, ROW_MARGIN, totalHeight);
    // jsdom (the test environment) does not implement a 2D canvas context
    // unless the optional native `canvas` package is installed, so this
    // draw pass is skipped rather than throwing there; the surrounding UI
    // (labels list, hover panel, click handling) is what the tests exercise.
    if (!ctx) return;
    ctx.clearRect(0, 0, ROW_MARGIN, totalHeight);
    ctx.fillStyle = '#ffffff';
    ctx.fillRect(0, 0, ROW_MARGIN, totalHeight);   // opaque: sits over the scrolling grid

    ctx.textAlign = 'right';
    ctx.textBaseline = 'middle';
    rowLabels.forEach((label, i) => {
      const { base, lang } = splitLabel(label);
      const y = i * cellSize + cellSize / 2;
      const active = hover && hover.i === i;
      if (active) {
        ctx.fillStyle = 'rgba(185, 28, 28, 0.16)';
        ctx.fillRect(0, i * cellSize, ROW_MARGIN, cellSize);
        ctx.strokeStyle = 'rgba(185, 28, 28, 0.9)';
        ctx.lineWidth = 1.5;
        ctx.strokeRect(0.75, i * cellSize + 0.75, ROW_MARGIN - 1.5, cellSize - 1.5);
        ctx.lineWidth = 1;
      }
      ctx.font = active ? LABEL_FONT_ACTIVE : LABEL_FONT;
      ctx.fillStyle = active ? LABEL_COLOR_ACTIVE : LABEL_COLOR;
      const showLang = lang && ambiguousBases[base] > 1;
      ctx.fillText(truncateToWidth(ctx, base, ROW_MARGIN - (showLang ? 40 : 14)), ROW_MARGIN - 8, y);
      if (showLang) {
        ctx.font = '8px sans-serif';
        ctx.fillStyle = '#9ca3af';                            // gray-400, small type
        ctx.fillText(lang, ROW_MARGIN - 8, y + 9);
      }
    });
    // A thin rule so the sticky panel reads as attached to the grid rather
    // than floating disconnected from it while scrolled.
    ctx.strokeStyle = '#e5e7eb';
    ctx.beginPath();
    ctx.moveTo(ROW_MARGIN - 0.5, 0);
    ctx.lineTo(ROW_MARGIN - 0.5, totalHeight);
    ctx.stroke();
  }, [rowLabels, cellSize, hover, totalHeight, ambiguousBases]);

  // ---- cells canvas (this is what scrolls; the column labels are on the header strip) --------
  useEffect(() => {
    const canvas = gridCanvasRef.current;
    if (!canvas) return;
    const ctx = sizeCanvasForDPR(canvas, gridWidth, totalHeight);
    if (!ctx) return;
    ctx.clearRect(0, 0, gridWidth, totalHeight);

    // Hover bands, drawn before the cells so the grid lines stay crisp.
    if (hover) {
      // Stronger than the first version (8%): from the middle of a fifty-
      // author grid the faint bands did not lead the eye to the two names
      // (NC, 2026-09-19). A tinted band plus a red outline runs the whole
      // row and the whole column, from the cell out to both label margins.
      ctx.fillStyle = 'rgba(185, 28, 28, 0.16)';
      ctx.fillRect(0, hover.i * cellSize, nCols * cellSize, cellSize);
      ctx.fillRect(hover.j * cellSize, 0, cellSize, nRows * cellSize);
      ctx.strokeStyle = 'rgba(185, 28, 28, 0.9)';
      ctx.lineWidth = 1.5;
      ctx.strokeRect(0.75, hover.i * cellSize + 0.75, nCols * cellSize - 1.5, cellSize - 1.5);
      ctx.strokeRect(hover.j * cellSize + 0.75, 0.75, cellSize - 1.5, nRows * cellSize - 1.5);
      ctx.lineWidth = 1;
    }

    for (let i = 0; i < nRows; i++) {
      for (let j = 0; j < nCols; j++) {
        const x = j * cellSize, y = i * cellSize;
        if (isDiagonalCell(rowIds, colIds, i, j)) {
          drawHatch(ctx, x, y, cellSize);
        } else {
          ctx.fillStyle = cellColor(normalised[i]?.[j]);
          ctx.fillRect(x, y, cellSize, cellSize);
        }
      }
    }

    // Grid lines only when cells are large enough to make them legible.
    if (cellSize >= 10) {
      ctx.strokeStyle = 'rgba(255,255,255,0.6)';
      for (let k = 0; k <= nCols; k++) {
        ctx.beginPath();
        ctx.moveTo(k * cellSize, 0);
        ctx.lineTo(k * cellSize, nRows * cellSize);
        ctx.stroke();
      }
      for (let k = 0; k <= nRows; k++) {
        ctx.beginPath();
        ctx.moveTo(0, k * cellSize);
        ctx.lineTo(nCols * cellSize, k * cellSize);
        ctx.stroke();
      }
    }

    // The clicked cell stays outlined after the click (NC, 2026-09-19: it
    // was not clear a new grid had appeared below) -- a persistent marker
    // distinct from the hover band, so the parent grid keeps showing exactly
    // which cell the drill-down below it came from.
    if (outlineCell && outlineCell.i < nRows && outlineCell.j < nCols) {
      ctx.save();
      ctx.strokeStyle = '#b91c1c';   // red-700
      ctx.lineWidth = 2;
      ctx.strokeRect(outlineCell.j * cellSize + 1, outlineCell.i * cellSize + 1,
                     cellSize - 2, cellSize - 2);
      ctx.restore();
    }

  }, [rowLabels, colLabels, rowIds, colIds, normalised, cellSize, hover, gridWidth,
      totalHeight, nRows, nCols, outlineCell]);

  // ---- header strip: the column labels, frozen while the page scrolls ----
  useEffect(() => {
    const canvas = headerCanvasRef.current;
    if (!canvas) return;
    const ctx = sizeCanvasForDPR(canvas, gridWidth, colMargin);
    if (!ctx) return;
    ctx.clearRect(0, 0, gridWidth, colMargin);
    ctx.fillStyle = '#ffffff';
    ctx.fillRect(0, 0, gridWidth, colMargin);
    // No vertical band up here: with slanted names it crossed the boxed name
    // at an angle and read as two different highlights (NC, 2026-09-19). The
    // boxed name alone marks the column; the band runs through the cells.
    // Column labels: rotated 45 degrees so more/longer names fit in the same
    // vertical space than a straight horizontal label would allow, but only
    // when they actually need it -- a handful of short labels (a books
    // grid's "1", "2", ...) draws upright, exactly like the row labels and
    // exactly the same font, same as every other grid (NC, 2026-09-19:
    // "every grid must draw its labels with the same LabeledHeatmap code
    // path and the same upright font as the top grid"). The canvas's own
    // colMargin/rightPad (computed above from the longest label) is sized
    // generously enough for either orientation, so it does not change here.
    ctx.font = LABEL_FONT;
    const rotate = columnLabelsNeedRotation(colLabels, cellSize, colText, ctx);
    colLabels.forEach((label, j) => {
      const active = hover && hover.j === j;
      const x = j * cellSize + cellSize / 2;
      const text = truncateToWidth(ctx, colText(label), LABEL_CAP);
      ctx.font = active ? LABEL_FONT_ACTIVE : LABEL_FONT;
      // The same highlight the row label gets (NC, 2026-09-19: "not the same
      // on rows and columns"): a tinted, outlined box behind the hovered
      // name, drawn in the label's own orientation.
      const boxFor = (w, h) => {
        ctx.fillStyle = 'rgba(185, 28, 28, 0.16)';
        ctx.fillRect(-3, -h / 2, w + 6, h);
        ctx.strokeStyle = 'rgba(185, 28, 28, 0.9)';
        ctx.lineWidth = 1.5;
        ctx.strokeRect(-2.25, -h / 2 + 0.75, w + 4.5, h - 1.5);
        ctx.lineWidth = 1;
      };
      if (rotate) {
        ctx.save();
        ctx.translate(x, colMargin - 6);
        ctx.rotate(-Math.PI / 4);
        ctx.textAlign = 'left';
        ctx.textBaseline = 'middle';
        if (active) boxFor(ctx.measureText(text).width, Math.min(cellSize, 16));
        ctx.fillStyle = active ? LABEL_COLOR_ACTIVE : LABEL_COLOR;
        ctx.fillText(text, 0, 0);
        ctx.restore();
      } else {
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        const w = ctx.measureText(text).width;
        ctx.save();
        ctx.translate(x - w / 2, colMargin - 14);
        if (active) boxFor(w, 14);
        ctx.restore();
        ctx.fillStyle = active ? LABEL_COLOR_ACTIVE : LABEL_COLOR;
        ctx.fillText(text, x, colMargin - 14);
      }
    });
  }, [colLabels, cellSize, hover, colMargin, gridWidth, colText, ambiguousBases]);

  function cellFromEvent(e) {
    const canvas = gridCanvasRef.current;
    const rect = canvas.getBoundingClientRect();
    // CSS-pixel offsets, not device pixels: sizeCanvasForDPR scales the
    // drawing context by devicePixelRatio so every draw call already works
    // in CSS-pixel units (cellSize among them), and rect is CSS-pixel sized
    // too (canvas.style.width/height) regardless of the backing store's
    // actual (devicePixelRatio-scaled) width/height attributes.
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    if (x < 0 || y < 0) return null;
    const j = Math.floor(x / cellSize);
    const i = Math.floor(y / cellSize);
    if (i < 0 || j < 0 || i >= nRows || j >= nCols) return null;
    return { i, j };
  }

  return (
    <div>
      {/* Frozen column labels: stuck just under the site menu bar while the
          page scrolls, clipped on the left where the row labels sit, and
          translated by the scroll box's own horizontal offset. */}
      <div className="sticky z-30 bg-white border border-b-0 border-gray-200 rounded-t"
           style={{ top: navHeight }}>
        <div className="overflow-hidden" style={{ marginLeft: ROW_MARGIN, height: colMargin }}>
          <canvas ref={headerCanvasRef}
                  style={{ display: 'block', transform: `translateX(${-scrollLeft}px)` }} />
        </div>
        <div style={{ position: 'absolute', left: 0, top: 0, width: ROW_MARGIN, height: colMargin,
                      background: '#ffffff', borderRight: '1px solid #e5e7eb' }} />
      </div>
      {/* The ONLY element that scrolls horizontally; the row-label canvas
          inside stays fixed on its left. Vertical padding only: horizontal
          padding would be part of the scrolling area (NC, 2026-09-19). */}
      <div className="overflow-auto border border-t-0 border-gray-200 rounded-b pb-2 bg-white w-full"
           onScroll={(e) => setScrollLeft(e.currentTarget.scrollLeft)}>
      <div className="flex" style={{ width: 'max-content' }}>
      <canvas
        ref={rowCanvasRef}
        // Opaque background + a z-index clearly above the scrolling grid
        // canvas (NC, 2026-09-19: cells were showing through the sticky row
        // strip on horizontal scroll) -- the canvas already paints its own
        // white background and a thin rule at its right edge, but the DOM
        // element carries the same as CSS too, so the boundary holds even
        // before the draw effect has run and reads crisply regardless of
        // device pixel ratio.
        style={{
          display: 'block', position: 'sticky', left: 0, zIndex: 10, flexShrink: 0,
          backgroundColor: '#ffffff', borderRight: '1px solid #e5e7eb',
        }}
      />
      <canvas
        ref={gridCanvasRef}
        onMouseMove={(e) => {
          const c = cellFromEvent(e);
          setHover(c);
          onHover?.(c, e);
        }}
        onMouseLeave={() => { setHover(null); onHover?.(null); }}
        onClick={(e) => { const c = cellFromEvent(e); if (c) onCellClick?.(c.i, c.j); }}
        style={{ display: 'block', cursor: 'pointer', flexShrink: 0 }}
        aria-label={ariaLabel}
      />
      </div>
      </div>
    </div>
  );
}

export default function ConnectionsMap() {
  const [view, setView] = useState('author');
  const [languages, setLanguages] = useState([]);   // [] means "all"
  const [showTranslations, setShowTranslations] = useState(false);
  const [colorMode, setColorMode] = useState('links');   // 'links' (raw count) or 'lift' (relative to size)
  const [top, setTop] = useState(50);

  const [mapData, setMapData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  // "Refresh map" (NC, 2026-09-20): re-runs whichever top-level load is
  // currently showing (the matrix, or a "start from one work" row) with
  // ?refresh=1, which clears the backend's process-level caches (see
  // connections_map.reset_process_caches()) so a freshly built cache and the
  // current window ids are picked up without a process restart. Tracked
  // separately from `loading` so the button's own "Refreshing…" label and
  // disabled state do not depend on the generic map-load spinner.
  const [refreshingMap, setRefreshingMap] = useState(false);

  // {labelA, labelB, count, normalised, x, y} for the tooltip that follows
  // the cursor; x/y are the raw client coordinates.
  const [hoverInfo, setHoverInfo] = useState(null);
  const [selectedCell, setSelectedCell] = useState(null);   // {a, b, labelA, labelB}
  const [cellData, setCellData] = useState(null);
  // Third level: books x books, reached either from the Authors view's
  // nested works matrix or straight from a Works-view top-grid cell.
  const [selectedWorkCell, setSelectedWorkCell] = useState(null);   // {workA, workB, labelA, labelB}
  const [booksData, setBooksData] = useState(null);
  const [loadingBooks, setLoadingBooks] = useState(false);
  const [selectedPair, setSelectedPair] = useState(null);   // {work_a, work_b, book_a, book_b}
  const [pairData, setPairData] = useState(null);

  // The clicked cell in each grid, outlined persistently in that SAME grid
  // (NC, 2026-09-19) so it stays visible once the next grid appears below --
  // {i, j} grid coordinates, one per level.
  const [topOutline, setTopOutline] = useState(null);
  const [worksOutline, setWorksOutline] = useState(null);
  const [booksOutline, setBooksOutline] = useState(null);

  // The grid itself can run to thousands of pixels tall at a high "Top"
  // setting, so a click on a cell near row 0 appends its result far below
  // the reader's current scroll position -- indistinguishable, in practice,
  // from the click doing nothing at all. Scroll each drill-down section
  // into view the moment its state is set, rather than leaving the reader
  // to discover it by scrolling past the whole grid.
  const cellSectionRef = useRef(null);
  const booksSectionRef = useRef(null);
  const pairSectionRef = useRef(null);
  // block: 'start' (NC, 2026-09-19), not 'nearest' -- the new grid's own
  // heading needs to land at the top of the viewport, not merely somewhere
  // visible, or a tall parent grid can leave it looking like nothing moved.
  useEffect(() => {
    if (selectedCell) cellSectionRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }, [selectedCell]);
  useEffect(() => {
    if (selectedWorkCell) booksSectionRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }, [selectedWorkCell]);
  useEffect(() => {
    if (selectedPair) pairSectionRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }, [selectedPair]);

  // Browser Back unwinds the drill-down one level at a time instead of
  // leaving the map (NC, 2026-09-19: "the back button goes all the way back
  // to the start of the full map, not the subordinate maps I clicked
  // through"). Each drill step pushes a history entry carrying the
  // selections at that depth; popstate restores them (and refetches a level
  // whose data is gone). The base entry is stamped depth 0 on mount so the
  // first Back lands on the top grid rather than on the previous page.
  const pushDrill = useCallback((depth, sel) => {
    try { window.history.pushState({ mapDrill: { depth, view, ...sel } }, ''); } catch (e) { /* ignore */ }
  }, [view]);
  useEffect(() => {
    try {
      if (!window.history.state?.mapDrill) window.history.replaceState({ mapDrill: { depth: 0, view } }, '');
    } catch (e) { /* ignore */ }
  }, []);   // eslint-disable-line react-hooks/exhaustive-deps
  const dataRef = useRef({});
  dataRef.current = { cellData, booksData, pairData, view };

  // "Start from one work": a searchable picker over the raw work ids that
  // have passage windows (the same /api/passages/works Browse Corpus uses
  // for its badge), so the map can be entered from a single work rather
  // than by browsing the whole matrix.
  const [workQuery, setWorkQuery] = useState('');
  const [workOptions, setWorkOptions] = useState([]);
  const [startWork, setStartWork] = useState(null);
  const [workRow, setWorkRow] = useState(null);

  const langParam = languages.length ? languages.join(',') : '';

  // `refresh` (NC, 2026-09-20) uses `refreshingMap`, not `loading`, and skips
  // the drill-down reset: the grid section below is gated on `!loading`, so
  // routing a refresh through the ordinary `loading` flag would hide the
  // whole grid (and the "Refresh map" button along with it) for as long as
  // the request is in flight, instead of the button alone reading
  // "Refreshing…" as the owner asked for.
  const loadMap = useCallback(async (refresh = false) => {
    if (refresh) setRefreshingMap(true); else setLoading(true);
    setError(null);
    if (!refresh) {
      setSelectedCell(null);
      setCellData(null);
      setTopOutline(null);
      setWorksOutline(null);
      setSelectedWorkCell(null);
      setBooksData(null);
      setBooksOutline(null);
      setSelectedPair(null);
      setPairData(null);
    }
    try {
      const params = new URLSearchParams({ view, top: String(top) });
      if (langParam) params.set('languages', langParam);
      if (showTranslations) params.set('translations', '1');
      if (refresh) params.set('refresh', '1');
      const res = await fetch(`/api/passages/map?${params}`);
      const json = await res.json();
      if (json.error) setError(json.error);
      else setMapData(json);
    } catch (e) {
      setError(e.message || 'the connections map could not be loaded');
    } finally {
      if (refresh) setRefreshingMap(false); else setLoading(false);
    }
  }, [view, langParam, showTranslations, top]);

  useEffect(() => {
    if (!startWork) loadMap();
  }, [loadMap, startWork]);

  // Work picker options: pull the raw work-id lists for the chosen
  // languages (or all five) from the existing Browse Corpus endpoint.
  useEffect(() => {
    const codes = languages.length ? languages : LANGUAGES.map(([c]) => c);
    Promise.all(codes.map((c) => fetch(`/api/passages/works?language=${c}`).then((r) => r.json())))
      .then((results) => {
        const all = results.flatMap((r) => r.works || []);
        setWorkOptions(Array.from(new Set(all)));
      })
      .catch(() => setWorkOptions([]));
  }, [langParam]);

  const filteredWorkOptions = useMemo(() => {
    const q = workQuery.trim().toLowerCase();
    if (!q) return [];
    return workOptions.filter((w) => w.toLowerCase().includes(q)).slice(0, 25);
  }, [workQuery, workOptions]);

  const loadWorkRow = useCallback(async (work, refresh = false) => {
    if (refresh) setRefreshingMap(true); else setLoading(true);
    setError(null);
    if (!refresh) {
      setStartWork(work);
      setWorkRow(null);
      setSelectedPair(null);
      setPairData(null);
    }
    try {
      const params = new URLSearchParams({ work });
      if (langParam) params.set('languages', langParam);
      if (showTranslations) params.set('translations', '1');
      if (refresh) params.set('refresh', '1');
      const res = await fetch(`/api/passages/map/work?${params}`);
      const json = await res.json();
      if (json.error) setError(json.error);
      else setWorkRow(json);
    } catch (e) {
      setError(e.message || 'that work could not be loaded');
    } finally {
      if (refresh) setRefreshingMap(false); else setLoading(false);
    }
  }, [langParam, showTranslations]);

  // Re-runs whichever top-level load is currently on screen with
  // ?refresh=1 -- see the refreshingMap state declaration above.
  const handleRefreshMap = useCallback(() => {
    if (startWork) loadWorkRow(startWork, true);
    else loadMap(true);
  }, [startWork, loadWorkRow, loadMap]);

  const clearStartWork = () => {
    setStartWork(null);
    setWorkRow(null);
    setWorkQuery('');
  };

  const cellSize = mapData?.labels?.length ? cellSizeFor(mapData.labels.length) : MIN_CELL;

  // The diagonal reads a same-author or same-work cell as a correlation
  // unless it is called out; only Authors and Works carry a meaningful
  // diagonal at the top-grid scale (century/genre's diagonal is an ordinary,
  // real cell -- two different works can share a century or a genre --
  // so it gets no special text).
  const diagonalTextForView = (viewArg, count) => {
    if (viewArg === 'author') {
      return `same author, other works: ${count} link${count === 1 ? '' : 's'} `
        + '(same-work matches are excluded)';
    }
    if (viewArg === 'work') return 'same work, excluded';
    return null;
  };

  // The three grids' colours under the chosen mode. 'links' uses the server's
  // log scale as before; 'lift' recomputes from the raw counts client-side.
  const shownFor = (data) => (colorMode === 'lift' && data?.counts
    ? liftScale(data.counts)
    : { normalised: data?.normalised, legend: data?.legend, lift: null });
  const mapShown = useMemo(() => shownFor(mapData), [mapData, colorMode]);          // eslint-disable-line react-hooks/exhaustive-deps
  const worksShown = useMemo(() => shownFor(cellData?.works_matrix), [cellData, colorMode]);   // eslint-disable-line react-hooks/exhaustive-deps
  const booksShown = useMemo(() => shownFor(booksData), [booksData, colorMode]);    // eslint-disable-line react-hooks/exhaustive-deps

  const onHoverMatrix = (cell, evt) => {
    if (!cell || !mapData) { setHoverInfo(null); return; }
    const idA = mapData.ids[cell.i], idB = mapData.ids[cell.j];
    const count = mapData.counts[cell.i][cell.j];
    setHoverInfo({
      labelA: mapData.labels[cell.i], labelB: mapData.labels[cell.j],
      count, normalised: mapData.normalised[cell.i][cell.j],
      lift: mapShown.lift ? mapShown.lift[cell.i][cell.j] : null,
      diagonalText: idA === idB ? diagonalTextForView(view, count) : null,
      x: evt?.clientX, y: evt?.clientY,
    });
  };

  const onHoverWorksMatrix = (cell, evt) => {
    const wm = cellData?.works_matrix;
    if (!cell || !wm) { setHoverInfo(null); return; }
    const idA = wm.ids_a[cell.i], idB = wm.ids_b[cell.j];
    setHoverInfo({
      labelA: wm.labels_a[cell.i], labelB: wm.labels_b[cell.j],
      count: wm.counts[cell.i][cell.j], normalised: wm.normalised[cell.i][cell.j],
      lift: worksShown.lift ? worksShown.lift[cell.i][cell.j] : null,
      diagonalText: idA === idB ? 'same work, excluded' : null,
      x: evt?.clientX, y: evt?.clientY,
    });
  };

  const onHoverBooks = (cell, evt) => {
    if (!cell || !booksData || booksData.error) { setHoverInfo(null); return; }
    setHoverInfo({
      labelA: `book ${booksData.labels_a[cell.i]}`, labelB: `book ${booksData.labels_b[cell.j]}`,
      count: booksData.counts[cell.i][cell.j], normalised: booksData.normalised[cell.i][cell.j],
      lift: booksShown.lift ? booksShown.lift[cell.i][cell.j] : null,
      diagonalText: null,
      x: evt?.clientX, y: evt?.clientY,
    });
  };

  // Third level: books x books for one work pair (NC, 2026-09-19). Reached
  // either from the Authors view's nested works matrix, or straight from a
  // Works-view top-grid cell -- "or a cell of the Works view" -- since the
  // top grid there is already work-by-work, the finest grain it can offer.
  const loadBooks = useCallback(async (workA, workB, labelA, labelB) => {
    setSelectedWorkCell({ workA, workB, labelA, labelB });
    setBooksData(null);
    setBooksOutline(null);
    setSelectedPair(null);
    setPairData(null);
    setLoadingBooks(true);
    try {
      const params = new URLSearchParams({ work_a: workA, work_b: workB });
      const res = await fetch(`/api/passages/map/books?${params}`);
      const json = await res.json();
      setBooksData(json);
      // A pair of single-book works (Plato's Epistles against Plutarch's
      // Aratus) has no books grid to show; go straight to the passages
      // instead of a "no book-level data" notice (NC, 2026-09-19).
      if (!json.error && (!json.ids_a?.length || !json.ids_b?.length)) {
        loadPair(workA, workB);
      }
    } catch (e) {
      setError(e.message || 'the books grid could not be loaded');
    } finally {
      setLoadingBooks(false);
    }
  }, []);

  const loadCell = useCallback(async (viewArg, a, b) => {
    try {
      const params = new URLSearchParams({ view: viewArg, a, b });
      if (langParam) params.set('languages', langParam);
      if (showTranslations) params.set('translations', '1');
      const res = await fetch(`/api/passages/map/cell?${params}`);
      const json = await res.json();
      setCellData(json);
    } catch (e2) {
      setError(e2.message || 'that cell could not be loaded');
    }
  }, [langParam, showTranslations]);

  const onClickMatrixCell = (i, j) => {
    if (!mapData || i === j) return;
    const a = mapData.ids[i];
    const b = mapData.ids[j];
    const labelA = mapData.labels[i], labelB = mapData.labels[j];
    setSelectedCell({ a, b, labelA, labelB });
    setTopOutline({ i, j });
    setCellData(null);
    setWorksOutline(null);
    setSelectedWorkCell(null);
    setBooksData(null);
    setBooksOutline(null);
    setSelectedPair(null);
    setPairData(null);
    if (view === 'work') {
      // The top grid is already work-by-work -- skip straight to the books
      // level rather than showing a one-row "work pairs" list of itself.
      loadBooks(a, b, labelA, labelB);
      pushDrill(2, { selectedCell: { a, b, labelA, labelB }, topOutline: { i, j },
                     selectedWorkCell: { workA: a, workB: b, labelA, labelB } });
      return;
    }
    loadCell(view, a, b);
    pushDrill(1, { selectedCell: { a, b, labelA, labelB }, topOutline: { i, j } });
  };

  // Second level, Authors view only: a work x work cell inside the nested
  // works matrix. A same-work cell can only occur when the top-grid cell
  // clicked was an author-against-itself diagonal (both axes then list that
  // author's own works) and is always empty by construction, same as the
  // Works-view diagonal, so it is a no-op here too.
  const onClickWorksMatrixCell = (i, j) => {
    const wm = cellData?.works_matrix;
    if (!wm) return;
    const workA = wm.ids_a[i], workB = wm.ids_b[j];
    if (workA === workB) return;
    setWorksOutline({ i, j });
    loadBooks(workA, workB, wm.labels_a[i], wm.labels_b[j]);
    pushDrill(2, { selectedCell, topOutline, worksOutline: { i, j },
                   selectedWorkCell: { workA, workB, labelA: wm.labels_a[i], labelB: wm.labels_b[j] } });
  };

  // Third level: a book x book cell -- the passage pairs behind it.
  const onClickBooksCell = (i, j) => {
    if (!booksData || booksData.error || !selectedWorkCell) return;
    const bookA = booksData.ids_a[i], bookB = booksData.ids_b[j];
    setBooksOutline({ i, j });
    loadPair(selectedWorkCell.workA, selectedWorkCell.workB, bookA, bookB);
    pushDrill(3, { selectedCell, topOutline, selectedWorkCell, worksOutline, booksOutline: { i, j },
                   selectedPair: { work_a: selectedWorkCell.workA, work_b: selectedWorkCell.workB,
                                   book_a: bookA, book_b: bookB } });
  };

  const loadPair = async (work_a, work_b, book_a, book_b) => {
    setSelectedPair({ work_a, work_b, book_a, book_b });
    setPairData(null);
    try {
      const params = new URLSearchParams({ work_a, work_b });
      if (book_a) params.set('book_a', book_a);
      if (book_b) params.set('book_b', book_b);
      const res = await fetch(`/api/passages/map/pair?${params}`);
      const json = await res.json();
      setPairData(json);
    } catch (e) {
      setError(e.message || 'that work pair could not be loaded');
    }
  };

  useEffect(() => {
    const onPop = (e) => {
      const d = e.state?.mapDrill;
      if (!d) return;
      const cur = dataRef.current;
      const clearAll = () => {
        setSelectedPair(null); setPairData(null); setBooksOutline(null);
        setSelectedWorkCell(null); setBooksData(null); setWorksOutline(null);
        setSelectedCell(null); setCellData(null); setTopOutline(null);
      };
      if (d.view && d.view !== cur.view) { clearAll(); return; }
      // Level 1: the clicked top-grid cell.
      if (d.depth >= 1 && d.selectedCell) {
        setSelectedCell(d.selectedCell); setTopOutline(d.topOutline || null);
        if (!cur.cellData && d.view !== 'work') loadCell(d.view, d.selectedCell.a, d.selectedCell.b);
      } else { setSelectedCell(null); setCellData(null); setTopOutline(null); }
      // Level 2: the work pair (books grid). loadBooks clears level 3 itself,
      // so it runs before level 3 is restored.
      if (d.depth >= 2 && d.selectedWorkCell) {
        const w = d.selectedWorkCell;
        if (!cur.booksData) loadBooks(w.workA, w.workB, w.labelA, w.labelB);
        else setSelectedWorkCell(w);
        setWorksOutline(d.worksOutline || null);
      } else { setSelectedWorkCell(null); setBooksData(null); setWorksOutline(null); }
      // Level 3: the passage pairs.
      if (d.depth >= 3 && d.selectedPair) {
        const sp = d.selectedPair;
        if (!cur.pairData) loadPair(sp.work_a, sp.work_b, sp.book_a, sp.book_b);
        else setSelectedPair(sp);
        setBooksOutline(d.booksOutline || null);
      } else { setSelectedPair(null); setPairData(null); setBooksOutline(null); }
    };
    window.addEventListener('popstate', onPop);
    return () => window.removeEventListener('popstate', onPop);
  }, [loadCell, loadBooks]);   // eslint-disable-line react-hooks/exhaustive-deps

  // Author and work in full for the pair-list breadcrumb too (NC,
  // 2026-09-19), read off the first loaded pair's own windows (which already
  // carry the backend's formatted title) rather than the raw work ids
  // `selectedPair` is set with before the fetch resolves.
  const pairHeading = () => {
    if (!selectedPair) return '';
    const wa = pairData?.pairs?.[0]?.window_a;
    const wb = pairData?.pairs?.[0]?.window_b;
    const left = wa ? `${wa.author_display}, ${wa.title}` : selectedPair.work_a;
    const right = wb ? `${wb.author_display}, ${wb.title}` : selectedPair.work_b;
    return `${left} × ${right}`;
  };

  // "Start from one work": a 1xN heatmap, same component, same label
  // treatment -- the row is the chosen work, each column one of its
  // connections. Built once here so the render below stays plain JSX.
  const rowLabel = workRow && !workRow.error
    ? `${workRow.author_display}, ${startWork.split('.').slice(1).join('.').replace(/_/g, ' ') || startWork} (${workRow.language})`
    : '';
  const workCols = workRow?.connections || [];
  const workRowMax = Math.max(1, ...workCols.map((c) => c.count));
  const workRowCellSize = workCols.length ? cellSizeFor(Math.max(workCols.length, 8)) : MIN_CELL;

  const onHoverWorkRow = (cell, evt) => {
    if (!cell || !workCols.length) { setHoverInfo(null); return; }
    const c = workCols[cell.j];
    setHoverInfo({
      labelA: rowLabel, labelB: `${c.author_display}, ${c.work} (${c.language})`,
      count: c.count, normalised: c.count / workRowMax,
      x: evt?.clientX, y: evt?.clientY,
    });
  };

  const onClickWorkRowCell = (_i, j) => {
    const c = workCols[j];
    if (c) { loadPair(startWork, c.work); pushDrill(3, { selectedPair: { work_a: startWork, work_b: c.work } }); }
  };

  return (
    <div className="relative">
      <p className="text-sm text-gray-600 leading-relaxed">
        A picture of Theme Search&rsquo;s own connections: the same passage index and the
        same description comparison Similar Passages uses, rolled up by{' '}
        {VIEWS.find(([v]) => v === view)?.[1].toLowerCase()}. A link between two cells means
        their passages&rsquo; descriptions came out close, not that anything new was
        computed. Translation pairs (the same text in two languages) are hidden unless shown.
      </p>

      <div className="mt-4 flex flex-wrap items-center gap-3 text-xs">
        <span className="inline-flex rounded border border-gray-300 overflow-hidden">
          {VIEWS.map(([v, label]) => (
            <button
              key={v}
              onClick={() => { setView(v); clearStartWork(); }}
              aria-pressed={view === v}
              disabled={!!startWork}
              className={`px-2.5 py-1 font-medium ${view === v ? 'bg-red-700 text-white' : 'bg-white text-gray-700 hover:bg-gray-50'} disabled:opacity-40`}
            >
              {label}
            </button>
          ))}
        </span>

        <span className="flex flex-wrap items-center gap-1">
          {/* A button, not a caption (NC, 2026-09-19): selected by default,
              mutually exclusive with the language buttons -- picking a
              specific language deselects it, and it always reads as
              selected exactly when no specific language is chosen. */}
          <button
            type="button"
            onClick={() => setLanguages([])}
            aria-pressed={!languages.length}
            className={`px-2 py-0.5 rounded border cursor-pointer select-none ${!languages.length ? 'bg-red-600 text-white border-red-600' : 'bg-white text-gray-700 border-gray-300 hover:bg-gray-50'}`}
          >
            All languages
          </button>
          {LANGUAGES.map(([code, label]) => {
            const on = languages.includes(code);
            return (
              <label key={code}
                     className={`px-2 py-0.5 rounded border cursor-pointer select-none ${on ? 'bg-red-600 text-white border-red-600' : 'bg-white text-gray-700 border-gray-300 hover:bg-gray-50'}`}>
                <input type="checkbox" className="sr-only" checked={on}
                       onChange={() => setLanguages((prev) => (on ? prev.filter((c) => c !== code) : [...prev, code]))} />
                {label}
              </label>
            );
          })}
        </span>

        <label className="flex items-center gap-1 text-gray-700">
          <input type="checkbox" checked={showTranslations}
                 onChange={(e) => setShowTranslations(e.target.checked)} />
          Show translation pairs
        </label>

        <span className="inline-flex rounded border border-gray-300 overflow-hidden"
              title="Links: the raw number of nearest-neighbour links, on a log colour scale. Relative to size: that number divided by what the two sizes alone would predict, so a big author does not light up a whole row just by being big.">
          <span className="px-2 py-0.5 text-xs text-gray-500 bg-gray-50 border-r border-gray-300">Colour by</span>
          {[['links', 'links'], ['lift', 'relative to size']].map(([v, label]) => (
            <button key={v} type="button" onClick={() => setColorMode(v)} aria-pressed={colorMode === v}
                    className={`px-2 py-0.5 text-xs ${colorMode === v
                      ? 'bg-red-700 text-white' : 'bg-white text-gray-700 hover:bg-gray-100'}`}>
              {label}
            </button>
          ))}
        </span>

        {!startWork && (
          <label className="flex items-center gap-1 text-gray-700"
                 title={ORDER_NOTE[view] || ORDER_NOTE.author}>
            Show the
            <select value={top} onChange={(e) => setTop(Number(e.target.value))}
                    className="border border-gray-300 rounded px-1 py-0.5">
              {[30, 50, 75, 100, 150].map((n) => <option key={n} value={n}>{n}</option>)}
            </select>
            most connected {VIEW_NOUN[view] || 'entities'}
          </label>
        )}
      </div>

      {/* One short sentence rather than a sidebar full of it (NC: give the
          map the whole width) -- everything past "hover" used to live
          beside the grid; now it lives below, once a cell is chosen. */}
      <p className="mt-2 text-xs text-gray-500">
        Hover a cell for both names and the count; click a cell, then a work pair, to see the
        passages behind it.
      </p>

      <div className="mt-3 relative">
        <input
          value={workQuery}
          onChange={(e) => setWorkQuery(e.target.value)}
          placeholder="Start from one work (search by filename, e.g. vergil.aeneid)"
          className="w-full max-w-sm border border-gray-300 rounded px-3 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-red-600"
        />
        {workQuery.trim() && filteredWorkOptions.length > 0 && (
          <ul className="absolute z-10 mt-1 w-full max-w-sm bg-white border border-gray-200 rounded shadow max-h-56 overflow-auto">
            {filteredWorkOptions.map((w) => (
              <li key={w}>
                <button
                  onClick={() => { loadWorkRow(w); setWorkQuery(w); }}
                  className="w-full text-left px-3 py-1.5 text-sm hover:bg-red-50"
                >
                  {w}
                </button>
              </li>
            ))}
          </ul>
        )}
        {startWork && (
          <button onClick={clearStartWork}
                  className="ml-2 text-xs text-red-700 hover:underline">
            &larr; back to the full map
          </button>
        )}
      </div>

      {error && (
        <div className="mt-4 rounded border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">
          {error}
        </div>
      )}
      {loading && <p className="mt-4 text-sm text-gray-500 italic">Loading…</p>}

      {/* Floating tooltip: follows the cursor, names both axes and the
          count, so a reader does not have to glance away from the grid to
          learn what a cell means. */}
      {hoverInfo && hoverInfo.x != null && (
        <div
          className="pointer-events-none fixed z-50 rounded border border-gray-300 bg-white px-2 py-1 text-xs shadow-lg"
          style={{ left: hoverInfo.x + 14, top: hoverInfo.y + 14, maxWidth: '18rem' }}
        >
          <div className="font-medium text-gray-900">{hoverInfo.labelA}</div>
          <div className="text-gray-500">&times;</div>
          <div className="font-medium text-gray-900">{hoverInfo.labelB}</div>
          {hoverInfo.diagonalText ? (
            <div className="mt-1 text-gray-700">{hoverInfo.diagonalText}</div>
          ) : (
            <div className="mt-1 text-gray-700">
              {hoverInfo.count} links{hoverInfo.lift != null && hoverInfo.lift > 0
                ? `, ${hoverInfo.lift.toFixed(1)}\u00d7 what the two sizes predict` : ''}
            </div>
          )}
        </div>
      )}

      {/* The map now spans the full width of the page; the drill-down (work
          pairs, then passage pairs) appears BELOW it once something is
          clicked, not squeezed into a side column. */}
      {!startWork && !loading && mapData && !mapData.error && (
        <div className="mt-4">
          {/* The ONLY element allowed to scroll horizontally. w-full lets it
              take the whole page width; overflow-auto puts the scrollbar
              here rather than on the page body, no matter how many columns
              "Top" asks for. The row-label canvas inside stays fixed on the
              left of THIS box as it scrolls (position: sticky). Vertical
              padding only: a horizontal padding here (the old p-2) is part
              of the scrolling area, so the grid scrolled through it to the
              LEFT of the sticky label strip (NC, 2026-09-19). */}
          <div>
            <LabeledHeatmap
              rowLabels={mapData.labels}
              colLabels={mapData.labels}
              rowIds={mapData.ids}
              colIds={mapData.ids}
              normalised={mapShown.normalised}
              cellSize={cellSize}
              onHover={onHoverMatrix}
              onCellClick={onClickMatrixCell}
              outlineCell={topOutline}
              ariaLabel={`Connections map, ${view} view`}
            />
          </div>
          <ColorLegend legend={mapShown.legend} />
          {mapData.translation_pairs_hidden > 0 && (
            <p className="mt-2 text-[11px] text-gray-500">
              {mapData.translation_pairs_hidden} translation-pair link
              {mapData.translation_pairs_hidden === 1 ? '' : 's'} hidden. Toggle &ldquo;Show
              translation pairs&rdquo; to include them.
            </p>
          )}
          <p className="mt-1 text-[11px] text-gray-400 flex items-center gap-2">
            {mapBuiltFooterText(mapData.cache_built_at) && (
              <span>{mapBuiltFooterText(mapData.cache_built_at)}</span>
            )}
            <button
              onClick={handleRefreshMap}
              disabled={refreshingMap}
              className="text-xs bg-gray-100 text-gray-600 px-3 py-2 rounded hover:bg-gray-200 whitespace-nowrap disabled:opacity-60"
              title="Reload the map from the latest stored connections"
            >
              {refreshingMap ? 'Refreshing...' : 'Refresh map'}
            </button>
          </p>

          {/* Century/genre views: unchanged -- the flat list of work pairs
              behind the clicked cell, clicking one loads its passage pairs.
              Author view clicks land below instead (a nested works grid);
              Works-view clicks skip both and go straight to books. */}
          {selectedCell && (view === 'century' || view === 'genre') && (
            <div ref={cellSectionRef} className="mt-4 text-sm">
              <p className="text-xs uppercase tracking-wide text-gray-500 font-semibold">
                Work pairs: {selectedCell.labelA} &times; {selectedCell.labelB}
              </p>
              {!cellData && <p className="text-gray-500 italic mt-1">Loading…</p>}
              {cellData?.work_pairs && (
                <ul className="mt-2 space-y-1">
                  {cellData.work_pairs.map((wp) => (
                    <li key={`${wp.work_a}|${wp.work_b}`}>
                      <button
                        onClick={() => {
                          loadPair(wp.work_a, wp.work_b);
                          pushDrill(3, { selectedCell, topOutline,
                                         selectedPair: { work_a: wp.work_a, work_b: wp.work_b } });
                        }}
                        className="text-left w-full text-red-800 hover:text-red-900 hover:underline"
                      >
                        {wp.work_a} &harr; {wp.work_b} ({wp.count})
                        {wp.is_translation && (
                          <span className="ml-1 text-[10px] text-gray-500 border border-gray-300 rounded px-1">
                            translation
                          </span>
                        )}
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}

          {/* Author view: the second heatmap -- rows the first author's
              works, columns the second's, cell = link count. Clicking a
              cell here drills to the books level below. */}
          {selectedCell && view === 'author' && (
            <div ref={cellSectionRef} className="mt-4">
              {/* A breadcrumb, not just a caption (NC, 2026-09-19): naming
                  what is being compared makes it plain a new grid appeared
                  below the one just clicked, rather than nothing happening. */}
              <p className="text-xs uppercase tracking-wide text-gray-500 font-semibold">
                Work by work: {selectedCell.labelA} &times; {selectedCell.labelB}
              </p>
              {!cellData && <p className="text-gray-500 italic mt-1">Loading…</p>}
              {cellData && !cellData.works_matrix && (
                <p className="mt-2 text-sm text-gray-500">No connections at the current filters.</p>
              )}
              {cellData?.works_matrix && (
                <div className="mt-3">
                  <LabeledHeatmap
                    rowLabels={cellData.works_matrix.labels_a}
                    colLabels={cellData.works_matrix.labels_b}
                    rowIds={cellData.works_matrix.ids_a}
                    colIds={cellData.works_matrix.ids_b}
                    normalised={worksShown.normalised}
                    cellSize={cellSizeFor(Math.max(
                      cellData.works_matrix.ids_a.length, cellData.works_matrix.ids_b.length))}
                    onHover={onHoverWorksMatrix}
                    onCellClick={onClickWorksMatrixCell}
                    outlineCell={worksOutline}
                    ariaLabel={`Works of ${selectedCell.labelA} by works of ${selectedCell.labelB}`}
                  />
                </div>
              )}
              <ColorLegend legend={worksShown.legend} />
            </div>
          )}

          {/* Third level, either path: books x books for one work pair. */}
          {selectedWorkCell && (
            <div ref={booksSectionRef} className="mt-4">
              <p className="text-xs uppercase tracking-wide text-gray-500 font-semibold">
                Book by book: {selectedWorkCell.labelA} &times; {selectedWorkCell.labelB}
              </p>
              {loadingBooks && <p className="text-gray-500 italic mt-1">Loading…</p>}
              {booksData?.error && <p className="text-amber-700 mt-1">{booksData.error}</p>}
              {booksData && !booksData.error && (
                booksData.ids_a?.length > 0 && booksData.ids_b?.length > 0 ? (
                  <div className="mt-3">
                    <LabeledHeatmap
                      rowLabels={booksData.labels_a}
                      colLabels={booksData.labels_b}
                      rowIds={booksData.ids_a}
                      colIds={booksData.ids_b}
                      normalised={booksShown.normalised}
                      cellSize={cellSizeFor(Math.max(booksData.ids_a.length, booksData.ids_b.length))}
                      onHover={onHoverBooks}
                      onCellClick={onClickBooksCell}
                      outlineCell={booksOutline}
                      ariaLabel={`Books of ${selectedWorkCell.labelA} by books of ${selectedWorkCell.labelB}`}
                    />
                  </div>
                ) : (
                  <p className="mt-2 text-sm text-gray-500">No book divisions to show for this pair; the passages are listed below.</p>
                )
              )}
              <ColorLegend legend={booksShown.legend} />
            </div>
          )}

          {selectedPair && (
            <div ref={pairSectionRef} className="mt-4 text-sm">
              <p className="text-xs uppercase tracking-wide text-gray-500 font-semibold">
                Passages: {pairHeading()}
              </p>
              {!pairData && <p className="text-gray-500 italic mt-1">Loading…</p>}
              {pairData?.error && <p className="text-amber-700 mt-1">{pairData.error}</p>}
              {pairData?.pairs && (
                <ul className="mt-2 space-y-2">
                  {pairData.pairs.map((p, idx) => (
                    <li key={idx} className="border border-gray-200 rounded p-2 bg-white">
                      <div className="text-[11px] text-gray-500">score {p.score}</div>
                      <a href={readerLinkForWindow(p.window_a, p.window_b)}
                         title={p.window_a.ref_start}
                         className="block mt-0.5 text-red-800 hover:underline">
                        {passageLabel(p.window_a)} {locusOnly(p.window_a.ref_start)}
                      </a>
                      {p.window_a.gist && <p className="text-gray-700 text-xs">{p.window_a.gist}</p>}
                      <a href={readerLinkForWindow(p.window_b, p.window_a)}
                         title={p.window_b.ref_start}
                         className="block mt-1 text-red-800 hover:underline">
                        {passageLabel(p.window_b)} {locusOnly(p.window_b.ref_start)}
                      </a>
                      {p.window_b.gist && <p className="text-gray-700 text-xs">{p.window_b.gist}</p>}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}
        </div>
      )}

      {startWork && (
        <div className="mt-4">
          {workRow && !workRow.error && (
            <div>
              <h3 className="font-medium text-gray-900">
                {rowLabel} &mdash; {workRow.count} connection{workRow.count === 1 ? '' : 's'}
              </h3>
              {workCols.length > 0 ? (
                <div className="mt-3">
                  <LabeledHeatmap
                    rowLabels={[rowLabel]}
                    colLabels={workCols.map((c) => `${c.author_display}, ${c.work} (${c.language})`)}
                    normalised={[workCols.map((c) => c.count / workRowMax)]}
                    cellSize={workRowCellSize}
                    onHover={onHoverWorkRow}
                    onCellClick={onClickWorkRowCell}
                    ariaLabel={`Connections for ${rowLabel}`}
                  />
                </div>
              ) : (
                <p className="mt-2 text-sm text-gray-500">No connections at the current filters.</p>
              )}
              <p className="mt-1 text-[11px] text-gray-400 flex items-center gap-2">
                {mapBuiltFooterText(workRow.cache_built_at) && (
                  <span>{mapBuiltFooterText(workRow.cache_built_at)}</span>
                )}
                <button
                  onClick={handleRefreshMap}
                  disabled={refreshingMap}
                  className="text-xs bg-gray-100 text-gray-600 px-3 py-2 rounded hover:bg-gray-200 whitespace-nowrap disabled:opacity-60"
                  title="Reload the map from the latest stored connections"
                >
                  {refreshingMap ? 'Refreshing...' : 'Refresh map'}
                </button>
              </p>
            </div>
          )}
          {workRow?.error && <p className="text-amber-700 text-sm">{workRow.error}</p>}

          {selectedPair && (
            <div ref={pairSectionRef} className="mt-4">
              <p className="text-xs uppercase tracking-wide text-gray-500 font-semibold">
                Passages: {pairHeading()}
              </p>
              {!pairData && <p className="text-gray-500 italic mt-1">Loading…</p>}
              {pairData?.pairs && (
                <ul className="mt-2 space-y-2 text-sm">
                  {pairData.pairs.map((p, idx) => (
                    <li key={idx} className="border border-gray-200 rounded p-2 bg-white">
                      <div className="text-[11px] text-gray-500">score {p.score}</div>
                      <a href={readerLinkForWindow(p.window_a, p.window_b)}
                         title={p.window_a.ref_start}
                         className="block mt-0.5 text-red-800 hover:underline">
                        {passageLabel(p.window_a)} {locusOnly(p.window_a.ref_start)}
                      </a>
                      {p.window_a.gist && <p className="text-gray-700 text-xs">{p.window_a.gist}</p>}
                      <a href={readerLinkForWindow(p.window_b, p.window_a)}
                         title={p.window_b.ref_start}
                         className="block mt-1 text-red-800 hover:underline">
                        {passageLabel(p.window_b)} {locusOnly(p.window_b.ref_start)}
                      </a>
                      {p.window_b.gist && <p className="text-gray-700 text-xs">{p.window_b.gist}</p>}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}
        </div>
      )}

      {!loading && mapData?.error && (
        <p className="mt-4 text-sm text-amber-700">{mapData.error}</p>
      )}
    </div>
  );
}
