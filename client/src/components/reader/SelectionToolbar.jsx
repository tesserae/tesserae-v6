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

import { useState } from 'react';
import { RequestDialog } from '../common';
import { formatSelectionRange, useCorpusTextMap } from '../../utils/textNames';

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

/** A selection of three lines or more reads as a passage, one line as a line,
 *  a double-clicked single word as a word. */
export function scopeFor(selection) {
  if (!selection) return 'line';
  if (wordOf(selection)) return 'word';
  if (inProseUnit(selection)) return selection.charStart != null ? 'sentence' : 'section';
  return (selection.lineCount || 1) >= 3 ? 'passage' : 'line';
}

export default function SelectionToolbar({
  selection, scope, onScope, work, language, onAct, onClose,
}) {
  const [reportOpen, setReportOpen] = useState(false);
  const corpusMap = useCorpusTextMap(language);

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
  const word = wordOf(selection);

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
    <div className="inline-flex flex-wrap items-center gap-2 max-w-full rounded-lg border border-gray-300 bg-white
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
          double-click one word to search for it
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
