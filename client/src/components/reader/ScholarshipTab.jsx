import React, { useEffect, useMemo, useState } from 'react';
import { LoadingSpinner } from '../common';
import { displayRef } from './refId';

/**
 * Secondary scholarship on the selected lines: the commentators' notes the
 * site holds (public domain, machine translation in front and the Latin one
 * click behind it), then every other piece -- articles, chapters, full-text
 * quotations, book pages -- in one reverse-chronological list, each opening
 * through the DOI, a legal open copy, or the reader's own library.
 *
 * Nothing here is fetched from a subscription service. The library link is
 * built from a setting the reader keeps in this browser (an OpenURL resolver
 * address), so the article opens under their own access.
 */
const LIBRARY_KEY = 'tesserae.libraryResolver';
const LIBRARY_SUGGESTION = 'https://search.lib.buffalo.edu/discovery/openurl?institution=01SUNY_BUF&vid=01SUNY_BUF:everything';

function loadLibrary() {
  try { return localStorage.getItem(LIBRARY_KEY) || ''; } catch { return ''; }
}

function libraryLink(base, item) {
  if (!base || !item.doi) return null;
  const sep = base.includes('?') ? '&' : '?';
  const genre = item.type && item.type.includes('book') ? 'book' : 'article';
  return `${base}${sep}rft_id=${encodeURIComponent('info:doi/' + item.doi)}&rft.genre=${genre}`;
}

// A key that identifies one piece across sources, so the same paper found
// twice (say, in the metadata search and again in the full-text search)
// appears once, not twice: the DOI when there is one, else
// the title's first 80 characters, the same rule the backend uses.
function pieceKey(item) {
  const doi = item.doi;
  if (doi) return 'doi:' + doi;
  return 'title:' + (item.title || '').toLowerCase().slice(0, 80);
}

function pieceYear(item) {
  const y = typeof item.year === 'string' ? parseInt(item.year, 10) : item.year;
  return Number.isFinite(y) ? y : null;
}

// Bolding the citation in a snippet: an exact match of the surface the
// backend found works for most sources, but Google Books and CORE return
// their own OCR-ish spacing ("Aen . 1.1 arma virumque cano", "Aen . 1.1-4")
// that an exact match never hits, so the "cites ..." line is right and the
// snippet next to it is not bolded at all. These build a
// tolerant match instead: the work's abbreviation or full title, then the
// passage's own locus, with optional spaces around periods and commas and
// an en dash or hyphen for a following range.
export function escapeRe(s) {
  return String(s).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

export function flexLocus(lo) {
  return String(lo).split(/([.,])/).map((part) => (
    part === '.' || part === ',' ? '\\s*[.,]\\s*' : escapeRe(part)
  )).join('');
}

export function buildLocusRegex(passage) {
  if (!passage || !passage.lo) return null;
  const names = [passage.abbrev, passage.title].filter(Boolean)
    .map((n) => escapeRe(n.replace(/\.$/, '')));
  if (!names.length) return null;
  const lo = flexLocus(passage.lo);
  // A range after the locus ("1.1-7", "1.1–4") is part of the same
  // citation; a comma after that is the start of a different one in a list
  // ("Aen. 1.1-7, 1.18, 1.22...") and must not be swallowed into the bold
  // span.
  const rangeTail = '(?:\\s*[-\\u2013]\\s*\\d+(?:\\s*[.:]\\s*\\d+){0,2})?';
  try {
    return new RegExp(`(?:${names.join('|')})[\\s.,]*${lo}${rangeTail}`, 'i');
  } catch {
    return null;
  }
}

// Where to bold in text: the exact surface first (fast, and right whenever
// a source's spacing matches ours), else the passage's abbreviation or
// title next to its locus allowing for loose OCR spacing, else -- nothing
// naming the passage at all -- the opening words of the passage itself in
// the original language, when they are present verbatim (a paper so often
// quotes a line before it numbers it). Returns {start, end} or null.
export function findMark(text, mark, passage, fallbackWords) {
  if (!text) return null;
  if (mark) {
    const i = text.toLowerCase().indexOf(String(mark).toLowerCase());
    if (i >= 0) return { start: i, end: i + mark.length };
  }
  const locusRe = buildLocusRegex(passage);
  if (locusRe) {
    const m = locusRe.exec(text);
    if (m) return { start: m.index, end: m.index + m[0].length };
  }
  if (fallbackWords && fallbackWords.trim()) {
    try {
      const re = new RegExp(escapeRe(fallbackWords.trim()).replace(/\s+/g, '\\s+'), 'i');
      const m = re.exec(text);
      if (m) return { start: m.index, end: m.index + m[0].length };
    } catch { /* malformed fallback text, no bolding */ }
  }
  return null;
}


export default function ScholarshipTab({ work, language, selection, units, second, onClearSecond }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [library, setLibrary] = useState(loadLibrary);
  const [editingLibrary, setEditingLibrary] = useState(false);

  const refStart = units?.[selection?.startIdx]?.ref;
  const refEnd = units?.[selection?.endIdx]?.ref;

  useEffect(() => {
    if (!work || !refStart) return;
    let cancelled = false;
    setLoading(true); setError(null);
    const q = new URLSearchParams({ work, ref_start: refStart });
    if (refEnd && refEnd !== refStart) q.set('ref_end', refEnd);
    // The opening words of the selection: papers quote a line more often
    // than they number it, so the full-text search looks for both.
    const opening = String(units?.[selection?.startIdx]?.text || '').replace(/<[^>]+>/g, ' ')
      .replace(/[^\p{L}\p{M}\s'’]/gu, ' ').split(/\s+/).filter(Boolean).slice(0, 6).join(' ');
    if (opening.split(' ').length >= 3) q.set('quote', opening);
    if (second?.work && second?.ref_start) {
      q.set('work2', second.work); q.set('ref2_start', second.ref_start);
      if (second.ref_end) q.set('ref2_end', second.ref_end);
    }
    fetch(`/api/scholarship?${q.toString()}`)
      .then((r) => r.json())
      .then((d) => { if (!cancelled) setData(d); })
      .catch(() => { if (!cancelled) setError('The scholarship lookup did not answer.'); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [work, refStart, refEnd, second?.work, second?.ref_start, second?.ref_end, units, selection?.startIdx]);

  const saveLibrary = (value) => {
    const v = (value || '').trim();
    setLibrary(v);
    try { if (v) localStorage.setItem(LIBRARY_KEY, v); else localStorage.removeItem(LIBRARY_KEY); } catch { /* private window */ }
    setEditingLibrary(false);
  };

  // The passage's own first three words, in the original language: the last
  // resort for bolding a citation in a snippet that names neither the work
  // nor a locus we can recognise, but quotes the line itself.
  const fallbackWords = useMemo(() => {
    const words = String(units?.[selection?.startIdx]?.text || '').replace(/<[^>]+>/g, ' ')
      .replace(/[^\p{L}\p{M}\s'’]/gu, ' ').split(/\s+/).filter(Boolean).slice(0, 3);
    return words.length >= 3 ? words.join(' ') : '';
  }, [units, selection?.startIdx]);

  // Every piece that is not a commentary, merged from the four services into
  // one reverse-chronological list (newest first, undated last), each with
  // a small tag naming its source and kind. A piece found by more than one
  // service is kept once, from whichever service found it first below.
  const pieces = useMemo(() => {
    if (!data) return [];
    const seen = new Set();
    const take = (item) => {
      const k = pieceKey(item);
      if (!k || seen.has(k)) return false;
      seen.add(k);
      return true;
    };
    const passage = data.passage;
    const out = [];
    for (const r of (data.index?.results || [])) {
      if (!take(r)) continue;
      out.push({ year: r.year || null, key: 'idx-' + (r.url || r.title),
                 node: <IndexPieceLI key={'idx-' + (r.url || r.title)} r={r} passage={passage} fallbackWords={fallbackWords} /> });
    }
    for (const r of (data.fulltext?.results || [])) {
      if (!take(r)) continue;
      out.push({ year: r.year || null, key: 'ft-' + (r.doi || r.url || r.title),
                 node: <FullTextPieceLI key={'ft-' + (r.doi || r.url || r.title)} r={r} library={library} passage={passage} fallbackWords={fallbackWords} /> });
    }
    for (const r of (data.results || [])) {
      if (!take(r)) continue;
      out.push({ year: r.year || null, key: 'main-' + (r.doi || r.title),
                 node: <MainPieceLI key={'main-' + (r.doi || r.title)} r={r} data={data} library={library} passage={passage} fallbackWords={fallbackWords} /> });
    }
    for (const b of (data.books?.results || [])) {
      if (!take(b)) continue;
      out.push({ year: pieceYear(b), key: 'book-' + b.id,
                 node: <BookPieceLI key={'book-' + b.id} b={b} passage={passage} fallbackWords={fallbackWords} /> });
    }
    out.sort((x, y) => {
      if (x.year == null && y.year == null) return 0;
      if (x.year == null) return 1;
      if (y.year == null) return -1;
      return y.year - x.year;
    });
    return out;
  }, [data, library, fallbackWords]);

  if (!selection) return null;

  return (
    <div className="space-y-4">
      {second?.work && (
        <p className="text-[11px] text-gray-500">
          Together with {second.label || second.work} {displayRef(second.ref_start)}
          {onClearSecond && (
            <button type="button" className="ml-1 text-red-700 hover:underline" onClick={onClearSecond}>(this passage alone)</button>
          )}
        </p>
      )}

      {loading && <LoadingSpinner />}
      {error && <p className="text-sm text-amber-700">{error}</p>}

      {!loading && data && (
        <>
          <Contents data={data} pieceCount={pieces.length} />
          <CommentarySection sections={data.commentary || []} work={work} />
          {data.commentary2?.length > 0 && (
            <CommentarySection sections={data.commentary2} heading="On the compared passage" work={second?.work} />
          )}

          <section id="sch-scholarship">
            <div className="flex items-baseline justify-between gap-2 flex-wrap">
              <h4 className="text-xs font-semibold text-gray-800 uppercase tracking-wide">Scholarship</h4>
              <button type="button" onClick={() => setEditingLibrary((v) => !v)}
                      className="text-[11px] text-red-700 hover:underline">
                {library ? 'My library: set' : 'Set my library'}
              </button>
            </div>
            {editingLibrary && (
              <LibraryForm value={library} onSave={saveLibrary} />
            )}
            {pieces.length === 0 && (
              <p className="text-sm text-gray-500 mt-2">No article, chapter, or book page found that cites these lines.</p>
            )}
            <ul className="mt-2 space-y-3">
              {pieces.map((p) => p.node)}
            </ul>
            <p className="text-[11px] text-gray-500 mt-3 leading-snug">
              Found by title and abstract in OpenAlex and Crossref (article record), with open copies from
              Unpaywall; in the full text of open-access papers by Semantic Scholar and CORE (open-access
              article); in journals from before 1923 by the site&rsquo;s own citation index (journal
              article, before 1923, JSTOR); and in Google Books (book page). Subscription articles open
              under your own access. Copy for Zotero puts the reference on the clipboard (in Zotero: File,
              Import from Clipboard). Sources and licenses are on the Sources page.
            </p>
            {data.books?.hathitrust_url && (
              <p className="text-[11px] text-gray-500 mt-2 leading-snug">
                <a className="text-red-700 hover:underline" href={data.books.hathitrust_url} target="_blank" rel="noreferrer">
                  Search HathiTrust&rsquo;s full text
                </a> for this passage: it answers with the books and page numbers where the citation occurs, without showing the text.
              </p>
            )}
          </section>

          {(data.links || []).length > 0 && (
            <p className="text-[11px] text-gray-500 leading-snug">
              {data.links.map((l) => (
                <a key={l.url} className="text-red-700 hover:underline mr-3" href={l.url} target="_blank" rel="noreferrer">{l.label}</a>
              ))}
            </p>
          )}
        </>
      )}
    </div>
  );
}

/** RIS for one item, the interchange format Zotero imports from the clipboard
 *  (Zotero: File, Import from Clipboard) or from a saved .ris file. */
function toRIS(r) {
  const t = r.type || '';
  const type = t.includes('book-chapter') || t === 'chapter' ? 'CHAP' : t.includes('book') ? 'BOOK' : 'JOUR';
  const lines = [`TY  - ${type}`];
  (r.authors || []).forEach((a) => lines.push(`AU  - ${a}`));
  if (r.title) lines.push(`TI  - ${r.title}`);
  if (r.venue) lines.push(type === 'CHAP' ? `BT  - ${r.venue}` : `JO  - ${r.venue}`);
  if (r.year) lines.push(`PY  - ${r.year}`);
  if (r.publisher) lines.push(`PB  - ${r.publisher}`);
  if (r.preview && !r.doi) lines.push(`UR  - ${r.preview}`);
  if (r.doi) { lines.push(`DO  - ${r.doi}`); lines.push(`UR  - https://doi.org/${r.doi}`); }
  lines.push('ER  - ');
  return lines.join('\n') + '\n';
}

function CopyRIS({ item }) {
  const [state, setState] = useState('');
  const copy = async () => {
    try { await navigator.clipboard.writeText(toRIS(item)); setState('copied'); }
    catch { setState('failed'); }
    setTimeout(() => setState(''), 2000);
  };
  return (
    <button type="button" onClick={copy} className="text-red-700 hover:underline"
            title="Copies the reference as RIS; in Zotero choose File, Import from Clipboard.">
      {state === 'copied' ? 'copied for Zotero' : state === 'failed' ? 'copy failed' : 'copy for Zotero'}
    </button>
  );
}

function LibraryForm({ value, onSave }) {
  const [v, setV] = useState(value || LIBRARY_SUGGESTION);
  return (
    <form onSubmit={(e) => { e.preventDefault(); onSave(v); }} className="mt-2 space-y-1">
      <label className="block text-[11px] text-gray-600">
        Your library's link-resolver address (OpenURL base). Kept in this browser only. The suggestion is the University at Buffalo's.
      </label>
      <input value={v} onChange={(e) => setV(e.target.value)}
             className="w-full text-xs px-2 py-1 border border-gray-300 rounded" />
      <div className="flex gap-2">
        <button type="submit" className="text-xs px-2 py-1 rounded bg-red-700 text-white">Save</button>
        <button type="button" onClick={() => onSave('')} className="text-xs px-2 py-1 rounded border border-gray-300 text-gray-700">Clear</button>
      </div>
    </form>
  );
}

// What the column holds, in one line at the top, each part a jump link: a
// reader used to see only the first commentator and took the column for
// commentary alone. Two counts now, commentators and
// everything else, kept separate: a single merged number
// would blur a commentator's note with a JSTOR article.
function Contents({ data, pieceCount }) {
  const parts = [
    ['sch-commentators', 'commentators', (data.commentary || []).length],
    ['sch-scholarship', 'pieces of scholarship on this passage', pieceCount],
  ].filter(([, , n]) => n !== null);
  const jump = (id) => (e) => {
    e.preventDefault();
    document.getElementById(id)?.scrollIntoView({ block: 'start', behavior: 'smooth' });
  };
  return (
    <p className="text-[11px] text-gray-600 flex flex-wrap gap-x-3 gap-y-0.5 border-b border-gray-200 pb-2">
      {parts.map(([id, label, n]) => (
        <a key={id} href={`#${id}`} onClick={jump(id)} className={n ? 'text-red-700 hover:underline' : 'text-gray-400'}>
          {n} {label}
        </a>
      ))}
    </p>
  );
}

// The small tag at the top of every piece, naming its source and kind: a
// journal article read from before-1923 JSTOR full text reads differently
// from a metadata-only record, and the reader should see which is which
// before the entry itself.
function KindTag({ children }) {
  return <span className="inline-block bg-gray-100 text-gray-600 text-[10px] px-1.5 py-0.5 rounded mb-1">{children}</span>;
}

// The citation the piece makes, in the label, so "cites this passage" is
// replaced by what was actually cited; a piece that only names the work
// says so in lighter type. A depth note ("(act and scene)") is appended
// outside the bolded surface when the citation is not precise to the line.
function CitesLabel({ item, passage, passage2 }) {
  const note1 = item.cites_note || '';
  const note2 = item.cites2_note || '';
  if (item.band === 1 && item.cites && item.cites2) return <span>cites {item.cites}{note1} and {item.cites2}{note2}</span>;
  if (item.band === 2 && item.cites) return <span>cites {item.cites}{note1}, names both works</span>;
  return <span>cites {item.cites || 'this passage'}{item.cites ? note1 : ''}</span>;
}

// A sentence with the citation in bold: the exact surface where that
// works, else a tolerant match on the passage's own name and locus, else
// the passage's opening words -- see findMark above.
function Marked({ text, mark, passage, fallbackWords }) {
  if (!text) return text;
  const hit = findMark(text, mark, passage, fallbackWords);
  if (!hit) return text;
  return <>{text.slice(0, hit.start)}<strong className="font-semibold text-gray-900">{text.slice(hit.start, hit.end)}</strong>{text.slice(hit.end)}</>;
}

// A metadata-only match from OpenAlex or Crossref: found by title and
// abstract, not by full text.
function MainPieceLI({ r, data, library, passage, fallbackWords }) {
  return (
    <li className="text-sm leading-snug">
      <KindTag>article record</KindTag>
      <p className="text-gray-900">
        {r.authors?.length ? r.authors.slice(0, 3).join(', ') + (r.authors.length > 3 ? ' and others' : '') : 'Unknown author'}
        {r.year ? ` (${r.year}). ` : '. '}
        <span className="italic">{r.title}</span>
        {r.venue ? `. ${r.venue}` : ''}.
      </p>
      {r.snippet && (
        <p className="text-[12px] text-gray-700 mt-0.5 border-l-2 border-gray-200 pl-2">
          <Marked text={r.snippet} mark={r.cites} passage={passage} fallbackWords={fallbackWords} />
        </p>
      )}
      <p className="text-[11px] text-gray-500 mt-0.5 flex flex-wrap gap-x-3">
        <CitesLabel item={r} passage={data.passage} passage2={data.passage2} />
        {r.doi && <a className="text-red-700 hover:underline" href={`https://doi.org/${r.doi}`} target="_blank" rel="noreferrer">DOI</a>}
        {r.oa_url && <a className="text-red-700 hover:underline" href={r.oa_url} target="_blank" rel="noreferrer">open copy</a>}
        {libraryLink(library, r) && <a className="text-red-700 hover:underline" href={libraryLink(library, r)} target="_blank" rel="noreferrer">open through my library</a>}
        {!r.oa_url && !libraryLink(library, r) && r.doi && <span>opens through your library or a subscription</span>}
        <CopyRIS item={r} />
      </p>
    </li>
  );
}

// An article from the offline citation index (full text of the pre-1923
// journals, more as agreements come), with the pages that cite the passage
// and the citing sentence.
function IndexPieceLI({ r, passage, fallbackWords }) {
  const pre1923 = !r.year || r.year < 1923;
  return (
    <li className="text-sm leading-snug">
      <KindTag>{pre1923 ? 'journal article, before 1923, JSTOR' : 'journal article, JSTOR'}</KindTag>
      <p className="text-gray-900">
        {r.authors?.length ? r.authors.slice(0, 3).join(', ') : 'Unknown author'}
        {r.year ? ` (${r.year}). ` : '. '}
        <span className="italic">{r.title}</span>
        {r.venue ? `. ${r.venue}` : ''}{r.volume ? ` ${r.volume}` : ''}{r.pages?.length ? `, p. ${r.pages.slice(0, 4).join(', ')}` : ''}.
      </p>
      {r.snippet && (
        <p className="text-[12px] text-gray-700 mt-0.5 border-l-2 border-gray-200 pl-2">
          <Marked text={r.snippet} mark={r.cites} passage={passage} fallbackWords={fallbackWords} />
        </p>
      )}
      <p className="text-[11px] text-gray-500 mt-0.5 flex flex-wrap gap-x-3">
        <span>cites {r.cites}{r.cites_note || ''}</span>
        {r.url_jstor && <a className="text-red-700 hover:underline" href={r.url_jstor} target="_blank" rel="noreferrer">on JSTOR</a>}
        {r.url_ia && <a className="text-red-700 hover:underline" href={r.url_ia} target="_blank" rel="noreferrer">free scan</a>}
        <CopyRIS item={r} />
      </p>
    </li>
  );
}

// A sentence from open-access full text that cites the passage: the
// author's own words, which the title-and-abstract services above cannot
// give.
function FullTextPieceLI({ r, library, passage, fallbackWords }) {
  return (
    <li className="text-sm leading-snug">
      <KindTag>open-access article</KindTag>
      <p className="text-gray-900">
        {r.authors?.length ? r.authors.slice(0, 3).join(', ') + (r.authors.length > 3 ? ' and others' : '') : 'Unknown author'}
        {r.year ? ` (${r.year}). ` : '. '}
        <span className="italic">{r.title}</span>{r.venue ? `. ${r.venue}` : ''}.
      </p>
      {r.snippet && (
        <p className="text-[12px] text-gray-700 mt-0.5 border-l-2 border-gray-200 pl-2">
          <Marked text={r.snippet} mark={r.cites} passage={passage} fallbackWords={fallbackWords} />
        </p>
      )}
      <p className="text-[11px] text-gray-500 mt-0.5 flex flex-wrap gap-x-3">
        {r.cites && <span>cites {r.cites}{r.cites_note || ''}</span>}
        {r.doi && <a className="text-red-700 hover:underline" href={`https://doi.org/${r.doi}`} target="_blank" rel="noreferrer">DOI</a>}
        {r.oa_url && <a className="text-red-700 hover:underline" href={r.oa_url} target="_blank" rel="noreferrer">open copy</a>}
        {r.url && <a className="text-red-700 hover:underline" href={r.url} target="_blank" rel="noreferrer">{r.source === 'core' ? 'at CORE' : 'at Semantic Scholar'}</a>}
        {libraryLink(library, r) && <a className="text-red-700 hover:underline" href={libraryLink(library, r)} target="_blank" rel="noreferrer">open through my library</a>}
        <CopyRIS item={r} />
      </p>
    </li>
  );
}

// A page in Google Books whose text mentions the passage, with the snippet
// the service returns and a link to the page in the book's preview.
function BookPieceLI({ b, passage, fallbackWords }) {
  return (
    <li className="text-sm leading-snug">
      <KindTag>book page, Google Books</KindTag>
      <p className="text-gray-900">
        {b.authors?.length ? b.authors.slice(0, 3).join(', ') : 'Unknown author'}{b.year ? ` (${b.year}). ` : '. '}
        <span className="italic">{b.title}</span>{b.publisher ? `. ${b.publisher}` : ''}.
      </p>
      {b.snippet && (
        <p className="text-[12px] text-gray-700 mt-0.5 border-l-2 border-gray-200 pl-2">
          <Marked text={b.snippet} mark={b.cites} passage={passage} fallbackWords={fallbackWords} />
        </p>
      )}
      <p className="text-[11px] text-gray-500 mt-0.5 flex flex-wrap gap-x-3">
        {b.preview && <a className="text-red-700 hover:underline" href={b.preview} target="_blank" rel="noreferrer">open the page in Google Books</a>}
        {b.viewability && <span>{b.viewability.toLowerCase().replace('_', ' ')}</span>}
        <CopyRIS item={{ ...b, type: 'book' }} />
      </p>
    </li>
  );
}

function CommentarySection({ sections, heading = 'Commentators', work }) {
  // With several commentators at a line, one is shown at a time and the
  // others are a click away, so a busy line does not become a wall of notes.
  const [picked, setPicked] = useState(0);
  if (!sections?.length) {
    return (
      <section id={heading === 'Commentators' ? 'sch-commentators' : undefined}>
        <h4 className="text-xs font-semibold text-gray-800 uppercase tracking-wide">{heading}</h4>
        <p className="text-sm text-gray-500 mt-1">No commentary held for these lines yet.</p>
      </section>
    );
  }
  const idx = Math.min(picked, sections.length - 1);
  const c = sections[idx];
  return (
    <section id={heading === 'Commentators' ? 'sch-commentators' : undefined}>
      <h4 className="text-xs font-semibold text-gray-800 uppercase tracking-wide">{heading}</h4>
      {sections.length > 1 && (
        <div className="flex flex-wrap gap-1.5 mt-1.5" role="tablist" aria-label="Commentators">
          {sections.map((sec, i) => (
            <button key={sec.commentator + sec.title} type="button" role="tab" aria-selected={i === idx}
                    onClick={() => setPicked(i)}
                    className={`text-xs px-2 py-0.5 rounded border ${i === idx
                      ? 'bg-red-700 border-red-700 text-white'
                      : 'bg-white border-gray-300 text-gray-700 hover:border-red-600 hover:text-red-700'}`}>
              {sec.commentator}
            </button>
          ))}
        </div>
      )}
      <div className="mt-2">
        <p className="text-[11px] text-gray-500">
          {c.commentator}, <span className="italic">{c.title}</span>{c.edition ? ` (${c.edition})` : ''}
          {c.translation ? `; English: ${c.translation}` : ''}
          <Provenance source={c.source} license={c.license} />
        </p>
        {c.version_note && <p className="text-[11px] text-gray-500">{c.version_note}</p>}
        <ul className="mt-1 space-y-2">
          {c.notes.map((n, i) => (
            <Note key={c.commentator + n.ref + i} note={n} commentator={c.commentator} language={c.language}
                  work={work} auto={i === 0} translatable={c.language !== 'en'} />
          ))}
        </ul>
      </div>
    </section>
  );
}

const RTL = new Set(['he', 'ar', 'fa', 'ur']);

function Original({ language, children }) {
  return <span lang={language || undefined} dir={RTL.has(language) ? 'rtl' : undefined}>{children}</span>;
}

// Where the text came from and on what terms: the Perseus and Sefaria
// licences ask for attribution, so the link and the licence sit with
// every commentary.
function sourceName(url) {
  if (!url) return null;
  if (/perseus|cltk\//.test(url)) return 'Perseus';
  if (/sefaria\.org/.test(url)) return 'Sefaria';
  if (/ccel\.org/.test(url)) return 'CCEL';
  try { return new URL(url).hostname.replace(/^www\./, ''); } catch { return 'source'; }
}

function shortLicence(text) {
  const t = (text || '').toLowerCase();
  if (!t || t === 'unknown') return null;
  if (t.includes('public domain')) return 'public domain';
  const m = t.match(/cc[ -]?by(?:[ -]?(?:sa|nc|nd))*(?:[ -]?\d(?:\.\d)?)?/);
  if (m) return m[0].toUpperCase().replace(/^CC[ -]?BY/, 'CC BY');
  if (t.includes('cc0')) return 'CC0';
  return null;
}

function Provenance({ source, license }) {
  const name = sourceName(source);
  const lic = shortLicence(license);
  if (!name && !lic) return null;
  const url = (source || '').split(' ')[0];
  return (
    <>
      {'; '}
      {name && /^https?:/.test(url)
        ? <a href={url} target="_blank" rel="noopener noreferrer" className="text-red-700 hover:underline">{name}</a>
        : name}
      {lic ? `${name ? ', ' : ''}${lic}` : ''}
    </>
  );
}

function Note({ note, commentator, language, work, auto, translatable = true }) {
  // A translation supplied with the commentary (a person's, not the
  // model's) is shown as the English, with the original one click behind.
  if (note.text_en) return <NoteWithTranslation note={note} language={language} />;
  return <MachineNote note={note} commentator={commentator} language={language} work={work} auto={auto} translatable={translatable} />;
}

function NoteWithTranslation({ note, language }) {
  const [showOriginal, setShowOriginal] = useState(false);
  return (
    <li className="text-sm text-gray-900 leading-relaxed">
      <span className="text-[10px] text-gray-500 mr-2">{displayRef(note.ref)}</span>
      {note.lemma && <span className="font-semibold mr-1">{note.lemma}</span>}
      {showOriginal ? <Original language={language}>{note.text}</Original> : <span>{note.text_en}</span>}
      <span className="block text-[10px] text-gray-500 mt-0.5">
        <button type="button" className="text-red-700 hover:underline" onClick={() => setShowOriginal((v) => !v)}>
          {showOriginal ? 'show the translation' : 'show the original'}
        </button>
      </span>
    </li>
  );
}

function MachineNote({ note, commentator, language, work, auto, translatable = true }) {
  const [english, setEnglish] = useState(null);
  const [showLatin, setShowLatin] = useState(false);
  const [busy, setBusy] = useState(false);
  // The local model takes ten to fifteen seconds a note, so only the first
  // note at a line is translated on its own; the rest wait for a click.
  const [wanted, setWanted] = useState(!!auto && translatable);

  useEffect(() => {
    if (!wanted || !work || !note.ref) return;
    let cancelled = false;
    setBusy(true);
    // work + ref name the note the route is being asked to translate; the
    // route only ever translates a note it already holds at that span, not
    // arbitrary text, so the exact text travels along to be checked against it.
    fetch('/api/scholarship/translate', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ work, ref: note.ref, text: note.text, commentator, language }),
    }).then((r) => r.json())
      .then((d) => { if (!cancelled) setEnglish(d); })
      .catch(() => { if (!cancelled) setEnglish({ available: false }); })
      .finally(() => { if (!cancelled) setBusy(false); });
    return () => { cancelled = true; };
  }, [work, note.ref, note.text, commentator, language, wanted]);

  const translated = english?.available;
  return (
    <li className="text-sm text-gray-900 leading-relaxed">
      <span className="text-[10px] text-gray-500 mr-2">{displayRef(note.ref)}</span>
      {note.lemma && <span className="font-semibold mr-1">{note.lemma}</span>}
      {translated && !showLatin ? <span>{english.text}</span> : <Original language={language}>{note.text}</Original>}
      <span className="block text-[10px] text-gray-500 mt-0.5">
        {busy && <span className="text-gray-400">translating… </span>}
        {translatable && !busy && !translated && !wanted && (
          <button type="button" className="text-red-700 hover:underline mr-2" onClick={() => setWanted(true)}>translate</button>
        )}
        {!busy && english && !translated && <span>Translation unavailable. </span>}
        {translated && !showLatin && <>{english.disclaimer} </>}
        {translated && (
          <button type="button" className="text-red-700 hover:underline" onClick={() => setShowLatin((v) => !v)}>
            {showLatin ? 'show the translation' : 'show the original'}
          </button>
        )}
      </span>
    </li>
  );
}
