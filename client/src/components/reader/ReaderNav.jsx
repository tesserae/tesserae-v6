/**
 * In-text navigation for the Reader (NC, 2026-09-19: "the only option from
 * the bottom of a text is a long scroll back up").
 *
 * ReaderNav is a thin strip that sticks to the top of the text column while
 * the page scrolls: previous and next book, a "go to line" box, and Back to
 * top. ReaderEndNav repeats the book links and Back to top once the whole
 * text is on screen, so the end of a book leads somewhere. Both take the
 * work's sections (the per-book files from the corpus hierarchy) and the
 * same onWork callback the header's Book dropdown uses.
 */
import { useState } from 'react';

/** The sections (books) of the work that contains `work`, from the corpus
 *  hierarchy, or [] when the hierarchy has not loaded or the work is unknown.
 *  Same lookup as ReaderHeader's dropdowns. */
export function sectionsFor(hierarchy, work) {
  const id = String(work || '');
  for (const a of hierarchy || []) {
    for (const w of a.works || []) {
      const sections = w.sections || [];
      if (sections.some((s) => s.file === id)) return sections;
    }
  }
  return [];
}

function neighbours(sections, work) {
  const i = sections.findIndex((s) => s.file === work);
  if (i < 0) return { prev: null, next: null };
  return { prev: sections[i - 1] || null, next: sections[i + 1] || null };
}

function scrollToTop() {
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

const linkCls = 'px-1.5 py-0.5 rounded border border-gray-300 bg-white text-gray-700 '
  + 'hover:bg-gray-100 hover:border-gray-400 disabled:opacity-40 disabled:hover:bg-white '
  + 'disabled:cursor-default whitespace-nowrap';

function BookLinks({ sections, work, onWork, size }) {
  const { prev, next } = neighbours(sections, work);
  if (sections.length < 2) return null;
  const go = (s) => { onWork(s.file); scrollToTop(); };
  return (
    <>
      <button type="button" className={`${linkCls} ${size}`} disabled={!prev}
              onClick={() => prev && go(prev)}
              aria-label={prev ? `Previous: ${prev.label}` : 'No previous book'}
              title={prev ? prev.label : ''}>
        &#8249; {prev ? prev.label : 'Previous'}
      </button>
      <button type="button" className={`${linkCls} ${size}`} disabled={!next}
              onClick={() => next && go(next)}
              aria-label={next ? `Next: ${next.label}` : 'No next book'}
              title={next ? next.label : ''}>
        {next ? next.label : 'Next'} &#8250;
      </button>
    </>
  );
}

/**
 * The sticky strip. `onJump(query)` returns '' when the Reader found the
 * line and is scrolling to it, otherwise a short message for the box to show
 * ("no line 6.9999 here", or that a bare number is ambiguous in this file).
 */
export default function ReaderNav({ sections, work, onWork, onJump }) {
  const [q, setQ] = useState('');
  const [miss, setMiss] = useState('');

  const submit = (e) => {
    e.preventDefault();
    const query = q.trim();
    if (!query) return;
    const problem = onJump(query) || '';
    setMiss(problem);
    if (!problem) setQ('');
  };

  return (
    <div className="sticky top-0 z-20 flex flex-wrap items-center gap-1.5 px-3 py-1
                    text-[11px] text-gray-600 border-b border-gray-200 bg-white">
      <BookLinks sections={sections} work={work} onWork={onWork} size="text-[11px]" />
      <form onSubmit={submit} className="flex items-center gap-1 ml-1">
        <label className="flex items-center gap-1">
          <span>Go to line</span>
          <input
            value={q}
            onChange={(e) => { setQ(e.target.value); if (miss) setMiss(''); }}
            placeholder="e.g. 6.851"
            aria-label="Go to line"
            className="w-20 rounded border border-gray-300 px-1.5 py-0.5 text-[11px]
                       focus:outline-none focus:ring-1 focus:ring-red-600"
          />
        </label>
        <button type="submit" className={`${linkCls} text-[11px]`}>Go</button>
        {miss && <span className="text-red-700" role="status">{miss}</span>}
      </form>
      <button type="button" onClick={scrollToTop}
              className={`${linkCls} text-[11px] ml-auto`} aria-label="Back to top">
        &#9650; Top
      </button>
    </div>
  );
}

/** The links again at the end of the text, where the reader actually is when
 *  a book runs out. Rendered by ReaderPage only once every line is shown. */
export function ReaderEndNav({ sections, work, onWork }) {
  return (
    <div className="flex flex-wrap items-center justify-center gap-2 px-3 py-4
                    text-sm text-gray-600 border-t border-gray-200 bg-gray-50">
      <BookLinks sections={sections} work={work} onWork={onWork} size="text-sm" />
      <button type="button" onClick={scrollToTop} className={`${linkCls} text-sm`}
              aria-label="Back to top">
        &#9650; Back to top
      </button>
    </div>
  );
}
