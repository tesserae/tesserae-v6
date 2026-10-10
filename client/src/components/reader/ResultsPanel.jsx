import { useState, useEffect, useRef } from 'react';
import useCollections from '../../hooks/useCollections';
import { READER_TABS } from '../../collections/collectionsConfig';
import useDocumentsTrial from '../../hooks/useDocumentsTrial';
import { useCorpusTextMap, citationFromCorpusMap } from '../../utils/textNames';
import { chronological, dateParts } from '../../utils/chronology';
import { LoadingSpinner } from '../common';
import { ResultsInsight } from '../assistant';
import { displayRef } from './refId';
import { LANGUAGE_NAMES as LANG_LABEL } from '../../utils/languageNames';
import { scholarshipLanguages } from '../../utils/scholarshipLanguages';
import ScholarshipTab from './ScholarshipTab';

/** Parse a response as JSON, failing with a message a reader can act on.
 *  While the server reloads, Apache answers API calls with an HTML error
 *  page, and r.json() on that used to put "Unexpected token '<', <!DOCTYPE
 *  ... is not valid JSON" on screen. */
async function asJson(r) {
  const ct = (r.headers && r.headers.get('content-type')) || '';
  if (r.ok === false || (ct && !ct.includes('json'))) {
    throw new Error('The server did not answer just now (it may have been '
      + 'restarting). Reselect the passage to try again.');
  }
  return r.json();
}

/**
 * The Reader's side panel: what the corpus has to say about the current selection.
 *
 * Three tabs, one per kind of connection:
 *   Similar Passages  content-level matches from the scene index (cross-language)
 *   Verbal Parallels  word-level matches from the lexical engines
 *   Translation       the aligned public-domain English, where one exists
 *
 * Every result is a button that opens that passage in the Reader, which is what
 * makes the corpus browsable by association rather than by search alone.
 */
export default function ResultsPanel({ selection, focus, language, work, units, onOpenPassage,
                                       initialTab, onClose, reuseFirst }) {
  // Arriving from Theme Search, the reader has just been shown an English
  // summary of a passage in a language they may not read. Opening on the
  // translation is the useful default there; everywhere else 'similar' is.
  const [tab, setTab] = useState(initialTab || 'similar');
  // Phone only: the sheet is a bare tab strip until a tab is tapped or a
  // line selected; on desktop the panel is always open.
  const [sheetOpen, setSheetOpen] = useState(false);

  // Follow a LATER request too. useState reads its argument once, so the popup
  // could ask for the translation and the panel would ignore it.
  useEffect(() => {
    if (initialTab) setTab(initialTab);
  }, [initialTab]);
  const [similar, setSimilar] = useState(null);
  const [translation, setTranslation] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  // Verbal keeps its own loading flag. A search of the whole corpus takes
  // around twelve seconds against the scene index's fraction of a second, and
  // sharing one flag means switching tabs mid-search leaves the other tab
  // spinning over results it already has.
  const [verbal, setVerbal] = useState(null);
  const [verbalLoading, setVerbalLoading] = useState(false);
  const [verbalError, setVerbalError] = useState(null);
  // Kept so the panel can hand the same query on to the full Line Search page.
  const [verbalQuery, setVerbalQuery] = useState('');
  // The whole work's translation, fetched on demand from the Translation
  // tab's no-selection state. null = not asked; 'loading'; or the payload.
  const [fullTranslation, setFullTranslation] = useState(null);
  useEffect(() => { setFullTranslation(null); }, [work]);

  // REUSE: other works whose lines verbatim-repeat the selection, from the
  // corpus-wide reuse table (backend/reuse_table.py). built per language --
  // a language with no table answers 404, which reads here as `available:
  // false` rather than an error, since "not built for this language" is a
  // normal state, not a failure.
  const [reuse, setReuse] = useState(null);
  const [reuseLoading, setReuseLoading] = useState(false);
  const [reuseError, setReuseError] = useState(null);
  // TIERED (2026-09-19): strict pairs (the original jaccard/containment
  // rules) list first with no heading, unchanged from before tiering;
  // possible pairs (the rare-single-ngram rule alone -- one rare shared
  // phrase, weaker evidence, see backend/reuse_table.py) sit behind a
  // collapsed section a reader opens on purpose. Collapsed again on a new
  // selection, so it never carries over from a line that had it open.
  const [possibleOpen, setPossibleOpen] = useState(false);
  useEffect(() => { setPossibleOpen(false); }, [selection]);

  // DOCUMENTARY REUSE (2026-10-08): inscriptions/papyri that quote or
  // near-quote the selection, from the cross-collection table
  // (backend/reuse_documents.py). A trial, same pattern as `documents_trial`
  // in client/src/components/search/LineSearch.jsx: ?documents=1 switches it
  // on and remembers that for the rest of the visit; the server already
  // gates the data behind TESSERAE_DOCUMENTS=1 (backend/blueprints/reuse.py),
  // so this flag only controls whether the Reader SHOWS what the server
  // already sent, not whether the server sends it.
  const documentsTrial = useDocumentsTrial();
  const [possibleDocumentsOpen, setPossibleDocumentsOpen] = useState(false);
  useEffect(() => { setPossibleDocumentsOpen(false); }, [selection]);

  // SCHOLARSHIP: a trial tab (commentators, articles and books on the
  // selection), not yet shown to every reader. ?scholarship=1 switches it on
  // and remembers that for the rest of the visit in sessionStorage, the same
  // way the names grouping was trialled behind ?names=1 first.
  const { anyOn } = useCollections();
  const scholarshipFlag = anyOn(['scholarship']);
  // Offer the tab only where the site holds scholarship for THIS language
  // (/api/scholarship/sources' own languages field, not a guess): Persian
  // and Urdu have none installed, so the trial switch alone must not show
  // a tab with nothing behind it.
  const [scholarshipLangs, setScholarshipLangs] = useState(null);
  useEffect(() => {
    if (!scholarshipFlag) return;
    let dead = false;
    scholarshipLanguages().then((langs) => { if (!dead) setScholarshipLangs(langs); });
    return () => { dead = true; };
  }, [scholarshipFlag]);
  const scholarshipAvailable = scholarshipFlag && !!scholarshipLangs?.has(language);
  useEffect(() => {
    if (!selection || tab !== 'reuse') return;
    const picked = (units || []).slice(selection.startIdx, selection.endIdx + 1);
    if (!picked.length) { setReuse({ available: true, quotations: [] }); return; }
    let cancelled = false;
    setReuseLoading(true);
    setReuseError(null);
    Promise.all(picked.map((u) => fetch(
      `/api/reuse/line?work=${encodeURIComponent(work)}`
      + `&ref=${encodeURIComponent(u.ref)}&language=${encodeURIComponent(language)}`,
    ).then((r) => (r.status === 404 ? { available: false } : asJson(r)))))
      .then((results) => {
        if (cancelled) return;
        const available = results.some((r) => r.available);
        const quotations = results.flatMap((r) => r.quotations || []);
        // `documents` is only present on a response when TESSERAE_DOCUMENTS=1
        // on the server AND a cross-collection table exists for this language
        // (backend/blueprints/reuse.py's _documents_for_line) -- a response
        // with no documents field at all flatMaps to nothing, same as one
        // with an empty list, so this needs no separate "is the trial even
        // live server-side" check.
        const documents = results.flatMap((r) => r.documents || []);
        setReuse({ available, quotations, documents, meta: results.find((r) => r.meta)?.meta });
      })
      .catch((e) => { if (!cancelled) setReuseError(e.message); })
      .finally(() => { if (!cancelled) setReuseLoading(false); });
    return () => { cancelled = true; };
  }, [selection, work, units, language, tab]);

  const loadFullTranslation = () => {
    setFullTranslation('loading');
    fetch(`/api/passages/translation-full?work=${encodeURIComponent(work)}`)
      .then(asJson)
      .then(setFullTranslation)
      .catch((e) => setFullTranslation({ available: false, reason: e.message }));
  };

  // How many similar passages to ask for. 15 is the first page; the
  // Show-more button raises it in steps, capped where relevance has long
  // since tailed off. Reset on every new selection.
  const [simLimit, setSimLimit] = useState(15);
  useEffect(() => { setSimLimit(15); }, [selection]);

  // "Same people and places" (research/specs/2026-10-07_names_panel_spec.md):
  // a second grouping, by shared rare proper names rather than content alone,
  // on by default since 2026-10-07 (trialled behind ?names=1 first); ?names=0
  // turns it off for comparison. Read once per page.
  const [namesFlag] = useState(
    () => new URLSearchParams(window.location.search).get('names') !== '0',
  );
  // Both groups default open; "Same people and places" starts collapsed
  // when the server flags it weak (a thin or single famous name gives a
  // crowded, low-value group). Reset for every new selection, then corrected
  // once the fetch itself reports weak -- see the effect below.
  const [namesOpen, setNamesOpen] = useState(true);
  const [sceneOpen, setSceneOpen] = useState(true);
  // Which "In other languages" section is open (one at a time, closed by default).
  const [langOpen, setLangOpen] = useState(null);
  const [commentaryOpen, setCommentaryOpen] = useState(false);
  const namesDefaultSet = useRef(false);
  useEffect(() => {
    setSceneOpen(true);
    setCommentaryOpen(false);
    setNamesOpen(true);
    namesDefaultSet.current = false;
  }, [selection]);
  useEffect(() => {
    if (similar?.same_names && !namesDefaultSet.current) {
      namesDefaultSet.current = true;
      setNamesOpen(!similar.same_names.weak);
    }
  }, [similar]);

  useEffect(() => {
    if (!selection || tab !== 'similar') return;
    let cancelled = false;
    if (simLimit === 15) setLoading(true);
    setError(null);
    const params = new URLSearchParams({
      work,
      ref_start: selection.refStart || '',
      ref_end: selection.refEnd || selection.refStart || '',
      limit: String(simLimit),
    });
    if (namesFlag) params.set('same_names', '1');
    // Per-language sections under the main list (2026-10-07).
    params.set('by_language', '1');
    fetch(`/api/passages/similar?${params}`)
      .then(asJson)
      .then((d) => {
        if (cancelled) return;
        if (d.error) setError(d.error);
        setSimilar(d);
      })
      .catch((e) => { if (!cancelled) setError(e.message); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [selection, work, tab, simLimit, namesFlag]);

  /* VERBAL PARALLELS: the selection's own wording, searched across the corpus.
   *
   * This tab said "Wiring in progress" for as long as the Reader has existed,
   * a state found by opening it. The red gutter beside the text was already
   * live, but that is a DENSITY measure -- how distinctive each line's
   * vocabulary is -- and it never had the parallels themselves behind it. The
   * marks pointed at something the panel could not show.
   *
   * /api/line-search is the engine the site's own Line Search runs on, so this
   * is the same result a reader would get by copying the line into the search
   * page, minus the copying. It matches on shared lemmata, which is why the
   * Caesar hit for Aeneid 6.1 comes back on classem/immisit rather than on any
   * shared surface form.
   */
  useEffect(() => {
    if (!selection || tab !== 'verbal') return;
    const picked = (units || []).slice(selection.startIdx, selection.endIdx + 1);
    const query = picked.map((u) => u.text).filter(Boolean).join(' ').trim();
    if (!query) { setVerbal({ results: [] }); setVerbalQuery(''); return; }
    setVerbalQuery(query);

    let cancelled = false;
    setVerbalLoading(true);
    setVerbalError(null);
    fetch('/api/line-search', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        query,
        language,
        search_type: 'lemma',
        max_results: 25,
        // The backend drops a hit only when text AND locus both match, so this
        // removes the source line itself without hiding the rest of the work:
        // a reader looking at Aeneid 6 should still be told when Aeneid 2 uses
        // the same words.
        // The whole-work name, since that is how the search index holds it.
        exclude_text_id: `${baseWork(work)}.tess`,
        exclude_locus: bareLocus(selection.refStart),
        // The selected lines by reference, so the server can take their
        // lemmas from the index instead of re-tagging the words.
        refs: picked.map((u) => u.ref),
        // Hide matches whose shared words are all commonplaces (quid + variis
        // matching quid + varii is Latin, not an echo). Reader-only: the Line
        // Search page keeps deliberate common-word queries intact.
        rare_focus: true,
      }),
    })
      .then(asJson)
      .then((d) => {
        if (cancelled) return;
        if (d.error) setVerbalError(d.error);
        // Belt and braces over the backend's single-locus exclusion: a
        // multi-line selection sends one locus but has several, and every one
        // of them would otherwise come back as a parallel to itself.
        const mine = new Set(picked.map((u) => bareLocus(u.ref)));
        setVerbal({
          ...d,
          results: (d.results || []).filter(
            (r) => !(sameWork(r.text_id, work) && mine.has(bareLocus(r.locus)))),
        });
      })
      .catch((e) => { if (!cancelled) setVerbalError(e.message); })
      .finally(() => { if (!cancelled) setVerbalLoading(false); });
    return () => { cancelled = true; };
  }, [selection, work, units, language, tab]);

  useEffect(() => {
    if (!selection || tab !== 'translation') return;
    let cancelled = false;
    setLoading(true);
    const refs = (units || [])
      .slice(selection.startIdx, selection.endIdx + 1)
      .map((u) => u.ref)
      .join('|');
    fetch(`/api/translation?work=${encodeURIComponent(work)}&refs=${encodeURIComponent(refs)}`)
      .then(asJson)
      .then((d) => { if (!cancelled) setTranslation(d); })
      .catch(() => { if (!cancelled) setTranslation(null); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [selection, work, units, tab]);

  const allTabs = [
    // Short labels so the four tabs fit one row without a scrollbar a
    // reader has no way to know is there (users who cannot see all of them
    // will not know they're there, 2026-09-19) -- matches
    // feat/scholarship-tab's wording. The full name is the title attribute.
    ['similar', 'Similar', 'Similar Passages'],
    ['verbal', 'Parallels', 'Verbal Parallels'],
    // In the English-focused reading view the middle column IS the
    // translation, so this tab holds the original instead.
    ['translation', focus === 'english' ? 'Original' : 'Translation',
     focus === 'english' ? 'The original text' : 'Translation'],
    ['reuse', 'Reuse', 'Reuse'],
    ['scholarship', 'Scholarship', 'Commentators, articles and books on the selection'],
  ];
  // Which tabs appear is decided by Collections (READER_TABS names the
  // collection each needs); the Scholarship tab also needs scholarship
  // installed for THIS language.
  const tabs = allTabs.filter(([id]) => {
    const spec = READER_TABS.find((t) => t.id === id);
    if (spec && !anyOn(spec.needs)) return false;
    return id !== 'scholarship' || scholarshipAvailable;
  });

  return (
    // Sticky on desktop: deep in Thebaid 12 the results used to be a full
    // page-scroll away, pinned to where the panel started. It now rides the
    // viewport and scrolls its own contents.
    // On a phone the panel used to be stacked UNDER the whole text, so its
    // tabs sat 798 lines down and the Reader looked as if it had no results
    // (2026-09-07). Below the lg breakpoint it is now a sheet fixed to
    // the bottom of the screen, shown once something is selected, with its
    // own close control; with nothing selected it stays out of the way.
    <aside className={`w-full lg:w-96 border-t lg:border-t-0 lg:border-l border-gray-200 bg-gray-50
                      flex flex-col fixed inset-x-0 bottom-0 z-40 shadow-2xl
                      lg:static lg:shadow-none lg:sticky lg:top-0 lg:self-start lg:h-screen lg:max-h-none
                      ${(selection || sheetOpen) ? 'max-h-[55vh]' : 'max-h-[2.75rem] overflow-hidden'}`}>
      {/* Room on the right for the Tessa button, which floats over the sheet
          on a phone. With five tabs (Scholarship added), WRAPPING put the
          fifth on a second line, where it no longer read as one of the tabs
          (2026-10-08). Tighter padding keeps every tab in one row at the
          panel's normal width; if a narrower width still will not fit them
          all, the strip scrolls horizontally rather than wrapping -- a
          scrollbar is at least visibly a strip that continues, where a
          dropped second line looked like a different, smaller tab bar. */}
      <div className="flex items-center flex-nowrap overflow-x-auto scrollbar-hide shrink-0 border-b border-gray-200 text-sm pr-20 lg:pr-0">
        {(selection || sheetOpen) && (
          <button
            onClick={() => { setSheetOpen(false); onClose?.(); }}
            className="lg:hidden px-3 py-2 text-gray-500 hover:text-gray-800"
            aria-label="Close results"
            title="Close"
          >
            ✕
          </button>
        )}
        {tabs.map(([id, label, full]) => (
          <button
            key={id}
            title={full || label}
            onClick={() => { setTab(id); setSheetOpen(true); }}
            className={`px-2 py-2 font-semibold border-b-2 transition-colors whitespace-nowrap ${
              tab === id
                ? 'text-red-700 border-red-700'
                : 'text-gray-500 border-transparent hover:text-gray-700'
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {/* THE TABS STAY WHATEVER IS SELECTED.
          With nothing selected this returned a bare paragraph and no tab bar at
          all, so the panel looked like a different component depending on
          whether a line was highlighted, and a reader who had just changed
          works saw the three things the Reader can tell them simply vanish. The
          tabs are what the panel IS; the body is what it currently knows. */}
      <div className="flex-1 overflow-y-auto p-3 space-y-2">
        {!selection && tab === 'translation' && (
          <>
            {fullTranslation === null && (
              <div className="space-y-2">
                <p className="text-sm text-gray-600">
                  Select a passage to see its translation beside the text, or read
                  the work&rsquo;s full translation here.
                </p>
                <button
                  onClick={loadFullTranslation}
                  className="w-full text-center text-xs font-medium text-red-700 border
                             border-gray-200 rounded py-1.5 hover:bg-red-50"
                >
                  Show full translation
                </button>
              </div>
            )}
            {fullTranslation === 'loading' && <LoadingSpinner />}
            {fullTranslation && fullTranslation !== 'loading' && fullTranslation.available === false && (
              <p className="text-sm text-gray-500">{fullTranslation.reason}</p>
            )}
            {fullTranslation && fullTranslation !== 'loading' && fullTranslation.available && (
              <div className="space-y-3">
                <p className="text-[11px] text-gray-500 leading-snug">
                  {fullTranslation.attribution}. Blocks follow the source text&rsquo;s
                  order; alignment is {fullTranslation.alignment_confidence || 'approximate'}.
                </p>
                {fullTranslation.blocks.map((b) => (
                  <div key={b.ref_start} className="bg-white border border-gray-200 rounded p-2">
                    <p className="text-[10px] text-gray-500 mb-1">{b.ref_start}
                      {b.ref_end !== b.ref_start ? ` – ${b.ref_end}` : ''}</p>
                    <p className="text-sm text-gray-800 leading-relaxed">{b.text}</p>
                  </div>
                ))}
              </div>
            )}
          </>
        )}
        {!selection && tab !== 'translation' && (
          <p className="text-sm text-gray-500 leading-relaxed p-3">
            Select a passage in the text to see what the corpus connects to it.
            Drag across several lines for content matches, or click a single line
            for word matches.
          </p>
        )}
        {selection && tab === 'similar' && (
          <>
            {loading && <LoadingSpinner />}
            {error && <p className="text-sm text-red-700">{error}</p>}
            {!loading && similar?.results?.length === 0
              && !(namesFlag && (similar?.same_names?.results?.length > 0
                                 || similar?.same_names?.commentaries?.length > 0)) && (
              <p className="text-sm text-gray-500">
                No passage in the corpus resembles this selection closely.
              </p>
            )}
            {/* "Same people and places" (research/specs/2026-10-07_names_panel_spec.md):
                a second grouping by shared rare proper names, behind ?names=1.
                Ranked by the server's own score (content similarity plus a
                shared-name-rarity bonus), so this list is NOT re-sorted
                chronologically the way the content-only group below is --
                the ranking itself is what the group is for. */}
            {!loading && namesFlag && similar?.same_names && (
              <div className="mb-3">
                <button
                  onClick={() => setNamesOpen((o) => !o)}
                  className="w-full flex items-center justify-between text-xs font-semibold
                             text-gray-700 border border-gray-200 rounded-lg px-2.5 py-1.5
                             hover:bg-gray-100"
                  aria-expanded={namesOpen}
                >
                  <span>Same people and places &middot; {similar.same_names.results.length}</span>
                  <span aria-hidden="true">{namesOpen ? '−' : '+'}</span>
                </button>
                {similar.same_names.weak && (
                  <p className="text-[11px] text-gray-500 mt-1 leading-snug">
                    Few distinctive names in this passage
                  </p>
                )}
                {namesOpen && (
                  <div className="mt-2 space-y-2">
                    {similar.same_names.results.length === 0 && (
                      <p className="text-sm text-gray-500">
                        No other work shares a distinctive name with this passage.
                      </p>
                    )}
                    {similar.same_names.results.map((r) => (
                      <SimilarResultCard key={r.id} r={r} onOpenPassage={onOpenPassage} />
                    ))}
                    {similar.same_names.commentaries.length > 0 && (
                      <div>
                        <button
                          onClick={() => setCommentaryOpen((o) => !o)}
                          className="w-full flex items-center justify-between text-[11px]
                                     text-gray-500 border border-gray-100 rounded px-2 py-1
                                     hover:bg-gray-50"
                          aria-expanded={commentaryOpen}
                        >
                          <span>Commentaries: {commentarySummary(similar.same_names.commentaries)}</span>
                          <span aria-hidden="true">{commentaryOpen ? '−' : '+'}</span>
                        </button>
                        {commentaryOpen && (
                          <div className="mt-2 space-y-2">
                            {similar.same_names.commentaries.map((r) => (
                              <SimilarResultCard key={r.id} r={r} onOpenPassage={onOpenPassage} />
                            ))}
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}
            {!loading && namesFlag && similar?.same_names && (
              <button
                onClick={() => setSceneOpen((o) => !o)}
                className="w-full flex items-center justify-between text-xs font-semibold
                           text-gray-700 border border-gray-200 rounded-lg px-2.5 py-1.5
                           hover:bg-gray-100 mb-2"
                aria-expanded={sceneOpen}
              >
                <span>Same kind of scene &middot; {similar.results?.length ?? 0}</span>
                <span aria-hidden="true">{sceneOpen ? '−' : '+'}</span>
              </button>
            )}
            {/* OLDEST FIRST, like Theme Search. These results cross centuries
                and the order they are read in is itself information: the
                Aeneid, then Ovid reworking it, then Silius after him. Ranking
                by score put Statius (96 CE) above Ovid (17 CE) and told the
                reader nothing about the line of descent. */}
            {!loading && (!namesFlag || !similar?.same_names || sceneOpen)
              && chronological(similar?.results)?.map((r) => (
                <SimilarResultCard key={r.id} r={r} onOpenPassage={onOpenPassage} />
            ))}
            {!loading && similar?.results?.length >= simLimit && simLimit < 60
              && (!namesFlag || !similar?.same_names || sceneOpen) && (
              /* More exist below the cut: the index ranks every window, and 15
                 is only the first page. Capped at 60, where content similarity
                 has tailed into noise. */
              <button
                onClick={() => setSimLimit((l) => Math.min(l + 15, 60))}
                className="w-full text-center text-xs font-medium text-red-700 border
                           border-gray-200 rounded py-1.5 hover:bg-red-50"
              >
                Show more matches
              </button>
            )}
            {!loading && similar?.by_language && Object.keys(similar.by_language).length > 0
              && (!namesFlag || !similar?.same_names || sceneOpen) && (
              /* IN OTHER LANGUAGES (2026-10-07). The main list ranks every
                 language together, so the largest corpora fill it: an Urdu
                 passage got 28 Persian matches and 2 Urdu ones. Each language
                 with few results above gets a button here, ordered by its best
                 match, opening that language's five best. The same for every
                 language, so Latin shows its Greek and English this way. */
              <div className="pt-1">
                <p className="text-[11px] font-semibold text-gray-600 mb-1">In other languages</p>
                <div className="flex flex-wrap gap-1 mb-1">
                  {Object.entries(similar.by_language)
                    .sort((a, b) => (b[1][0]?.score || 0) - (a[1][0]?.score || 0))
                    .map(([lang, rows]) => (
                      <button key={lang} onClick={() => setLangOpen((o) => (o === lang ? null : lang))}
                              aria-expanded={langOpen === lang}
                              className={`text-[11px] px-2 py-0.5 rounded border ${langOpen === lang
                                ? 'bg-red-700 text-white border-red-700'
                                : 'bg-white text-gray-700 border-gray-300 hover:bg-gray-100'}`}>
                        {LANG_LABEL[lang] || lang} &middot; {rows.length}
                      </button>
                    ))}
                </div>
                {langOpen && (similar.by_language[langOpen] || []).map((r) => (
                  <SimilarResultCard key={r.id} r={r} onOpenPassage={onOpenPassage} />
                ))}
              </div>
            )}
            <p className="text-[11px] text-gray-500 pt-1 leading-snug">
              These passages match in content, not wording, so a match in another language
              usually shares no words with the selection. Summaries are machine-written.
            </p>
            {!loading && similar?.results?.length > 0 && (
              <ResultsInsight
                results={similar.results.map((r) => ({
                  // The scene index reports one passage per hit, so present the
                  // selection as the source side and the match as the target.
                  source: { ref: selection.refStart, text: '' },
                  target: { ref: `${r.work} ${r.ref_start}`, text: r.gist || '' },
                  channels: ['context'],
                  themes: r.themes || [],
                }))}
                source={work}
                target="the corpus"
                className="mt-2"
              />
            )}
          </>
        )}

        {selection && tab === 'verbal' && (
          <>
            {verbalLoading && (
              <>
                <LoadingSpinner />
                {/* Said out loud because this one is slow. The scene index
                    answers in a fraction of a second and this takes about
                    twelve, so silence for twelve seconds reads as a hang. */}
                <p className="text-xs text-gray-500 text-center">
                  Searching the corpus for these words...
                </p>
              </>
            )}
            {verbalError && <p className="text-sm text-red-700">{verbalError}</p>}
            {!verbalLoading && verbal?.rare_focus?.hidden > 0 && (
              <p className="text-xs text-gray-500">
                {verbal.rare_focus.hidden} match{verbal.rare_focus.hidden === 1 ? '' : 'es'} sharing
                only common words ({verbal.rare_focus.common_lemmas.join(', ')}) not shown.
                The full Line Search page shows everything.
              </p>
            )}
            {!verbalLoading && verbal?.query_reduced && (
              /* A passage-sized selection is searched on its rarest words, and
                 the reader is told which, so the results are never mistaken
                 for a search of the whole wording. */
              <p className="text-xs text-gray-500">
                Passage-sized selection: matched on its most distinctive words
                ({verbal.query_reduced.to_lemmas.join(', ')}).
              </p>
            )}
            {!verbalLoading && verbal?.results?.length === 0 && (
              <p className="text-sm text-gray-500">
                No other passage in the corpus shares this selection&rsquo;s distinctive
                wording. Common words are set aside before searching, so a line built
                mostly from them often has nothing to report.
              </p>
            )}
            {!verbalLoading && chronological(verbal?.results)?.map((r, i) => (
              <button
                key={`${r.text_id}-${r.locus}-${i}`}
                onClick={() => onOpenPassage?.({ work: r.text_id, language })}
                className="group w-full text-left bg-white border border-gray-200 rounded-lg p-3
                           hover:border-red-400 hover:bg-red-50/40 transition-colors
                           focus:outline-none focus:ring-2 focus:ring-red-400"
              >
                <div className="flex items-baseline gap-2 flex-wrap">
                  <span className="font-bold text-sm text-red-800 group-hover:underline">
                    {r.author}{r.work ? `, ${r.work}` : ''}
                  </span>
                  <span className="text-xs text-gray-500">{r.locus}</span>
                  {dateParts(r) && (
                    <span className="text-[11px] text-gray-500 tabular-nums whitespace-nowrap">
                      {dateParts(r).date}
                    </span>
                  )}
                </div>
                {/* THE MATCHED WORDS ARE THE POINT. This is a lemma search, so
                    the shared words are usually in different forms in the two
                    passages (classique/classem, immittit/immisit) and a reader
                    scanning the quoted line will not always spot them. */}
                {!!(r.matched_words || []).length && (
                  <div className="flex gap-1 flex-wrap mt-1.5">
                    {r.matched_words.map((w) => (
                      <span key={w}
                            className="text-[11px] font-semibold bg-red-100 text-red-800 rounded px-1">
                        {w}
                      </span>
                    ))}
                  </div>
                )}
                {/* NO "Open in Reader" line here: the link under each verbal
                    parallel result saying 'view in reader' was redundant,
                    since clicking the work name does the same thing. The title
                    carries the link colour and underlines on hover, which is
                    the affordance; a second one under every card was clutter in
                    a list where the passage text is the thing to read. */}
                {r.text && (
                  <p className="text-xs text-gray-700 mt-1.5 leading-snug">
                    <Marked text={clip(r.text, r.matched_words)}
                            words={r.matched_words} latin={language === 'la'} />
                  </p>
                )}
              </button>
            ))}
            {!verbalLoading && verbal?.results?.length > 0 && (
              <>
                {/* THE WAY OUT TO THE REAL TOOLS. The panel runs one line
                    against the corpus and shows 25; Line Search runs the same
                    query with the filters, the timeline, era and author facets,
                    and CSV export. This hands the query over rather than making
                    the reader retype it. */}
                <a
                  href={`/?tab=line&lang=${encodeURIComponent(language)}`
                        + `&q=${encodeURIComponent(verbalQuery)}&type=lemma`}
                  className="block w-full text-center text-xs font-semibold text-red-700
                             border border-red-200 bg-red-50 rounded-lg py-2
                             hover:bg-red-100 hover:border-red-300"
                >
                  See the full result list in Line Search &rarr;
                </a>
                <p className="text-[11px] text-gray-500 pt-1 leading-snug">
                  Matches share dictionary forms, not necessarily spellings. Oldest first.
                  {verbal.capped && ' The corpus holds more than are shown here.'}
                </p>
              </>
            )}
          </>
        )}

        {selection && tab === 'translation' && focus === 'english' && (
          <div className="space-y-1">
            <p className="text-[11px] text-gray-500 mb-2">
              The original text of the selected block.
            </p>
            {(units || []).slice(selection.startIdx, selection.endIdx + 1).map((u) => (
              <p key={u.ref} className="text-sm text-gray-900 leading-relaxed">
                <span className="text-[10px] text-gray-500 mr-2">{displayRef(u.ref)}</span>
                {u.text}
              </p>
            ))}
          </div>
        )}
        {selection && tab === 'translation' && focus !== 'english' && (
          <>
            {loading && <LoadingSpinner />}
            {!loading && translation?.available === false
              && (translation.external_links || []).length === 0 && (
              <p className="text-sm text-gray-500">
                {['fa', 'ur', 'ar'].includes(language)
                  ? `No English translation is aligned to any ${{ fa: 'Persian', ur: 'Urdu', ar: 'Arabic' }[language]} work yet. Aligned open translations (public-domain and non-commercial-licensed) currently cover over half of the Greek corpus and nearly half of the Latin.`
                  : `${translation.reason} Aligned open translations (public-domain and non-commercial-licensed) currently cover over half of the Greek corpus and nearly half of the Latin.`}
              </p>
            )}
            {!loading && translation?.available && (
              <div className="bg-white border border-gray-200 rounded-lg p-3">
                {/* A block-only warning goes ABOVE the text. Below it, a reader who
                    has already taken the English for a rendering of their lines
                    will never see it. */}
                {translation.block_only && (
                  <p className="text-[11px] text-amber-800 bg-amber-50 border border-amber-200 rounded px-2 py-1.5 mb-2 leading-snug">
                    {translation.note}
                  </p>
                )}
                <p className="text-sm text-gray-800 whitespace-pre-line leading-relaxed">
                  {translation.text}
                </p>
                {translation.note && !translation.block_only && (
                  <p className="text-[11px] text-amber-700 mt-2 leading-snug">{translation.note}</p>
                )}
                <p className="text-[11px] text-gray-500 mt-2 leading-snug">
                  {translation.translator}
                  {translation.year ? `, ${translation.year}` : ''}
                  {translation.attribution ? ` \u00b7 ${translation.attribution}` : ''}
                </p>
              </div>
            )}
            {/* External links stand in where the translator's own licence does
                not let Tesserae copy the English (e.g. Frances W. Pritchett's
                Ghalib commentary): below the text when there is one, or on
                their own when there is none. */}
            {!loading && (translation?.external_links || []).length > 0 && (
              <div className={translation.available
                ? 'mt-2 space-y-1'
                : 'bg-white border border-gray-200 rounded-lg p-3 space-y-1'}>
                {translation.external_links.map((link) => (
                  <p key={link.url} className="text-[11px] text-gray-600 leading-snug">
                    <a href={link.url} target="_blank" rel="noopener noreferrer"
                       className="text-red-700 underline">
                      {link.translator || 'The translator'}&rsquo;s translation and
                      commentary for this verse
                    </a>
                    {link.site_title ? `, in ${link.site_title}` : ''}
                  </p>
                ))}
              </div>
            )}
          </>
        )}

        {selection && tab === 'reuse' && (
          <>
            <p className="text-[11px] text-gray-500 leading-snug">
              Lines sharing enough word-triples with this line to count as a quotation
              or near-quotation, computed once over the corpus.
            </p>
            {reuseLoading && <LoadingSpinner />}
            {reuseError && <p className="text-sm text-red-700">{reuseError}</p>}
            {!reuseLoading && !reuseError && reuse?.available === false && (
              <p className="text-sm text-gray-500">
                No reuse table has been built for {LANG_LABEL[language] || language} yet.
              </p>
            )}
            {!reuseLoading && !reuseError && reuse?.available && reuse.quotations.length === 0 && (
              <p className="text-sm text-gray-500">
                No other work in the corpus repeats this line closely enough to count.
              </p>
            )}
            {/* The amber box in the text (quoted in inscriptions or papyri)
                opens this tab with the documents first (2026-10-10: the lead
                clicked that box and saw the literary quotations first). The
                red box, and the tab opened any other way, keep the literary
                groups first. */}
            {(() => {
              const literaryGroups = (
                <>
            {!reuseLoading && reuse?.available && reuse.quotations.length > 0 && (() => {
              // TIERED: strict first with no heading (the original
              // behavior); possible pairs -- one rare shared phrase, kept
              // only by the rare-single-ngram rule -- behind a collapsed
              // section, since a 30-pair sample of that rule's yield was
              // still mostly coincidental (2026-09-19).
              const strict = reuse.quotations.filter((q) => q.tier !== 'possible');
              const possible = reuse.quotations.filter((q) => q.tier === 'possible');
              return (
                <div className={reuseFirst === 'documents' && reuse.documents?.length > 0
                                  ? 'mt-4 pt-3 border-t border-gray-200' : ''}>
                  {reuseFirst === 'documents' && reuse.documents?.length > 0 && (
                    <h3 className="text-xs font-bold uppercase tracking-wide text-gray-500 mb-2">
                      In other works
                    </h3>
                  )}
                  {strict.length > 0 && (
                    <ReuseGroups quotations={strict} onOpenPassage={onOpenPassage} />
                  )}
                  {possible.length > 0 && (
                    <div className={strict.length > 0 ? 'mt-3' : ''}>
                      <button
                        onClick={() => setPossibleOpen((o) => !o)}
                        className="w-full flex items-center justify-between text-xs font-semibold
                                   text-gray-600 border border-gray-200 rounded-lg px-2.5 py-1.5
                                   hover:bg-gray-100"
                        aria-expanded={possibleOpen}
                      >
                        <span>Possible echoes (one rare shared phrase) &middot; {possible.length}</span>
                        <span aria-hidden="true">{possibleOpen ? '−' : '+'}</span>
                      </button>
                      {possibleOpen && (
                        <div className="mt-2">
                          <ReuseGroups quotations={possible} onOpenPassage={onOpenPassage} />
                        </div>
                      )}
                    </div>
                  )}
                </div>
              );
            })()}
                </>
              );
              const documentGroups = (
                <>
            {/* DOCUMENTARY REUSE: inscriptions and papyri quoting or
                near-quoting the selection, after the literary groups --
                a separate group, not merged into them, since a document hit
                carries edition/date/place fields a literary quotation does
                not and reads oddly interleaved with "work, year". Only
                rendered behind the documents_trial flag (?documents=1,
                same session flag LineSearch.jsx's documents collection
                uses) even though the server may have sent the data
                regardless -- see the documentsTrial state above. */}
            {documentsTrial && !reuseLoading && reuse?.documents?.length > 0 && (() => {
              const strictDocs = reuse.documents.filter((d) => d.tier !== 'possible');
              const possibleDocs = reuse.documents.filter((d) => d.tier === 'possible');
              return (
                <div className={(reuse.quotations?.length > 0 && reuseFirst !== 'documents') ? 'mt-4 pt-3 border-t border-gray-200' : ''}>
                  <h3 className="text-xs font-bold uppercase tracking-wide text-gray-500 mb-2">
                    In inscriptions and papyri
                  </h3>
                  {strictDocs.length > 0 && (
                    <DocumentReuseGroups documents={strictDocs} language={language} />
                  )}
                  {possibleDocs.length > 0 && (
                    <div className={strictDocs.length > 0 ? 'mt-3' : ''}>
                      <button
                        onClick={() => setPossibleDocumentsOpen((o) => !o)}
                        className="w-full flex items-center justify-between text-xs font-semibold
                                   text-gray-600 border border-gray-200 rounded-lg px-2.5 py-1.5
                                   hover:bg-gray-100"
                        aria-expanded={possibleDocumentsOpen}
                      >
                        <span>Possible echoes (one rare shared phrase) &middot; {possibleDocs.length}</span>
                        <span aria-hidden="true">{possibleDocumentsOpen ? '−' : '+'}</span>
                      </button>
                      {possibleDocumentsOpen && (
                        <div className="mt-2">
                          <DocumentReuseGroups documents={possibleDocs} language={language} />
                        </div>
                      )}
                    </div>
                  )}
                </div>
              );
            })()}
                </>
              );
              return reuseFirst === 'documents'
                ? <>{documentGroups}{literaryGroups}</>
                : <>{literaryGroups}{documentGroups}</>;
            })()}
          </>
        )}

        {scholarshipAvailable && selection && tab === 'scholarship' && (
          <ScholarshipTab work={work} language={language} selection={selection} units={units} />
        )}
        {scholarshipAvailable && !selection && tab === 'scholarship' && (
          <p className="text-sm text-gray-500">Select a line or a span to see the scholarship on it.</p>
        )}
      </div>
    </aside>
  );
}

/** One Similar Passages result card: content tab and, behind ?names=1, both
 *  the "same people and places" and "same kind of scene" groups. A card
 *  carrying `shared_names` (only the names group's cards do) gets the extra
 *  line naming what it shares with the selection; everywhere else that field
 *  is simply absent, so this is the same card the flag-off Reader has
 *  always shown. */
function SimilarResultCard({ r, onOpenPassage }) {
  return (
    <button
      onClick={() => onOpenPassage?.(r)}
      className="group w-full text-left bg-white border border-gray-200 rounded-lg p-3
                 hover:border-red-400 hover:bg-red-50/40 transition-colors
                 focus:outline-none focus:ring-2 focus:ring-red-400"
    >
      <div className="flex items-baseline gap-2 flex-wrap">
        <span className="text-[10px] font-bold uppercase tracking-wide bg-gray-100 text-gray-600 rounded px-1">
          {LANG_LABEL[r.language] || r.language}
        </span>
        {/* The title carries the link colour and underlines on hover,
            because nothing else said these cards open anything. A
            hover border on a div is not an affordance.

            Real name, not the file slug: the scene index sends
            author/title/display_name from get_text_metadata, the
            same source Browse Corpus and Theme Search use, so
            "quintus_smyrnaeus.fall_of_troy" reads as "Quintus
            Smyrnaeus, Fall of Troy". prettyWork is only a fallback
            for an older cached response that predates those
            fields. */}
        <span className="font-bold text-sm text-red-800 group-hover:underline">
          {r.display_name || prettyWork(r.work)}
        </span>
        <span className="text-xs text-gray-500">{shortRef(r.ref_start)}</span>
        {dateParts(r) && (
          <span className="text-[11px] text-gray-500 tabular-nums whitespace-nowrap">
            {dateParts(r).date}
          </span>
        )}
        {r.strong && (
          <span className="ml-auto text-[11px] font-semibold text-green-700">strong</span>
        )}
      </div>
      {r.gist && (
        <p className="text-xs text-gray-600 mt-1 leading-snug">
          {r.gist}
          {/* The summary named someone the passage does not. Often that
              is sound inference (Vergil writes virgo where the summary
              says Sibyl), sometimes it is the wrong person, and a
              served result cannot tell those apart. So it is marked
              rather than asserted or hidden. */}
          {/* Name WHICH one. The old marker only appeared when NO
              name could be found, so the case it exists for slipped
              past: Valerius Flaccus 1.1-30 is summarised as "Apollo,
              Cumaean Sibyl, Aeneas", Apollo and the Sibyl are both in
              the text, Aeneas is not, and the record passed on
              Apollo's strength with nothing shown to the reader. */}
          {!!(r.names_unverified || []).length && (
            <span
              className="ml-1 text-[10px] text-amber-700"
              title="This name was not found in the passage. The summary may be naming someone the text refers to indirectly, or may have the wrong person. Check the text."
            >
              (not found here: {r.names_unverified.join(', ')})
            </span>
          )}
          {r.names_in_text === false && !(r.names_unverified || []).length && (
            <span
              className="ml-1 text-[10px] text-amber-700 whitespace-nowrap"
              title="This summary names people the passage itself does not name. It may be correct inference from context, or a misidentification. Check the text."
            >
              (names unconfirmed)
            </span>
          )}
        </p>
      )}
      {/* "Same people and places": the rare proper names this card shares
          with the selection, shown in the selection's own spelling. Only
          present on a names-group card (backend/passage_index.py,
          same_names_for_window). */}
      {r.shared_names?.length > 0 && (
        <p className="text-[11px] text-gray-600 mt-1 leading-snug">
          Shared names: {r.shared_names.join(', ')}
        </p>
      )}
      {/* One scriptural passage the corpus holds in several versions,
          collapsed into a single result. Naming the other versions is
          useful; giving each one its own row is not. */}
      {r.also_in?.length > 0 && (
        <p className="text-[11px] text-gray-500 mt-1 leading-snug">
          Also in{' '}
          {r.also_in
            .map((a) => LANG_LABEL[a.language] || a.language)
            .filter((v, i, arr) => arr.indexOf(v) === i)
            .join(', ')}
        </p>
      )}
      {r.themes?.length > 0 && (
        <div className="flex gap-1 flex-wrap mt-1">
          {r.themes.slice(0, 4).map((t) => (
            <span key={t} className="text-[10px] bg-gray-100 text-gray-600 rounded px-1">{t}</span>
          ))}
        </div>
      )}
      {/* Licensed for indexing and search only (data/restricted_texts.json). */}
      {r.restricted && (
        <p className="text-[10px] text-gray-400 mt-1">{r.credit}</p>
      )}
      {/* SAID OUTRIGHT: nothing indicated that titles were
          clickable. The whole card has always been a button, which
          is invisible; Theme Search says this in words on every
          result and the Reader should not be quieter about the same
          action. */}
      <span className="mt-2 inline-block text-[11px] font-medium text-red-700
                       group-hover:underline">
        Open in Reader &rarr;
      </span>
    </button>
  );
}

/** "Commentaries: Lactantius Placidus on Statius, 2 passages" -- one clause
 *  per commentary work represented, so several commentators set aside at
 *  once still read as a list rather than a bare count. */
function commentarySummary(commentaries) {
  const byWork = [];
  const counts = {};
  for (const r of commentaries) {
    const key = r.work;
    if (!counts[key]) {
      counts[key] = { label: r.display_name || prettyWork(r.work), count: 0 };
      byWork.push(key);
    }
    counts[key].count += 1;
  }
  return byWork
    .map((key) => `${counts[key].label}, ${counts[key].count} passage${counts[key].count === 1 ? '' : 's'}`)
    .join('; ');
}

/** The Reuse tab's per-work groups: the same card layout for either tier,
 *  factored out so tiering (strict shown directly, possible behind a
 *  collapsed section) does not duplicate the markup. */
function ReuseGroups({ quotations, onOpenPassage }) {
  // Work names and line references through the same resolver as the result
  // cards, so "sauda.kulliyat_wikisource.6.6" reads "Sauda, Kulliyat 6.6".
  const corpusMap = useCorpusTextMap(quotations[0]?.language);
  const workName = (w) => {
    const hit = citationFromCorpusMap(`${w}.0`, corpusMap);
    return hit ? (hit.work ? `${hit.author}, ${hit.work}` : hit.author) : prettyWork(w);
  };
  const refName = (q) => {
    const hit = citationFromCorpusMap(q.ref, corpusMap);
    return hit && hit.reference ? hit.reference : q.ref;
  };
  return (
    <div className="space-y-3">
      {groupReuseByWork(quotations).map(({ work: otherWork, year, items }) => (
        <div key={otherWork}>
          <div className="flex items-baseline gap-2 mb-1">
            <span className="font-bold text-sm text-red-800">{workName(otherWork)}</span>
            {year != null && (
              <span className="text-[11px] text-gray-500 tabular-nums">
                {year < 0 ? `${Math.abs(year)} BCE` : `${year} CE`}
              </span>
            )}
          </div>
          <div className="space-y-1.5">
            {items.map((q) => (
              <button
                key={`${q.work}-${q.ref}`}
                onClick={() => onOpenPassage?.({ work: q.work, language: q.language, ref_start: q.ref })}
                className="group w-full text-left bg-white border border-gray-200 rounded-lg p-2.5
                           hover:border-red-400 hover:bg-red-50/40 transition-colors
                           focus:outline-none focus:ring-2 focus:ring-red-400"
              >
                <div className="flex items-baseline gap-2 flex-wrap">
                  <span className="text-xs text-gray-500">{refName(q)}</span>
                  {q.span_len > 1 && (
                    <span className="text-[10px] font-semibold bg-gray-100 text-gray-600 rounded px-1">
                      {q.span_len} lines
                    </span>
                  )}
                </div>
                <p className="text-sm text-gray-800 mt-0.5 leading-snug">
                  <BoldSpans text={q.text} spans={q.bold_spans} />
                </p>
              </button>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

/** Group reuse quotations by the other work, newest author-date first (a
 *  work with no known author date sorts last, not first -- an unguessed date
 *  should not read as "oldest"). Within a work, order by span (a chained
 *  multi-line quotation before single lines) then by shared count. */
function groupReuseByWork(quotations) {
  const byWork = new Map();
  for (const q of quotations) {
    if (!byWork.has(q.work)) byWork.set(q.work, { work: q.work, year: q.year ?? null, items: [] });
    byWork.get(q.work).items.push(q);
  }
  const groups = [...byWork.values()];
  for (const g of groups) {
    g.items.sort((a, b) => (b.span_len - a.span_len) || (b.shared - a.shared));
  }
  groups.sort((a, b) => {
    if (a.year == null && b.year == null) return a.work < b.work ? -1 : 1;
    if (a.year == null) return 1;
    if (b.year == null) return -1;
    return b.year - a.year;
  });
  return groups;
}

/** "Date · place · region" or "" -- the label line a documents-collection
 *  card already shows (client/src/components/search/LineSearch.jsx's own
 *  documentDateLabel), reused here so the Reuse tab's documentary cards
 *  read the same way everywhere a document is cited. */
function documentDateLabel(d) {
  const nb = d.date_not_before, na = d.date_not_after;
  if (nb == null && na == null) return null;
  const fmt = (y) => (y < 0 ? `${-y} BC` : `${y} AD`);
  if (nb != null && na != null && nb !== na) return `${fmt(nb)}–${fmt(na)}`;
  return fmt(nb != null ? nb : na);
}

/** The Reuse tab's documentary group ("In inscriptions and papyri"): one
 *  card per document hit, each showing its edition, date, place and text
 *  type, the document's own text with the shared words bold (same
 *  BoldSpans component the literary cards use, from the character spans
 *  backend/reuse_documents.py computes), a "match on restored text" note
 *  when the hit's `restored` flag is set, and a link to the full /document
 *  page (the same Reader-adjacent view LineSearch.jsx's documentViewUrl
 *  opens from a documents-collection search hit). Not grouped by work --
 *  each hit IS its own document, so there is no "work" to group under the
 *  way literary quotations group by the quoting work. */
function DocumentReuseGroups({ documents, language }) {
  const sorted = [...documents].sort((a, b) => (b.span_len - a.span_len) || (b.shared - a.shared));
  return (
    <div className="space-y-1.5">
      {sorted.map((d) => {
        const labels = [d.text_type_label, d.object_type_label, d.material_label].filter(Boolean);
        const place = d.ancient_place || d.modern_place;
        const dateLabel = documentDateLabel(d);
        const docUrl = `/document?doc=${encodeURIComponent(d.doc_id)}&lang=${encodeURIComponent(language)}&documents=1`;
        return (
          <a
            key={`${d.doc_id}-${d.ref}`}
            href={docUrl}
            className="group block bg-white border border-gray-200 rounded-lg p-2.5
                       hover:border-red-400 hover:bg-red-50/40 transition-colors
                       focus:outline-none focus:ring-2 focus:ring-red-400"
          >
            <div className="flex items-baseline gap-2 flex-wrap">
              <span className="text-sm font-bold text-red-800 group-hover:underline">
                {d.credit?.principal_edition || d.doc_id}
              </span>
              {(dateLabel || place) && (
                <span className="text-[11px] text-gray-500">
                  {[dateLabel, place].filter(Boolean).join(' · ')}
                </span>
              )}
              {d.span_len > 1 && (
                <span className="text-[10px] font-semibold bg-gray-100 text-gray-600 rounded px-1">
                  {d.span_len} lines
                </span>
              )}
            </div>
            {labels.length > 0 && (
              <div className="flex gap-1 flex-wrap mt-1">
                {labels.map((lab) => (
                  <span key={lab} className="text-[10px] bg-gray-100 text-gray-600 rounded px-1">{lab}</span>
                ))}
              </div>
            )}
            <p className="text-sm text-gray-800 mt-1 leading-snug">
              <BoldSpans text={d.text} spans={d.bold_spans} />
            </p>
            {d.restored && (
              <p className="mt-1 text-[11px] text-sky-700">match on restored text</p>
            )}
          </a>
        );
      })}
    </div>
  );
}

/** "verg. aen. 6.1" -> "6.1". The Reader's refs carry the work's short tag and
 *  line-search's loci do not, so the numeric tail is the only part of the two
 *  that can be compared. */
function bareLocus(ref) {
  const m = String(ref || '').match(/(\d+(?:[.:]\d+)*)\s*$/);
  return m ? m[1] : String(ref || '').trim();
}

/** Bold the words a Reuse-tab quotation shares with the selected line, from
 *  the [start, end) character spans backend/reuse_table.py's line()
 *  computes server-side (_shared_word_mask/_bold_spans) -- a word-triple
 *  match (or, failing that, the plain shared token a possible-echo pair was
 *  matched on) reconstructed against the SAME normalized tokens the reuse
 *  table itself was built from, not a client-side guess at which words
 *  matter. Spans are non-overlapping and given in left-to-right order, so
 *  this only needs to walk them once. Same visual treatment as Verbal
 *  Parallels' Marked, below, for one consistent "this word is why" look
 *  across the two tabs. */
function BoldSpans({ text, spans }) {
  if (!text) return null;
  if (!spans || !spans.length) return <>{text}</>;
  const parts = [];
  let pos = 0;
  spans.forEach(([start, end], i) => {
    if (start > pos) parts.push(<span key={`t${i}`}>{text.slice(pos, start)}</span>);
    parts.push(
      <mark key={`b${i}`} className="bg-red-100 text-red-900 font-semibold rounded-sm px-[1px]">
        {text.slice(start, end)}
      </mark>
    );
    pos = end;
  });
  if (pos < text.length) parts.push(<span key="tail">{text.slice(pos)}</span>);
  return <>{parts}</>;
}

/** Mark the matched words inside a quoted passage.
 *
 *  Matching words in the reader were not highlighted. The card named them in
 *  chips above the quotation but left the quotation itself unmarked, so on a
 *  prose hit the reader had to scan a paragraph hunting for the two words that
 *  earned it a place in the list. Some of those paragraphs run past three
 *  thousand characters.
 *
 *  Whole-word and case-insensitive. Not stem matching: `matched_words` are the
 *  forms as they appear in THIS passage, so they are already the right shape.
 */
function Marked({ text, words, latin = false }) {
  const list = (words || []).filter(Boolean);
  if (!text) return null;
  if (!list.length) return <>{text}</>;
  // In Latin the matched word is reported in the SOURCE text's spelling, and
  // the two texts may not agree on u/v and i/j: Silius' "cateruas" against
  // Vergil's "catervas" left the Vergil line unmarked (2026-09-20). Each
  // u or v in the pattern matches either letter, and i or j likewise.
  const fold = (w) => (latin ? w.toLowerCase().replace(/v/g, 'u').replace(/j/g, 'i') : w.toLowerCase());
  const pattern = (w) => (latin
    ? escapeRe(w).replace(/[uv]/gi, '[uvUV]').replace(/[ij]/gi, '[ijIJ]')
    : escapeRe(w));
  const alt = [...new Set(list)]
    .sort((a, b) => b.length - a.length)          // longest first, so a short
    .map(pattern)                                 // word cannot eat a longer one
    .join('|');
  const parts = String(text).split(new RegExp(`(?<![\\p{L}])(${alt})(?![\\p{L}])`, 'giu'));
  return (
    <>
      {parts.map((p, i) => (
        list.some((w) => fold(w) === fold(p))
          ? <mark key={i} className="bg-red-100 text-red-900 font-semibold rounded-sm px-[1px]">{p}</mark>
          : <span key={i}>{p}</span>
      ))}
    </>
  );
}

function escapeRe(s) {
  return String(s).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

/** Trim a long passage, but never cut off the words that matched.
 *
 *  A flat 260-character cut hid the evidence on exactly the hits that need it:
 *  in a 3,749-character chapter of William of Tyre the matched words sit far
 *  past the cut, so the reader saw an unmarked opening and no reason the result
 *  was there at all. This keeps the window around the first match instead.
 */
function clip(text, words, span = 260) {
  const s = String(text || '');
  if (s.length <= span) return s;
  const first = (words || [])
    .map((w) => s.toLowerCase().indexOf(String(w).toLowerCase()))
    .filter((i) => i >= 0)
    .sort((a, b) => a - b)[0];
  if (first == null || first < span - 40) return `${s.slice(0, span)}…`;
  const start = Math.max(0, first - 60);
  return `…${s.slice(start, start + span)}…`;
}

/** The same underlying text, ignoring the suffix and any book split.
 *
 *  The Reader opens a book at a time -- "vergil.aeneid.part.6.tess" -- while
 *  the search index holds the whole poem as "vergil.aeneid.tess" and gives its
 *  loci as "6.1". Compared as plain strings the two never match, so Aeneid 6.1
 *  came back as a verbal parallel to itself, matching on fatur, classique and
 *  immittit. Dropping ".part.N" from both sides is what makes them the same
 *  work. The locus still has to match as well, so this does not hide Aeneid 2
 *  from a reader of Aeneid 6: only the selected lines themselves.
 */
function baseWork(s) {
  return String(s || '').replace(/\.tess$/, '').replace(/\.part\.[^.]+$/, '').toLowerCase();
}

function sameWork(a, b) {
  return baseWork(a) === baseWork(b) && baseWork(a) !== '';
}

/** Trailing book.line of a reference tag, which is what a reader recognises. */
export function shortRef(ref) {
  if (!ref) return '';
  const m = String(ref).match(/(\d+[.:]\d+)\s*$/);
  return m ? m[1] : String(ref).split(/\s+/).pop();
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
