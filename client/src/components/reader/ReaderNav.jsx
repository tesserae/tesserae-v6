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

/** The per-book files among `sections`. The corpus hierarchy lists a work's
 *  whole-file copy as a section too (labelled with the work's title), and
 *  stepping through books must skip it; a work held only as one file keeps
 *  its single section. */
export function bookSections(sections) {
  const parts = (sections || []).filter((s) => /\.part\.\d+\.tess$/.test(s.file || ''));
  return parts.length ? parts : (sections || []);
}

/** For a whole-file work that also exists as book files: the book file that
 *  holds `ref` (a locus like "sil. 8.135" names book 8), or the first book
 *  when no ref is given. '' when `work` already is a book file or the work
 *  has no book files (NC, 2026-09-20: works with books are read one book at
 *  a time; the whole-file Punica ran seventeen books together). */
export function bookFileFor(sections, work, ref) {
  const id = String(work || '');
  if (/\.part\.\d+\.tess$/.test(id)) return '';
  const base = id.replace(/\.tess$/, '');
  const mine = (sections || []).filter((s) => (s.file || '').startsWith(`${base}.part.`));
  if (!mine.length) return '';
  const m = /(\d+)\.\d+/.exec(String(ref || ''));
  if (m) {
    const hit = mine.find((s) => s.file === `${base}.part.${m[1]}.tess`);
    if (hit) return hit.file;
  }
  return mine[0].file;
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
  const books = bookSections(sections);
  const { prev, next } = neighbours(books, work);
  if (books.length < 2) return null;
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

function scrollToEnd() {
  window.scrollTo({ top: document.documentElement.scrollHeight, behavior: 'smooth' });
}

const floatCls = 'w-9 h-9 rounded-full border border-gray-300 bg-white/95 shadow text-gray-700 '
  + 'text-sm leading-none hover:bg-gray-100 disabled:opacity-40 disabled:hover:bg-white '
  + 'disabled:cursor-default';

/** A small fixed cluster at the bottom left of the window, on screen wherever
 *  the reader is in the text: to the top, to the end, and the previous and
 *  next book (NC, 2026-09-20: "we still don't have a way of navigating up and
 *  down the page easily"). Fixed positioning does not depend on the sticky
 *  strip, whose behaviour NC could not see. Hidden on phones, where the
 *  bottom sheet lives. */
export function ReaderFloatNav({ sections, work, onWork }) {
  const books = bookSections(sections);
  const { prev, next } = neighbours(books, work);
  const go = (s) => { onWork(s.file); scrollToTop(); };
  return (
    <div className="hidden md:flex fixed bottom-4 left-4 z-30 flex-col gap-1 print:hidden"
         role="navigation" aria-label="Reader navigation">
      <button type="button" className={floatCls} onClick={scrollToTop}
              aria-label="Back to top" title="Back to top">&#9650;</button>
      <button type="button" className={floatCls} onClick={scrollToEnd}
              aria-label="To the end" title="To the end">&#9660;</button>
      {books.length > 1 && (
        <>
          <button type="button" className={floatCls} disabled={!prev}
                  onClick={() => prev && go(prev)}
                  aria-label={prev ? `Previous: ${prev.label}` : 'No previous book'}
                  title={prev ? prev.label : 'No previous book'}>&#8249;</button>
          <button type="button" className={floatCls} disabled={!next}
                  onClick={() => next && go(next)}
                  aria-label={next ? `Next: ${next.label}` : 'No next book'}
                  title={next ? next.label : 'No next book'}>&#8250;</button>
        </>
      )}
    </div>
  );
}
