/**
 * What to do with the passage you just selected.
 *
 * A three-way scope toggle, one primary action, and the range selected. It
 * replaces a four-item list of links, which made the reader read four options
 * and choose, when the size of what they had selected already implied the
 * answer. Here the scope is a control they can correct in one click instead.
 *
 * WHY SCOPE AND ACTION ARE SEPARATE
 *
 * The scope says what the query is ABOUT -- a word, a line, a passage -- and
 * the button says what to do with it. Folding them together, as the old list
 * did, meant every combination needed its own row, and the rows that made no
 * sense still had to be listed. Three scopes and one button cover the same
 * ground in one line.
 *
 * The primary action follows the scope, because the useful question genuinely
 * differs: a word or a line is a question about wording, and a passage is a
 * question about content. Guessing right most of the time is worth more than
 * making the reader decide every time, and one click corrects it.
 */

import { useEffect, useRef, useState } from 'react';
import { RequestDialog } from '../common';
import { formatSelectionRange, useCorpusTextMap } from '../../utils/textNames';
import { fetchDefinition } from '../../utils/api';

const SCOPES = [
  { key: 'word', label: 'Word' },
  { key: 'line', label: 'Line' },
  { key: 'passage', label: 'Passage' },
];

// Inside one long prose unit (a chapter or section) the reader can pick a
// sentence, so the toggle offers Sentence and Section where verse has Line.
const PROSE_SCOPES = [
  { key: 'word', label: 'Word' },
  { key: 'sentence', label: 'Sentence' },
  { key: 'section', label: 'Section' },
  { key: 'passage', label: 'Passage' },
];

/** True when the selection lies inside one unit that has sentences. */
export function inProseUnit(selection) {
  return !!(selection && selection.sentenceTotal && (selection.lineCount || 1) === 1);
}

const ACTION = {
  word: { label: 'Find this word', tab: null },
  line: { label: 'Find shared wording', tab: 'verbal' },
  sentence: { label: 'Find shared wording', tab: 'verbal' },
  section: { label: 'Find shared wording', tab: 'verbal' },
  passage: { label: 'Find similar passages', tab: 'similar' },
};

/** The single word a selection amounts to, or null. A double-click on a word
 *  gives the browser selection exactly that word; a drag or a bare click does
 *  not. Trailing punctuation swept up with the word is not part of it. */
export function wordOf(selection) {
  const t = String(selection?.text || '').trim().replace(/^[^\p{L}]+|[^\p{L}]+$/gu, '');
  if (!t || /\s/.test(t) || !/\p{L}/u.test(t)) return null;
  return t;
}

/** The word the Word scope works on. TextPane records the whole word a click
 *  or a sweep landed in as clickedWord, and that is preferred: a drag over
 *  some of a word's letters swept "irumq" out of "virumque", and the toolbar
 *  searched and looked up the fragment (2026-11-08). The swept token itself
 *  serves when no clicked word is recorded, or when the two are different
 *  words (a sweep of several words with the pointer released on one). */
export function lookupWordOf(selection) {
  const token = wordOf(selection);
  const clicked = selection?.clickedWord || null;
  if (token && clicked && clicked.toLowerCase().includes(token.toLowerCase())) return clicked;
  return token || clicked;
}

/** A selection of three lines or more reads as a passage, one line as a line,
 *  a double-clicked single word as a word. */
export function scopeFor(selection) {
  if (!selection) return 'line';
  if (wordOf(selection)) return 'word';
  if (inProseUnit(selection)) return selection.charStart != null ? 'sentence' : 'section';
  return (selection.lineCount || 1) >= 3 ? 'passage' : 'line';
}

/** The small dictionary popover under the toolbar. It shows the lemma, the
 *  dictionary's name and the definition (or "No entry found" with the external
 *  link), and closes on Escape, on a click outside it and when the selection
 *  changes (the parent unmounts it then). */
function DefinitionPopover({ word, language, onClose }) {
  const [state, setState] = useState({ loading: true });
  const box = useRef(null);

  useEffect(() => {
    let live = true;
    fetchDefinition(word, language)
      .then((d) => { if (live) setState({ data: d }); })
      .catch(() => { if (live) setState({ failed: true }); });
    return () => { live = false; };
  }, [word, language]);

  useEffect(() => {
    const onKey = (e) => { if (e.key === 'Escape') onClose(); };
    // A press on the Look up button itself is the toggle's business, not a click outside.
    const onDown = (e) => {
      if (e.target.closest && e.target.closest('[data-lookup-toggle]')) return;
      if (box.current && !box.current.contains(e.target)) onClose();
    };
    document.addEventListener('keydown', onKey);
    document.addEventListener('mousedown', onDown);
    return () => {
      document.removeEventListener('keydown', onKey);
      document.removeEventListener('mousedown', onDown);
    };
  }, [onClose]);

  const d = state.data;
  return (
    <div ref={box} role="dialog" aria-label={`Dictionary entry for ${word}`}
         className="absolute left-0 top-full z-50 mt-1 w-80 max-w-[90vw] rounded-lg border border-gray-300
                    bg-white p-3 text-left shadow-xl">
      {state.loading && <p className="text-xs text-gray-500">Looking up {word}…</p>}
      {state.failed && <p className="text-xs text-gray-600">The dictionary could not be reached.</p>}
      {d && (
        <>
          <p className="text-sm font-semibold text-gray-900">{d.lemma || word}</p>
          {d.enclitic && (
            <p className="text-[11px] text-gray-500">{word} with -{d.enclitic} taken off</p>
          )}
          {d.dictionary && <p className="text-[11px] text-gray-500 mb-1">{d.dictionary}</p>}
          <p className="text-xs text-gray-800 whitespace-pre-line">
            {d.definition || 'No entry found'}
          </p>
          {d.url && (
            <a href={d.url} target="_blank" rel="noopener noreferrer"
               className="mt-2 inline-block text-xs text-red-700 hover:underline">
              Full entry
            </a>
          )}
        </>
      )}
    </div>
  );
}

export default function SelectionToolbar({
  selection, scope, onScope, work, language, onAct, onClose,
}) {
  const [reportOpen, setReportOpen] = useState(false);
  const [lookupOpen, setLookupOpen] = useState(false);
  const corpusMap = useCorpusTextMap(language);

  // In Word mode the entry for the word in hand is open: on entering the
  // mode, and on every click that lands on a word (each click is a new
  // selection object, so clicking the same word again after Escape reopens
  // it). Outside Word mode a new selection puts the popover away.
  useEffect(() => { setLookupOpen(scope === 'word' && !!lookupWordOf(selection)); }, [selection, scope]);

  if (!selection) return null;

  const refStart = selection.refStart;
  const refEnd = selection.refEnd || refStart;
  const range = formatSelectionRange(refStart, refEnd, corpusMap, work);
  const scopes = inProseUnit(selection) ? PROSE_SCOPES : SCOPES;
  let shown = range;
  if (selection.charStart != null && selection.sentenceTotal) {
    const first = (selection.startSentence || 0) + 1;
    const last = first + (selection.sentenceCount || 1) - 1;
    shown = `${range}, ${last > first ? `sentences ${first}\u2013${last}` : `sentence ${first}`}`;
  }
  const action = ACTION[scope] || ACTION.line;
  const word = lookupWordOf(selection);

  const go = () => {
    if (scope === 'word') {
      // The string-search page seeds its box from this key, not from the URL.
      if (!word) return;
      try { sessionStorage.setItem('tesserae_goto_query', word); } catch { /* fine */ }
      const p = new URLSearchParams({ language: language || 'la' });
      window.location.href = `/string-search?${p.toString()}`;
      return;
    }
    if (scope === 'sentence') {
      // The sentence's own words, run as a Line Search (the page runs a `q`
      // link on arrival).
      const q = String(selection.sentenceText || selection.text || '').trim();
      if (q) {
        const p = new URLSearchParams({
          work: String(work || '').replace(/\.tess$/, ''),
          language: language || 'la', q, type: 'lemma',
        });
        window.location.href = `/line-search?${p.toString()}`;
        return;
      }
    }
    if (scope === 'line' || scope === 'sentence' || scope === 'section') {
      const p = new URLSearchParams({
        work: String(work || '').replace(/\.tess$/, ''),
        language: language || 'la', ref: refStart || '',
      });
      window.location.href = `/line-search?${p.toString()}`;
      return;
    }
    onAct?.(action.tab);
  };

  return (
    <div className="relative inline-flex flex-wrap items-center gap-2 max-w-full rounded-lg border border-gray-300 bg-white
                    px-2 py-1.5 shadow-xl"
         role="toolbar"
         aria-label="What to do with the selected passage">
      <div className="flex shrink-0 rounded border border-gray-300 overflow-hidden">
        {scopes.map((s) => (
          <button
            key={s.key}
            onClick={() => onScope?.(s.key)}
            aria-pressed={scope === s.key}
            className={`px-2 py-1 text-xs font-medium whitespace-nowrap shrink-0 ${
              scope === s.key
                ? 'bg-gray-100 text-gray-900'
                : 'bg-white text-gray-500 hover:text-gray-800'}`}
          >
            {s.label}
          </button>
        ))}
      </div>

      {scope === 'word' && !word ? (
        // Word scope with no single word in hand: say what to do instead of
        // offering a search that has nothing to search for.
        <span className="text-[11px] text-gray-500 whitespace-nowrap px-1">
          click one word to search for it or look it up
        </span>
      ) : (
        <button
          onClick={go}
          className="rounded bg-red-700 px-3 py-1 text-xs font-medium text-white hover:bg-red-800
                     focus:outline-none focus:ring-2 focus:ring-red-400"
        >
          {scope === 'word' ? `Find “${word}” in the corpus` : action.label}
        </button>
      )}

      {/* ONE SWITCH FOR WORD LOOKUP. Word scope is the lookup mode: while it
          is on, every word clicked opens its dictionary entry. The switch
          shows the state (filled when on), because a plain "Look up" button
          that sat unlit while the mode was on read as "off" (the project
          lead, 2026-11-08). Pressing it when on returns the toolbar to Line. */}
      <button
        onClick={() => {
          if (scope === 'word') { onScope?.('line'); setLookupOpen(false); return; }
          onScope?.('word');
        }}
        aria-pressed={scope === 'word'}
        data-lookup-toggle=""
        title={scope === 'word'
          ? 'Word lookup is on: click any word for its dictionary entry. Press to turn it off.'
          : 'Turn on word lookup, then click any word for its dictionary entry.'}
        className={scope === 'word'
          ? `rounded bg-red-700 px-3 py-1 text-xs font-medium text-white hover:bg-red-800
             focus:outline-none focus:ring-2 focus:ring-red-400`
          : `rounded border border-gray-300 bg-white px-3 py-1 text-xs font-medium text-gray-600
             hover:bg-gray-50 hover:text-gray-800 focus:outline-none focus:ring-2 focus:ring-red-400`}
      >
        {scope === 'word' ? 'Looking up words' : 'Look up words'}
      </button>
      {lookupOpen && scope === 'word' && word && (
        <DefinitionPopover word={word} language={language || 'la'}
                           onClose={() => setLookupOpen(false)} />
      )}

      <span className="min-w-0 truncate text-[11px] text-gray-500 tabular-nums whitespace-nowrap"
            title={`${shown} selected`}>
        {shown} selected
      </span>

      {/* Requests workflow (2026-10-08): a transcription fix starts from
          exactly the passage already selected, so work/refs/text need no
          typing in by the reader. */}
      <button
        type="button"
        onClick={() => setReportOpen(true)}
        className="inline-flex items-center gap-1 text-[11px] text-red-700 hover:underline whitespace-nowrap"
      >
        <svg aria-hidden="true" viewBox="0 0 16 16" width="12" height="12" fill="none" className="shrink-0"><path d="M11 2.5l2.5 2.5L6 12.5H3.5V10L11 2.5z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" /></svg>
        Suggest a correction
      </button>

      <button onClick={onClose}
              aria-label="Dismiss"
              className="text-gray-500 hover:text-gray-700 text-base leading-none px-1">
        ×
      </button>

      <RequestDialog
        isOpen={reportOpen}
        onClose={() => setReportOpen(false)}
        type="text-correction"
        showCorrection
        context={{
          work: String(work || '').replace(/\.tess$/, ''),
          language,
          refs: range,
          selected_text: selection.text || '',
        }}
      />
    </div>
  );
}
