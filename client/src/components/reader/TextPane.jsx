import { useCallback, useEffect, useRef, useState } from 'react';
import { cssRef } from './refId';
import { RTL_LANGS as RTL } from '../../utils/rtl';
import { useIsPhone } from '../../hooks/useIsPhone';
import { sentencesOf, sentenceFields, sentenceRangeOf } from '../../utils/sentences';

// The sentences of a long unit, cut once per text. Most units are verse lines
// and have none (null).
const partsCache = new Map();
function partsOf(text) {
  if (!text || text.length <= 400) return null;
  if (!partsCache.has(text)) {
    if (partsCache.size > 4000) partsCache.clear();
    partsCache.set(text, sentencesOf(text));
  }
  return partsCache.get(text);
}

/** The sentence index of the <span data-sentence> holding a DOM node, or null. */
function sentenceIndexOf(node) {
  const el = node && (node.nodeType === 1 ? node : node.parentElement);
  const span = el && el.closest ? el.closest('[data-sentence]') : null;
  return span ? Number(span.getAttribute('data-sentence')) : null;
}

/**
 * The reading surface: the text itself, with selection.
 *
 * Selection size routes the query, so a reader never chooses a search type. A
 * click selects one line, a drag selects a span, and the panel decides what to
 * ask on that basis (a line asks both engines, a passage asks for content
 * matches). Reference numbers appear every fifth line, the convention in printed
 * editions, so the margin stays quiet while remaining navigable.
 */
export default function TextPane({ units, language, selection, onSelect, total, onMore,
                                    reuseMarks, onReuseClick, documentsTrial }) {
  // On a phone: a narrower line-number column, a smaller gap and a hanging
  // indent, so the text has the width and a wrapped line reads as one line.
  const phone = useIsPhone();
  // LONG TEXTS ARRIVE IN STRETCHES. Hafez's diwan is 9,502 lines and Anvari's
  // 26,616; drawing every line and gutter tile at once froze a phone and
  // crashed its tab (2026-09-07). The page draws what it has been given
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
  // PAINT WHILE DRAGGING. The browser's own selection colour is hidden in
  // the text (index.css), so until the mouse was released nothing showed and
  // a reader could not see what they were selecting (2026-09-07). A
  // mouse drag is now tracked line by line and the page's band follows it;
  // on release the dragged span is what gets selected.
  const [drag, setDrag] = useState(null);   // { anchor, current } during a mouse drag
  const selLo = drag ? Math.min(drag.anchor, drag.current)
    : selection ? Math.min(selection.startIdx, selection.endIdx) : -1;
  const selHi = drag ? Math.max(drag.anchor, drag.current)
    : selection ? Math.max(selection.startIdx, selection.endIdx) : -1;
  const isSelected = useCallback((i) => (drag != null || selection != null) && i >= selLo && i <= selHi,
    [drag, selection, selLo, selHi]);
  const dragRef = useRef(null);
  dragRef.current = drag;
  // The sentence the mouse went down on, so a plain click (which leaves no
  // browser selection) can still select that sentence.
  const downRef = useRef(null);
  useEffect(() => {
    // Releasing outside the pane still ends the drag.
    const up = () => {
      const d = dragRef.current;
      if (!d) return;
      setDrag(null);
      const lo = Math.min(d.anchor, d.current);
      const hi = Math.max(d.anchor, d.current);
      const el = document.getElementById(`line-${cssRef(units[hi]?.ref)}`);
      const sel = window.getSelection();
      const native = sel ? String(sel).trim() : '';
      const top = el ? el.offsetTop + el.offsetHeight : 0;
      const parts = lo === hi ? partsOf(units[lo]?.text) : null;
      if (!parts) { emit(lo, hi, top, native); return; }
      // Inside one long unit: the sentences the click or the drag touched.
      const down = downRef.current && downRef.current.i === lo ? downRef.current.sent : null;
      const inUnit = (node) => lineIndexOf(node) === lo;
      const aS = sel && !sel.isCollapsed && inUnit(sel.anchorNode) ? sentenceIndexOf(sel.anchorNode) : null;
      const bS = sel && !sel.isCollapsed && inUnit(sel.focusNode) ? sentenceIndexOf(sel.focusNode) : null;
      const a = aS ?? down;
      const b = bS ?? a;
      if (a == null) {
        // Not on a sentence (the margin, or space between): the whole unit.
        emit(lo, hi, top, native, sentenceFields(units[lo].text, parts, 0, parts.length - 1));
        return;
      }
      const f = sentenceFields(units[lo].text, parts, Math.min(a, b), Math.max(a, b));
      // A double-clicked word stays the word (the toolbar searches for it); the
      // sentence is still recorded for the tabs.
      const word = native && !/\s/.test(native);
      emit(lo, hi, top, word ? native : (f.charStart == null ? native : f.text), f);
    };
    window.addEventListener('mouseup', up);
    return () => window.removeEventListener('mouseup', up);
  });

  // THE BROWSER'S SELECTION IS THE SELECTION.
  //
  // This used to track its own drag with mousedown and mouseenter while the
  // browser did its own selecting underneath, and the two disagreed: the page
  // showed twenty lines highlighted in blue while the panel said "1 line
  // selected". Reading the native selection instead means there is only one
  // answer to what is selected, and ordinary text selection works as it does
  // everywhere else, including keyboard and double-click.
  const emit = (a, b, anchorTop, text, extra) => {
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
      // Set inside a long prose unit: charStart/charEnd (null for the whole
      // unit), sentenceText, sentenceCount, sentenceTotal, startSentence.
      ...(extra || {}),
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
  // (2026-09-07); it is gone.
  const paneRef = useRef(null);

  return (
    <div
      ref={paneRef}
      className={`flex-1 ${phone ? 'px-2 py-4' : 'px-6 py-6'} overflow-y-auto reader-text`}
      onKeyUp={(e) => { if (e.shiftKey) readSelection(); }}
    >
      {/* Gentium Book carries Latin, polytonic Greek and Cyrillic, and
          nothing else here does: Georgia, the old fallback, has no polytonic
          Greek and no Hebrew, so Greek fell back character by character to
          whatever the reader's machine held and Hebrew borrowed a system face
          that sits smaller than Latin at the same size. Hebrew and Coptic
          follow Gentium in the stack because Gentium covers neither, and the
          browser drops through per character to the first family that has the
          glyph. `lang` is set so the browser picks the right glyph shapes and
          breaks lines by the right rules, which it cannot infer from the
          characters alone. */}
      <div
        className="max-w-3xl"
        style={{
          fontFamily: '"Gentium Book", "Noto Serif Hebrew", '
            + '"Noto Sans Coptic", Georgia, serif',
          fontSize: '1.06rem',
          lineHeight: 1.75,
        }}
        lang={language || undefined}
        dir={rtl ? 'rtl' : 'ltr'}
      >
        {units.map((u, i) => {
          const n = lineNumber(u.ref);
          const showNumber = n != null && n % 5 === 0;
          const selected = isSelected(i);
          // A long prose unit is drawn as its sentences, and the selected ones
          // are lit. When some but not all of a unit's sentences are selected,
          // the unit itself is NOT painted: with the whole chapter pink behind
          // them, the lit sentences could not be told from the rest, and the
          // owner read it as "I still can't select by sentence, just by large
          // chunk" (2026-10-12). The unit keeps its left bar either way.
          const parts = partsOf(u.text);
          const lit = parts && selected && selection && selection.charStart != null
            && selection.startIdx === i && selection.endIdx === i
            ? sentenceRangeOf(selection, parts) : null;
          const partial = !!(lit && (lit[0] > 0 || lit[1] < parts.length - 1));
          return (
            <div
              key={u.ref}
              id={`line-${cssRef(u.ref)}`}
              className={`grid ${phone ? 'gap-1' : 'gap-2'} cursor-text ${selected ? `${partial ? '' : 'bg-red-50 '}border-l-[3px] border-red-700 -ml-[3px] rounded-r` : ''}`}
              // The second column holds the "quoted in N works" mark. With the
              // documents trial on, a line can carry a second mark (the amber
              // inscriptions count) beside it, and 1.15rem fitted one mark only:
              // the second overlapped the line's text (seen on Aeneid 1.1,
              // 2026-10-09). Reserve room for two whenever the trial is on, so
              // every line's text stays on the same left edge.
              style={{ gridTemplateColumns: `${phone ? '1.6rem' : '2.6rem'} ${documentsTrial ? '2.5rem' : '1.15rem'} 1fr`, minHeight: '1.75rem' }}
              // A tap on a phone makes no text selection, so nothing used to
              // happen. A click or tap that leaves no selection selects the
              // line itself; a drag still selects the swept span.
              onMouseDown={(e) => {
                if (coarse || e.button !== 0) return;
                downRef.current = { i, sent: sentenceIndexOf(e.target) };
                setDrag({ anchor: i, current: i });
              }}
              onMouseEnter={() => {
                if (dragRef.current) setDrag((d) => (d && d.current !== i ? { ...d, current: i } : d));
              }}
              onClick={(e) => {
                const el = e.currentTarget;
                const bottom = el.offsetTop + el.offsetHeight;
                if (!coarse) return;   // the mouse path selects on mousedown/mouseup above
                // TOUCH SCREENS SELECT BY TAPPING. Native text selection is
                // off there (see index.css), so the phone's own Copy bar
                // never appears over the page (2026-09-07). A tap
                // selects a line; a tap on another line extends the span
                // to it; a tap inside the span narrows it to that line.
                //
                // INSIDE A LONG PROSE UNIT the tap selects a sentence. A tap
                // on another sentence of the same unit extends to it, a tap
                // on the selected sentence (or on the unit's reference
                // label) widens to the whole unit, and a tap on one sentence
                // of a multi-sentence selection narrows to it.
                if (selection && (i < selLo || i > selHi)) {
                  emit(Math.min(selLo, i), Math.max(selHi, i), bottom, '');
                  return;
                }
                const parts = partsOf(u.text);
                const k = sentenceIndexOf(e.target);
                const onLabel = !!(e.target.closest && e.target.closest('[data-label]'));
                const whole = () => emit(i, i, bottom, u.text,
                  parts ? sentenceFields(u.text, parts, 0, parts.length - 1) : undefined);
                if (!parts || onLabel || k == null) { whole(); return; }
                const here = selection && selection.startIdx === i && selection.endIdx === i;
                if (!here) {
                  const f = sentenceFields(u.text, parts, k, k);
                  emit(i, i, bottom, f.text, f);
                  return;
                }
                if (selection.charStart == null) {      // the whole unit: narrow to the tapped sentence
                  const f = sentenceFields(u.text, parts, k, k);
                  emit(i, i, bottom, f.text, f);
                  return;
                }
                const [lo, hi] = sentenceRangeOf(selection, parts);
                if (k >= lo && k <= hi) {
                  if (lo === hi) { whole(); return; }    // second tap on the one selected sentence
                  const f = sentenceFields(u.text, parts, k, k);
                  emit(i, i, bottom, f.text, f);
                  return;
                }
                const f = sentenceFields(u.text, parts, Math.min(lo, k), Math.max(hi, k));
                emit(i, i, bottom, f.text, f);
              }}
            >
              <span
                data-label="1"
                className={`${phone ? 'text-[10px]' : 'text-[0.72rem]'} text-gray-500 text-right pt-[0.35em] tabular-nums select-none`}
                style={{ fontFamily: 'inherit' }}
              >
                {showNumber ? n : ''}
              </span>
              {/* "Quoted in N works": a small mark for a line the corpus-wide
                  reuse table shows repeated verbatim (or near-verbatim) in
                  other works. Red-and-grey, matching the rest of the
                  Reader's palette; opens the Reuse tab on the line it marks.
                  onMouseDown stops here so the line's own drag-to-select
                  never starts under the mark: without it, pressing the mark
                  also began a one-line drag on the parent, and the mouseup
                  that ends it fired onSelect (panel -> Verbal Parallels)
                  moments before the click fired onReuseClick (panel ->
                  Reuse). The two usually raced to the right answer, but only
                  by luck of event order: a slow render between mouseup and
                  click let Verbal win, which could make a click appear to do
                  nothing.

                  TIERED (2026-09-19): reuseMarks[ref] is now
                  {n_works, n_possible_works} -- n_works counts only STRICT
                  pairs (kept by the original jaccard/containment rules);
                  n_possible_works counts only POSSIBLE pairs (kept by the
                  rare-single-ngram rule alone, shared==1 -- a corpus-rare
                  three-word match is real evidence, but weaker than the
                  two-or-more-shared-word matches the solid mark stands for,
                  and a 30-pair sample of that rule's yield was still mostly
                  coincidental, 2026-09-19). A line with any strict pair
                  gets the solid mark; a line with possible pairs gets the
                  lighter, dashed-outline mark, beside the solid one when
                  the line has both (2026-10-18; before that the solid mark
                  hid the dashed one). */}
              <span className="pt-[0.3em] flex items-center gap-0.5">
                {reuseMarks?.[u.ref] && (() => {
                  const strict = reuseMarks[u.ref].n_works || 0;
                  const possible = reuseMarks[u.ref].n_possible_works || 0;
                  /* BOTH MARKS (2026-10-18): a line quoted outright AND
                     echoed elsewhere shows both boxes, the solid one first.
                     Until tonight the solid mark hid the dashed one, so
                     Aen. 1.1 showed "2" while the Reuse tab listed seven
                     possible echoes, and the project lead asked why the
                     gutter gave no sign of them. */
                  const marks = [];
                  if (strict > 0) {
                    marks.push(
                      <button
                        key="strict"
                        type="button"
                        onMouseDown={(e) => e.stopPropagation()}
                        onClick={(e) => { e.stopPropagation(); onReuseClick?.(u); }}
                        title={`Quoted in ${strict} other work${strict === 1 ? '' : 's'}`}
                        aria-label={`quoted in ${strict} work${strict === 1 ? '' : 's'}`}
                        className="inline-flex items-center justify-center text-[9px] font-bold leading-none
                                   text-red-700 bg-gray-100 border border-gray-300 rounded px-1 py-[2px]
                                   hover:bg-red-50 hover:border-red-300"
                      >
                        {strict}
                      </button>
                    );
                  }
                  if (possible > 0) {
                    marks.push(
                      <button
                        key="possible"
                        type="button"
                        onMouseDown={(e) => e.stopPropagation()}
                        onClick={(e) => { e.stopPropagation(); onReuseClick?.(u); }}
                        title={`Possible echo in ${possible} other work${possible === 1 ? '' : 's'} (one rare shared phrase)`}
                        aria-label={`possible echo in ${possible} work${possible === 1 ? '' : 's'}`}
                        className="inline-flex items-center justify-center text-[9px] font-bold leading-none
                                   text-gray-500 bg-white border border-dashed border-gray-300 rounded px-1 py-[2px]
                                   hover:bg-gray-50 hover:border-gray-400"
                      >
                        {possible}
                      </button>
                    );
                  }
                  return marks.length ? marks : null;
                })()}
                {/* DOCUMENTARY REUSE (2026-10-08): a separate badge, not
                    merged into the strict/possible "quoted in N works"
                    count above -- a document (an inscription or papyrus)
                    is a different kind of witness from another literary
                    work, and folding its count into the same number would
                    silently change what an already-shipped number means.
                    Shown only behind the documents_trial flag (the
                    server sends n_documents/n_possible_documents whenever
                    TESSERAE_DOCUMENTS=1 server-side, regardless of this
                    flag -- see ReaderPage.jsx's reuseMarks fetch). Amber,
                    matching the documents collection's own highlight color
                    elsewhere in the Reader (LineSearch.jsx's matched-word
                    mark). */}
                {documentsTrial && reuseMarks?.[u.ref] && (() => {
                  const nDocs = reuseMarks[u.ref].n_documents || 0;
                  const nPossibleDocs = reuseMarks[u.ref].n_possible_documents || 0;
                  if (nDocs > 0) {
                    return (
                      <button
                        type="button"
                        onMouseDown={(e) => e.stopPropagation()}
                        onClick={(e) => { e.stopPropagation(); onReuseClick?.(u, 'documents'); }}
                        title={`Quoted in ${nDocs} inscription${nDocs === 1 ? '' : 's'} or papyr${nDocs === 1 ? 'us' : 'i'}`}
                        aria-label={`quoted in ${nDocs} document${nDocs === 1 ? '' : 's'}`}
                        className="inline-flex items-center justify-center text-[9px] font-bold leading-none
                                   text-amber-800 bg-amber-50 border border-amber-300 rounded px-1 py-[2px]
                                   hover:bg-amber-100"
                      >
                        {nDocs}
                      </button>
                    );
                  }
                  if (nPossibleDocs > 0) {
                    return (
                      <button
                        type="button"
                        onMouseDown={(e) => e.stopPropagation()}
                        onClick={(e) => { e.stopPropagation(); onReuseClick?.(u, 'documents'); }}
                        title={`Possible echo in ${nPossibleDocs} inscription${nPossibleDocs === 1 ? '' : 's'} or papyr${nPossibleDocs === 1 ? 'us' : 'i'} (one rare shared phrase)`}
                        aria-label={`possible echo in ${nPossibleDocs} document${nPossibleDocs === 1 ? '' : 's'}`}
                        className="inline-flex items-center justify-center text-[9px] font-bold leading-none
                                   text-amber-700 bg-white border border-dashed border-amber-300 rounded px-1 py-[2px]
                                   hover:bg-amber-50"
                      >
                        {nPossibleDocs}
                      </button>
                    );
                  }
                  return null;
                })()}
              </span>
              <p className="m-0"
                 style={phone ? { textIndent: '-1em', [rtl ? 'paddingRight' : 'paddingLeft']: '1em' } : undefined}>
                {(() => {
                  // A long prose unit is drawn as its sentences (the text is
                  // unchanged), so one can be clicked, and the selected one lit.
                  if (!parts) return u.text;
                  return parts.map((pt, k) => (
                    <span
                      key={pt.start}
                      data-sentence={k}
                      className={lit && k >= lit[0] && k <= lit[1] ? 'bg-red-100 rounded-sm' : undefined}
                    >
                      {u.text.slice(pt.start, pt.end)}
                    </span>
                  ));
                })()}
              </p>
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
