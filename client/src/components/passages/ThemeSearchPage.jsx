import { useCallback, useEffect, useRef, useState } from 'react';
import { chronological, byBestMatch, dateParts } from '../../utils/chronology';
import { baseWorkId, coverageCounts, fetchCoveredWorks } from '../../utils/passageCoverage';
import SearchableSelect from '../common/SearchableSelect';
import { LANGUAGE_NAMES as LANG_LABEL } from '../../utils/languageNames';
import { useCorpus } from '../../hooks';
import TextSelector from '../search/TextSelector';
import ThemeExport from './ThemeExport';
import ConnectionsMap from './ConnectionsMap';
import ThemeCoins from '../coins/ThemeCoins';
import ThemeObjects from '../objects/ThemeObjects';
import useCollections from '../../hooks/useCollections';
import { PAGE_NEEDS } from '../../collections/collectionsConfig';
import ScopeBox from '../common/ScopeBox';

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
 * visitor four suggestions and failing on half of them (2026-09-09). It is
 * the same fault as the Latin authors that once appeared in the Persian tab, a
 * fixed list that does not follow what is served.
 *
 * Every query in every set below was MEASURED against the corpus it is offered
 * to, not guessed. Each rated strong or moderate when run. If the corpus
 * changes substantially, measure them again rather than assuming they hold:
 * scripts exist for this in evaluation/probe_sets/.
 */
const EXAMPLE_SETS = {
  // Latin, Greek and English. Re-measured on production 2026-09-20 against the
  // requirement that suggested sample searches be known winners: every query
  // here rated STRONG that day, and the funeral games query is the one the
  // 16-theme benchmark scores best (first-ten precision 1.00; Iliad 23,
  // Thebaid 6, the Punica, Quintus). "a wife or child recognizes someone
  // long thought dead or lost" was dropped: it rated moderate and missed the
  // Odyssey's recognitions, which the encoder ranks 63rd by work for that
  // wording (docs/DECISIONS.md, 2026-09-20, Theme Search sample searches).
  classical: [
    'a guest arrives and is welcomed with food, wine, and a bath',
    'a mother laments her dead son over his body',
    'a warrior arms himself before battle, piece by piece',
    'funeral games with athletic contests held in honor of the dead',
    'a storm at sea batters ships and terrifies the crew',
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
  // A theme common enough in the searched language that a good match can't
  // stand out from the ordinary run of that language's own corpus (2026-10-08:
  // "passionate love" in Persian). Distinct from both a weak match (nothing
  // resembles the query) and an ordinary moderate/strong one (a match that
  // does stand out); see the note text in backend/passage_index.py.
  pervasive: {
    label: 'Common theme',
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

/** "Latin, Greek, English, Coptic, Hebrew, Persian and Urdu" (whatever this
 *  server serves) -- used for the fixed coverage sentence shown when the
 *  picker is narrowed to one language this server doesn't serve at all. */
function joinLangNames(codes) {
  const names = codes.map((c) => LANG_LABEL[c] || c);
  if (names.length < 2) return names.join('');
  return `${names.slice(0, -1).join(', ')} and ${names[names.length - 1]}`;
}

// Order as the rest of the site uses: Latin, Greek, English, then the
// others. The order is local to this picker; the names themselves come
// from the one shared table (this used to be a fourth hand-written copy of
// the same code -> name lookup, missed by the 2026-09-21 code review's
// finding 3, which caught two other copies but not this one).
const LANG_CHOICE_ORDER = ['la', 'grc', 'en', 'he', 'cop', 'fa', 'ur', 'ar', 'it', 'fro', 'gmh'];
const LANG_CHOICES = [
  ['', 'All languages'],
  ...LANG_CHOICE_ORDER.map((code) => [code, LANG_LABEL[code] || code]),
];

// The passage index on production has held Persian and Urdu windows since
// 2026-08-25 by design, while word search does not serve those languages, so
// /api/languages does not list them. They stay on offer here regardless.
const INDEX_ONLY = ['fa', 'ur'];

/** Plain-language readings of the /api/passages/compare confidence level,
 *  for a reader who has no other way to tell "these two works genuinely
 *  echo each other" from "everything resembles everything a little". */
const COMPARE_LEVEL_TEXT = {
  strong: 'The two works share passages of the same kind well above their '
        + 'general resemblance.',
  moderate: 'Some passages match in kind; read the top of the list with care.',
  low: 'Little beyond general resemblance; the pairs below are the closest '
     + 'the two come.',
};

/** One side of a comparison pair: author/title, the reference span, the
 *  gist, and a link into the Reader. Same fields Theme Search's own result
 *  rows use (`_result` in backend/passage_index.py supplies both). */
function CompareSideCard({ side }) {
  if (!side) return null;
  const span = side.ref_end && side.ref_end !== side.ref_start
    ? `${side.ref_start}–${side.ref_end}` : side.ref_start;
  return (
    <div className="min-w-0">
      <div className="text-[10px] uppercase tracking-wide text-gray-500">
        {LANG_LABEL[side.language] || side.language}
      </div>
      <div className="font-medium text-gray-900 text-sm">
        {side.display_name || side.work}
      </div>
      {side.reader_url && (
        <a href={side.reader_url} target="_blank" rel="noreferrer"
           className="text-sm text-red-800 hover:text-red-900 hover:underline">
          {span} · Open in Reader
        </a>
      )}
      {side.gist && (
        <p className="mt-0.5 text-sm text-gray-700 leading-snug">{side.gist}</p>
      )}
      {!!(side.themes || []).length && (
        <div className="mt-1 flex flex-wrap gap-1">
          {side.themes.slice(0, 5).map((t) => (
            <span key={t} className="text-[11px] bg-gray-100 text-gray-600 rounded px-1.5 py-0.5">
              {t}
            </span>
          ))}
        </div>
      )}
      {/* Licensed for indexing and search only (data/restricted_texts.json). */}
      {side.restricted && (
        <p className="mt-1 text-[10px] text-gray-400">{side.credit}</p>
      )}
    </div>
  );
}

/** A language select plus the same author/work pickers the classic Search
 *  page uses (TextSelector, fed by useCorpus) -- one language at a time
 *  because the corpus is organized by language, but any language pair is
 *  allowed since content matching does not need shared vocabulary. */
function CompareWorkPicker({ label, langChoices, language, setLanguage,
                              author, setAuthor, text, setText }) {
  const { authors, hierarchy, loading, getTextsForAuthor } = useCorpus(language);
  return (
    <div className="border border-gray-200 rounded p-3 bg-white space-y-3">
      <h3 className="text-base font-semibold text-gray-900">{label}</h3>
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">
          Language
        </label>
        <select
          aria-label={`${label} language`}
          value={language}
          onChange={(e) => { setLanguage(e.target.value); setAuthor(''); setText(''); }}
          className="w-full border rounded px-2 py-2 text-base sm:text-sm"
        >
          {langChoices.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
        </select>
      </div>
      {loading ? (
        <p className="text-xs text-gray-500">Loading texts…</p>
      ) : (
        <TextSelector
          label={label}
          plainFieldLabels
          language={language}
          authors={authors}
          selectedAuthor={author}
          setSelectedAuthor={setAuthor}
          selectedText={text}
          setSelectedText={setText}
          hierarchy={hierarchy}
          fetchTexts={getTextsForAuthor}
        />
      )}
    </div>
  );
}

function csvCell(v) {
  const s = String(v ?? '');
  return /[",\r\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

/** The pairs table as a downloadable CSV. Built client-side straight from
 *  the response already on screen: there is no compare-specific export
 *  route the way Theme Search's own results have one (ThemeExport, backed
 *  by /api/passages/export), and one work's worth of pairs is small enough
 *  that a server round trip buys nothing. */
function downloadComparePairsCsv(data) {
  const rows = [[
    'score', 'strong',
    'work_a', 'title_a', 'ref_start_a', 'ref_end_a', 'gist_a',
    'work_b', 'title_b', 'ref_start_b', 'ref_end_b', 'gist_b',
  ]];
  for (const p of data.pairs || []) {
    rows.push([
      p.score, p.strong ? 'yes' : 'no',
      p.a?.work, p.a?.display_name || p.a?.title || '', p.a?.ref_start, p.a?.ref_end, p.a?.gist || '',
      p.b?.work, p.b?.display_name || p.b?.title || '', p.b?.ref_start, p.b?.ref_end, p.b?.gist || '',
    ]);
  }
  // A BOM, same reason ThemeExport's CSV carries one: without it Excel turns
  // Greek, Coptic and Persian text into mojibake.
  const csv = '﻿' + rows.map((r) => r.map(csvCell).join(',')).join('\r\n');
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `theme-comparison-${data.work_a?.work || 'a'}-vs-${data.work_b?.work || 'b'}.csv`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

/** The "in this author or work" restriction as request parameters. A chosen
 *  work wins over its author: `works=` names it exactly, `author=` means every
 *  work of that author. Empty when nothing is chosen, so the default request
 *  is byte for byte what it was before the restriction existed. */
export function scopeQuery(scope) {
  if (scope && scope.work) return `&works=${encodeURIComponent(scope.work)}`;
  if (scope && scope.author) return `&author=${encodeURIComponent(scope.author)}`;
  return '';
}

export default function ThemeSearchPage() {
  const [query, setQuery] = useState('');
  // Coins: an option of its own, shown only when the Coins collection is on.
  // It searches the coin descriptions and shows them as a separate list; it is
  // never mixed into the passage ranking.
  const { anyOn } = useCollections();
  const coinsAvailable = anyOn(PAGE_NEEDS.coins);
  const [coinsChosen, setCoinsChosen] = useState(false);
  const [coinsSearch, setCoinsSearch] = useState(null);
  const coinsMode = coinsAvailable && coinsChosen;
  // Objects (museum catalogue descriptions): the same kind of option, beside
  // Coins. One catalogue is searched at a time, each as its own list.
  const objectsAvailable = anyOn(PAGE_NEEDS.objects);
  const [objectsChosen, setObjectsChosen] = useState(false);
  const [objectsSearch, setObjectsSearch] = useState(null);
  const objectsMode = objectsAvailable && objectsChosen;
  const catalogueMode = coinsMode || objectsMode;
  // Read synchronously (a lazy initializer, not an effect) so that on the
  // very first render -- before any effect has run -- `language` already
  // reflects a shared link's languages= param. Without this, the aggregate
  // coverage fetch below (which only runs when the picker ISN'T on a single
  // covered language) would see the pre-deep-link '' for one extra render
  // and fetch coverage for all four languages even when the link was
  // headed straight for one of them.
  const [language, setLanguage] = useState(() => {
    const p = new URLSearchParams(window.location.search);
    // The language carries over whether or not a query does: Browse Corpus's
    // "Theme Search" badge links here with languages= alone (2026-10-03),
    // and the "arriving from a link with the search already in it" effect
    // below runs the query, when there is one, in this same language.
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
  // The languages Theme Search covers are whatever this server actually
  // serves (`served`, fetched above from /api/languages), not a fixed list.
  // This used to be hard-coded to ['la', 'grc', 'en', 'cop'], written when
  // that was the whole corpus; it went stale the moment Hebrew, Persian and
  // Urdu were indexed too; and it drove the one line on this page that said
  // so, which kept telling a Persian or Hebrew reader their language wasn't
  // covered at all. Falls back to the original four only for the brief
  // window before /api/languages has answered.
  const BROWSE_CORPUS_LANGUAGES = served && served.length ? served : ['la', 'grc', 'en', 'cop'];
  // Which of the three coverage-line states applies: one covered language
  // picked alone keeps the per-language sentence; one uncovered language
  // (anything this server doesn't serve) alone gets the fixed sentence;
  // "All languages" (nothing picked) or several picked together get the
  // summed sentence. Computed here (not just above the JSX) because the
  // aggregate fetch below needs it too.
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
  // Keyed on which language LIST this was last fetched for, not a plain
  // once-ever ref: BROWSE_CORPUS_LANGUAGES starts as the four-language
  // fallback (before /api/languages has answered) and then becomes
  // whatever this server actually serves. A once-ever guard would lock in
  // on that first, stale fetch and never redo it once `served` arrives,
  // which is exactly backwards for the thing this effect exists to keep
  // current.
  const allCoverageFor = useRef(null);
  useEffect(() => {
    if (singleCoveredLang) return;
    const key = BROWSE_CORPUS_LANGUAGES.join(',');
    if (allCoverageFor.current === key) return;
    allCoverageFor.current = key;
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
    }).catch(() => { allCoverageFor.current = null; });
    return () => { dead = true; };
  }, [singleCoveredLang, served]);

  // "Search within": restrict the search to one author or one work. Read from
  // the address so a shared link carries it. Empty strings mean the whole corpus.
  const [scopeAuthor, setScopeAuthor] = useState(() => {
    const p = new URLSearchParams(window.location.search);
    const w = (p.get('works') || '').split(',')[0].trim();
    return (p.get('author') || '').trim().toLowerCase() || (w ? w.split('.')[0].toLowerCase() : '');
  });
  const [scopeWork, setScopeWork] = useState(() => {
    const p = new URLSearchParams(window.location.search);
    return (p.get('works') || '').split(',')[0].trim();
  });
  const [scopeOpen, setScopeOpen] = useState(() => Boolean(scopeAuthor || scopeWork));
  // Works that have passage windows in the chosen languages, with the author
  // and title labels the pickers show. Loaded the first time the section is
  // opened, because it takes one catalogue call and one coverage call per
  // language and most searches never need it.
  const [scopeWorks, setScopeWorks] = useState(null);
  useEffect(() => {
    if (!scopeOpen) return undefined;
    const codes = selectedLangCodes.length ? selectedLangCodes : BROWSE_CORPUS_LANGUAGES;
    let dead = false;
    Promise.all(codes.map((code) => (
      fetch(`/api/texts?language=${code}`).then((r) => r.json()).catch(() => []).then((texts) => {
        const arr = Array.isArray(texts) ? texts : [];
        return fetchCoveredWorks(code, arr.length > 0).then((covered) => {
          const have = new Set(covered || []);
          return arr.filter((t) => have.has(baseWorkId(t.id)));
        });
      })
    ))).then((lists) => {
      if (dead) return;
      const byId = new Map();
      lists.flat().forEach((t) => {
        const id = baseWorkId(t.id);
        if (!byId.has(id)) {
          byId.set(id, { id, authorKey: id.split('.')[0].toLowerCase(),
                         author: t.author || id.split('.')[0], title: t.title || t.work || id });
        }
      });
      setScopeWorks([...byId.values()]);
    }).catch(() => { if (!dead) setScopeWorks([]); });
    return () => { dead = true; };
  }, [scopeOpen, language, served]);
  const scopeAuthors = (() => {
    const m = new Map();
    (scopeWorks || []).forEach((w) => { if (!m.has(w.authorKey)) m.set(w.authorKey, w.author); });
    return [...m.entries()].map(([value, label]) => ({ value, label }))
      .sort((a, b) => a.label.localeCompare(b.label));
  })();
  const scopeWorkOptions = (scopeWorks || []).filter((w) => w.authorKey === scopeAuthor)
    .map((w) => ({ value: w.id, label: w.title })).sort((a, b) => a.label.localeCompare(b.label));
  const scopeLabel = (() => {
    const w = (scopeWorks || []).find((x) => x.id === scopeWork);
    if (scopeWork) return w ? `${w.author}, ${w.title}` : scopeWork;
    if (!scopeAuthor) return '';
    const a = scopeAuthors.find((x) => x.value === scopeAuthor);
    return a ? a.label : scopeAuthor;
  })();

  const [data, setData] = useState(null);
  const [running, setRunning] = useState(false);
  const [showWeak, setShowWeak] = useState(false);
  const [error, setError] = useState(null);

  // How deep the ranked list goes. 25 at first; Show more steps it up to the
  // API's cap of 100. Hunting Genesis 22 once reached the bottom of the 25,
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

  const run = useCallback(async (q, lang, depth, scopeOverride) => {
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
    const scope = scopeOverride || { author: scopeAuthor, work: scopeWork };
    try {
      const res = await fetch(
        `/api/passages/theme-search?query=${encodeURIComponent(text)}&limit=${wanted}`
        + (langParam ? `&languages=${encodeURIComponent(langParam)}` : '')
        + scopeQuery(scope));
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
        if (scope.work) p.set('works', scope.work);
        else if (scope.author) p.set('author', scope.author);
        window.history.replaceState({}, '', `/theme-search?${p.toString()}`);
      }
    } catch (e) {
      setError(e.message || 'the search could not be run');
    } finally {
      setRunning(false);
      setLoadingMore(false);
    }
  }, [running, loadingMore, data, language, scopeAuthor, scopeWork]);

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
        + (language ? `&languages=${encodeURIComponent(language)}` : '')
        + scopeQuery({ author: scopeAuthor, work: scopeWork }));
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
  }, [data, running, loadingMore, pastCap, language, query, scopeAuthor, scopeWork]);

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
  // ConnectionsMap.jsx); 'compare' reads two whole works, or two books,
  // against each other (backend/passage_index.py compare_works). Read from
  // the URL so a link to /theme-search?tab=map, or one carrying
  // compare=<id>&with=<id>, lands there directly.
  const [tab, setTab] = useState(() => {
    const p = new URLSearchParams(window.location.search);
    if (p.get('tab') === 'map') return 'map';
    if ((p.get('compare') || '').trim() && (p.get('with') || '').trim()) return 'compare';
    return p.get('tab') === 'compare' ? 'compare' : 'search';
  });
  const setTabAndUrl = (t) => {
    setTab(t);
    const p = new URLSearchParams(window.location.search);
    if (t === 'map' || t === 'compare') p.set('tab', t); else p.delete('tab');
    if (t !== 'compare') { p.delete('compare'); p.delete('with'); }
    window.history.replaceState({}, '', `/theme-search${p.toString() ? `?${p}` : ''}`);
  };

  // Compare Two Works: pick a language, author and work on each side (the
  // same TextSelector/useCorpus pair the classic Search page's Source/Target
  // pickers use), run the comparison, and show the best-matching passage
  // pairs with the confidence block the route reports.
  const compareLangChoices = LANG_CHOICE_ORDER
    .filter((c) => !served || served.includes(c) || INDEX_ONLY.includes(c))
    .map((c) => [c, LANG_LABEL[c] || c]);
  const [cmpLangA, setCmpLangA] = useState('la');
  const [cmpAuthorA, setCmpAuthorA] = useState('');
  const [cmpTextA, setCmpTextA] = useState('');
  const [cmpLangB, setCmpLangB] = useState('la');
  const [cmpAuthorB, setCmpAuthorB] = useState('');
  const [cmpTextB, setCmpTextB] = useState('');
  const [cmpData, setCmpData] = useState(null);
  const [cmpRunning, setCmpRunning] = useState(false);
  const [cmpError, setCmpError] = useState(null);
  // Shared wording inside each pair: joins the theme comparison against
  // whatever word-level (fusion) comparison of the same two works is already
  // cached, see backend/blueprints/passages.py _attach_phrase_parallels. On
  // by default since the join costs nothing when nothing is cached (one
  // lookup per distinct book pair, not a fresh search).
  const [showPhrases, setShowPhrases] = useState(true);

  const runCompare = useCallback(async (workA, workB) => {
    const a = (workA || '').trim();
    const b = (workB || '').trim();
    if (!a || !b || cmpRunning) return;
    setCmpRunning(true);
    setCmpError(null);
    setCmpData(null);
    try {
      const params = new URLSearchParams({ work_a: a, work_b: b });
      if (showPhrases) params.set('with_phrases', '1');
      const res = await fetch(`/api/passages/compare?${params.toString()}`);
      const json = await res.json();
      if (json.error) setCmpError(json.error);
      else {
        setCmpData(json);
        const p = new URLSearchParams({ compare: a, with: b, tab: 'compare' });
        window.history.replaceState({}, '', `/theme-search?${p.toString()}`);
      }
    } catch (e) {
      setCmpError(e.message || 'the comparison could not be run');
    } finally {
      setCmpRunning(false);
    }
  }, [cmpRunning, showPhrases]);

  // Arriving from a link that already names both works (Tessa, a bookmark, a
  // colleague): run the comparison rather than making the reader repick both
  // sides in the pickers, which the ids alone don't populate.
  const ranCompareFromUrl = useRef(false);
  useEffect(() => {
    if (ranCompareFromUrl.current) return;
    ranCompareFromUrl.current = true;
    const p = new URLSearchParams(window.location.search);
    const a = (p.get('compare') || '').trim();
    const b = (p.get('with') || '').trim();
    if (!a || !b) return;
    runCompare(a, b);
  }, [runCompare]);

  return (
    <div className="max-w-4xl mx-auto p-6">
      <h1 className="text-2xl font-semibold text-gray-900">Theme Search</h1>
      <span className="ml-2 align-middle rounded border border-amber-200 bg-amber-50 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-amber-800">
        Beta
      </span>

      <ScopeBox id="theme" className="mt-3" />

      <div className="mt-4 inline-flex rounded border border-gray-300 overflow-hidden text-sm">
        {[['search', 'Theme Search'], ['map', 'Similarity Map'], ['compare', 'Compare two works']].map(([v, label]) => (
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
      ) : tab === 'compare' ? (
        <div className="mt-4">
          <p className="text-sm text-gray-600 leading-relaxed">
            Pick two works, or two books, and see which passages match each other
            in content. This works across languages: the two sides need not
            share a single word to be found alike.
          </p>

          <div className="mt-4 grid grid-cols-1 sm:grid-cols-2 gap-4">
            <CompareWorkPicker
              label="First work" langChoices={compareLangChoices}
              language={cmpLangA} setLanguage={setCmpLangA}
              author={cmpAuthorA} setAuthor={setCmpAuthorA}
              text={cmpTextA} setText={setCmpTextA}
            />
            <CompareWorkPicker
              label="Second work" langChoices={compareLangChoices}
              language={cmpLangB} setLanguage={setCmpLangB}
              author={cmpAuthorB} setAuthor={setCmpAuthorB}
              text={cmpTextB} setText={setCmpTextB}
            />
          </div>

          <label className="mt-4 flex items-center gap-2 text-sm text-gray-700">
            <input
              type="checkbox"
              checked={showPhrases}
              onChange={(e) => setShowPhrases(e.target.checked)}
              className="rounded border-gray-300"
            />
            Show shared wording inside pairs
          </label>

          <button
            onClick={() => runCompare(cmpTextA, cmpTextB)}
            disabled={cmpRunning || !cmpTextA || !cmpTextB}
            className="mt-3 px-4 py-2 rounded bg-red-700 text-white text-sm font-medium hover:bg-red-800 disabled:opacity-40"
          >
            {cmpRunning ? 'Comparing…' : 'Compare'}
          </button>

          {/* The full comparison of two whole poems can take up to about
              twelve seconds the first time (a matrix of every window of one
              against every window of the other). The N-against-N phrasing
              only becomes available once the response lands -- at which
              point this spinner is already gone and the counts line below
              shows it -- so the plain form is what shows while waiting. */}
          {cmpRunning && (
            <p className="mt-4 flex items-center gap-2 text-sm text-gray-500 italic">
              <span className="w-4 h-4 border-2 border-gray-200 border-t-red-700 rounded-full animate-spin" />
              Comparing…
            </p>
          )}

          {cmpError && (
            <div className="mt-4 rounded border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">
              {cmpError}
            </div>
          )}

          {cmpData && !cmpRunning && (
            <div className="mt-6">
              {cmpData.confidence?.level && (
                <div className={`rounded border px-3 py-2 text-sm ${
                  (BAND[cmpData.confidence.level] || BAND.unrated).className}`}>
                  <strong className="font-semibold">
                    {(BAND[cmpData.confidence.level] || BAND.unrated).label}.
                  </strong>{' '}
                  {COMPARE_LEVEL_TEXT[cmpData.confidence.level]
                    || 'The corpus holds passages of this kind.'}
                </div>
              )}

              <p className="mt-2 text-xs text-gray-500">
                {cmpData.n_a} windows of {cmpData.work_a?.display_name || cmpData.work_a?.work}{' '}
                against {cmpData.n_b} windows of{' '}
                {cmpData.work_b?.display_name || cmpData.work_b?.work}.
              </p>

              {cmpData.phrases && cmpData.phrases.available === false && (
                <p className="mt-2 text-xs text-gray-500">
                  No word-level comparison of these two works is cached yet.{' '}
                  <a href={cmpData.phrases.run_url}
                     className="text-red-800 hover:text-red-900 hover:underline">
                    Run the word-level comparison of these two works
                  </a>
                </p>
              )}

              {!!(cmpData.pairs || []).length && (
                <div className="mt-3">
                  <button
                    onClick={() => downloadComparePairsCsv(cmpData)}
                    className="text-xs font-semibold text-gray-700 border border-gray-300 bg-white
                               rounded px-3 py-1.5 hover:bg-gray-50"
                  >
                    Download CSV
                  </button>
                </div>
              )}

              {!(cmpData.pairs || []).length && (
                <p className="mt-4 text-sm text-gray-600">
                  No matching passage pairs came back for these two works.
                </p>
              )}

              <ul className="mt-4 space-y-3">
                {(cmpData.pairs || []).map((pair, i) => (
                  <li key={`${pair.a?.id || i}-${pair.b?.id || i}`}
                      className="border border-gray-200 rounded p-3 bg-white">
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-xs text-gray-500">score {pair.score?.toFixed?.(3) ?? pair.score}</span>
                      {pair.strong && (
                        <span className="text-[10px] bg-red-50 text-red-800 border border-red-200 rounded px-1.5 py-0.5 font-medium">
                          strong
                        </span>
                      )}
                    </div>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                      <CompareSideCard side={pair.a} />
                      <CompareSideCard side={pair.b} />
                    </div>
                    {!!(pair.phrases || []).length && (
                      <div className="mt-3 pt-3 border-t border-gray-100">
                        <div className="text-[11px] font-semibold uppercase tracking-wide text-gray-500 mb-1">
                          Shared wording inside this pair
                        </div>
                        <ul className="space-y-1">
                          {pair.phrases.map((ph, j) => (
                            <li key={j} className="text-xs text-gray-700">
                              <span className="text-gray-500">{ph.source_ref}</span>
                              {' · '}
                              <span className="text-gray-500">{ph.target_ref}</span>
                              {' — '}
                              <span className="font-semibold text-gray-900">
                                {(ph.matched_words || []).map((w) => (
                                  typeof w === 'object' ? (w.lemma || w.word || w.display || '') : w
                                )).filter(Boolean).join(', ')}
                              </span>
                              {typeof ph.score === 'number' && (
                                <span className="text-gray-400"> (score {ph.score.toFixed(2)})</span>
                              )}
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </li>
                ))}
              </ul>

              <p className="mt-5 text-xs text-gray-500 leading-relaxed">
                These summaries are written by a language model from the passage
                itself, so treat them as a finding aid rather than as evidence.
                Read the passage before citing it.
              </p>
            </div>
          )}
        </div>
      ) : (
      <>
      <p className="mt-2 text-sm text-gray-600 leading-relaxed">
        Describe what happens in a passage and this finds passages that match the
        description.
      </p>

      <form
        className="mt-5 flex gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          if (coinsMode) setCoinsSearch({ q: query.trim(), n: (coinsSearch?.n || 0) + 1 });
          else if (objectsMode) setObjectsSearch({ q: query.trim(), n: (objectsSearch?.n || 0) + 1 });
          else run(query);
        }}
      >
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="a warrior arms himself before battle"
          className="flex-1 border border-gray-300 rounded px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-red-600"
        />
        <button
          type="submit"
          disabled={(!catalogueMode && running) || !query.trim()}
          className="px-4 py-2 rounded bg-red-700 text-white text-sm font-medium hover:bg-red-800 disabled:opacity-40"
        >
          {!catalogueMode && running ? 'Searching…' : 'Search'}
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
      <div className={`mt-3 flex flex-wrap items-center gap-2 ${catalogueMode ? 'opacity-40 pointer-events-none' : ''}`}>
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
            // pressed Search (2026-09-06).
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

      {coinsAvailable && (
        <div className="mt-2 flex flex-wrap items-center gap-2">
          <label className={`text-xs px-2 py-0.5 rounded border cursor-pointer select-none ${coinsMode ? 'bg-red-600 text-white border-red-600' : 'bg-white text-gray-700 border-gray-300 hover:bg-gray-50'}`}>
            <input type="checkbox" className="sr-only" checked={coinsMode}
                   onChange={() => { setCoinsChosen((v) => !v); setObjectsChosen(false); }} />
            Coins
          </label>
          <span className="text-[11px] text-gray-500">
            {coinsMode
              ? 'Searching coin descriptions only, as a separate list. The languages above are not used.'
              : 'Search the coin catalogue instead of the passages (a separate list).'}
          </span>
        </div>
      )}

      {objectsAvailable && (
        <div className="mt-2 flex flex-wrap items-center gap-2">
          <label className={`text-xs px-2 py-0.5 rounded border cursor-pointer select-none ${objectsMode ? 'bg-red-600 text-white border-red-600' : 'bg-white text-gray-700 border-gray-300 hover:bg-gray-50'}`}>
            <input type="checkbox" className="sr-only" checked={objectsMode}
                   onChange={() => { setObjectsChosen((v) => !v); setCoinsChosen(false); }} />
            Objects
          </label>
          <span className="text-[11px] text-gray-500">
            {objectsMode
              ? 'Searching museum object descriptions only, as a separate list. The languages above are not used.'
              : 'Search the museum object descriptions instead of the passages (a separate list).'}
          </span>
        </div>
      )}

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

      {/* Search within one author or work. Off by default: the page behaves
          exactly as before until a name is chosen. */}
      <div className="mt-3">
        {!scopeOpen ? (
          <button
            type="button"
            onClick={() => setScopeOpen(true)}
            className="text-xs text-red-700 hover:underline"
          >
            Narrow to one author or work
          </button>
        ) : (
          <div className="rounded border border-gray-200 bg-white p-3">
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium text-gray-700">Search within</span>
              <button
                type="button"
                onClick={() => {
                  setScopeAuthor(''); setScopeWork(''); setScopeOpen(false);
                  if (data && query.trim()) run(query, undefined, undefined, { author: '', work: '' });
                }}
                className="text-xs text-red-700 hover:underline"
              >
                Clear: search the whole corpus
              </button>
            </div>
            {scopeWorks === null ? (
              <p className="mt-2 text-xs text-gray-500">Loading authors…</p>
            ) : (
              <div className="mt-2 grid grid-cols-1 sm:grid-cols-2 gap-2">
                <SearchableSelect
                  ariaLabel="Search within author"
                  value={scopeAuthor}
                  placeholder="Author: whole corpus"
                  options={[{ value: '', label: 'Whole corpus' }, ...scopeAuthors]}
                  onChange={(v) => {
                    setScopeAuthor(v); setScopeWork('');
                    if (data && query.trim()) run(query, undefined, undefined, { author: v, work: '' });
                  }}
                />
                <SearchableSelect
                  ariaLabel="Search within work"
                  value={scopeWork}
                  disabled={!scopeAuthor}
                  placeholder="Work: all of this author"
                  options={[{ value: '', label: 'All works of this author' }, ...scopeWorkOptions]}
                  onChange={(v) => {
                    setScopeWork(v);
                    if (data && query.trim()) run(query, undefined, undefined, { author: scopeAuthor, work: v });
                  }}
                />
              </div>
            )}
          </div>
        )}
      </div>

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

      {!catalogueMode && running && (
        <p className="mt-6 text-sm text-gray-500 italic">
          Comparing your description against every indexed passage…
        </p>
      )}

      {coinsMode && <ThemeCoins search={coinsSearch} />}
      {objectsMode && <ThemeObjects search={objectsSearch} />}

      {!catalogueMode && error && (
        <div className="mt-6 rounded border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">
          {error}
        </div>
      )}

      {!catalogueMode && data && (
        <div className="mt-6">
          {band && (
            <div className={`rounded border px-3 py-2 text-sm ${band.className}`}>
              <strong className="font-semibold">{band.label}.</strong>{' '}
              {data.note || 'The corpus holds passages of this kind.'}
            </div>
          )}

          {data.restricted && (
            <div className="rounded border border-gray-200 bg-gray-50 px-3 py-2 text-sm text-gray-700">
              {scopeLabel && <strong className="font-semibold">In {scopeLabel}.</strong>}{' '}
              {data.note}
            </div>
          )}

          {!data.results?.length && !data.restricted && (
            <p className="mt-4 text-sm text-gray-600">
              Nothing in the corpus resembles that description.
            </p>
          )}

          {!data.results?.length && data.restricted && (
            <p className="mt-4 text-sm text-gray-600">
              Nothing in the chosen {scopeWork ? 'work' : 'author'} resembles that description.
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
                        // No year, but the table may still give an era: the
                        // Hebrew Bible is deliberately left without a year
                        // (composition spans centuries) and carries the era
                        // "Biblical". Show that rather than "undated"
                        // (2026-09-20: these texts were otherwise showing as
                        // undated).
                        return (
                          <span className="inline-block rounded bg-gray-50 border border-gray-200 px-2 py-0.5 text-sm text-gray-500">
                            {head.era || 'undated'}
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
