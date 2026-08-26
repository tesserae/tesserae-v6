import { useCallback } from 'react';
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
export default function TextPane({ units, language, selection, onSelect }) {

  const isSelected = useCallback((ref) => {
    if (!selection) return false;
    const { startIdx, endIdx } = selection;
    const i = units.findIndex((u) => u.ref === ref);
    return i >= Math.min(startIdx, endIdx) && i <= Math.max(startIdx, endIdx);
  }, [selection, units]);

  // THE BROWSER'S SELECTION IS THE SELECTION.
  //
  // This used to track its own drag with mousedown and mouseenter while the
  // browser did its own selecting underneath, and the two disagreed: the page
  // showed twenty lines highlighted in blue while the panel said "1 line
  // selected". Reading the native selection instead means there is only one
  // answer to what is selected, and ordinary text selection works as it does
  // everywhere else, including keyboard and double-click.
  const emit = (a, b, anchorTop) => {
    const lo = Math.min(a, b);
    const hi = Math.max(a, b);
    onSelect?.({
      startIdx: lo,
      endIdx: hi,
      refStart: units[lo]?.ref,
      refEnd: units[hi]?.ref,
      lineCount: hi - lo + 1,
      anchorTop,
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
    emit(lo, hi, el ? el.offsetTop + el.offsetHeight : 0);
  };

  const rtl = RTL.has(language);

  return (
    <div
      className="flex-1 px-6 py-6 overflow-y-auto"
      onMouseUp={readSelection}
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
          const selected = isSelected(u.ref);
          return (
            <div
              key={u.ref}
              id={`line-${cssRef(u.ref)}`}
              className={`grid gap-2 cursor-text ${selected ? 'bg-red-50 border-l-[3px] border-red-700 -ml-[3px] rounded-r' : ''}`}
              style={{ gridTemplateColumns: '2.6rem 1fr', minHeight: '1.75rem' }}
            >
              <span
                className="text-[0.72rem] text-gray-400 text-right pt-[0.35em] tabular-nums select-none"
                style={{ fontFamily: 'inherit' }}
              >
                {showNumber ? n : ''}
              </span>
              <p className="m-0">{u.text}</p>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function lineNumber(ref) {
  const nums = String(ref || '').match(/\d+/g);
  return nums ? parseInt(nums[nums.length - 1], 10) : null;
}
