import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import SearchProgress from '../common/SearchProgress';
import SearchableSelect from '../common/SearchableSelect';
import ScopeBox from '../common/ScopeBox';
import { useIsPhone } from '../../hooks/useIsPhone';
import { baseWorkId, fetchCoveredWorks } from '../../utils/passageCoverage';
import { readerLink } from '../passages/ThemeSearchPage';
import CiteRecordButton from '../common/CiteRecordButton';
import CiteAll from '../common/CiteAll';
import { recordFrom, toText, loadEditions, withEditionSync } from '../../utils/citations';
import { RECENT_SERVICES, RECENT_LABELS, joinNames, mergeRecent, recentUrl, fetchRecent } from '../../utils/recentArticles';
import OriginalScript from '../common/OriginalScript';
import TransliterationToggle from '../common/TransliterationToggle';
import { hasOriginalScript } from '../../utils/transliterate';
import { getView } from '../../collections/collectionsStore';
import useCollections from '../../hooks/useCollections';
import { viewById } from '../../collections/collectionsConfig';
import { getJson, postJsonTo } from '../../utils/api';
import { windowLocus, fullRef } from '../reader/refId';
import AboutSourcesLink from '../scholarship/AboutSourcesLink';

/**
 * Theme Search, one-text scope: pick one work, say a subject in plain words, and get the passages
 * of that work about it, listed by score, with a strip across the top that shows
 * where in the work they fall.
 *
 * The search is Theme Search restricted to one work (the same route with
 * `works=`). Passing the base work id covers a work held in books, because the
 * route collapses a book file onto its work, and a single work is returned as a
 * flat list that pages by offset with no per-work cap.
 *
 * Two facts about that route shape this page. A search within one work carries
 * a provisional confidence band when the route could fit one (`confidence.fitted`),
 * and marks a result strong only from it. Without a band the route marks nothing
 * strong, so the strip falls back to the score when no result is strong. And no
 * line counts are held anywhere the page can read, so the books of the strip
 * have equal widths.
 */

// Twenty-five a page: each card fetches its first lines, and fifty at once was a burst of
// fifty requests on the server for one search.
const PAGE = 25;
const LANGUAGES = [['la', 'Latin'], ['grc', 'Greek'], ['en', 'English'], ['he', 'Hebrew'],
  ['cop', 'Coptic'], ['fa', 'Persian'], ['ur', 'Urdu']];

// What is shown when the route reports no band for the search (a work too small to rate).
export const UNRATED_NOTE = 'Confidence is not rated for this search because the work has too few passages to compare a subject against. Read the passages before relying on them.';

const BANDS = {
  // The lowest level is a caution about the order, not a verdict on the work
  // (refit of 2026-10-12: right answers came first under it for Browning,
  // Ferdowsi and the Annals). The list is shown under every level.
  low: { label: 'Closest passages', className: 'bg-gray-100 text-gray-700 border-gray-300' },
  moderate: { label: 'Moderate match', className: 'bg-amber-50 text-amber-800 border-amber-200' },
  strong: { label: 'Strong match', className: 'bg-red-50 text-red-800 border-red-200' },
};

// A route note that says confidence is not rated carries no band label and no
// band color: a label such as "Strong match." would contradict the sentence.
const NEUTRAL_BAND = 'bg-gray-50 text-gray-700 border-gray-200';
const UNRATED_NOTE_START = /^\s*Confidence is not rated/i;

// A visit with no work chosen opens on the Aeneid, so the first sight of the
// page shows what it does (owner 2026-10-12).
export const DEFAULT_WORK = { lang: 'la', work: 'vergil.aeneid' };

/** The work the page opens on in the current view (Literature the Aeneid,
 *  History the Annals; see collectionsConfig askDefault). */
export function defaultWorkFor(view) {
  return viewById(view).askDefault || DEFAULT_WORK;
}

// Six example searches, one work each. The owner's rule, 2026-10-12: at most
// one from the Aeneid, a wide spread of authors, one woman among them, and
// nothing that is not a solid success. Rewritten 2026-10-19 on the owner's
// second rule ("they should describe a theme or a topic or something that
// might appear in more than one place"): each subject recurs through its
// work, and every one was run live that night and read. Sappho, the Aeneid,
// the Odyssey, Herodotus and the Annals rated strong with every answer on
// the subject, Thucydides moderate with every answer on it.
const EXAMPLES = [
  { lang: 'grc', work: 'sappho.fragments', q: 'a wedding song for the bride and the groom', label: 'wedding songs', on: 'Sappho' },
  { lang: 'la', work: 'vergil.aeneid', q: 'a mother mourns her dead son', label: 'a mother mourns her son', on: 'the Aeneid' },
  { lang: 'grc', work: 'homer.odyssey', q: 'a host welcomes a stranger with a meal and a bath', label: 'a host welcomes a stranger', on: 'the Odyssey' },
  { lang: 'grc', work: 'thucydides.peloponnesian_war', q: 'a besieged city surrenders', label: 'a besieged city surrenders', on: 'Thucydides' },
  { lang: 'grc', work: 'herodotus.histories', q: 'a dream warns a king', label: 'a dream warns a king', on: 'Herodotus' },
  { lang: 'la', work: 'tacitus.annales', q: 'an accused senator takes his own life before the verdict', label: 'an accused senator kills himself', on: 'the Annals' },
];

// The History view's six, rewritten the same night on the same rule and run
// live: Livy and Suetonius moderate with every answer on the subject, Caesar
// in the lowest band (the ethnographic digressions of books 1, 4 and 6 are
// all six answers, but nothing in a book of campaigns stands far above the
// rest), and the Annals, Herodotus and Thucydides shared with the Literature set.
const HISTORY_EXAMPLES = [
  { lang: 'la', work: 'livy.ab_urbe_condita', q: 'prodigies are reported and expiated', label: 'prodigies reported and expiated', on: 'Livy' },
  { lang: 'la', work: 'tacitus.annales', q: 'an accused senator takes his own life before the verdict', label: 'an accused senator kills himself', on: 'the Annals' },
  { lang: 'grc', work: 'herodotus.histories', q: 'a dream warns a king', label: 'a dream warns a king', on: 'Herodotus' },
  { lang: 'la', work: 'caesar.de_bello_gallico', q: 'the customs of the Gauls and the Germans', label: 'the customs of the Gauls and Germans', on: 'Caesar' },
  { lang: 'grc', work: 'thucydides.peloponnesian_war', q: 'a besieged city surrenders', label: 'a besieged city surrenders', on: 'Thucydides' },
  { lang: 'la', work: 'suetonius.de_vita_caesarum', q: 'omens foretell the death of the emperor', label: 'omens foretell an emperor\'s death', on: 'Suetonius' },
];

/** The example set of the current view. */
export function examplesFor(view) {
  return view === 'history' ? HISTORY_EXAMPLES : EXAMPLES;
}

/** The works of one language that have passage windows, one entry per work
 *  (a book file and its whole file collapse onto one id), with the books it is
 *  held in. */
function worksFrom(texts, covered) {
  const have = new Set(covered || []);
  const byId = new Map();
  (Array.isArray(texts) ? texts : []).forEach((t) => {
    const id = baseWorkId(t.id);
    if (!have.has(id)) return;
    if (!byId.has(id)) {
      byId.set(id, {
        id, authorKey: id.split('.')[0].toLowerCase(),
        author: t.author || id.split('.')[0], title: t.work || t.title || id, books: [],
      });
    }
    const w = byId.get(id);
    if (t.is_part && /^\d+$/.test(String(t.part_num))) w.books.push(Number(t.part_num));
  });
  return [...byId.values()];
}

/** The book a passage starts in, read from its reference: the first number of
 *  the trailing locus ("verg. aen. 6.268" gives 6, "thuc. pele. 2.1.1" gives 2).
 *  A reference with a single number has no book in it, and gives null. */
export function bookOf(ref, workId) {
  let s = String(ref || '').trim();
  if (workId && s.startsWith(`${workId}.`)) s = s.slice(workId.length + 1);
  const m = s.match(/(\d+(?:\.\d+)*)\s*$/);
  if (!m) return null;
  const nums = m[1].split('.');
  return nums.length >= 2 ? Number(nums[0]) : null;
}

function lineOf(ref) {
  const m = String(ref || '').match(/(\d+)\s*$/);
  return m ? Number(m[1]) : 0;
}

/** Where each result sits on the strip: its book (or the one segment of a work
 *  without books) and a fraction across that segment. Marks in one book are
 *  spread in line order, since no line counts are held to place them exactly. */
export function stripLayout(results, workId, workBooks) {
  const books = new Set(workBooks || []);
  const placed = results.map((r, i) => ({ i, book: bookOf(r.ref_start, workId), line: lineOf(r.ref_start) }));
  placed.forEach((p) => { if (p.book !== null) books.add(p.book); });
  // Without the catalogue's list of books, every book from 1 to the highest
  // seen is drawn, so a book with no passage still shows as a gap (the strip
  // once drew the Aeneid as eleven books because book 4 had no hit).
  if (!(workBooks || []).length && books.size) {
    const top = Math.max(...books);
    for (let b = 1; b <= top; b += 1) books.add(b);
  }
  const order = [...books].sort((a, b) => a - b);
  const segments = order.length ? order : [null];
  const groups = new Map(segments.map((b) => [b, []]));
  placed.forEach((p) => {
    const key = order.length ? p.book : null;
    (groups.get(key) || groups.get(segments[0])).push(p);
  });
  const marks = [];
  segments.forEach((b, segIndex) => {
    const g = groups.get(b).sort((x, y) => x.line - y.line || x.i - y.i);
    g.forEach((p, k) => {
      marks.push({ i: p.i, book: b, left: (segIndex + (k + 1) / (g.length + 1)) / segments.length });
    });
  });
  return { books: order, segments, marks };
}

/** What one segment of the strip is, read from the references: "frag." means
 *  fragments, "carm."/"epigr."/"ecl."/"od."/"sat." poems, "ep."/"epist." letters,
 *  otherwise books. Sappho's strip read "137 books" with the fragment numbers
 *  squeezed into columns a few pixels wide (owner, 2026-10-12). */
export function unitWord(results) {
  const ref = String((results && results[0] && results[0].ref_start) || '').toLowerCase();
  if (/\bfrag\.?/.test(ref)) return 'fragments';
  if (/\b(carm|epigr|ecl|od|sat|eleg|idyll|hymn)\.?\s/.test(ref)) return 'poems';
  if (/\b(ep|epist)\.?\s/.test(ref)) return 'letters';
  return 'books';
}

/** The same, before any result exists, from the work's id: "sappho.fragments",
 *  "catullus.carmina", "pliny.epistulae". Books when the title says nothing. */
export function unitForWork(workId) {
  const id = String(workId || '').toLowerCase();
  if (/fragment/.test(id)) return 'fragments';
  if (/(carmina|epigram|odes|eclog|satir|eleg|idyll|hymn|sonnet)/.test(id)) return 'poems';
  if (/(epistul|epistol|letters)/.test(id)) return 'letters';
  return 'books';
}

const NAME_STOP = new Set(['The', 'A', 'An', 'What', 'How', 'Why', 'Where', 'When', 'Who', 'Which', 'I']);

/** Capitalised words of a question that may be a name: not the first word, not in
 *  the stop list, a possessive 's removed, at most four. */
export function namesIn(question) {
  const words = String(question || '').trim().split(/\s+/);
  const out = [];
  words.slice(1).forEach((raw) => {
    const w = raw.replace(/^[^\p{L}]+|[^\p{L}]+$/gu, '').replace(/['\u2019]s$/, '');
    if (!w || !/^\p{Lu}/u.test(w) || NAME_STOP.has(w) || out.includes(w)) return;
    out.push(w);
  });
  return out.slice(0, 4);
}

/** "2-3" -> {from: 2, to: 3}, or null for anything else. */
function parseBooks(s) {
  const m = String(s || '').match(/^(\d+)-(\d+)$/);
  return m && Number(m[1]) <= Number(m[2]) ? { from: Number(m[1]), to: Number(m[2]) } : null;
}

function booksPhrase(s) {
  const b = parseBooks(s);
  if (!b) return '';
  return b.from === b.to ? `book ${b.from}` : `books ${b.from} to ${b.to}`;
}

/** The heading's text without the question: "Tacitus, Annals, books 1 to 6". */
function workLabel(w, workId, firstResult, books) {
  const base = w ? `${w.author}, ${w.title}`
    : (firstResult?.author ? `${firstResult.author}, ${(firstResult.title || '').replace(/, Book \d+$/, '')}` : workId);
  const bp = booksPhrase(books);
  return bp ? `${base}, ${bp}` : base;
}

/** The summary text with each cited reference made a link to its card. */
function SummaryText({ text, cites, onJump }) {
  const refs = [...new Set((cites || []).filter(Boolean))].sort((a, b) => b.length - a.length);
  if (!refs.length) return <OriginalScript text={text} />;
  const re = new RegExp(`(${refs.map((c) => c.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|')})`);
  return text.split(re).map((part, k) => (refs.includes(part) ? (
    <button key={k} type="button" onClick={() => onJump(part)}
            className="text-red-800 hover:text-red-900 hover:underline">{part}</button>
  ) : <OriginalScript key={k} text={part} />));
}

const RECENT_CAP_MS = 12000;
// The route reads at most this many passage ranges; the page sends the first page's.
const CITING_MAX = 25;
const CITING_SHOWN = 8;
const CITING_BADGE = { ejc: '1827 to 1922', muse: 'MUSE' };

/** The record an exported article becomes: title, authors, journal, year and link. */
export function citingRecord(it) {
  return recordFrom({
    title: it.title, authors: it.authors, year: it.year, venue: it.journal, url: it.url,
  }, 'index');
}

export { mergeRecent };

/** The scholarship paragraph with each [n] made a link to its note or article, in a new tab. */
function ScholarshipText({ text, cites }) {
  const byN = new Map((cites || []).map((c) => [String(c.n), c]));
  // A commentary note's edition comes from the sources list, fetched once
  // when a note is cited; the tooltips are redrawn when it arrives.
  const [, setLoaded] = useState(false);
  const hasNote = (cites || []).some((c) => c.kind === 'commentary');
  useEffect(() => {
    if (hasNote) loadEditions().then(() => setLoaded(true));
  }, [hasNote]);
  return String(text || '').split(/(\[\d+\])/).map((part, k) => {
    const m = /^\[(\d+)\]$/.exec(part);
    const c = m && byN.get(m[1]);
    if (!c) return <OriginalScript key={k} text={part} />;
    const tip = toText(withEditionSync(recordFrom(c, 'cite'))) || c.label;
    if (!c.link?.url) return <span key={k} title={tip}>{part}</span>;
    return (
      <a key={k} href={c.link.url} target="_blank" rel="noopener noreferrer" title={tip}
         className="text-red-800 hover:text-red-900 hover:underline">{part}</a>
    );
  });
}

function FirstLines({ r }) {
  const [lines, setLines] = useState(null);
  useEffect(() => {
    let dead = false;
    const p = new URLSearchParams({ work: r.work || '', ref_start: r.ref_start || '', ref_end: r.ref_end || r.ref_start || '' });
    getJson(`/api/passages/lines?${p.toString()}`)
      .then((d) => { if (!dead && Array.isArray(d.lines)) setLines(d.lines.slice(0, 3)); })
      .catch(() => {});
    return () => { dead = true; };
  }, [r.work, r.ref_start, r.ref_end]);
  if (!lines || !lines.length) return null;
  return (
    <div className="mt-1 text-sm text-gray-600 leading-snug border-l-2 border-gray-200 pl-2">
      {lines.map((l) => <div key={l.ref}>{l.text}</div>)}
    </div>
  );
}

export default function AskAWorkPage({ prefill = '', onQueryChange = null }) {
  const phone = useIsPhone();
  const initial = useMemo(() => {
    const p = new URLSearchParams(window.location.search);
    return { work: (p.get('work') || '').trim(), lang: (p.get('lang') || '').trim(), q: (p.get('q') || '').trim(), books: (p.get('books') || '').trim() };
  }, []);
  const viewDefault = defaultWorkFor(getView());
  const startWork = initial.work || viewDefault.work;
  const [lang, setLang] = useState(initial.work ? (initial.lang || 'la') : viewDefault.lang);
  const [author, setAuthor] = useState(startWork.split('.')[0].toLowerCase());
  const [work, setWork] = useState(startWork);
  const [q, setQ] = useState(initial.q || prefill);
  useEffect(() => { if (onQueryChange) onQueryChange(q); }, [q, onQueryChange]);
  const initialRange = useMemo(() => parseBooks(initial.books), [initial]);
  const [bookFrom, setBookFrom] = useState(initialRange ? initialRange.from : null);   // null = the first book
  const [bookTo, setBookTo] = useState(initialRange ? initialRange.to : null);         // null = the last book

  // Both views open on this page, so switching Literature and History keeps it
  // mounted and the old view's work stayed (2026-10-15: Vergil under History).
  // When no subject has been typed and the work is still the old view's
  // default, follow the new view's default.
  const { view } = useCollections();
  const prevView = useRef(view);
  useEffect(() => {
    if (view === prevView.current) return;
    const oldDefault = defaultWorkFor(prevView.current);
    prevView.current = view;
    if (q.trim() || work !== oldDefault.work) return;
    const d = defaultWorkFor(view);
    setLang(d.lang); setAuthor(d.work.split('.')[0].toLowerCase()); setWork(d.work);
    setBookFrom(null); setBookTo(null);
  }, [view, q, work]);
  // The author control follows the work. A work set by another path (a view
  // switch, an example, a link) must never sit under another author, which
  // showed as an author with an empty work box (the lead, 2026-10-18).
  useEffect(() => {
    if (work && author && !work.toLowerCase().startsWith(author.toLowerCase() + '.')) {
      setAuthor(work.split('.')[0].toLowerCase());
    }
  }, [work, author]);
  const [catalogue, setCatalogue] = useState({});   // language -> works, once loaded
  const loading = useRef({});

  const loadWorks = useCallback((code) => {
    if (loading.current[code]) return;
    loading.current[code] = true;
    getJson(`/api/texts?language=${code}`).catch(() => []).then((texts) => {
      const arr = Array.isArray(texts) ? texts : [];
      return fetchCoveredWorks(code, arr.length > 0).then((covered) => {
        setCatalogue((c) => ({ ...c, [code]: worksFrom(arr, covered) }));
      });
    }).catch(() => setCatalogue((c) => ({ ...c, [code]: [] })));
  }, []);
  useEffect(() => {
    [...new Set([lang, 'la', 'grc'])].forEach(loadWorks);
  }, [lang, loadWorks]);

  const catalogueRef = useRef(catalogue);
  catalogueRef.current = catalogue;
  const works = catalogue[lang];
  const chosen = useMemo(() => (works || []).find((w) => w.id === work), [works, work]);
  const bookList = useMemo(() => [...new Set(chosen?.books || [])].sort((a, b) => a - b), [chosen]);
  const hasBooks = bookList.length >= 2;
  const fromBook = hasBooks ? (bookFrom ?? bookList[0]) : null;
  const toBook = hasBooks ? (bookTo ?? bookList[bookList.length - 1]) : null;
  const narrowed = hasBooks && (fromBook > bookList[0] || toBook < bookList[bookList.length - 1]);
  const booksParam = narrowed ? `${fromBook}-${toBook}` : '';
  const authors = useMemo(() => {
    const m = new Map();
    (works || []).forEach((w) => { if (!m.has(w.authorKey)) m.set(w.authorKey, w.author); });
    return [...m.entries()].map(([value, label]) => ({ value, label })).sort((a, b) => a.label.localeCompare(b.label));
  }, [works]);
  const workOptions = useMemo(() => (works || []).filter((w) => w.authorKey === author)
    .map((w) => ({ value: w.id, label: w.title })).sort((a, b) => a.label.localeCompare(b.label)), [works, author]);
  // An author with one work has that work chosen at once (owner, 2026-10-16:
  // "It's silly to have to pick one"). Runs after the author changes and
  // after the catalogue arrives for an author set from the address.
  useEffect(() => {
    if (author && !work && workOptions.length === 1) {
      setWork(workOptions[0].value); setBookFrom(null); setBookTo(null);
    }
  }, [author, work, workOptions]);

  const [data, setData] = useState(null);
  const [results, setResults] = useState([]);
  const [running, setRunning] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [exhausted, setExhausted] = useState(false);
  const [showWeak, setShowWeak] = useState(false);
  const [error, setError] = useState(null);
  const [asked, setAsked] = useState({ q: '', work: '', lang: '', books: '' });
  const [flash, setFlash] = useState(null);
  const cards = useRef({});
  const nameCards = useRef({});
  const [mentions, setMentions] = useState(null);   // { names, total, rows } for the current search
  const [showAllNames, setShowAllNames] = useState(false);
  // The list's order: by closeness to the question (the route's order), or in
  // the order of the work (owner, 2026-10-12: "Give an option for readers to
  // order the passages by relevance or by order of occurrence, with relevance
  // the default"). Cards keep their original index so the strip's marks and
  // the summary's links still find them.
  const [order, setOrder] = useState('match');
  const [loadingNames, setLoadingNames] = useState(false);
  const [summary, setSummary] = useState(null);     // { state: 'loading' | 'ready', summary, cites }
  const [scholarship, setScholarship] = useState(null); // { state: 'loading' | 'ready' | 'none', holdings, summary, cites }
  const [recent, setRecent] = useState(null);   // { pending: [service], items: [...] } for the current search
  const [citing, setCiting] = useState(null);   // { state: 'loading' | 'ready', items } articles in the citation indexes that cite the passages
  const [showAllCiting, setShowAllCiting] = useState(false);
  const searchId = useRef(0);

  const fetchMentions = useCallback(async (names, workId, books, offset, question) => {
    const p = new URLSearchParams({ work: workId, names: names.join(','), limit: String(PAGE), offset: String(offset) });
    if (question) p.set('q', question);
    if (books) p.set('books', books);
    return getJson(`/api/passages/mentions?${p.toString()}`);
  }, []);

  // The whole list of passages that name the person: the first page comes with the
  // search, the rest when "Show all" is pressed.
  const showAllMentions = async () => {
    setShowAllNames(true);
    const m = mentions;
    if (!m || m.rows.length >= m.total) return;
    const id = searchId.current;
    setLoadingNames(true);
    try {
      const rows = [...m.rows];
      while (rows.length < m.total) {
        const json = await fetchMentions(m.names, m.workId, m.books, rows.length, m.question);
        if (id !== searchId.current) return;
        const got = json.results || [];
        if (!got.length) break;
        rows.push(...got);
      }
      setMentions((cur) => (cur && id === searchId.current ? { ...cur, rows } : cur));
    } catch (e) { /* the loaded passages stay */ } finally { setLoadingNames(false); }
  };

  const run = useCallback(async (text, workId, code, more = false, books = '') => {
    const query = (text || '').trim();
    if (!query || !workId) return;
    if (more) setLoadingMore(true);
    else {
      setRunning(true); setData(null); setResults([]); setExhausted(false); setShowWeak(false);
      setMentions(null); setShowAllNames(false); setSummary(null); setScholarship(null); setRecent(null);
      setCiting(null); setShowAllCiting(false);
      searchId.current += 1;
    }
    const id = searchId.current;
    setError(null);
    const offset = more ? results.length : 0;
    try {
      const json = await getJson(
        `/api/passages/theme-search?q=${encodeURIComponent(query)}&works=${encodeURIComponent(workId)}`
        + (books ? `&books=${encodeURIComponent(books)}` : '')
        + `&limit=${PAGE}&offset=${offset}&languages=${encodeURIComponent(code)}`);
      if (json.error) { setError(json.error); return; }
      const got = json.results || [];
      setData(json);
      setAsked({ q: query, work: workId, lang: code, books });
      setResults((prev) => (more ? [...prev, ...got] : got));
      if (got.length < PAGE) setExhausted(true);
      const p = new URLSearchParams({ scope: 'one', work: workId, lang: code, q: query });
      if (books) p.set('books', books);
      window.history.replaceState({}, '', `/theme-search?${p.toString()}`);
      if (!more && got.length) {
        const w = (catalogueRef.current[code] || []).find((x) => x.id === workId);
        const names = namesIn(query);
        if (names.length) {
          fetchMentions(names, workId, books, 0, query).then((m) => {
            if (id !== searchId.current) return;
            setMentions({
              names, workId, books, question: query, total: Number(m.total) || 0, rows: m.results || [],
              rankedBy: m.ranked_by === 'closeness' ? 'closeness' : 'mentions',
              source: m.source === 'text' ? 'text' : 'description',
              searched: Array.isArray(m.books_searched) ? m.books_searched : null,
            });
          }).catch(() => {});
        }
        // The journal citation indexes are asked in parallel with the two requests
        // below: which articles cite one of the passages just found.
        setCiting({ state: 'loading', items: [] });
        postJsonTo('/api/passages/ask-citing', {
          work: workId,
          refs: got.slice(0, CITING_MAX).map((r) => ({ ref_start: r.ref_start, ref_end: r.ref_end || r.ref_start })),
        }).then((c) => {
          if (id !== searchId.current) return;
          setCiting(c && c.available ? { state: 'ready', items: c.results || [] } : null);
        }).catch(() => { if (id === searchId.current) setCiting(null); });
        setScholarship({ state: 'loading' });
        // The live services are asked first, one request each, and paint under the
        // paragraph as they answer (owner, 2026-10-12: "If it helps you can have
        // them appear in the search as they arrive to show the user progress.").
        // The paragraph follows when they have settled, or after a page-side cap,
        // and finds their answers in the server's cache.
        setRecent({ pending: [...RECENT_SERVICES], items: [] });
        const asks = fetchRecent(query, workId, (svc, r) => {
          if (id !== searchId.current) return;
          setRecent((cur) => (cur ? {
            pending: cur.pending.filter((x) => x !== svc),
            items: r && r.available && Array.isArray(r.results) ? mergeRecent(cur.items, r.results) : cur.items,
          } : cur));
        }).done;
        let capTimer;
        const capped = new Promise((resolve) => { capTimer = setTimeout(resolve, RECENT_CAP_MS); });
        Promise.race([asks, capped]).then(() => {
          clearTimeout(capTimer);
          if (id !== searchId.current) return;
          return postJsonTo('/api/passages/ask-scholarship', { question: query, work: workId, lang: code }).then((s) => {
            if (id !== searchId.current) return;
            if (s && s.available && s.none_relevant) {
              setScholarship({ state: 'ready', noneRelevant: true, holdings: s.holdings || '', summary: '', cites: [], queryUsed: s.query_used || '' });
            } else if (s && s.available && s.summary) {
              setScholarship({ state: 'ready', holdings: s.holdings || '', summary: s.summary, cites: s.cites || [], queryUsed: s.query_used || '' });
            } else if (s && s.holdings) {
              setScholarship({ state: 'none', holdings: s.holdings });
            } else {
              setScholarship(null);
            }
          });
        }).catch(() => { if (id === searchId.current) setScholarship(null); });
        if (json.confidence?.level !== 'low') {
          setSummary({ state: 'loading' });
          postJsonTo('/api/passages/ask-summary', {
            question: query,
            work_label: workLabel(w, workId, got[0], books),
            passages: got.slice(0, 20).map((r) => ({ ref: r.ref_start, gist: r.gist || '' })),
          }).then((s) => {
            if (id !== searchId.current) return;
            setSummary(s && s.available && s.summary ? { state: 'ready', summary: s.summary, cites: s.cites || [] } : null);
          }).catch(() => { if (id === searchId.current) setSummary(null); });
        }
      }
    } catch (e) {
      setError(e.message || 'the search could not be run');
    } finally {
      setRunning(false);
      setLoadingMore(false);
    }
  }, [results.length, fetchMentions]);

  // An address that carries a work and a question runs once, as soon as the
  // work is known to be one the index holds.
  const autoRan = useRef(false);
  useEffect(() => {
    if (autoRan.current || !initial.work || !initial.q) return;
    autoRan.current = true;
    run(initial.q, initial.work, initial.lang || 'la', false, initialRange ? initial.books : '');
  }, [initial, initialRange, run]);

  const go = (e) => {
    if (e) e.preventDefault();
    run(q, work, lang, false, booksParam);
  };

  const example = (ex) => {
    setLang(ex.lang); setAuthor(ex.work.split('.')[0]); setWork(ex.work); setQ(ex.q);
    setBookFrom(null); setBookTo(null);
    run(ex.q, ex.work, ex.lang, false, '');
  };
  const shownExamples = examplesFor(view).filter((ex) => (catalogue[ex.lang] || []).some((w) => w.id === ex.work));

  const level = data?.confidence?.level;
  const fitted = Boolean(data?.confidence?.fitted);
  const weakVerdict = level === 'low';
  const noteUnrated = UNRATED_NOTE_START.test(data?.note || '');
  const emptyList = data && !results.length;
  // 2026-10-11: words no passage description contains. When none of the query's
  // words is known the note says so and no list is offered; when some are, the
  // note (or, where the note is not shown, this line) names the unknown ones.
  const noKnownWords = Boolean(data?.confidence?.no_known_words);
  const unknownWords = data?.confidence?.unknown_words || [];
  const unknownLine = unknownWords.length && !noKnownWords
    && !(data?.note || '').includes('appear in no passage description')
    && !(data?.note || '').includes('appears in no passage description')
    ? `${unknownWords.length === 1 ? 'The word' : 'The words'} ${unknownWords.join(', ')} ${unknownWords.length === 1 ? 'appears' : 'appear'} in no passage description, so ${unknownWords.length === 1 ? 'it' : 'they'} did not help the search.`
    : '';
  // A low band within one work does not hide the list: in the measurement three
  // of fifteen real questions came out low (2026-10-11), so the passages are
  // shown under a weak-match banner and the reader judges.
  const listVisible = results.length > 0 && !noKnownWords && (!weakVerdict || showWeak || fitted);
  const askedWork = (catalogue[asked.lang] || []).find((w) => w.id === asked.work);
  const askedRange = parseBooks(asked.books);
  // The books the strip draws: those the server says it searched, else the range, else every book.
  const stripBooks = useMemo(() => {
    if (Array.isArray(data?.books_searched) && data.books_searched.length) return data.books_searched;
    const all = askedWork?.books || [];
    return askedRange ? all.filter((b) => b >= askedRange.from && b <= askedRange.to) : all;
  }, [data, askedWork, askedRange?.from, askedRange?.to]);   // eslint-disable-line react-hooks/exhaustive-deps
  // Passages that name a person are drawn on the same strip, in grey; one already in the list is not drawn twice.
  const namedRows = useMemo(() => {
    const have = new Set(results.map((r) => r.id));
    return (mentions?.rows || []).filter((r) => !have.has(r.id));
  }, [mentions, results]);
  const layout = useMemo(
    () => stripLayout([...results, ...namedRows], asked.work, stripBooks), [results, namedRows, asked.work, stripBooks]);
  const redMarks = layout.marks.filter((m) => m.i < results.length);
  const greyMarks = layout.marks.filter((m) => m.i >= results.length);
  const anyStrong = results.some((r) => r.strong === true);
  const scores = results.map((r) => r.score || 0);
  const lo = Math.min(...scores);
  const hi = Math.max(...scores);
  const weight = (r) => {
    if (anyStrong) return r.strong === true ? 1 : 0;
    return hi > lo ? ((r.score || 0) - lo) / (hi - lo) : 0.5;
  };
  const inBooks = new Set(redMarks.map((m) => m.book)).size;

  const jump = (i) => {
    const el = cards.current[i];
    if (el && el.scrollIntoView) el.scrollIntoView({ behavior: 'smooth', block: 'center' });
    setFlash(i);
    setTimeout(() => setFlash((f) => (f === i ? null : f)), 1600);
  };
  const jumpRef = (ref) => {
    const i = results.findIndex((r) => r.ref_start === ref);
    if (i >= 0) jump(i);
  };
  const jumpName = (i) => {
    setShowAllNames(true);
    setTimeout(() => {
      const el = nameCards.current[i];
      if (el && el.scrollIntoView) el.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }, 0);
  };
  const shownNames = mentions ? (showAllNames ? mentions.rows : mentions.rows.slice(0, 10)) : [];
  const orderedCards = results.map((r, i) => ({ r, i }));
  if (order === 'work') {
    orderedCards.sort((a, b) => (bookOf(a.r.ref_start, asked.work) - bookOf(b.r.ref_start, asked.work))
      || (lineOf(a.r.ref_start) - lineOf(b.r.ref_start)) || (a.i - b.i));
  }

  // With nothing held on the question, the online articles come first and the
  // empty Scholarship box follows as a short note (2026-10-15: the owner saw
  // an empty box hiding the two articles found online).
  // One Scholarship box holds the paragraph on the held notes and articles
  // and, under it, the list found online (owner, 2026-10-16: two boxes
  // looked like they should be one, and "articles found online" were partly
  // books). The inner heading says how each list was found.
  const recentSection = recent?.items.length > 0 && (<div aria-label="Found online for this question" className="mt-2 border-t border-gray-200 pt-2" data-testid="ask-recent">
                      <p className="text-xs font-medium text-gray-700">Found online for this question</p>
                      <p className="text-xs text-gray-500">Open-access books and articles matched to the words of your question by a live search of the repositories. Their abstracts feed the summary above. They need not cite the passages found.</p>
                      <ul className="mt-1 space-y-2">
                        {recent.items.map((it) => {
                          const url = recentUrl(it);
                          const meta = [(it.authors || []).join(', '), it.year, it.venue].filter(Boolean).join(', ');
                          return (
                            <li key={`${it.doi || ''}|${it.title}`} className="text-sm text-gray-800 leading-snug" data-testid="ask-recent-item">
                              {url ? (
                                <a href={url} target="_blank" rel="noopener noreferrer" className="text-red-800 hover:text-red-900 hover:underline">{it.title}</a>
                              ) : it.title}
                              {meta && <span className="text-gray-600">{`, ${meta}`}</span>}
                              <span className="ml-1 rounded bg-gray-100 px-1 text-[11px] text-gray-500">{it.source === 'google_books' ? 'book' : 'article'}</span>
                              {it.oa_url && <span className="ml-1 rounded bg-gray-100 px-1 text-[11px] text-gray-500">free copy</span>}
                              {it.excerpt && <span className="block text-xs text-gray-500">{it.excerpt}</span>}
                              <span className="block text-xs mt-0.5"><CiteRecordButton record={recordFrom(it, 'recent')} /></span>
                            </li>
                          );
                        })}
                      </ul>
                    </div>);
  const locusOf = (ref) => {
    const r = results.find((x) => x.ref_start === ref);
    return (r && r.locus) || String(ref || '').trim().split(/\s+/).pop();
  };
  const citingItems = citing?.items || [];
  const citingShown = showAllCiting ? citingItems : citingItems.slice(0, CITING_SHOWN);
  const citingSection = citing?.state === 'ready' && (
    <div aria-label="Articles that cite these passages" className="mt-2 border-t border-gray-200 pt-2" data-testid="ask-citing">
      <div className="flex flex-wrap items-baseline justify-between gap-x-2 gap-y-0.5">
        <p className="text-xs font-medium text-gray-700">Articles that cite these passages</p>
        <CiteAll records={citingItems.map(citingRecord)} name={`${asked.work || 'work'} articles citing`}
                 label="Export the citing articles" />
      </div>
      <p className="text-xs text-gray-500">From the journal citation indexes (journals of 1827 to 1922, and Project MUSE journals from 1996 on): articles whose pages cite one of the passages above.</p>
      {citingItems.length === 0 ? (
        <p className="mt-1 text-xs text-gray-700 leading-snug" data-testid="ask-citing-none">No article in the citation indexes cites these passages.</p>
      ) : (
        <>
          <ul className="mt-1 space-y-2">
            {citingShown.map((it) => (
              <li key={`${it.source}|${it.url || ''}|${it.title}`} className="text-sm text-gray-800 leading-snug" data-testid="ask-citing-item">
                {it.url ? (
                  <a href={it.url} target="_blank" rel="noopener noreferrer" className="text-red-800 hover:text-red-900 hover:underline">{it.title}</a>
                ) : it.title}
                {[(it.authors || []).join(', '), it.journal, it.year].filter(Boolean).length > 0 && (
                  <span className="text-gray-600">{`, ${[(it.authors || []).join(', '), it.journal, it.year].filter(Boolean).join(', ')}`}</span>
                )}
                <span className="ml-1 rounded bg-gray-100 px-1 text-[11px] text-gray-500">{CITING_BADGE[it.source] || it.source}</span>
                <span className="block text-xs text-gray-600">
                  {'cites '}
                  {(it.cites || []).map((ref, k) => (
                    <span key={ref}>
                      {k > 0 && ', '}
                      <button type="button" onClick={() => jumpRef(ref)} className="text-red-800 hover:text-red-900 hover:underline">{locusOf(ref)}</button>
                    </span>
                  ))}
                </span>
                <span className="block text-xs mt-0.5"><CiteRecordButton record={citingRecord(it)} /></span>
              </li>
            ))}
          </ul>
          {citingItems.length > CITING_SHOWN && (
            <button type="button" onClick={() => setShowAllCiting((v) => !v)} className="mt-1 text-xs text-red-700 hover:underline" data-testid="ask-citing-toggle">
              {showAllCiting ? 'Show fewer' : `Show all ${citingItems.length}`}
            </button>
          )}
        </>
      )}
    </div>
  );
  const noneFirst = scholarship?.state === 'ready' && scholarship.noneRelevant && !!recentSection;
  const showScholarshipBox = ['loading', 'ready', 'none'].includes(scholarship?.state)
    || !!recentSection || !!citingSection || recent?.pending.length > 0;

  return (
    <div className="max-w-6xl mx-auto p-6">
      <div className="max-w-4xl">
      <p className="mt-1 text-sm text-gray-600">Pick a work and ask what it says about a subject.</p>

      <ScopeBox id="ask_a_work" className="mt-3" />

      <form onSubmit={go} className="mt-4 space-y-3">
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
          <select
            aria-label="Language"
            value={lang}
            onChange={(e) => { setLang(e.target.value); setAuthor(''); setWork(''); setBookFrom(null); setBookTo(null); }}
            className="w-full border rounded px-2 py-2 text-base sm:text-sm"
          >
            {LANGUAGES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>
          <SearchableSelect
            ariaLabel="Author"
            value={author}
            placeholder={works ? 'Author' : 'Loading authors…'}
            options={authors}
            onChange={(v) => { setAuthor(v); setWork(''); setBookFrom(null); setBookTo(null); }}
          />
          <SearchableSelect
            ariaLabel="Work"
            value={work}
            disabled={!author}
            placeholder="Work"
            options={workOptions}
            onChange={(v) => { setWork(v); setBookFrom(null); setBookTo(null); }}
          />
        </div>
        {hasBooks && (
          <div className="flex items-center gap-2 text-sm text-gray-600">
            <span>{unitForWork(work).replace(/^./, (c) => c.toUpperCase())}</span>
            <select
              aria-label="From book"
              value={fromBook}
              onChange={(e) => { const v = Number(e.target.value); setBookFrom(v); if (v > toBook) setBookTo(v); }}
              className="border rounded px-2 py-1.5 text-base sm:text-sm"
            >
              {bookList.map((b) => <option key={b} value={b}>{b}</option>)}
            </select>
            <span>to</span>
            <select
              aria-label="To book"
              value={toBook}
              onChange={(e) => { const v = Number(e.target.value); setBookTo(v); if (v < fromBook) setBookFrom(v); }}
              className="border rounded px-2 py-1.5 text-base sm:text-sm"
            >
              {bookList.map((b) => <option key={b} value={b}>{b}</option>)}
            </select>
          </div>
        )}
        <div className="flex flex-col sm:flex-row gap-2">
          <input
            type="text"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="a subject in plain words, such as fate and the plan of the gods"
            aria-label="Your question"
            className="flex-1 border rounded px-3 py-2 text-base sm:text-sm"
          />
          <button
            type="submit"
            disabled={!work || !q.trim() || running}
            className="rounded bg-red-700 px-4 py-2 text-sm font-medium text-white hover:bg-red-800 disabled:bg-gray-300"
          >
            Go
          </button>
        </div>
      </form>

      {!!shownExamples.length && (
        <div className="mt-3 flex flex-wrap gap-2">
          {shownExamples.map((ex) => (
            <button
              key={ex.q}
              type="button"
              onClick={() => example(ex)}
              className="text-xs text-red-700 hover:text-red-900 hover:bg-red-50 border border-gray-200 rounded px-2 py-1"
            >
              {ex.label} <span className="text-gray-500">in {ex.on}</span>
            </button>
          ))}
        </div>
      )}

      {running && <SearchProgress text="Reading the work for that subject…" />}
      {error && (
        <div className="mt-6 rounded border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">{error}</div>
      )}

      </div>
      {data && !running && (
        <div className="mt-6">
          {noKnownWords && (
            <div className="rounded border border-gray-300 bg-gray-100 px-3 py-2 text-sm text-gray-700" data-testid="ask-nothing">
              <strong className="font-semibold">Nothing to search for.</strong>{' '}{data.note}
            </div>
          )}
          {!noKnownWords && unknownLine && (
            <div className="mb-2 text-xs text-gray-600" data-testid="ask-unknown-words">{unknownLine}</div>
          )}
          {!noKnownWords && (emptyList || (weakVerdict && !fitted)) && (
            <div className="rounded border border-gray-300 bg-gray-100 px-3 py-2 text-sm text-gray-700">
              <strong className="font-semibold">Nothing in this work resembles that subject.</strong>
              {data.note && !emptyList ? ` ${data.note}` : ''}
            </div>
          )}
          {!noKnownWords && !emptyList && fitted && BANDS[level] && (
            <div className={`rounded border px-3 py-2 text-sm ${noteUnrated ? NEUTRAL_BAND : BANDS[level].className}`} data-testid="ask-band">
              {!noteUnrated && <><strong className="font-semibold">{BANDS[level].label}.</strong>{' '}</>}{data.note}
            </div>
          )}
          {!noKnownWords && !emptyList && !weakVerdict && !fitted && (
            <div className="rounded border border-gray-200 bg-gray-50 px-3 py-2 text-xs text-gray-600" data-testid="ask-unrated">{UNRATED_NOTE}</div>
          )}
          {!noKnownWords && weakVerdict && !fitted && results.length > 0 && !showWeak && (
            <div className="mt-4">
              <button type="button" onClick={() => setShowWeak(true)}
                      className="text-sm text-red-700 hover:underline">
                Show the closest passages anyway
              </button>
            </div>
          )}

          {listVisible && (
            <>
              <h2 className="mt-4 text-base font-semibold text-gray-900" data-testid="ask-heading">
                {workLabel(askedWork, asked.work, results[0], asked.books)}
                <span className="font-normal text-gray-600"> on {asked.q}</span>
              </h2>
              {/* The passages come first and the three written boxes stand beside
                  them (owner, 2026-10-12: the summary, the scholarship paragraph and
                  the article list "buries the text results"). On a phone the boxes
                  follow the passages. */}
              <div className="mt-3 lg:grid lg:grid-cols-[minmax(0,1fr)_22rem] lg:gap-6 lg:items-start" data-testid="ask-columns">
                <div className="min-w-0">
                  <section aria-label="Where in the work" className="mt-3 lg:mt-0">
                    <h2 className="text-sm font-semibold text-gray-700">Where in the work</h2>
                    <div className="relative mt-2 h-12 flex border-b border-gray-300" data-testid="ask-strip">
                      {layout.segments.map((b, k) => (
                        <div key={String(b)} className={`flex-1 ${k > 0 ? 'border-l border-gray-200' : ''} ${k % 2 ? 'bg-gray-50' : 'bg-white'}`} />
                      ))}
                      {greyMarks.map((m) => {
                        const r = namedRows[m.i - results.length];
                        const at = (mentions?.rows || []).findIndex((x) => x.id === r.id);
                        return (
                          <button
                            key={`n-${r.id || m.i}`}
                            type="button"
                            data-testid="ask-mark-name"
                            aria-label={`${r.ref_start}, names ${joinNames(mentions.names)}`}
                            title={`${r.ref_start}: names ${joinNames(mentions.names)}`}
                            onClick={() => jumpName(at)}
                            style={{ left: `${m.left * 100}%`, height: '40%', width: 2 }}
                            className="absolute bottom-0 -translate-x-1/2 rounded-t bg-gray-400 focus:outline-none focus:ring-2 focus:ring-red-300"
                          />
                        );
                      })}
                      {redMarks.map((m) => {
                        const r = results[m.i];
                        const w = weight(r);
                        return (
                          <button
                            key={r.id || m.i}
                            type="button"
                            data-testid="ask-mark"
                            aria-label={`${r.ref_start}${r.strong ? ', strong' : ''}`}
                            title={`${r.ref_start}: ${r.strong ? 'strong match' : `match ${m.i + 1} of ${results.length}`}${typeof r.score === 'number' ? `, score ${r.score.toFixed(2)}` : ''}`}
                            onClick={() => jump(m.i)}
                            style={{ left: `${m.left * 100}%`, height: `${40 + w * 60}%`, width: w > 0.66 ? 4 : 2 }}
                            className={`absolute bottom-0 -translate-x-1/2 rounded-t focus:outline-none focus:ring-2 focus:ring-red-300 ${w > 0.66 ? 'bg-red-700' : 'bg-red-300'}`}
                          />
                        );
                      })}
                    </div>
                    {!!layout.books.length && (() => {
                      // A work of many short units (Sappho's fragments: 137) cannot
                      // label every one, so about twelve labels on a wide screen and
                      // six on a phone are placed at their columns' centres, each
                      // free to be as wide as its number (owner, 2026-10-12: the
                      // labels had been squeezed into their columns, "16" showing
                      // as "1").
                      const n = layout.books.length;
                      const step = Math.max(1, Math.ceil(n / (phone ? 6 : 12)));
                      return (
                        <div className="relative h-4 text-[10px] text-gray-500" data-testid="ask-strip-labels">
                          {layout.books.map((b, k) => (k % step ? null : (
                            <span key={b} className="absolute top-0 -translate-x-1/2 whitespace-nowrap"
                                  style={{ left: `${((k + 0.5) / n) * 100}%` }}>{b}</span>
                          )))}
                        </div>
                      );
                    })()}
                    <p className="mt-1 text-xs text-gray-500">
                      {layout.books.length > 1
                        ? `${results.length} passages in ${inBooks} of ${layout.books.length} ${results.length ? unitWord(results) : unitForWork(asked.work)}`
                        : `${results.length} passages`}
                      {/* What the shades mean, asked for by the owner 2026-10-12;
                          each bar also says on hover which passage it is. */}
                      <span className="ml-2" data-testid="ask-strip-legend">
                        {anyStrong
                          ? `Dark red: a strong match, far above the work's typical score. Light red: the rest of the ${results.length} passages closest to your question.`
                          : `Red: the ${results.length} passages closest to your question, darker the closer.`}
                        {greyMarks.length ? ` Grey: passages that name ${joinNames(mentions.names)}, listed further down.` : ''}
                        {' '}Hover a bar for the passage.
                      </span>
                    </p>
                  </section>


                  <div className="mt-4 flex items-center gap-2 text-xs text-gray-600" data-testid="ask-order">
                    <span>Order</span>
                    <div className="inline-flex rounded border border-gray-300 overflow-hidden">
                      <button type="button" aria-pressed={order === 'match'} onClick={() => setOrder('match')}
                              className={`px-2 py-0.5 ${order === 'match' ? 'bg-gray-700 text-white' : 'bg-white text-gray-700 hover:bg-gray-50'}`}>
                        Best match
                      </button>
                      <button type="button" aria-pressed={order === 'work'} onClick={() => setOrder('work')}
                              className={`px-2 py-0.5 border-l border-gray-300 ${order === 'work' ? 'bg-gray-700 text-white' : 'bg-white text-gray-700 hover:bg-gray-50'}`}>
                        Order of the work
                      </button>
                    </div>
                  </div>
                  <ul className="mt-2 space-y-3">
                    {orderedCards.map(({ r, i }) => (
                      <li
                        key={r.id || `${r.ref_start}-${i}`}
                        ref={(el) => { cards.current[i] = el; }}
                        data-testid="ask-card"
                        className={`border rounded p-3 bg-white transition-colors ${flash === i ? 'border-red-400 bg-red-50' : 'border-gray-200'}`}
                      >
                        <div className="flex items-baseline gap-2 flex-wrap">
                          <a href={readerLink(r, asked.q)} className="text-sm text-red-800 hover:text-red-900 hover:underline">
                            <span title={fullRef(r)}>{windowLocus(r)}</span>
                          </a>
                          {r.strong === true && (
                            <span className="text-[10px] bg-red-50 text-red-800 border border-red-200 rounded px-1.5 py-0.5 font-medium">
                              strong
                            </span>
                          )}
                          <a href={readerLink(r, asked.q)} className="ml-auto text-xs text-gray-500 hover:underline">
                            Open in the Reader
                          </a>
                        </div>
                        {r.gist && <p className="mt-0.5 text-sm text-gray-700 leading-snug">{r.gist}</p>}
                        <FirstLines r={r} />
                      </li>
                    ))}
                  </ul>

                  {!exhausted && (
                    <div className="mt-4 text-center">
                      <button
                        type="button"
                        onClick={() => run(asked.q, asked.work, asked.lang, true, asked.books || '')}
                        disabled={loadingMore}
                        className="rounded border border-gray-300 bg-white px-4 py-1.5 text-sm text-gray-700 hover:border-gray-400 disabled:text-gray-500"
                      >
                        {loadingMore ? 'Loading…' : 'Show more'}
                      </button>
                    </div>
                  )}

                  {mentions && (
                    <section aria-label="Passages that name" className="mt-5" data-testid="ask-names">
                      <h2 className="text-sm font-semibold text-gray-700">Passages that name {joinNames(mentions.names)}</h2>
                      {mentions.total === 0 ? (
                        <p className="mt-1 text-xs text-gray-500">No passage description or text names {joinNames(mentions.names)} in this work.</p>
                      ) : (
                        <>
                          <p className="mt-1 text-xs text-gray-500">
                            {mentions.total} {mentions.total === 1 ? 'passage whose' : 'passages whose'} {mentions.source === 'text' ? 'text' : 'description'} names {joinNames(mentions.names)}, {mentions.rankedBy === 'closeness' ? 'the closest to your question first' : 'in the order of the work'}
                          </p>
                          <ul className="mt-2 space-y-2">
                            {shownNames.map((r, i) => (
                              <li
                                key={r.id || `${r.ref_start}-${i}`}
                                ref={(el) => { nameCards.current[i] = el; }}
                                data-testid="ask-name-card"
                                className="border border-gray-200 rounded px-3 py-2 bg-white"
                              >
                                <div className="flex items-baseline gap-2 flex-wrap">
                                  <a href={readerLink(r, asked.q)} className="text-sm text-red-800 hover:text-red-900 hover:underline"><span title={fullRef(r)}>{windowLocus(r)}</span></a>
                                  {(r.matched || []).map((n) => (
                                    <span key={n} className="text-[10px] bg-gray-100 text-gray-600 border border-gray-200 rounded px-1.5 py-0.5">{n}</span>
                                  ))}
                                </div>
                                {r.gist && <p className="mt-0.5 text-sm text-gray-700 leading-snug">{r.gist}</p>}
                              </li>
                            ))}
                          </ul>
                          {!showAllNames && mentions.total > 10 && (
                            <button type="button" onClick={showAllMentions}
                                    className="mt-2 text-sm text-red-700 hover:underline">
                              Show all {mentions.total}
                            </button>
                          )}
                          {loadingNames && <p className="mt-2 text-xs text-gray-500 italic">Loading…</p>}
                        </>
                      )}
                    </section>
                  )}
                  {exhausted && (
                    <p className="mt-4 text-center text-xs text-gray-500">End of the ranked list for this work.</p>
                  )}
                  <p className="mt-5 text-xs text-gray-500 leading-relaxed">
                    These summaries are written by a language model from the passage itself, so treat them
                    as a finding aid. Read the passage before citing it.
                  </p>
                </div>
                <aside aria-label="About the work and its scholarship" className="mt-6 lg:mt-0 min-w-0" data-testid="ask-side">
                  {summary?.state === 'loading' && (
                    <p className="mt-1 text-sm text-gray-500 italic">Tessa is reading the passages.</p>
                  )}
                  {summary?.state === 'ready' && (
                    <section aria-label="Summary of the passages found" className="mt-3 rounded border border-gray-200 bg-gray-50 px-3 py-2" data-testid="ask-summary">
                      <p className="text-xs font-semibold text-gray-600">Summary of the passages found</p>
                      <p className="mt-1 text-sm text-gray-800 leading-snug">
                        <SummaryText text={summary.summary} cites={summary.cites} onJump={jumpRef} />
                      </p>
                      <p className="mt-1 text-xs text-gray-500">Written by Tessa from the passage descriptions. Read the passages before relying on it.</p>
                    </section>
                  )}
                  {showScholarshipBox && (
                  <section aria-label="Scholarship" className="mt-3 rounded border border-gray-200 bg-gray-50 px-3 py-2" data-testid="ask-scholarship-box">
                  <div className="flex items-baseline justify-between gap-2 flex-wrap">
                    <p className="text-xs font-semibold text-gray-600">Scholarship</p>
                    <AboutSourcesLink anchor="methods" />
                  </div>
                  {scholarship?.state === 'loading' && (
                    <p className="mt-1 text-sm text-gray-500 italic">Reading the secondary literature...</p>
                  )}
                  {noneFirst && recentSection}
                  {scholarship?.state === 'ready' && (
                    <div aria-label="Summary of the scholarship found" className="mt-1" data-testid="ask-scholarship">
                      {/* The heading and the export link wrap onto two lines
                          rather than squeeze the heading into three (owner,
                          2026-10-16: "the layout of the box is messed up"). */}
                      <div className="flex flex-wrap items-baseline justify-between gap-x-2 gap-y-0.5">
                        <p className="text-xs font-medium text-gray-700">Summary of the scholarship found</p>
                        {!scholarship.noneRelevant && (
                          <CiteAll records={(scholarship.cites || []).map((c) => recordFrom(c, 'cite'))}
                                   name={`${asked.work || 'work'} ${asked.q || ''}`}
                                   label="Export the cited notes and articles" />
                        )}
                      </div>
                      {scholarship.noneRelevant ? (
                        <p className="mt-1 text-xs text-gray-700 leading-snug" data-testid="ask-scholarship-none">
                          None of the commentary notes or journal articles held for this work discuss this question.
                        </p>
                      ) : (
                        <p className="mt-1 text-sm text-gray-800 leading-snug">
                          <ScholarshipText text={scholarship.summary} cites={scholarship.cites} />
                        </p>
                      )}
                      {(hasOriginalScript(scholarship.summary) || hasOriginalScript(summary?.summary)) && (
                        <p className="mt-1"><TransliterationToggle /></p>
                      )}
                      {!scholarship.noneRelevant && (
                        <p className="mt-1 text-xs text-gray-500" data-testid="ask-scholarship-covers">
                          Written by Tessa from the notes and articles held here and the abstracts of those found online, both listed below. It does not cover the articles that cite these passages. Read the sources before relying on it.
                        </p>
                      )}
                      {scholarship.holdings && <p className="mt-1 text-xs text-gray-500" data-testid="ask-scholarship-holdings">{scholarship.holdings}</p>}
                      {/* The paragraph reads at most eight; the scholarship search
                          lists every note and article for the same question
                          (owner, 2026-10-12: "Is it eight slots and then some
                          link you can click to see more?"). */}
                      <p className="mt-1 text-xs">
                        <a href={`/theme-search?query=${encodeURIComponent(scholarship.queryUsed || asked.q)}&in=scholarship&work=${encodeURIComponent(asked.work)}`}
                           className="text-red-700 hover:underline" data-testid="ask-scholarship-more">
                          See every note and article for this question
                        </a>
                      </p>
                    </div>
                  )}
                  {scholarship?.state === 'none' && (
                    <p className="mt-2 text-xs text-gray-500" data-testid="ask-scholarship-holdings">{scholarship.holdings}</p>
                  )}
                  {citingSection}
                  {!noneFirst && recentSection}
                  {recent?.pending.length > 0 && (
                    <p className="mt-1 text-xs text-gray-500" data-testid="ask-recent-pending">
                      {`Asking ${joinNames(recent.pending.map((x) => RECENT_LABELS[x]))} for articles...`}
                    </p>
                  )}
                  </section>
                  )}
                </aside>
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}
