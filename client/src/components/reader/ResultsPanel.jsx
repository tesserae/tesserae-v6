import { useState, useEffect } from 'react';
import { chronological, dateParts } from '../../utils/chronology';
import { LoadingSpinner } from '../common';
import { ResultsInsight } from '../assistant';

const LANG_LABEL = { la: 'Latin', grc: 'Greek', he: 'Hebrew', en: 'English', cop: 'Coptic' };

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
export default function ResultsPanel({ selection, language, work, units, onOpenPassage,
                                       initialTab }) {
  // Arriving from Theme Search, the reader has just been shown an English
  // summary of a passage in a language they may not read. Opening on the
  // translation is the useful default there; everywhere else 'similar' is.
  const [tab, setTab] = useState(initialTab || 'similar');

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

  useEffect(() => {
    if (!selection || tab !== 'similar') return;
    let cancelled = false;
    setLoading(true);
    setError(null);
    const params = new URLSearchParams({
      work,
      ref_start: selection.refStart || '',
      ref_end: selection.refEnd || selection.refStart || '',
      limit: '15',
    });
    fetch(`/api/passages/similar?${params}`)
      .then((r) => r.json())
      .then((d) => {
        if (cancelled) return;
        if (d.error) setError(d.error);
        setSimilar(d);
      })
      .catch((e) => { if (!cancelled) setError(e.message); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [selection, work, tab]);

  /* VERBAL PARALLELS: the selection's own wording, searched across the corpus.
   *
   * This tab said "Wiring in progress" for as long as the Reader has existed,
   * which NC found by opening it. The red gutter beside the text was already
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
    if (!query) { setVerbal({ results: [] }); return; }

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
        exclude_text_id: work,
        exclude_locus: bareLocus(selection.refStart),
      }),
    })
      .then((r) => r.json())
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
      .then((r) => r.json())
      .then((d) => { if (!cancelled) setTranslation(d); })
      .catch(() => { if (!cancelled) setTranslation(null); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [selection, work, units, tab]);

  const tabs = [
    ['similar', 'Similar Passages'],
    ['verbal', 'Verbal Parallels'],
    ['translation', 'Translation'],
  ];

  return (
    <aside className="w-full lg:w-96 border-t lg:border-t-0 lg:border-l border-gray-200 bg-gray-50 flex flex-col">
      <div className="flex border-b border-gray-200 text-sm">
        {tabs.map(([id, label]) => (
          <button
            key={id}
            onClick={() => setTab(id)}
            className={`px-3 py-2 font-semibold border-b-2 transition-colors ${
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
        {!selection && (
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
            {!loading && similar?.results?.length === 0 && (
              <p className="text-sm text-gray-500">
                No passage in the corpus resembles this selection closely.
              </p>
            )}
            {/* OLDEST FIRST, like Theme Search. These results cross centuries
                and the order they are read in is itself information: the
                Aeneid, then Ovid reworking it, then Silius after him. Ranking
                by score put Statius (96 CE) above Ovid (17 CE) and told the
                reader nothing about the line of descent. */}
            {!loading && chronological(similar?.results)?.map((r) => (
              <button
                key={r.id}
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
                      hover border on a div is not an affordance. */}
                  <span className="font-bold text-sm text-red-800 group-hover:underline">
                    {prettyWork(r.work)}
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
                {/* SAID OUTRIGHT. NC: "nothing indicates that their titles are
                    clickable." The whole card has always been a button, which
                    is invisible; Theme Search says this in words on every
                    result and the Reader should not be quieter about the same
                    action. */}
                <span className="mt-2 inline-block text-[11px] font-medium text-red-700
                                 group-hover:underline">
                  Open in Reader &rarr;
                </span>
              </button>
            ))}
            <p className="text-[11px] text-gray-400 pt-1 leading-snug">
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
                {r.text && (
                  <p className="text-xs text-gray-700 mt-1.5 leading-snug">
                    {r.text.length > 260 ? `${r.text.slice(0, 260)}…` : r.text}
                  </p>
                )}
                <span className="mt-2 inline-block text-[11px] font-medium text-red-700
                                 group-hover:underline">
                  Open in Reader &rarr;
                </span>
              </button>
            ))}
            {!verbalLoading && verbal?.results?.length > 0 && (
              <p className="text-[11px] text-gray-400 pt-1 leading-snug">
                Matches share dictionary forms, not necessarily spellings. Oldest first.
                {verbal.capped && ' The corpus holds more than are shown here.'}
              </p>
            )}
          </>
        )}

        {selection && tab === 'translation' && (
          <>
            {loading && <LoadingSpinner />}
            {!loading && translation?.available === false && (
              <p className="text-sm text-gray-500">
                {translation.reason} Aligned public-domain translations currently cover
                about a fifth of the Greek corpus and a tenth of the Latin.
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
          </>
        )}
      </div>
    </aside>
  );
}

/** "verg. aen. 6.1" -> "6.1". The Reader's refs carry the work's short tag and
 *  line-search's loci do not, so the numeric tail is the only part of the two
 *  that can be compared. */
function bareLocus(ref) {
  const m = String(ref || '').match(/(\d+(?:[.:]\d+)*)\s*$/);
  return m ? m[1] : String(ref || '').trim();
}

/** Same text, whether or not either side carries the .tess suffix. */
function sameWork(a, b) {
  const norm = (s) => String(s || '').replace(/\.tess$/, '').toLowerCase();
  return norm(a) === norm(b) && norm(a) !== '';
}

/** Trailing book.line of a reference tag, which is what a reader recognises. */
function shortRef(ref) {
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
