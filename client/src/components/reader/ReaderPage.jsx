import { useState, useEffect, useCallback } from 'react';
import { cssRef } from './refId';
import SelectionPopup from './SelectionPopup';
import { TextSelector } from '../search';
import { useCorpus } from '../../hooks';
import { LoadingSpinner } from '../common';
import TextPane from './TextPane';
import ConnectionGutter from './ConnectionGutter';
import ResultsPanel from './ResultsPanel';

const DEFAULT_WORK = 'vergil.aeneid.part.6.tess';
const DEFAULT_LANGUAGE = 'la';

/**
 * The Reader: read a text, select a passage, see what the corpus connects to it.
 *
 * This inverts the site's usual stance. The search pages serve a scholar who
 * already has a hypothesis ("compare these two works"); the Reader serves one
 * who is reading and wants to know what a passage touches. Results open in the
 * Reader in turn, so the corpus can be followed by association.
 */
export default function ReaderPage() {
  const [work, setWork] = useState(() => paramOr('work', DEFAULT_WORK));
  const [language, setLanguage] = useState(() => paramOr('lang', DEFAULT_LANGUAGE));
  const { authors, hierarchy, getTextsForAuthor } = useCorpus(language);
  // Where a link asked us to land. Theme Search sends the reader here with a
  // specific passage in mind, and dropping them at line 1 of the work would
  // lose the thing they clicked.
  // CHOOSING A WORK. The Reader opened on Aeneid 6 and offered no way to read
  // anything else: a reader arriving at /read had to know to edit the URL. The
  // same selector the search page uses, so the two behave alike.
  const [pickAuthor, setPickAuthor] = useState('');
  const [pickText, setPickText] = useState('');
  // The popup that appears at a selection. Dismissed on a new selection or by
  // acting on it, so it never lingers over the text.
  const [popupOpen, setPopupOpen] = useState(false);
  const [panelTab, setPanelTab] = useState(null);

  const [wantedRef] = useState(() => paramOr('ref', ''));
  const [wantedRefEnd] = useState(() => paramOr('refEnd', ''));
  const [wantedTab] = useState(() => paramOr('tab', ''));
  const [cameFrom] = useState(() => paramOr('q', ''));
  const [units, setUnits] = useState([]);
  const [metadata, setMetadata] = useState(null);
  const [selection, setSelection] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Load the work's text.
  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    setSelection(null);
    fetch(`/api/text/${encodeURIComponent(work)}?language=${language}`)
      .then((r) => r.json())
      .then((d) => {
        if (cancelled) return;
        if (d.error) { setError(d.error); return; }
        setUnits(d.units || []);
        setMetadata(d.metadata || null);
      })
      .catch((e) => { if (!cancelled) setError(e.message); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [work, language]);

  // Keep the URL in step, so any passage is linkable and Back works.
  useEffect(() => {
    const p = new URLSearchParams(window.location.search);
    p.set('work', work);
    p.set('lang', language);
    if (selection?.refStart) p.set('at', selection.refStart); else p.delete('at');
    window.history.replaceState({}, '', `${window.location.pathname}?${p}`);
  }, [work, language, selection]);

  /** Open a result in the Reader, which is what makes the corpus browsable. */
  // Select the line the link named, once the text is in. Runs on units so it
  // fires after the fetch rather than racing it.
  useEffect(() => {
    if (!wantedRef || !units.length) return;
    const i = units.findIndex((u) => u.ref === wantedRef);
    if (i < 0) return;
    // Select the WHOLE found passage, not just its first line, so the
    // translation panel renders the English for the same span the reader was
    // shown a summary of.
    const j = wantedRefEnd ? units.findIndex((u) => u.ref === wantedRefEnd) : i;
    const end = j >= i ? j : i;
    setSelection({ startIdx: i, endIdx: end, refStart: units[i].ref,
                   refEnd: units[end].ref, lineCount: end - i + 1 });
    // Let the line render before scrolling to it.
    const id = window.setTimeout(() => {
      const el = document.getElementById(`line-${cssRef(units[i].ref)}`);
      if (el) el.scrollIntoView({ block: 'center', behavior: 'smooth' });
    }, 120);
    return () => window.clearTimeout(id);
  }, [wantedRef, wantedRefEnd, units]);

  // Load whatever the picker chooses.
  useEffect(() => {
    if (!pickText) return;
    setWork(pickText.endsWith('.tess') ? pickText : `${pickText}.tess`);
    setSelection(null);
    window.scrollTo({ top: 0 });
  }, [pickText]);

  const openPassage = useCallback((result) => {
    if (!result?.work) return;
    setWork(result.work.endsWith('.tess') ? result.work : `${result.work}.tess`);
    setLanguage(result.language || 'la');
    window.scrollTo({ top: 0 });
  }, []);

  const title = metadata
    ? `${metadata.author || ''} ${metadata.title || ''}`.trim()
    : prettyWork(work.replace('.tess', ''));

  return (
    <div className="bg-white rounded-lg shadow overflow-hidden">
      <div className="flex items-center gap-3 px-4 py-3 border-b border-gray-200 flex-wrap">
        <h2 className="font-semibold text-gray-900" style={{ fontFamily: '"Gentium Book Plus", Georgia, serif' }}>
          {title || 'Reader'}
        </h2>
        {/* Marked where it is used. The Reader, Theme Search and Tessa all
            shipped in the last few days and are all still changing. */}
        <span
          className="rounded border border-amber-200 bg-amber-50 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-amber-800"
          title="This feature is in development and still changing."
        >
          Beta
        </span>
        <div className="ml-auto flex items-end gap-2 min-w-0">
          <TextSelector
            label=""
            language={language}
            authors={authors}
            selectedAuthor={pickAuthor}
            setSelectedAuthor={setPickAuthor}
            selectedText={pickText}
            setSelectedText={setPickText}
            hierarchy={hierarchy}
            fetchTexts={getTextsForAuthor}
          />
        </div>

        {selection && (
          <span className="text-sm text-gray-500">
            {selection.lineCount} line{selection.lineCount === 1 ? '' : 's'} selected
          </span>
        )}
        <button
          onClick={() => setSelection(null)}
          className={`ml-auto text-sm text-gray-500 hover:text-gray-700 ${selection ? '' : 'invisible'}`}
        >
          Clear selection
        </button>
      </div>

      {loading && <div className="p-10"><LoadingSpinner /></div>}
      {error && <p className="p-6 text-red-700">{error}</p>}

      {!loading && !error && (
        <div className="flex flex-col lg:flex-row" style={{ minHeight: '32rem' }}>
          <div className="flex flex-col flex-1 min-w-0">
            {/* The key for the gutter marks. The gutter itself is nine pixels
                wide per column and can only carry a letter, and its tooltip does
                not exist on a phone, so the words go here where there is room.
                Without this a reader saw two columns of coloured squares beside
                the poem and had no way to find out what they were. */}
            {/* What the reader searched for, carried through the link. Landing
                deep inside a text with no memory of the question is
                disorienting, and the summary they clicked was an interpretation
                that they should be able to weigh against the passage. */}
            {cameFrom && (
              <p className="px-3 py-2 text-xs text-gray-700 border-b border-gray-200 bg-red-50">
                Found by Theme Search for{' '}
                <span className="font-medium">&ldquo;{cameFrom}&rdquo;</span>
                {selection?.lineCount > 1 && (
                  <span className="text-gray-500">
                    {' '}&middot; the matching passage is selected below
                  </span>
                )}
                <a href="/theme-search" className="ml-2 text-red-700 hover:underline">
                  back to results
                </a>
              </p>
            )}
            <p className="px-3 py-1.5 text-[11px] text-gray-600 border-b border-gray-200 bg-gray-50 flex flex-wrap gap-x-4 gap-y-1">
              <span className="flex items-center gap-1.5">
                <span className="inline-block w-[9px] h-[7px] rounded-sm bg-red-700" />
                <strong className="font-semibold text-gray-700">W</strong>
                shared wording
              </span>
              <span className="flex items-center gap-1.5">
                <span className="inline-block w-[9px] h-[7px] rounded-sm"
                      style={{ backgroundColor: '#7c6bb0' }} />
                <strong className="font-semibold text-gray-700">C</strong>
                similar content, wording need not match
              </span>
              <span className="text-gray-500">darker means more; select a line to see them</span>
            </p>
          <div className="flex flex-1 min-w-0">
            <ConnectionGutter
              work={work.replace('.tess', '')}
              units={units}
              onSelectLine={(u) => {
                const i = units.findIndex((x) => x.ref === u.ref);
                setSelection({ startIdx: i, endIdx: i, refStart: u.ref, refEnd: u.ref, lineCount: 1 });
                setPopupOpen(true);
              }}
            />
            <div className="relative flex-1 min-w-0">
              <TextPane
                units={units}
                language={language}
                selection={selection}
                onSelect={(sel) => { setSelection(sel); setPopupOpen(!!sel); }}
              />
              {popupOpen && (
                // Under the last selected line, not pinned to the corner. It
                // used to sit at the top of the pane whatever was selected, so
                // it covered the opening lines of the text.
                <div className="absolute left-10"
                     style={{ top: `${(selection?.anchorTop ?? 0) + 8}px` }}>
                  <SelectionPopup
                    selection={selection}
                    work={work}
                    language={language}
                    onClose={() => setPopupOpen(false)}
                    onTab={(t) => setPanelTab(t)}
                  />
                </div>
              )}
            </div>
            </div>
          </div>
          <ResultsPanel
            selection={selection}
            language={language}
            work={work.replace('.tess', '')}
            units={units}
            onOpenPassage={openPassage}
            initialTab={panelTab || wantedTab || undefined}
          />
        </div>
      )}
    </div>
  );
}

function paramOr(name, fallback) {
  const v = new URLSearchParams(window.location.search).get(name);
  return v || fallback;
}

/** "vergil.aeneid.part.6" -> "Vergil, Aeneid 6", good enough for a result label. */
function prettyWork(work) {
  if (!work) return '';
  const parts = String(work).replace(/\.tess$/, '').split('.');
  const author = cap(parts[0] || '');
  const title = cap(parts[1] || '');
  const partIdx = parts.indexOf('part');
  const book = partIdx > -1 ? ` ${parts[partIdx + 1]}` : '';
  return title ? `${author}, ${title}${book}` : author;
}

function cap(s) {
  return s.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}
