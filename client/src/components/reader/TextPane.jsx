import { useCallback, useRef } from 'react';
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
  const anchor = useRef(null);

  const isSelected = useCallback((ref) => {
    if (!selection) return false;
    const { startIdx, endIdx } = selection;
    const i = units.findIndex((u) => u.ref === ref);
    return i >= Math.min(startIdx, endIdx) && i <= Math.max(startIdx, endIdx);
  }, [selection, units]);

  const begin = (idx) => { anchor.current = idx; emit(idx, idx); };
  const extend = (idx) => { if (anchor.current != null) emit(anchor.current, idx); };

  const emit = (a, b) => {
    const lo = Math.min(a, b);
    const hi = Math.max(a, b);
    onSelect?.({
      startIdx: lo,
      endIdx: hi,
      refStart: units[lo]?.ref,
      refEnd: units[hi]?.ref,
      lineCount: hi - lo + 1,
    });
  };

  const rtl = RTL.has(language);

  return (
    <div
      className="flex-1 px-6 py-6 overflow-y-auto"
      onMouseUp={() => { anchor.current = null; }}
      onMouseLeave={() => { anchor.current = null; }}
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
              onMouseDown={() => begin(i)}
              onMouseEnter={(e) => { if (e.buttons === 1) extend(i); }}
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
