import { useCallback, useEffect, useRef } from 'react';
import { cssRef } from './refId';

const RTL = new Set(['he']);

/**
 * The reading surface: the text itself, with selection.
 *
 * Selection size routes the query, so a reader never chooses a search type. A
 * click selects one line, a drag selects a span, and the panel decides what to
 * ask on that basis (a line asks both engines, a passage asks for content
 * matches). Reference numbers appear every fifth line, the convention in printed
 * editions, so the margin stays quiet while remaining navigable.
 */
export default function TextPane({ units, language, selection, onSelect, total, onMore }) {
  // LONG TEXTS ARRIVE IN STRETCHES. Hafez's diwan is 9,502 lines and Anvari's
  // 26,616; drawing every line and gutter tile at once froze a phone and
  // crashed its tab (NC, 2026-09-07). The page draws what it has been given
  // and asks for more when the reader nears the end, or when they press the
  // button. `total` is the whole text's line count, `onMore` extends it.
  const sentinelRef = useRef(null);
  useEffect(() => {
    if (!onMore || !sentinelRef.current || (total != null && units.length >= total)) return undefined;
    if (typeof IntersectionObserver === 'undefined') return undefined;
    const obs = new IntersectionObserver((entries) => {
      if (entries.some((e) => e.isIntersecting)) onMore();
    }, { rootMargin: '600px 0px' });
    obs.observe(sentinelRef.current);
    return () => obs.disconnect();
  }, [onMore, total, units.length]);

  // By index, not by searching the ref: the old test ran findIndex for every
  // line on every render, 90 million comparisons for a 9,500-line diwan, and
  // a click in Anvari took several seconds to show its highlight.
  const selLo = selection ? Math.min(selection.startIdx, selection.endIdx) : -1;
  const selHi = selection ? Math.max(selection.startIdx, selection.endIdx) : -1;
  const isSelected = useCallback((i) => selection != null && i >= selLo && i <= selHi,
    [selection, selLo, selHi]);

  // THE BROWSER'S SELECTION IS THE SELECTION.
  //
  // This used to track its own drag with mousedown and mouseenter while the
  // browser did its own selecting underneath, and the two disagreed: the page
  // showed twenty lines highlighted in blue while the panel said "1 line
  // selected". Reading the native selection instead means there is only one
  // answer to what is selected, and ordinary text selection works as it does
  // everywhere else, including keyboard and double-click.
  const emit = (a, b, anchorTop, text) => {
    const lo = Math.min(a, b);
    const hi = Math.max(a, b);
    onSelect?.({
      startIdx: lo,
      endIdx: hi,
      refStart: units[lo]?.ref,
      refEnd: units[hi]?.ref,
      lineCount: hi - lo + 1,
      anchorTop,
      // The literal characters the reader swept, so the toolbar can tell a
      // double-clicked word from a whole line and search for the word itself.
      text: text || '',
    });
  };

  /** The index of the line element containing a DOM node, or -1. */
  const lineIndexOf = (node) => {
    let el = node && (node.nodeType === 1 ? node : node.parentElement);
    while (el && !(el.id || '').startsWith('line-')) el = el.parentElement;
    if (!el) return -1;
    return units.findIndex((u) => `line-${cssRef(u.ref)}` === el.id);
  };

  const readSelection = () => {
    const sel = window.getSelection();
    if (!sel || sel.rangeCount === 0) return;
    const a = lineIndexOf(sel.anchorNode);
    const b = lineIndexOf(sel.focusNode);
    if (a < 0 && b < 0) return;
    const lo = Math.min(a < 0 ? b : a, b < 0 ? a : b);
    const hi = Math.max(a, b);
    // Where to put the popup: just under the last line of the selection, so it
    // never covers what was selected. It used to sit at the top-left corner of
    // the pane whatever the reader had chosen.
    const el = document.getElementById(`line-${cssRef(units[hi]?.ref)}`);
    emit(lo, hi, el ? el.offsetTop + el.offsetHeight : 0, String(sel).trim());
  };

  const rtl = RTL.has(language);
  const coarse = typeof window !== 'undefined' && window.matchMedia
    && window.matchMedia('(pointer: coarse)').matches;

  // Touch screens select by tapping (below), with native selection switched
  // off, so there is no finger drag to read. A selectionchange listener that
  // read the selection during a MOUSE drag re-rendered the lines mid-drag
  // and made the browser's highlight jump from the first line to the second
  // (NC, 2026-09-07); it is gone.
  const paneRef = useRef(null);

  return (
    <div
      ref={paneRef}
      className="flex-1 px-6 py-6 overflow-y-auto reader-text"
      onMouseUp={coarse ? undefined : readSelection}
      onKeyUp={(e) => { if (e.shiftKey) readSelection(); }}
    >
      <div
        className="max-w-3xl"
        style={{ fontFamily: '"Gentium Book Plus", Georgia, serif', fontSize: '1.06rem', lineHeight: 1.75 }}
        dir={rtl ? 'rtl' : 'ltr'}
      >
        {units.map((u, i) => {
          const n = lineNumber(u.ref);
          const showNumber = n != null && n % 5 === 0;
          const selected = isSelected(i);
          return (
            <div
              key={u.ref}
              id={`line-${cssRef(u.ref)}`}
              className={`grid gap-2 cursor-text ${selected ? 'bg-red-50 border-l-[3px] border-red-700 -ml-[3px] rounded-r' : ''}`}
              style={{ gridTemplateColumns: '2.6rem 1fr', minHeight: '1.75rem' }}
              // A tap on a phone makes no text selection, so nothing used to
              // happen. A click or tap that leaves no selection selects the
              // line itself; a drag still selects the swept span.
              onClick={(e) => {
                const el = e.currentTarget;
                const bottom = el.offsetTop + el.offsetHeight;
                if (coarse) {
                  // TOUCH SCREENS SELECT BY TAPPING. Native text selection is
                  // off there (see index.css), so the phone's own Copy bar
                  // never appears over the page (NC, 2026-09-07). A tap
                  // selects a line; a tap on another line extends the span
                  // to it; a tap inside the span narrows it to that line.
                  if (selection && (i < selLo || i > selHi)) {
                    emit(Math.min(selLo, i), Math.max(selHi, i), bottom, '');
                  } else {
                    emit(i, i, bottom, u.text);
                  }
                  return;
                }
                const s = window.getSelection();
                if (s && !s.isCollapsed && String(s).trim()) return;
                emit(i, i, bottom, u.text);
              }}
            >
              <span
                className="text-[0.72rem] text-gray-500 text-right pt-[0.35em] tabular-nums select-none"
                style={{ fontFamily: 'inherit' }}
              >
                {showNumber ? n : ''}
              </span>
              <p className="m-0">{u.text}</p>
            </div>
          );
        })}
        {total != null && units.length < total && (
          <div ref={sentinelRef} className="py-4 text-center" dir="ltr">
            <button
              type="button"
              onClick={onMore}
              className="text-sm px-3 py-1.5 rounded border border-gray-300 text-gray-700 hover:border-red-600 hover:text-red-700"
            >
              Show more ({units.length.toLocaleString()} of {total.toLocaleString()} lines shown)
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

function lineNumber(ref) {
  const nums = String(ref || '').match(/\d+/g);
  return nums ? parseInt(nums[nums.length - 1], 10) : null;
}
