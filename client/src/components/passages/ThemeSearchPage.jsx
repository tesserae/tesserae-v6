import { useCallback, useEffect, useRef, useState } from 'react';
import { chronological, byBestMatch, dateParts } from '../../utils/chronology';
import { coverageCounts, fetchCoveredWorks } from '../../utils/passageCoverage';
import ThemeExport from './ThemeExport';
import ConnectionsMap from './ConnectionsMap';

/**
 * Theme Search: describe a passage in your own words, get passages that match
 * the DESCRIPTION rather than the wording.
 *
 * This had no interface at all. The route and the MCP tool existed, and content
 * search was called "live" on the strength of them, but no reader could reach
 * it without writing an HTTP request. This is that page.
 *
 * The confidence band is shown because the API reports one and the reader has
 * no other way to tell a real subject from a near miss. "A farmer lifts potatoes
 * out of the ground" scores higher than eight genuine classical subjects,
 * because everything in it but the potato is in the corpus, so the band is
 * doing real work and hiding it would be worse than showing it.
 */

/* THE EXAMPLES HAVE TO SUIT THE CORPUS THE SERVER ACTUALLY HOLDS.
 *
 * The four below on the left were written when the corpus was Latin and Greek,
 * and they are Homeric and Virgilian topoi. On a preview serving Coptic,
 * Persian, Urdu and Arabic, two of them came back "the corpus does not appear
 * to contain passages of this kind": the page was offering a first-time
 * visitor four suggestions and failing on half of them (NC, 2026-09-09). It is
 * the same fault as the Latin authors that once appeared in the Persian tab, a
 * fixed list that does not follow what is served.
 *
 * Every query in every set below was MEASURED against the corpus it is offered
 * to, not guessed. Each rated strong or moderate when run. If the corpus
 * changes substantially, measure them again rather than assuming they hold:
 * scripts exist for this in evaluation/probe_sets/.
 */
const EXAMPLE_SETS = {
  // Latin, Greek and English. The set the production site has always shown.
  classical: [
    'a guest arrives and is welcomed with food, wine, and a bath',
    'a mother laments her dead son over his body',
    'a wife or child recognizes someone long thought dead or lost',
    'a warrior arms himself before battle, piece by piece',
  ],
  // Persian, Urdu and Arabic, with Coptic alongside. Measured 2026-09-09:
  // all four rated strong, and three of the four return Coptic passages too.
  persoArabic: [
    'a moth is drawn to the candle flame and burns, love as self-destruction',
    'the cupbearer is asked to pour wine at dawn',
    'a poet praises his patron’s generosity and courage',
    'the dead are mourned and the mourner tears his clothes',
  ],
};

/** The example set for the languages this server serves. Classical wins when
 *  any of its languages is present, so production is unchanged. */
function examplesFor(served) {
  const has = (codes) => Array.isArray(served) && served.some((c) => codes.includes(c));
  if (has(['la', 'grc', 'en'])) return EXAMPLE_SETS.classical;
  if (has(['fa', 'ur', 'ar'])) return EXAMPLE_SETS.persoArabic;
  return EXAMPLE_SETS.classical;
}

const BAND = {
  unrated: {
    label: 'Not rated',
    className: 'bg-gray-50 text-gray-700 border-gray-300',
  },
  strong: {
    label: 'Strong match',
    className: 'bg-red-50 text-red-800 border-red-200',
  },
  moderate: {
    label: 'Moderate match',
    className: 'bg-amber-50 text-amber-800 border-amber-200',
  },
  low: {
    label: 'Weak match',
    className: 'bg-gray-100 text-gray-700 border-gray-300',
  },
};

/** A link into the Reader, landing on this passage with the translation open.
 *
 * A reader who finds a Persian or Coptic passage by its English summary needs
 * two things next: the passage itself, and a translation. Sending them to line 1
 * of the work with the "similar passages" tab showing would lose both.
 *
 * A real href, not a click handler, so the result can be opened in a new tab and
 * kept. Scholars compare things side by side.
 */
function readerLink(r, query) {
  const work = String(r.work || '').replace(/\.tess$/, '');
  const params = new URLSearchParams({
    work: `${work}.tess`,
    lang: r.language || 'la',
    // BOTH ends of the window. Sending only ref_start selected a single line, so
    // the Reader showed the whole original beside a translation of one line: the
    // found passage and its English were nowhere near each other. The passage
    // index knows the span, so the Reader should select the span.
    ref: r.ref_start || '',
    refEnd: r.ref_end || r.ref_start || '',
    tab: 'translation',
    // Carried through so the Reader can say what was searched for. Landing deep
    // in a text with no memory of the question is disorienting.
    q: query || '',
  });
  return `/read?${params.toString()}`;
}

/** Group consecutive results from the same work, keeping every passage.
 *
 *  Two windows of Aeschylus's Seven matched, and the header, date and title
 *  were repeated in full for each, which reads as two works. They are one work
 *  and two passages. Collapsing them to a single row would be worse: the
 *  passages are genuinely different and their loci and summaries are the point.
 *  So the work is stated once and the passages are listed under it.
 *
 *  Consecutive is enough because the list is already sorted by date, so all
 *  passages of one work sit together.
 */
function byWork(results) {
  const groups = [];
  for (const r of results) {
    const key = `${r.work}|${r.language}`;
    const last = groups[groups.length - 1];
    if (last && last.key === key) last.items.push(r);
    else groups.push({ key, head: r, items: [r] });
  }
  return groups;
}

const LANG_LABEL = {
  la: 'Latin', grc: 'Greek', he: 'Hebrew', cop: 'Coptic',
  en: 'English', fa: 'Persian', ur: 'Urdu', ar: 'Arabic',
  it: 'Italian', fro: 'Old French', gmh: 'Middle High German',
};

/** "Latin, Greek, English and Coptic" -- used for the fixed coverage
 *  sentence shown when the picker is narrowed to one language Browse Corpus
 *  doesn't cover (Hebrew, Persian, Urdu). */
function joinLangNames(codes) {
  const names = codes.map((c) => LANG_LABEL[c] || c);
  if (names.length < 2) return names.join('');
  return `${names.slice(0, -1).join(', ')} and ${names[names.length - 1]}`;
}

// Order as the rest of the site uses: Latin, Greek, English, then the others.
const LANG_CHOICES = [
  ['', 'All languages'],
  ['la', 'Latin'],
  ['grc', 'Greek'],
  ['en', 'English'],
  ['he', 'Hebrew'],
  ['cop', 'Coptic'],
  ['fa', 'Persian'],
  ['ur', 'Urdu'],
  ['ar', 'Arabic'],
  ['it', 'Italian'],
  ['fro', 'Old French'],
  ['gmh', 'Middle High German'],
];

// The passage index on production has held Persian and Urdu windows since
// 2026-08-25 by design, while word search does not serve those languages, so
// /api/languages does not list them. They stay on offer here regardless.
const INDEX_ONLY = ['fa', 'ur'];

export default function ThemeSearchPage() {
  const [query, setQuery] = useState('');
  // Read synchronously (a lazy initializer, not an effect) so that on the
  // very first render -- before any effect has run -- `language` already
  // reflects a shared link's languages= param. Without this, the aggregate
  // coverage fetch below (which only runs when the picker ISN'T on a single
  // covered language) would see the pre-deep-link '' for one extra render
  // and fetch coverage for all four languages even when the link was
  // headed straight for one of them.
  const [language, setLanguage] = useState(() => {
    const p = new URLSearchParams(window.location.search);
    // Mirrors the "arriving from a link with the search already in it"
    // effect below: the language only carries over when a query does too,
    // matching what that effect will go on to run.
    if (!(p.get('query') || '').trim()) return '';
    return (p.get('languages') || '').split(',').map((x) => x.trim()).filter(Boolean).join(',');
  });
  // Only the languages this server serves are offered (a preview serves a
  // few; the full row on it promised Latin and Old French, 2026-09-07).
  const [served, setServed] = useState(null);
  useEffect(() => {
    fetch('/api/languages').then((r) => r.json()).then((d) => {
      const codes = (d.languages || []).map((l) => l.code || l).filter(Boolean);
      if (codes.length) setServed(codes);
    }).catch(() => {});
  }, []);
  // How much of the current single language Theme Search actually reaches
  // ("Searches N of M works in this language"), with a link to the full list
  // in Browse Corpus. Cheap to compute -- both fetches are already used
  // elsewhere for this -- but only meaningful for exactly one language at a
  // time, and only for the four Browse Corpus itself covers; multi-select
  // and "All languages" (the default) skip it rather than show something
  // that doesn't parse or a link Browse Corpus can't honor.
  const [coverage, setCoverage] = useState(null);
  const BROWSE_CORPUS_LANGUAGES = ['la', 'grc', 'en', 'cop'];
  // Which of the three coverage-line states applies: one covered language
  // picked alone keeps the per-language sentence; one uncovered language
  // (Hebrew, Persian, Urdu, or any other not in Browse Corpus) alone gets
  // the fixed sentence; "All languages" (nothing picked) or several picked
  // together get the summed sentence. Computed here (not just above the
  // JSX) because the aggregate fetch below needs it too.
  const selectedLangCodes = language ? language.split(',').map((s) => s.trim()).filter(Boolean) : [];
  const singleCoveredLang = selectedLangCodes.length === 1 && BROWSE_CORPUS_LANGUAGES.includes(selectedLangCodes[0]);
  const singleUncoveredLang = selectedLangCodes.length === 1 && !singleCoveredLang;
  // `coverage` can be stale (left over from a previously selected covered
  // language) while its fetch for the current one is still in flight, so
  // "resolved" checks the language it was fetched for, not just whether it
  // is non-null.
  const coverageResolved = Boolean(coverage) && coverage.language === selectedLangCodes[0];
  useEffect(() => {
    const codes = language ? language.split(',').map((s) => s.trim()).filter(Boolean) : [];
    if (codes.length !== 1 || !BROWSE_CORPUS_LANGUAGES.includes(codes[0])) {
      setCoverage(null);
      return;
    }
    const code = codes[0];
    let dead = false;
    fetch(`/api/texts?language=${code}`).then((r) => r.json()).catch(() => []).then((texts) => {
      if (dead) return texts;
      // Right after a deploy reload the passage index can still be
      // loading on this server and /api/passages/works answers slow or
      // empty; fetchCoveredWorks retries at +3s and +10s (see Browse
      // Corpus, utils/passageCoverage) rather than trust a first answer
      // of zero.
      return fetchCoveredWorks(code, (texts || []).length > 0).then((works) => {
        if (dead) return;
        // Same helper Browse Corpus's own count uses (utils/passageCoverage),
        // so the two "N of M" numbers can't drift apart from each other.
        const { covered, total } = coverageCounts(texts, works || []);
        setCoverage({ covered, total, language: code });
      });
    }).catch(() => { if (!dead) setCoverage(null); });
    return () => { dead = true; };
  }, [language]);

  // The same coverage question, summed over all four languages Browse Corpus
  // indexes, for the line shown when the picker isn't narrowed to exactly one
  // covered language: the default "All languages", several picked together,
  // or one language Browse Corpus doesn't index. Fetched only the first time
  // one of those states is reached (not on every mount -- the single-covered-
  // -language path, the common case, never needs it) and cached here rather
  // than refetched on every later language click -- one /api/texts and one
  // /api/passages/works call per language, four pairs total, at most once.
  const [allCoverage, setAllCoverage] = useState(null);
  const allCoverageStarted = useRef(false);
  useEffect(() => {
    if (singleCoveredLang || allCoverageStarted.current) return;
    allCoverageStarted.current = true;
    let dead = false;
    Promise.all(BROWSE_CORPUS_LANGUAGES.map((code) => (
      fetch(`/api/texts?language=${code}`).then((r) => r.json()).catch(() => []).then((texts) => {
        const arr = Array.isArray(texts) ? texts : [];
        return fetchCoveredWorks(code, arr.length > 0).then((works) => coverageCounts(arr, works || []));
      })
    ))).then((results) => {
      if (dead) return;
      const total = results.reduce((sum, r) => sum + r.covered, 0);
      setAllCoverage({ total, languageCount: BROWSE_CORPUS_LANGUAGES.length });
    }).catch(() => { allCoverageStarted.current = false; });
    return () => { dead = true; };
  }, [singleCoveredLang]);

  const [data, setData] = useState(null);
  const [running, setRunning] = useState(false);
  const [showWeak, setShowWeak] = useState(false);
  const [error, setError] = useState(null);

  // How deep the ranked list goes. 25 at first; Show more steps it up to the
  // API's cap of 100. NC reached the bottom of the 25 hunting Genesis 22,
  // which sat just below the cutoff, with no way to page deeper.
  const [limit, setLimit] = useState(25);
  const [loadingMore, setLoadingMore] = useState(false);
  // Once `limit` maxes out at 100, Show More switches from re-running the
  // query with a bigger limit (a superset it can drop in whole) to paging
  // with `offset`: results (pastCap+1) to (pastCap+100) of the same ranking,
  // appended rather than replacing what is already on screen. Verified
  // 2026-09-10: for a broad topos, passages a scholar would want -- Alan of
  // Lille Anticlaudianus 1.73, Nonnus Dionysiaca 3.147, Seneca Oedipus 525,
  // Pliny Letters 5.6.5 -- ranked 300 to 3,000, well past the old cap with no
  // way to reach them.
  const [pastCap, setPastCap] = useState(0);
  // Set once an offset fetch comes back with nothing new, which is the only
  // reliable signal that the ranking has run out (the confidence-band floor
  // in _rank means the ranking can end well short of the corpus).
  const [exhausted, setExhausted] = useState(false);
  // Display order. 'score' shows the strongest matches first, which is what
  // a search should default to: chronological-only display let weak ancient
  // matches sit above strong later ones, and pushed the (deliberately
  // undated) Hebrew Bible to the bottom of every list. 'date' remains for
  // tracing an image through time, which the moth-and-candle search does
  // beautifully. The API already returns work groups in score order.
  const [order, setOrder] = useState('score');

  const run = useCallback(async (q, lang, depth) => {
    const text = (q || '').trim();
    if (!text || running || loadingMore) return;
    const wanted = depth || 25;
    const deepening = Boolean(depth) && data;
    // A fresh search blanks the page; Show more keeps the list on screen and
    // swaps in the longer one when it arrives.
    if (deepening) setLoadingMore(true);
    else {
      setRunning(true); setData(null); setShowWeak(false); setLimit(25);
      setPastCap(0); setExhausted(false);
    }
    setError(null);
    const langParam = lang === undefined ? language : lang;
    try {
      const res = await fetch(
        `/api/passages/theme-search?query=${encodeURIComponent(text)}&limit=${wanted}`
        + (langParam ? `&languages=${encodeURIComponent(langParam)}` : ''));
      const json = await res.json();
      // The API reports trouble in the body rather than by status, so that a
      // missing index degrades this panel instead of breaking the page.
      if (json.error) setError(json.error);
      else {
        setData(json);
        setLimit(wanted);
        // Record the search in the address. The page has always been able to
        // READ a query from the URL, and never wrote one, so reloading lost
        // the search and there was nothing to copy out of the address bar
        // (2026-09-08). replaceState rather than pushState: the reader gets a
        // reloadable, sendable link without the Back button filling up with
        // every refinement of the same search.
        const p = new URLSearchParams({ query: text });
        if (langParam) p.set('languages', langParam);
        window.history.replaceState({}, '', `/theme-search?${p.toString()}`);
      }
    } catch (e) {
      setError(e.message || 'the search could not be run');
    } finally {
      setRunning(false);
      setLoadingMore(false);
    }
  }, [running, loadingMore, data, language]);

  // Show More past `limit`'s cap of 100: fetches the next 100 ranked results
  // (offset+1 .. offset+100) and appends them. Grouping and ordering are
  // re-derived from the full accumulated `data.results` on every render (see
  // byWork/byBestMatch/chronological below), so appending here -- rather than
  // replacing -- is what keeps a passage already on screen from moving: a
  // full re-sort by score or date is idempotent on rows whose scores/dates
  // did not change, and every appended row ranks below everything already
  // shown.
  const loadPastCap = useCallback(async () => {
    if (!data || running || loadingMore) return;
    const text = (data.query || query || '').trim();
    if (!text) return;
    setLoadingMore(true);
    setError(null);
    const nextOffset = pastCap + 100;
    try {
      const res = await fetch(
        `/api/passages/theme-search?query=${encodeURIComponent(text)}`
        + `&limit=100&offset=${nextOffset}`
        + (language ? `&languages=${encodeURIComponent(language)}` : ''));
      const json = await res.json();
      if (json.error) {
        setError(json.error);
      } else if (!json.results || !json.results.length) {
        // Nothing more past this point; hide the button rather than let a
        // reader click into empty fetches.
        setExhausted(true);
      } else {
        // On a multi-language page the language interleave can pull a work
        // up from deeper in the pool, so a later page may carry a passage
        // already on screen. Keep the first copy.
        setData((prev) => {
          const have = new Set((prev.results || []).map((r) => `${r.work}|${r.ref_start}|${r.ref_end}`));
          const fresh = json.results.filter((r) => !have.has(`${r.work}|${r.ref_start}|${r.ref_end}`));
          return { ...prev, results: [...(prev.results || []), ...fresh] };
        });
        setPastCap(nextOffset);
      }
    } catch (e) {
      setError(e.message || 'the search could not be run');
    } finally {
      setLoadingMore(false);
    }
  }, [data, running, loadingMore, pastCap, language, query]);

  // Arriving from a link with the search already in it -- from Tessa, from a
  // bookmark, from a colleague. The page runs it rather than making the reader
  // press Search on a query that is already filled in.
  const ranFromUrl = useRef(false);
  useEffect(() => {
    if (ranFromUrl.current) return;
    ranFromUrl.current = true;
    const p = new URLSearchParams(window.location.search);
    const q = (p.get('query') || '').trim();
    if (!q) return;
    // any number of languages, comma-separated (2026-09-06: a pick-several
    // control). `language` state already carries this (see its lazy
    // initializer above, which reads the same params), and `run` falls back
    // to `language` when its second argument is omitted.
    setQuery(q);
    run(q);
  }, [run]);

  const band = data && BAND[data.confidence?.level];

  // 'search' is Theme Search itself; 'map' is a picture of the same
  // connections at a larger scale (see client/src/components/passages/
  // ConnectionsMap.jsx). Read from the URL so a link to /theme-search?tab=map
  // lands on the map directly.
  const [tab, setTab] = useState(() => {
    const p = new URLSearchParams(window.location.search);
    return p.get('tab') === 'map' ? 'map' : 'search';
  });
  const setTabAndUrl = (t) => {
    setTab(t);
    const p = new URLSearchParams(window.location.search);
    if (t === 'map') p.set('tab', 'map'); else p.delete('tab');
    window.history.replaceState({}, '', `/theme-search${p.toString() ? `?${p}` : ''}`);
  };

  return (
    <div className="max-w-4xl mx-auto p-6">
      <h1 className="text-2xl font-semibold text-gray-900">Theme Search</h1>
      <span className="ml-2 align-middle rounded border border-amber-200 bg-amber-50 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-amber-800">
        Beta
      </span>

      <div className="mt-4 inline-flex rounded border border-gray-300 overflow-hidden text-sm">
        {[['search', 'Theme Search'], ['map', 'Similarity Map']].map(([v, label]) => (
          <button
            key={v}
            onClick={() => setTabAndUrl(v)}
            aria-pressed={tab === v}
            className={`px-3 py-1.5 font-medium ${tab === v ? 'bg-red-700 text-white' : 'bg-white text-gray-700 hover:bg-gray-50'}`}
          >
            {label}
          </button>
        ))}
      </div>

      {tab === 'map' ? (
        <div className="mt-4">
          <ConnectionsMap />
        </div>
      ) : (
      <>
      <p className="mt-2 text-sm text-gray-600 leading-relaxed">
        Describe what happens in a passage and this finds passages that match the
        description.
      </p>

      <form
        className="mt-5 flex gap-2"
        onSubmit={(e) => { e.preventDefault(); run(query); }}
      >
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="a warrior arms himself before battle"
          className="flex-1 border border-gray-300 rounded px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-red-600"
        />
        <button
          type="submit"
          disabled={running || !query.trim()}
          className="px-4 py-2 rounded bg-red-700 text-white text-sm font-medium hover:bg-red-800 disabled:opacity-40"
        >
          {running ? 'Searching…' : 'Search'}
        </button>
      </form>

      {/* WHY THIS IS HERE
        *
        * The page shows 25 works, and the corpus holds seven languages, so each
        * language gets three or four slots. That is why "warrior arming scene"
        * returned no Vergil: the Aeneid was the 28th work, behind Persian,
        * Greek, Neo-Latin and English arming scenes that are all genuine hits.
        * Restricted to Latin it is 8th; restricted to Greek, the Iliad is 1st.
        *
        * So a scholar working in one language was being outvoted by the breadth
        * of the corpus. The API already took `languages`; nothing exposed it. */}
      <div className="mt-3 flex flex-wrap items-center gap-2">
        <span className="text-xs text-gray-600">Search in</span>
        {/* Pick any set of languages (2026-09-06). 'All' clears the set; the
            request sends the chosen codes comma-separated, which the API has
            always accepted. */}
        {LANG_CHOICES.filter(([v]) => !v || !served || served.includes(v) || INDEX_ONLY.includes(v)).map(([v, label]) => {
          const chosen = language ? language.split(',') : [];
          const on = v ? chosen.includes(v) : chosen.length === 0;
          const toggle = () => {
            let next;
            if (!v) next = '';
            else next = (on ? chosen.filter((c) => c !== v) : [...chosen, v]).join(',');
            setLanguage(next);
            // Re-run only a search that has already been run, so changing the
            // languages refines the list on screen. Typing a query and then
            // picking languages used to start the search before the reader
            // pressed Search (NC, 2026-09-06).
            if (data && query.trim()) run(query, next);
          };
          return (
            <label key={v || 'all'} className={`text-xs px-2 py-0.5 rounded border cursor-pointer select-none ${on ? 'bg-red-600 text-white border-red-600' : 'bg-white text-gray-700 border-gray-300 hover:bg-gray-50'}`}>
              <input type="checkbox" className="sr-only" checked={on} onChange={toggle} />
              {label}
            </label>
          );
        })}
        <span className="text-[11px] text-gray-500">
          fewer languages show more of each
        </span>
      </div>

      {singleCoveredLang && coverageResolved && coverage.total > 0 && (
        <p className="mt-1 text-[11px] text-gray-500">
          {coverage.covered > 0
            // A covered count of zero is indistinguishable from "the
            // coverage fetch hasn't succeeded yet" (see fetchCoveredWorks
            // in utils/passageCoverage), so this never asserts "0 of N".
            ? <>Searches {coverage.covered} of {coverage.total} works in {LANG_LABEL[coverage.language] || coverage.language}.{' '}</>
            : <>Theme Search coverage is loading.{' '}</>}
          <a
            href={`/corpus?theme=1&language=${coverage.language}`}
            className="text-red-700 hover:underline"
          >
            See the list of covered works
          </a>
        </p>
      )}

      {singleCoveredLang && coverageResolved && coverage.total === 0 && (
        // This covered language genuinely has zero indexed works. "0 of 0"
        // asserts nothing, so point at the general list instead of a
        // per-language one that would have nothing to show.
        <p className="mt-1 text-[11px] text-gray-500">
          Theme Search covers works in {joinLangNames(BROWSE_CORPUS_LANGUAGES)};{' '}
          <a href="/corpus?theme=1&language=la" className="text-red-700 hover:underline">
            see the list
          </a>.
        </p>
      )}

      {singleCoveredLang && !coverageResolved && (
        // Still fetching, or the language just changed and the fetch for it
        // hasn't landed yet. This used to render nothing at all -- the gap
        // the coverage line exists to close.
        <p className="mt-1 text-[11px] text-gray-500">
          Theme Search coverage is loading.{' '}
          <a
            href={`/corpus?theme=1&language=${selectedLangCodes[0]}`}
            className="text-red-700 hover:underline"
          >
            See the list of covered works
          </a>
        </p>
      )}

      {singleUncoveredLang && (
        <p className="mt-1 text-[11px] text-gray-500">
          Theme Search covers works in {joinLangNames(BROWSE_CORPUS_LANGUAGES)};{' '}
          <a href="/corpus?theme=1&language=la" className="text-red-700 hover:underline">
            see the list
          </a>.
        </p>
      )}

      {!singleCoveredLang && !singleUncoveredLang && (
        <p className="mt-1 text-[11px] text-gray-500">
          {allCoverage
            ? <>Theme Search covers {allCoverage.total} works in {allCoverage.languageCount} languages.{' '}</>
            : <>Theme Search coverage is loading.{' '}</>}
          <a href="/corpus?theme=1&language=la" className="text-red-700 hover:underline">
            See the list.
          </a>
        </p>
      )}

      <div className="mt-3 flex flex-wrap gap-2">
        {examplesFor(served).map((ex) => (
          <button
            key={ex}
            onClick={() => { setQuery(ex); run(ex); }}
            className="text-xs text-red-700 hover:text-red-900 hover:bg-red-50 border border-gray-200 rounded px-2 py-1"
          >
            {ex}
          </button>
        ))}
      </div>

      {running && (
        <p className="mt-6 text-sm text-gray-500 italic">
          Comparing your description against every indexed passage…
        </p>
      )}

      {error && (
        <div className="mt-6 rounded border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">
          {error}
        </div>
      )}

      {data && (
        <div className="mt-6">
          {band && (
            <div className={`rounded border px-3 py-2 text-sm ${band.className}`}>
              <strong className="font-semibold">{band.label}.</strong>{' '}
              {data.note || 'The corpus holds passages of this kind.'}
            </div>
          )}

          {!data.results?.length && (
            <p className="mt-4 text-sm text-gray-600">
              Nothing in the corpus resembles that description.
            </p>
          )}

          {/* A weak verdict followed by twenty results reads as twenty findings,
              whatever the banner says. The passages are not hidden -- knowing
              what came closest is sometimes the useful answer -- but they are
              not laid out as results until asked for. */}
          {data.confidence?.level === 'low' && !!data.results?.length && !showWeak && (
            <div className="mt-4">
              <button
                onClick={() => setShowWeak(true)}
                className="text-sm text-red-700 hover:text-red-900 hover:underline"
              >
                Show the {data.results.length} nearest passages anyway
              </button>
              <p className="mt-1 text-xs text-gray-500">
                These are the closest the corpus comes. For a subject it does not
                contain, the closest thing is not evidence of anything.
              </p>
            </div>
          )}

          {/* Offered only where the results are, so it is not held out beside a
              low-confidence set the reader has not chosen to look at. */}
          {(data.confidence?.level !== 'low' || showWeak) && (
            <ThemeExport query={data.query || query} language={language}
                         corpusVersion={data.corpus_version}
                         ranking={data.reader?.applied && data.reader.model ? `re-ranked by reader ${data.reader.model}` : undefined}
                         count={data.results?.length || 0} />
          )}
          {(data.confidence?.level !== 'low' || showWeak) && (
          <div className="mt-4 mb-2 flex items-center gap-3 text-xs text-gray-500">
            <span className="flex rounded border border-gray-300 overflow-hidden">
              {[['score', 'Best match'], ['date', 'Oldest first']].map(([k, label]) => (
                <button
                  key={k}
                  onClick={() => setOrder(k)}
                  aria-pressed={order === k}
                  className={`px-2 py-1 font-medium ${
                    order === k ? 'bg-gray-100 text-gray-900'
                                : 'bg-white text-gray-500 hover:text-gray-800'}`}
                >
                  {label}
                </button>
              ))}
            </span>
            <span>
              {order === 'date'
                ? 'Oldest first. Undated authors are listed last.'
                : 'Strongest matches first.'}
            </span>
          </div>
          )}
          {(data.confidence?.level !== 'low' || showWeak) && (
          <ul className="space-y-3">
            {byWork(order === 'date' ? chronological(data.results) : byBestMatch(data.results))
              .map(({ key, head, items }) => (
              <li key={key} className="border border-gray-200 rounded p-3 bg-white">
                {/* On a phone the three columns do not fit: the fixed date
                    column plus the language label squeezed the title to three
                    lines and pushed "GREEK" off the right edge. So the row
                    stacks below `sm` and becomes columns above it. */}
                <div className="flex flex-col sm:flex-row sm:items-baseline gap-1 sm:gap-3">
                  {/* Above `sm` the date column is fixed so the years line up
                      down the page and can be scanned. Everything inside it
                      must wrap: only the chip is allowed one unbroken line. */}
                  <div className="sm:w-36 sm:shrink-0 min-w-0 break-words">
                    {(() => {
                      const d = dateParts(head);
                      if (!d) {
                        return (
                          <span className="inline-block rounded bg-gray-50 border border-gray-200 px-2 py-0.5 text-sm text-gray-500">
                            undated
                          </span>
                        );
                      }
                      return (
                        <>
                          <span className="inline-block rounded bg-gray-100 border border-gray-200 px-2 py-0.5 text-sm font-semibold text-gray-900 tabular-nums whitespace-nowrap">
                            {d.date}
                          </span>
                          <div className="mt-0.5 text-[11px] text-gray-500 leading-tight">
                            {d.kind && `(${d.kind})`}
                            {d.kind && head.era ? ' · ' : ''}
                            {head.era}
                          </div>
                          {d.about && (
                            <div className="mt-0.5 text-[11px] text-gray-500 leading-tight">
                              {d.about}
                            </div>
                          )}
                        </>
                      );
                    })()}
                  </div>

                  <div className="min-w-0 flex-1">
                    <span className="font-medium text-gray-900">
                      {head.display_name || head.work}
                    </span>
                    {items.length > 1 && (
                      <span className="ml-2 text-xs text-gray-500">
                        {items.length} passages
                      </span>
                    )}
                  </div>

                  <span className="sm:shrink-0 text-[10px] uppercase tracking-wide text-gray-500">
                    {LANG_LABEL[head.language] || head.language}
                  </span>
                </div>

                {/* Every matching passage, in full. The work is named once; the
                    passages are not merged, because their loci and summaries are
                    what the reader came for. */}
                <ul className="mt-2 sm:ml-[8.75rem] space-y-2">
                  {items.map((r) => (
                    <li key={r.id || r.ref_start}
                        className={items.length > 1
                          ? 'border-l-2 border-gray-200 pl-3'
                          : ''}>
                      <div className="flex items-baseline gap-2 flex-wrap">
                        <a
                          href={readerLink(r, data.query || query)}
                          className="text-sm text-red-800 hover:text-red-900 hover:underline"
                        >
                          {r.ref_start}
                        </a>
                        {r.strong === false && (
                          <span className="text-[10px] text-gray-500 border border-gray-300 rounded px-1">
                            weak neighbor
                          </span>
                        )}
                      </div>
                      {r.gist && (
                        <p className="mt-0.5 text-sm text-gray-700 leading-snug">{r.gist}</p>
                      )}
                      {!!(r.names_unverified || []).length && (
                        <p className="mt-0.5 text-[11px] text-amber-700">
                          Not found in the passage:{' '}
                          <span className="font-medium">{r.names_unverified.join(', ')}</span>.
                          The summary may be naming someone the text refers to
                          indirectly, or may have the wrong person.
                        </p>
                      )}
                      {!!(r.themes || []).length && (
                        <div className="mt-1 flex flex-wrap gap-1">
                          {r.themes.slice(0, 5).map((t) => (
                            <span key={t}
                                  className="text-[11px] bg-gray-100 text-gray-600 rounded px-1.5 py-0.5">
                              {t}
                            </span>
                          ))}
                        </div>
                      )}
                    </li>
                  ))}
                </ul>
              </li>
            ))}
          </ul>
          )}

          {(data.confidence?.level !== 'low' || showWeak) &&
            (data.results || []).length > 0 && !(limit >= 100 && exhausted) && (
            <div className="mt-4 text-center">
              <button
                onClick={() => (limit < 100
                  ? run(query, undefined, Math.min(limit + 25, 100))
                  : loadPastCap())}
                disabled={loadingMore}
                className="rounded border border-gray-300 bg-white px-4 py-1.5 text-sm
                           text-gray-700 hover:border-gray-400 hover:text-gray-900
                           disabled:text-gray-500"
              >
                {loadingMore ? 'Loading…' : 'Show more results'}
              </button>
              {limit >= 100 && (
                <p className="mt-1 text-xs text-gray-500">
                  Past the default cutoff. Matches below this line are weaker.
                </p>
              )}
            </div>
          )}
          {(data.confidence?.level !== 'low' || showWeak) && limit >= 100 && exhausted && (
            <p className="mt-4 text-center text-xs text-gray-500">
              End of the ranked list. Narrowing to one language shows more of it.
            </p>
          )}
          {(data.confidence?.level !== 'low' || showWeak) && (
          <p className="mt-5 text-xs text-gray-500 leading-relaxed">
            These summaries are written by a language model from the passage
            itself, and for Coptic from its English translation, so treat them as
            a finding aid rather than as evidence. Read the passage before citing
            it.
          </p>
          )}
        </div>
      )}
      </>
      )}
    </div>
  );
}
