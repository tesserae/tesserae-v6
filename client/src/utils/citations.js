/**
 * Citations for the secondary scholarship the site shows (articles, chapters,
 * books, theses and commentary notes), in three formats: RIS (Zotero, EndNote),
 * BibTeX (LaTeX) and one plain author-date line.
 *
 * Every place that lists scholarship builds the same normalised record with
 * recordFrom() and hands it to the formatters, so a reference reads the same
 * wherever it is copied. This is separate from utils/citation.js, which cites a
 * search finding (a parallel), not a piece of scholarship.
 *
 * Record: { type: 'article' | 'book' | 'chapter' | 'thesis' | 'commentary',
 *   title, authors: [], year, venue, volume, issue, pages, publisher, place,
 *   doi, url, oa_url, commentator, edition, work, ref_start, ref_end, snippet }
 */

const str = (v) => (v === null || v === undefined ? '' : String(v).trim());

function authorList(a) {
  if (Array.isArray(a)) return a.map(str).filter(Boolean);
  if (typeof a === 'string') return a.split(/;\s*/).map(str).filter(Boolean);
  return [];
}

const THESIS_RE = /\b(e-?theses|theses|thesis|dissertations?)\b/i;

/** A journal field that names a thesis repository rather than a journal. */
export function looksLikeThesis(venue, type) {
  return THESIS_RE.test(str(venue)) || /dissertation|thesis/i.test(str(type));
}

function typeOf(rawType, venue) {
  const t = str(rawType).toLowerCase();
  if (looksLikeThesis(venue, t)) return 'thesis';
  if (t.includes('chapter')) return 'chapter';
  if (t.includes('book')) return 'book';
  return 'article';
}

/** Page text for the article's own range. A list is the pages that cite the
 *  passage (the index's meaning), which is not a page range, so it is dropped. */
function pageText(p) {
  return typeof p === 'string' || typeof p === 'number' ? str(p) : '';
}

const blank = () => ({
  type: 'article', title: '', authors: [], year: '', venue: '', volume: '', issue: '', pages: '',
  publisher: '', place: '', doi: '', url: '', oa_url: '', commentator: '', edition: '', work: '',
  ref_start: '', ref_end: '', snippet: '',
});

/**
 * Maps one of the site's item shapes to the record.
 *  source 'main'     Reader tab: OpenAlex or Crossref record (type, authors, venue, doi, oa_url)
 *  source 'fulltext' Reader tab: open-access sentence (adds url)
 *  source 'index'    Reader tab: early-journal citation index (url_jstor, url_ia)
 *  source 'book'     Reader tab: Google Books row (publisher, preview)
 *  source 'note'     a commentary note: { note, section, work }
 *  source 'card'     Theme Search card (kind article or commentary, link)
 *  source 'recent'   "Articles found online" item (excerpt)
 *  source 'cite'     Search One Text paragraph cite (kind article, recent or commentary)
 *  source 'document' a document page's scholarship row (journal, page, url)
 */
export function recordFrom(item, source) {
  const it = item || {};
  const r = blank();
  switch (source) {
    case 'note': {
      const { note = {}, section = {}, work = '' } = it;
      r.type = 'commentary';
      r.commentator = str(section.commentator);
      r.edition = str(section.edition);
      r.title = str(section.title);
      r.work = str(work);
      r.ref_start = str(note.ref);
      r.snippet = str(note.text_en || note.text);
      return r;
    }
    case 'card':
    case 'cite': {
      const kind = str(it.kind);
      if (kind === 'commentary') {
        r.type = 'commentary';
        r.commentator = str(it.commentator);
        r.edition = str(it.edition);
        r.title = str(it.edition_title);
        r.work = str(it.work);
        r.ref_start = str(it.ref_start);
        r.ref_end = str(it.ref_end);
        r.snippet = str(it.snippet);
        return r;
      }
      r.type = typeOf(it.type, it.journal || it.venue);
      r.title = str(it.title);
      r.authors = authorList(it.authors);
      r.year = str(it.year);
      r.venue = str(it.journal || it.venue);
      r.doi = str(it.doi);
      r.url = str(it.url || (it.link && it.link.url));
      r.oa_url = str(it.oa_url);
      r.snippet = str(it.snippet || it.excerpt);
      return r;
    }
    case 'book':
      r.type = 'book';
      r.title = str(it.title);
      r.authors = authorList(it.authors);
      r.year = str(it.year);
      r.publisher = str(it.publisher);
      r.url = str(it.preview || it.url);
      r.snippet = str(it.snippet);
      return r;
    case 'index':
      r.type = typeOf(it.type, it.venue);
      r.title = str(it.title);
      r.authors = authorList(it.authors);
      r.year = str(it.year);
      r.venue = str(it.venue);
      r.volume = str(it.volume);
      r.url = str(it.url_jstor || it.url_ia || it.url);
      r.snippet = str(it.snippet);
      return r;
    case 'document':
      r.type = 'article';
      r.title = str(it.title);
      r.authors = authorList(it.authors);
      r.year = str(it.year);
      r.venue = str(it.journal);
      r.url = str(it.url);
      return r;
    default: // 'main', 'fulltext', 'recent'
      r.type = typeOf(it.type, it.venue);
      r.title = str(it.title);
      r.authors = authorList(it.authors);
      r.year = str(it.year);
      r.venue = str(it.venue || it.journal);
      r.volume = str(it.volume);
      r.issue = str(it.issue);
      r.pages = pageText(it.pages);
      r.publisher = str(it.publisher);
      r.doi = str(it.doi);
      r.url = str(it.url);
      r.oa_url = str(it.oa_url);
      r.snippet = str(it.snippet || it.excerpt);
      return r;
  }
}

// ---------------------------------------------------------------- editions

/** "Georgius Thilo and Hermannus Hagen, eds., Servii ... commentarii (Leipzig: B. G. Teubner, 1878-1902)"
 *  -> { editors, title, place, publisher, year }, or null when the string
 *  does not have that form. */
export function parseEdition(edition) {
  const s = str(edition);
  const m = /^(.+?),\s*eds?\.,\s*(.+?)\s*\((?:([^:()]+):\s*)?([^,()]+),\s*([0-9][0-9\-– ]*[0-9])\)\s*\.?$/.exec(s);
  if (!m) return null;
  const editors = m[1].split(/\s*(?:,|\band\b|&)\s*/).map(str).filter(Boolean);
  return { editors, title: str(m[2]), place: str(m[3]), publisher: str(m[4]), year: str(m[5]) };
}

let editionsCache = null; // a promise of Map(lower-cased commentator -> edition string)
let editionsMap = null;   // the same, once loaded

/** GET /api/scholarship/sources once per page load. */
export function loadEditions() {
  if (!editionsCache) {
    editionsCache = fetch('/api/scholarship/sources')
      .then((r) => (r && r.ok !== false ? r.json() : {}))
      .then((d) => {
        const m = new Map();
        for (const c of (d && d.commentaries) || []) {
          const k = str(c.commentator).toLowerCase();
          if (k && c.edition && !m.has(k)) m.set(k, str(c.edition));
        }
        editionsMap = m;
        return m;
      })
      .catch(() => { editionsMap = new Map(); return editionsMap; });
  }
  return editionsCache;
}

/** Test hook: forget the cached lookup. */
export function resetEditions() { editionsCache = null; editionsMap = null; }

/** The record with its edition filled in from the cache, if loaded (sync). */
export function withEditionSync(rec) {
  if (!rec || rec.type !== 'commentary' || rec.edition || !editionsMap) return rec;
  const e = editionsMap.get(str(rec.commentator).toLowerCase());
  return e ? { ...rec, edition: e } : rec;
}

/** The record with its edition filled in, fetching the list on first use. */
export async function withEdition(rec) {
  if (!rec || rec.type !== 'commentary' || rec.edition) return rec;
  await loadEditions();
  return withEditionSync(rec);
}

export function withEditions(recs) { return Promise.all((recs || []).map(withEdition)); }

// ------------------------------------------------------------------- shared

const firstYear = (y) => (/\d{4}/.exec(str(y)) || [''])[0];

/** "vergil.aeneid" as "Vergil, Aeneid" (the Theme Search list's rule), for a note's locus. */
export function workTitle(work) {
  const parts = str(work).replace(/\.part\.\d+.*$/, '').split('.').filter(Boolean)
    .map((p) => p.split('_').filter(Boolean).map((w) => w.charAt(0).toUpperCase() + w.slice(1)).join(' '));
  return parts.join(', ');
}

function locus(rec) {
  const work = workTitle(rec.work);
  const a = str(rec.ref_start);
  const b = str(rec.ref_end);
  const range = b && b !== a ? `${a}-${b}` : a;
  // A ref that already begins with the work's abbreviation ("verg. aen. 7.641") stands alone.
  const joined = /^[A-Za-z]/.test(a) ? range : [work, range].filter(Boolean).join(' ');
  return joined.trim();
}

/** The free copy, else the DOI link, else the url. */
function bestUrl(rec) {
  return str(rec.oa_url) || (rec.doi ? `https://doi.org/${str(rec.doi)}` : '') || str(rec.url);
}

function doiLink(rec) { return rec.doi ? `https://doi.org/${str(rec.doi)}` : ''; }

// --------------------------------------------------------------------- RIS

const RIS_TYPE = { article: 'JOUR', book: 'BOOK', chapter: 'CHAP', thesis: 'THES', commentary: 'BOOK' };

export function toRIS(rec) {
  const r = rec || {};
  const type = r.type || 'article';
  const lines = [`TY  - ${RIS_TYPE[type] || 'JOUR'}`];
  const add = (tag, v) => { if (str(v)) lines.push(`${tag}  - ${str(v)}`); };

  if (type === 'commentary') {
    const ed = parseEdition(r.edition);
    add('AU', r.commentator);
    if (ed) {
      add('TI', ed.title);
      ed.editors.forEach((e) => add('A2', e));
      add('PB', ed.publisher);
      add('CY', ed.place);
      add('PY', firstYear(ed.year));
    } else if (str(r.edition)) {
      add('TI', r.edition);
    } else {
      add('TI', r.title);
    }
    const loc = locus(r);
    if (loc) lines.push(`N1  - on ${loc}`);
    add('UR', bestUrl(r));
    lines.push('ER  - ');
    return lines.join('\n') + '\n';
  }

  (r.authors || []).forEach((a) => add('AU', a));
  add('TI', r.title);
  if (type === 'chapter') add('BT', r.venue);
  else if (type === 'thesis') add('PB', r.venue);
  else add('JO', r.venue);
  add('PY', r.year);
  if (type !== 'thesis') add('PB', r.publisher);
  add('CY', r.place);
  add('VL', r.volume);
  add('IS', r.issue);
  if (str(r.pages)) {
    const m = /^(\S+?)\s*[-–]+\s*(\S+)$/.exec(str(r.pages));
    if (m) { add('SP', m[1]); add('EP', m[2]); } else add('SP', r.pages);
  }
  add('DO', r.doi);
  add('UR', bestUrl(r));
  lines.push('ER  - ');
  return lines.join('\n') + '\n';
}

export function risList(records) {
  return (records || []).map(toRIS).join('\n');
}

// ------------------------------------------------------------------ BibTeX

const STOP = new Set(['with', 'from', 'that', 'this', 'into', 'their', 'about', 'some', 'what', 'when', 'where', 'which', 'other', 'upon', 'than', 'then', 'them', 'these', 'those', 'have', 'been']);

function asciiLower(s) {
  return str(s).normalize('NFD').replace(/[̀-ͯ]/g, '').replace(/[^A-Za-z]/g, '').toLowerCase();
}

function surnameOf(name) {
  const n = str(name);
  if (!n) return '';
  if (n.includes(',')) return n.split(',')[0];
  const parts = n.split(/\s+/);
  return parts[parts.length - 1];
}

function titleWordFor(rec) {
  const t = rec.type === 'commentary' ? (parseEdition(rec.edition)?.title || rec.edition || rec.title) : rec.title;
  const words = str(t).split(/\s+/).map(asciiLower).filter(Boolean);
  return words.find((w) => w.length >= 4 && !STOP.has(w)) || words.find((w) => w.length >= 3) || words[0] || '';
}

/** <firstauthorsurname><year><firstlongtitleword>, lowercased ASCII. */
export function bibKey(rec) {
  const who = rec.type === 'commentary' ? rec.commentator : (rec.authors || [])[0];
  const yr = rec.type === 'commentary'
    ? firstYear(parseEdition(rec.edition)?.year)
    : firstYear(rec.year);
  return `${asciiLower(surnameOf(who))}${yr}${titleWordFor(rec)}` || 'ref';
}

/** Keys for a list, made unique with a, b, c on repeats. */
export function bibKeys(records) {
  const base = (records || []).map(bibKey);
  const count = new Map();
  base.forEach((k) => count.set(k, (count.get(k) || 0) + 1));
  const seen = new Map();
  return base.map((k) => {
    if (count.get(k) === 1) return k;
    const i = seen.get(k) || 0;
    seen.set(k, i + 1);
    return k + String.fromCharCode(97 + i);
  });
}

const esc = (s) => str(s).replace(/([&%$#_{}])/g, '\\$1');

export function toBibTeX(rec, key) {
  const r = rec || {};
  const type = r.type || 'article';
  const k = key || bibKey(r);
  const f = [];
  const add = (name, v, raw) => { if (str(v)) f.push([name, raw ? str(v) : esc(v)]); };
  let entry = 'article';
  if (type === 'commentary') {
    entry = 'book';
    const ed = parseEdition(r.edition);
    add('author', r.commentator);
    if (ed) {
      f.push(['title', `{${esc(ed.title)}}`]);
      add('editor', ed.editors.join(' and '));
      add('publisher', ed.publisher);
      add('address', ed.place);
      add('year', firstYear(ed.year));
    } else if (str(r.edition)) {
      f.push(['title', `{${esc(r.edition)}}`]);
    } else if (str(r.title)) {
      f.push(['title', `{${esc(r.title)}}`]);
    }
    const loc = locus(r);
    if (loc) add('note', `on ${loc}`);
    add('url', bestUrl(r), true);
  } else {
    if (type === 'book') entry = 'book';
    else if (type === 'chapter') entry = 'incollection';
    else if (type === 'thesis') entry = 'phdthesis';
    add('author', (r.authors || []).join(' and '));
    if (str(r.title)) f.push(['title', `{${esc(r.title)}}`]);
    if (type === 'article') add('journal', r.venue);
    else if (type === 'chapter') add('booktitle', r.venue);
    else if (type === 'thesis') add('school', r.venue);
    if (type !== 'thesis') add('publisher', r.publisher);
    add('address', r.place);
    add('year', r.year);
    add('volume', r.volume);
    add('number', r.issue);
    add('pages', str(r.pages).replace(/\s*[-–]+\s*/, '--'));
    add('doi', r.doi, true);
    const u = bestUrl(r);
    add('url', u && u !== doiLink(r) ? u : '', true);
  }
  const body = f.map(([n, v]) => `  ${n} = ${/^\{.*\}$/.test(v) ? v : `{${v}}`}`).join(',\n');
  return `@${entry}{${k},\n${body}\n}\n`;
}

export function bibList(records) {
  const keys = bibKeys(records);
  return (records || []).map((r, i) => toBibTeX(r, keys[i])).join('\n');
}

// -------------------------------------------------------------------- text

function invert(name) {
  const n = str(name);
  if (!n || n.includes(',')) return n;
  const parts = n.split(/\s+/);
  if (parts.length < 2) return n;
  return `${parts[parts.length - 1]}, ${parts.slice(0, -1).join(' ')}`;
}

function namesText(authors) {
  const list = (authors || []).map(str).filter(Boolean);
  if (!list.length) return '';
  const names = list.map((a, i) => (i === 0 ? invert(a) : a));
  if (names.length === 1) return names[0];
  if (names.length === 2) return `${names[0]}, and ${names[1]}`;
  return `${names.slice(0, -1).join(', ')}, and ${names[names.length - 1]}`;
}

const dot = (s) => { const t = str(s); return !t ? '' : /[.?!]$/.test(t) ? t : `${t}.`; };

export function toText(rec) {
  const r = rec || {};
  const type = r.type || 'article';
  if (type === 'commentary') {
    const loc = locus(r);
    return [dot(r.commentator), dot(r.edition || r.title), loc ? `On ${loc}.` : ''].filter(Boolean).join(' ');
  }
  const parts = [dot(namesText(r.authors)), dot(r.year)];
  const title = str(r.title);
  const place = [str(r.place), str(r.publisher)].filter(Boolean).join(': ');
  if (type === 'book') {
    parts.push(dot(title), dot(place));
  } else if (type === 'chapter') {
    if (title) parts.push(/[.?!]$/.test(title) ? `"${title}"` : `"${title}."`);
    const where = [r.venue ? `In ${str(r.venue)}` : '', r.pages ? `pp. ${str(r.pages)}` : ''].filter(Boolean).join(', ');
    parts.push(dot(where), dot(place));
  } else {
    if (title) parts.push(/[.?!]$/.test(title) ? `"${title}"` : `"${title}."`);
    let venue = str(r.venue);
    if (venue && r.volume) venue += ` ${str(r.volume)}`;
    if (venue && r.issue) venue += ` (${str(r.issue)})`;
    if (venue && r.pages) venue += `: ${str(r.pages)}`;
    parts.push(dot(venue));
  }
  const link = doiLink(r) || str(r.oa_url) || str(r.url);
  if (link) parts.push(link);
  return parts.filter(Boolean).join(' ');
}

// ---------------------------------------------------------- clipboard, files

export async function copyText(text) {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    return false;
  }
}

/** An ASCII file name stem under 60 characters. */
export function safeName(name, fallback = 'citations') {
  const s = str(name).normalize('NFD').replace(/[̀-ͯ]/g, '')
    .replace(/[^A-Za-z0-9]+/g, '_').replace(/^_+|_+$/g, '').slice(0, 55).replace(/_+$/, '');
  return s || fallback;
}

export function download(filename, text, mime = 'text/plain') {
  const blob = new Blob([text], { type: `${mime};charset=utf-8` });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export const RIS_MIME = 'application/x-research-info-systems';
export const BIB_MIME = 'application/x-bibtex';
