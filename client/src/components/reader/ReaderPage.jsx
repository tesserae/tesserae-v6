import { useState, useEffect, useCallback, useRef } from 'react';
import { cssRef } from './refId';
import ReaderHeader from './ReaderHeader';
import SelectionToolbar, { scopeFor } from './SelectionToolbar';
import { useCorpus } from '../../hooks';
import { LoadingSpinner } from '../common';
import TextPane from './TextPane';
import ConnectionGutter from './ConnectionGutter';
import ResultsPanel from './ResultsPanel';

// Book 1, not book 6: the Reader opens where a reader expects a poem to start,
// and "arma virumque cano" is the line most visitors will recognise.
const DEFAULT_WORK = 'vergil.aeneid.part.1.tess';
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
  const { hierarchy, loading: corpusLoading } = useCorpus(language);
  // Where a link asked us to land. Theme Search sends the reader here with a
  // specific passage in mind, and dropping them at line 1 of the work would
  // lose the thing they clicked.
  // CHOOSING A WORK. The Reader opened on Aeneid 6 and offered no way to read
  // anything else: a reader arriving at /read had to know to edit the URL. The
  // same selector the search page uses, so the two behave alike.
  // What the selection toolbar is scoped to. Seeded from the size of what was
  // selected and then the reader's to change.
  const [scope, setScope] = useState('line');
  // The popup that appears at a selection. Dismissed on a new selection or by
  // acting on it, so it never lingers over the text.
  const [popupOpen, setPopupOpen] = useState(false);
  const [panelTab, setPanelTab] = useState(null);

  // `ref` is what Theme Search sends; `at` is what this page writes back, so a
  // URL copied out of the address bar reselects its passage too. Reading only
  // `ref` meant the Reader wrote a position it could not itself read.
  const [wantedRef] = useState(() => paramOr('ref', '') || paramOr('at', ''));
  const [wantedRefEnd] = useState(() => paramOr('refEnd', ''));
  const [wantedTab] = useState(() => paramOr('tab', ''));
  const [cameFrom, setCameFrom] = useState(() => paramOr('q', ''));
  const [units, setUnits] = useState([]);
  const [metadata, setMetadata] = useState(null);
  const [selection, setSelection] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Load the work's text.
  useEffect(() => {
    // No work yet: the language just changed and the effect below is choosing
    // one. Fetching an empty id would 404 and paint an error over a page that
    // is simply mid-change.
    if (!work) return undefined;
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
  //
  // BACK USED TO LEAVE THE READER ENTIRELY. NC: "I did one reader search,
  // clicked the link on a related work that came up in the tab for verbal
  // parallels. When I clicked the back button from there, it didn't take me
  // back but to the main regular search page." This wrote every change with
  // replaceState, which overwrites the current history entry instead of adding
  // one, so moving from the Aeneid to Caesar left no trace and Back went to
  // whatever preceded the Reader. The comment above it claimed Back worked.
  //
  // So: opening a different text PUSHES an entry, and merely moving the
  // selection within a text REPLACES, because dragging across lines should not
  // fill the history with steps a reader then has to walk back through.
  const lastKeyRef = useRef(null);
  const fromPopRef = useRef(false);

  useEffect(() => {
    const p = new URLSearchParams(window.location.search);
    p.set('work', work);
    p.set('lang', language);
    if (selection?.refStart) p.set('at', selection.refStart); else p.delete('at');
    // ARRIVAL PARAMETERS ARE ONE-SHOT, and were being kept forever. `q` is what
    // draws the "Found by Theme Search" banner, so it survived changing work,
    // running a new search, and reloading -- the page kept claiming a passage
    // had been found by a search the reader had long since left. They are read
    // into state at mount, so dropping them from the URL here costs nothing and
    // `at` carries the position instead.
    ['ref', 'refEnd', 'tab', 'q'].forEach((k) => p.delete(k));
    const url = `${window.location.pathname}?${p}`;
    const key = `${work}|${language}`;
    const movedToAnotherText = lastKeyRef.current !== null && lastKeyRef.current !== key;
    if (movedToAnotherText && !fromPopRef.current) {
      window.history.pushState({}, '', url);
    } else {
      window.history.replaceState({}, '', url);
    }
    lastKeyRef.current = key;
    fromPopRef.current = false;
  }, [work, language, selection]);

  // Going Back inside the Reader has to put the Reader back, not just change
  // the address bar. Without this the pushed entries above would restore the
  // URL and leave the page showing the text the reader had navigated away from.
  useEffect(() => {
    const onPop = () => {
      const p = new URLSearchParams(window.location.search);
      const w = p.get('work');
      if (!w) return;            // left the Reader; App's own handler has it
      fromPopRef.current = true; // so the sync effect does not re-push this
      setLanguage(p.get('lang') || 'la');
      setWork(w);
      setSelection(null);
      setCameFrom('');
    };
    window.addEventListener('popstate', onPop);
    return () => window.removeEventListener('popstate', onPop);
  }, []);

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

  // A language with no work chosen opens that language's first text. Changing
  // language clears the work, because the old one is not in the new language;
  // without this the Reader would sit on an empty page waiting.
  useEffect(() => {
    // WAIT FOR THE NEW LANGUAGE'S LISTING. useCorpus refetches when the
    // language changes, and until it lands `hierarchy` still holds the OLD
    // language's texts -- picking from it would open a Latin work while the
    // Reader asked for it in Greek, and the fetch would fail on a page that was
    // only mid-change.
    if (work || corpusLoading || !hierarchy?.length) return;
    for (const a of hierarchy) {
      const file = ((a.works || [])[0]?.sections || [])[0]?.file;
      if (file) { setWork(file); return; }
    }
  }, [work, hierarchy, corpusLoading]);

  const openPassage = useCallback((result) => {
    if (!result?.work) return;
    setWork(result.work.endsWith('.tess') ? result.work : `${result.work}.tess`);
    setLanguage(result.language || 'la');
    window.scrollTo({ top: 0 });
  }, []);

  return (
    <div className="bg-white rounded-lg shadow overflow-hidden">
      <ReaderHeader
        language={language}
        onLanguage={(code) => {
          // A language of its own, so every corpus is reachable. Changing it
          // clears the work: the previous text is not in the new language, and
          // leaving it named left the header describing something not open.
          setLanguage(code);
          setWork('');
          setCameFrom('');
        }}
        hierarchy={hierarchy}
        work={work}
        onWork={(file) => {
          setWork(file);
          setSelection(null);
          // The banner describes a passage in the work being left.
          setCameFrom('');
        }}
        units={units}
        selection={selection}
      />

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
            {/* DISMISSIBLE, and it does not depend on the URL staying clean.
                Stripping the arrival parameters is right and is tested, but the
                banner outliving its arrival is the thing NC actually sees, and
                it should not take a correct URL to be rid of it. It goes on the
                first click of the ×, and the reader is never stuck with it. */}
            {cameFrom && (
              <p className="px-3 py-2 text-xs text-gray-700 border-b border-gray-200 bg-red-50 flex items-center gap-2">
                <span className="min-w-0">
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
                </span>
                <button
                  onClick={() => setCameFrom('')}
                  aria-label="Dismiss"
                  className="ml-auto shrink-0 text-gray-400 hover:text-gray-700 text-base leading-none px-1"
                >
                  ×
                </button>
              </p>
            )}
            {/* The key names the marks the same way the panel names its tabs.
                It used to read "W shared wording" and "C similar content" while
                the tabs beside it said "Verbal Parallels" and "Similar
                Passages", so the two halves of the same screen described the
                same two things in different words. */}
            <p className="px-3 py-1.5 text-[11px] text-gray-600 border-b border-gray-200 bg-gray-50 flex flex-wrap items-center gap-x-4 gap-y-1">
              <span className="flex items-center gap-1.5">
                <span className="inline-block w-[9px] h-[7px] rounded-sm bg-red-700" />
                verbal parallels
              </span>
              <span className="flex items-center gap-1.5">
                <span className="inline-block w-[9px] h-[7px] rounded-sm"
                      style={{ backgroundColor: '#7c6bb0' }} />
                similar passages
              </span>
              <span className="ml-auto text-gray-500">darker = more connections</span>
            </p>
          <div className="flex flex-1 min-w-0">
            <ConnectionGutter
              work={work.replace('.tess', '')}
              units={units}
              onSelectLine={(u) => {
                const i = units.findIndex((x) => x.ref === u.ref);
                const sel = { startIdx: i, endIdx: i, refStart: u.ref,
                              refEnd: u.ref, lineCount: 1 };
                setSelection(sel);
                setScope(scopeFor(sel));
                setPopupOpen(true);
              }}
            />
            <div className="relative flex-1 min-w-0">
              <TextPane
                units={units}
                language={language}
                selection={selection}
                onSelect={(sel) => {
                  setSelection(sel);
                  if (sel) setScope(scopeFor(sel));
                  setPopupOpen(!!sel);
                  // The reader has chosen their own passage, so the note about
                  // how they arrived at someone else's is spent.
                  if (sel) setCameFrom('');
                }}
              />
              {popupOpen && selection && (
                // Under the last selected line, not pinned to the corner. It
                // used to sit at the top of the pane whatever was selected, so
                // it covered the opening lines of the text.
                <div className="absolute left-10 z-20"
                     style={{ top: `${(selection?.anchorTop ?? 0) + 8}px` }}>
                  <SelectionToolbar
                    selection={selection}
                    scope={scope}
                    onScope={setScope}
                    work={work}
                    language={language}
                    onAct={(t) => { if (t) setPanelTab(t); setPopupOpen(false); }}
                    onClose={() => setPopupOpen(false)}
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

