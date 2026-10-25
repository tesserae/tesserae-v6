/**
 * In-text navigation for the Reader (2026-09-19): previously the only option
 * from the bottom of a text was a long scroll back up.
 *
 * ReaderNav is a thin strip that sticks to the top of the text column while
 * the page scrolls: previous and next book, a "go to line" box, and Back to
 * top. ReaderEndNav repeats the book links and Back to top once the whole
 * text is on screen, so the end of a book leads somewhere. Both take the
 * work's sections (the per-book files from the corpus hierarchy) and the
 * same onWork callback the header's Book dropdown uses.
 */
import { useEffect, useState } from 'react';
import { useIsPhone } from '../../hooks/useIsPhone';

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
  const parts = (sections || []).filter((s) => /\.part\.\d+(\.[^.]+)?\.tess$/.test(s.file || ''));
  return parts.length ? parts : (sections || []);
}

/** For a whole-file work that also exists as book files: the book file that
 *  holds `ref` (a locus like "sil. 8.135" names book 8), or the first book
 *  when no ref is given. '' when `work` already is a book file or the work
 *  has no book files (2026-09-20: works with books are read one book at
 *  a time; the whole-file Punica ran seventeen books together). */
export function bookFileFor(sections, work, ref) {
  const id = String(work || '');
  if (/\.part\.\d+(\.[^.]+)?\.tess$/.test(id)) return '';
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

/** "151.1.1": the story, couplet and hemistich at the end of a dotted ref
 *  ("ferdowsi.shahnameh.151.1.1"). This is what the Go to line path takes. */
export function storyShortRef(ref) {
  return String(ref || '').split('.').slice(-3).join('.');
}

/** The story number a dotted ref falls in ("ferdowsi.shahnameh.151.1.1" is
 *  story 151), or null. */
export function storyNumberOfRef(ref) {
  const m = /\.(\d+)\.\d+\.\d+$/.exec(String(ref || ''));
  return m ? Number(m[1]) : null;
}

/** The number of the story or section that holds `ref`: the last entry whose
 *  first_ref is not after it, comparing the numbers that end each ref
 *  ("rumi.masnavi.2.1.1" is [2, 1, 1]). Null when nothing is known. Works for
 *  the Shahnameh's stories and for the sections of the Persian and Urdu works,
 *  whose refs are not all story.couplet.hemistich. */
function refNumbers(ref) {
  const m = /(?:\.\d+)+$/.exec(String(ref || ''));
  return m ? m[0].slice(1).split('.').map(Number) : [];
}
function cmpNumbers(a, b) {
  for (let i = 0; i < Math.max(a.length, b.length); i += 1) {
    const d = (a[i] ?? 0) - (b[i] ?? 0);
    if (d) return d;
  }
  return 0;
}
export function storyNumberForRef(stories, ref) {
  const at = refNumbers(ref);
  if (!at.length || !stories?.length) return null;
  let found = null;
  for (const s of stories) {
    if (cmpNumbers(refNumbers(s.first_ref), at) <= 0) found = s.number;
    else break;
  }
  return found;
}

/** "151 Rustam and Suhrab" with the Persian title after it when there is one. */
export function storyLabel(s, withNative = false) {
  const en = s.title_en || '';
  const head = `${s.number}${en ? ` ${en}` : ''}`;
  return withNative && s.title_fa ? `${head} \u00b7 ${s.title_fa}` : head;
}

/** The stories either side of story `number` (null at the ends). With no
 *  number known the reader is taken to be at the first story. */
export function storyNeighbours(stories, number) {
  const list = stories || [];
  let i = list.findIndex((s) => s.number === number);
  if (i < 0) i = 0;
  return { prev: list[i - 1] || null, next: list[i + 1] || null };
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

export function BookLinks({ sections, work, onWork, size }) {
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

/** Previous and next story, for a work divided into stories rather than
 *  book files (the Shahnameh). `onStory(story)` jumps to the story's start. */
export function StoryLinks({ stories, storyNumber, onStory, size, storyUnit = 'story' }) {
  const unit = storyUnit === 'section' ? 'section' : 'story';
  const Unit = unit === 'section' ? 'Section' : 'Story';
  if (!stories || stories.length < 2) return null;
  const { prev, next } = storyNeighbours(stories, storyNumber);
  return (
    <>
      <button type="button" className={`${linkCls} ${size}`} disabled={!prev}
              onClick={() => prev && onStory(prev)}
              aria-label={prev ? `Previous ${unit}: ${storyLabel(prev)}` : `No previous ${unit}`}
              title={prev ? storyLabel(prev, true) : ''}>
        &#8249; {prev ? `${Unit} ${prev.number}` : 'Previous'}
      </button>
      <button type="button" className={`${linkCls} ${size}`} disabled={!next}
              onClick={() => next && onStory(next)}
              aria-label={next ? `Next ${unit}: ${storyLabel(next)}` : `No next ${unit}`}
              title={next ? storyLabel(next, true) : ''}>
        {next ? `${Unit} ${next.number}` : 'Next'} &#8250;
      </button>
    </>
  );
}

/** The "Go to line" box. `onJump(query)` returns '' when the Reader found the
 *  line, otherwise a short message to show. `onDone` runs after a good jump.
 *  Used by the sticky strip and by the phone picker sheet. */
export function GoToLineForm({ onJump, onDone, size = 'text-[11px]', className = 'flex items-center gap-1 ml-1', inputWidth = 'w-20' }) {
  const [q, setQ] = useState('');
  const [miss, setMiss] = useState('');

  const submit = (e) => {
    e.preventDefault();
    const query = q.trim();
    if (!query) return;
    const problem = onJump(query) || '';
    setMiss(problem);
    if (!problem) {
      setQ('');
      if (onDone) onDone();
    }
  };

  return (
    <form onSubmit={submit} className={className}>
      <label className="flex items-center gap-1">
        <span>Go to line</span>
        <input
          value={q}
          onChange={(e) => { setQ(e.target.value); if (miss) setMiss(''); }}
          placeholder="e.g. 6.851"
          aria-label="Go to line"
          className={`${inputWidth} rounded border border-gray-300 px-1.5 py-0.5 ${size}
                     focus:outline-none focus:ring-1 focus:ring-red-600`}
        />
      </label>
      <button type="submit" className={`${linkCls} ${size}`}>Go</button>
      {miss && <span className="text-red-700" role="status">{miss}</span>}
    </form>
  );
}

/**
 * The sticky strip. `onJump(query)` returns '' when the Reader found the
 * line and is scrolling to it, otherwise a short message for the box to show
 * ("no line 6.9999 here", or that a bare number is ambiguous in this file).
 * On a phone it renders nothing: its controls live in the header's picker sheet.
 */
export default function ReaderNav({ sections, work, onWork, onJump, stories, storyNumber, onStory, storyUnit = 'story' }) {
  const phone = useIsPhone();
  if (phone) return null;

  return (
    <div data-reader-nav-strip className="sticky top-0 z-20 flex flex-wrap items-center gap-1.5 px-3 py-1
                    text-[11px] text-gray-600 border-b border-gray-200 bg-white">
      <BookLinks sections={sections} work={work} onWork={onWork} size="text-[11px]" />
      <StoryLinks stories={stories} storyNumber={storyNumber} onStory={onStory} size="text-[11px]" storyUnit={storyUnit} />
      <GoToLineForm onJump={onJump} />
      <button type="button" onClick={scrollToTop}
              className={`${linkCls} text-[11px] ml-auto`} aria-label="Back to top">
        &#9650; Top
      </button>
    </div>
  );
}

/** The links again at the end of the text, where the reader actually is when
 *  a book runs out. Rendered by ReaderPage only once every line is shown. */
export function ReaderEndNav({ sections, work, onWork, stories, storyNumber, onStory, storyUnit = 'story' }) {
  return (
    <div className="flex flex-wrap items-center justify-center gap-2 px-3 py-4
                    text-sm text-gray-600 border-t border-gray-200 bg-gray-50">
      <BookLinks sections={sections} work={work} onWork={onWork} size="text-sm" />
      <StoryLinks stories={stories} storyNumber={storyNumber} onStory={onStory} size="text-sm" storyUnit={storyUnit} />
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
 *  next book (2026-09-20): there was no way to navigate up and down the
 *  page easily. Fixed positioning does not depend on the sticky strip,
 *  which did not behave reliably. Hidden on phones, where the bottom
 *  sheet lives. */
export function ReaderFloatNav({ sections, work, onWork, stories, storyNumber, onStory, storyUnit = 'story' }) {
  const books = bookSections(sections);
  const { prev, next } = neighbours(books, work);
  const unit = storyUnit === 'section' ? 'section' : 'story';
  const storyNav = stories && stories.length > 1 ? storyNeighbours(stories, storyNumber) : null;
  const go = (s) => { onWork(s.file); scrollToTop(); };
  return (
    <div className="hidden md:flex fixed bottom-4 left-4 z-30 flex-col gap-1 print:hidden"
         role="navigation" aria-label="Reader navigation">
      <button type="button" className={floatCls} onClick={scrollToTop}
              aria-label="Back to top" title="Back to top">&#9650;</button>
      <button type="button" className={floatCls} onClick={scrollToEnd}
              aria-label="To the end" title="To the end">&#9660;</button>
      {storyNav && (
        <>
          <button type="button" className={floatCls} disabled={!storyNav.prev}
                  onClick={() => storyNav.prev && onStory(storyNav.prev)}
                  aria-label={storyNav.prev ? `Previous ${unit}: ${storyLabel(storyNav.prev)}` : `No previous ${unit}`}
                  title={storyNav.prev ? storyLabel(storyNav.prev) : `No previous ${unit}`}>&#8249;</button>
          <button type="button" className={floatCls} disabled={!storyNav.next}
                  onClick={() => storyNav.next && onStory(storyNav.next)}
                  aria-label={storyNav.next ? `Next ${unit}: ${storyLabel(storyNav.next)}` : `No next ${unit}`}
                  title={storyNav.next ? storyLabel(storyNav.next) : `No next ${unit}`}>&#8250;</button>
        </>
      )}
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

/** Phone only: a round "Back to top" button at the bottom left, shown after
 *  the page has scrolled more than 600 pixels and hidden while the results
 *  sheet is open (`hidden`). It sits above the closed sheet's tab strip. */
export function ReaderPhoneTopButton({ hidden }) {
  const phone = useIsPhone();
  const [far, setFar] = useState(false);
  useEffect(() => {
    if (!phone) return undefined;
    const onScroll = () => setFar(window.scrollY > 600);
    onScroll();
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, [phone]);
  if (!phone || !far || hidden) return null;
  return (
    <button type="button" className={`${floatCls} fixed bottom-[3.5rem] left-3 z-30 print:hidden`}
            onClick={scrollToTop} aria-label="Back to top" title="Back to top">&#9650;</button>
  );
}
