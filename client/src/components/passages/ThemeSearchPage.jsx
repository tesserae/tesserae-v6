import { useCallback, useEffect, useRef, useState } from 'react';

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

const EXAMPLES = [
  'a warrior arms himself before battle, piece by piece',
  'a city falls and its people are led away captive',
  'a descent into the world of the dead to consult a shade',
  'a storm at sea scatters a fleet and the crew despairs',
];

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

/** Oldest first. A content search crosses centuries, so the order in which the
 *  results are read is itself information: seeing a Homeric scene, then its
 *  Hellenistic reworking, then a Latin one, is the point.
 *
 *  Undated works (Persian and Urdu authors are not in the dates table) go last
 *  rather than being guessed at or dropped.
 */
function chronological(results) {
  return [...(results || [])].sort((a, b) => {
    const ay = typeof a.year === 'number' ? a.year : null;
    const by = typeof b.year === 'number' ? b.year : null;
    if (ay === null && by === null) return (b.score || 0) - (a.score || 0);
    if (ay === null) return 1;
    if (by === null) return -1;
    if (ay !== by) return ay - by;
    return (b.score || 0) - (a.score || 0);
  });
}

/** Split a date note into the date itself, what kind of date it is, and the
 *  scholarly caveat that often trails behind it.
 *
 *  The whole note used to be set as one small grey string, so the eye hit "d."
 *  before the year in a column whose entire job is to be scanned by year. The
 *  date now leads and the qualifier follows, spelled out: "c. 1020 CE (died)".
 *
 *  WHY THE REMAINDER IS SEPARATED TOO
 *
 *  103 of the 474 notes run past a bare date -- "fl. c. 55 CE (date contested;
 *  some scholars place in 3rd c.)", "d. c. 215 CE (c. 150-215), Clement of
 *  Alexandria" -- and the chip is one nowrap line in an 8rem column, so those
 *  ran straight across the work title. Truncating them would throw away real
 *  scholarly hedging. So the chip takes the date proper and the rest is set
 *  below it, where it wraps.
 *
 *  Notes whose date is not at the front ("Greek philosopher (d. 322 BCE);
 *  Latin translations primarily 12th-13th c.") fall back to the structured
 *  `year`, with the whole note beneath. Seven entries have neither, and they
 *  are genuinely undated.
 */
const QUALIFIER = [
  [/^d\.\s*/i, 'died'],
  [/^fl\.\s*/i, 'flourished'],
  [/^b\.\s*/i, 'born'],
  [/^r\.\s*/i, 'reigned'],
  [/^comp\.\s*/i, 'composed'],
  [/^composed\s+/i, 'composed'],
  [/^revealed\s+/i, 'revealed'],
  [/^active\s+/i, 'active'],
];

// A date at the front of what is left: "322 BCE", "c. 1020 CE", "c. 150-215".
const DATE_CORE = /^(?:c\.\s*)?\d{1,4}(?:\s*[-–]\s*(?:c\.\s*)?\d{1,4})?(?:\s*(?:BCE|CE|BC|AD))?/i;

function yearLabel(year) {
  return year < 0 ? `${Math.abs(year)} BCE` : `${year} CE`;
}

/** Trim the punctuation a remainder is left holding when the date is cut off.
 *
 *  Cutting "d. c. 215 CE (c. 150-215), Clement of Alexandria" after the date
 *  leaves the opening bracket behind and the closing one orphaned, so unmatched
 *  brackets are dropped from either end rather than just the leading one.
 */
function tidy(s) {
  let out = s.replace(/^[\s,;:.–-]+/, '').replace(/[\s,;:]+$/, '').trim();
  while (out.startsWith('(') && !out.includes(')')) out = out.slice(1).trim();
  while (out.endsWith(')') && !out.slice(0, -1).includes('(')) out = out.slice(0, -1).trim();
  if (out.startsWith('(') && out.endsWith(')') && out.indexOf('(', 1) === -1) {
    out = out.slice(1, -1).trim();
  }
  return out.replace(/^[\s,;:.–-]+/, '').trim();
}

function dateParts(r) {
  const note = (r.date_note || '').trim();
  const hasYear = typeof r.year === 'number';
  if (note) {
    let kind = null;
    let rest = note;
    for (const [re, word] of QUALIFIER) {
      if (re.test(rest)) { kind = word; rest = rest.replace(re, '').trim(); break; }
    }
    const m = rest.match(DATE_CORE);
    if (m && m[0].trim()) {
      return { date: m[0].trim(), kind, about: tidy(rest.slice(m[0].length)) || null };
    }
    // The note is prose. Keep the structured year in the chip and the prose below.
    if (hasYear) return { date: yearLabel(r.year), kind: null, about: note };
    return null;
  }
  if (!hasYear) return null;
  return { date: yearLabel(r.year), kind: null, about: null };
}

function dateLabel(r) {
  const p = dateParts(r);
  return p ? p.date : null;
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
  en: 'English', fa: 'Persian', ur: 'Urdu',
};

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
];

export default function ThemeSearchPage() {
  const [query, setQuery] = useState('');
  const [language, setLanguage] = useState('');
  const [data, setData] = useState(null);
  const [running, setRunning] = useState(false);
  const [showWeak, setShowWeak] = useState(false);
  const [error, setError] = useState(null);

  const run = useCallback(async (q, lang) => {
    const text = (q || '').trim();
    if (!text || running) return;
    setRunning(true);
    setError(null);
    setData(null);
    setShowWeak(false);
    const langParam = lang === undefined ? language : lang;
    try {
      const res = await fetch(
        `/api/passages/theme-search?query=${encodeURIComponent(text)}&limit=25`
        + (langParam ? `&languages=${encodeURIComponent(langParam)}` : ''));
      const json = await res.json();
      // The API reports trouble in the body rather than by status, so that a
      // missing index degrades this panel instead of breaking the page.
      if (json.error) setError(json.error);
      else setData(json);
    } catch (e) {
      setError(e.message || 'the search could not be run');
    } finally {
      setRunning(false);
    }
  }, [running, language]);

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
    const lang = (p.get('languages') || '').split(',')[0].trim();
    setQuery(q);
    if (lang) setLanguage(lang);
    run(q, lang || '');
  }, [run]);

  const band = data && BAND[data.confidence?.level];

  return (
    <div className="max-w-4xl mx-auto p-6">
      <h1 className="text-2xl font-semibold text-gray-900">Theme Search</h1>
      <span className="ml-2 align-middle rounded border border-amber-200 bg-amber-50 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-amber-800">
        Beta
      </span>
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
        <label className="text-xs text-gray-600" htmlFor="theme-language">
          Search in
        </label>
        <select
          id="theme-language"
          value={language}
          onChange={(e) => {
            const next = e.target.value;
            setLanguage(next);
            if (query.trim()) run(query, next);
          }}
          className="text-xs border border-gray-300 rounded px-2 py-1 bg-white focus:outline-none focus:ring-1 focus:ring-red-600"
        >
          {LANG_CHOICES.map(([v, label]) => (
            <option key={v || 'all'} value={v}>{label}</option>
          ))}
        </select>
        <span className="text-[11px] text-gray-500">
          one language at a time shows more of it
        </span>
      </div>

      <div className="mt-3 flex flex-wrap gap-2">
        {EXAMPLES.map((ex) => (
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

          {(data.confidence?.level !== 'low' || showWeak) && (
          <p className="mt-4 mb-2 text-xs text-gray-500">
            Oldest first. Undated authors are listed last.
          </p>
          )}
          {(data.confidence?.level !== 'low' || showWeak) && (
          <ul className="space-y-3">
            {byWork(chronological(data.results)).map(({ key, head, items }) => (
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
                          <span className="inline-block rounded bg-gray-50 border border-gray-200 px-2 py-0.5 text-sm text-gray-400">
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
                            <div className="mt-0.5 text-[11px] text-gray-400 leading-tight">
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
                            weak neighbour
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
    </div>
  );
}
