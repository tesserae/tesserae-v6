/**
 * Scholarship viewer: every article in the three citation indexes that cites a
 * passage, a book or a whole work, with search, sort, filters, paging, a summary
 * strip and RIS export. It reads GET /api/scholarship/list. Every control writes
 * to the address (replaceState while typing, pushState on a submit or a change)
 * and the page restores its state from the address on load, so a view can be
 * bookmarked and sent. Opened from the Reader's Scholarship tab, the Events pages
 * and the Ask page.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { LoadingSpinner } from '../common';
import { IndexPieceLI } from '../reader/ScholarshipTab';
import { getJson } from '../../utils/api';
import { recordFrom, risList, download, safeName, RIS_MIME } from '../../utils/citations';
import { workHeading } from '../events/eventsFormat';
import { VIEWER_PATH } from '../../utils/scholarshipViewer';

export const PER_PAGE = 50;
export const EXPORT_LIMIT = 500;
const EXPORT_PAGE = 200;

const SOURCES = [['ejc', 'Early Journal Content'], ['muse', 'Project MUSE'], ['jstor', 'JSTOR']];
const KINDS = [['article', 'Research articles'], ['review', 'Book reviews'], ['other', 'Other']];
const SORTS = [['newest', 'Newest'], ['oldest', 'Oldest'], ['author', 'Author'], ['journal', 'Journal'], ['most', 'Most citations of this scope']];
const SCOPES = [['passage', 'This passage'], ['book', 'Book'], ['work', 'Whole work']];
const SOURCE_NAMES = Object.fromEntries(SOURCES);
const num = (n) => Number(n || 0).toLocaleString('en-US');

// The state a view is made of, as the address carries it. A source or kind list
// that is empty means all of them.
export function stateFromSearch(search) {
  const p = new URLSearchParams(search || '');
  const list = (name, allowed) => (p.get(name) || '').split(',').map((x) => x.trim()).filter((x) => allowed.includes(x));
  const page = parseInt(p.get('page'), 10);
  const scope = p.get('scope');
  return {
    work: p.get('work') || '',
    lo: p.get('lo') || '',
    hi: p.get('hi') || '',
    scope: ['passage', 'book', 'work'].includes(scope) ? scope : (p.get('lo') ? 'passage' : 'work'),
    q: p.get('q') || '',
    source: list('source', SOURCES.map((s) => s[0])),
    kind: list('kind', KINDS.map((s) => s[0])),
    year_from: p.get('year_from') || '',
    year_to: p.get('year_to') || '',
    journal: p.get('journal') || '',
    sort: SORTS.some((s) => s[0] === p.get('sort')) ? p.get('sort') : 'newest',
    page: page > 0 ? page : 1,
  };
}

// The request (and the address) for a state. Defaults are left out.
export function paramsFromState(st, extra = {}) {
  const p = new URLSearchParams();
  p.set('work', st.work);
  if (st.lo) p.set('lo', st.lo);
  if (st.hi) p.set('hi', st.hi);
  p.set('scope', st.scope);
  if (st.q.trim()) p.set('q', st.q.trim());
  if (st.source.length && st.source.length < SOURCES.length) p.set('source', st.source.join(','));
  if (st.kind.length && st.kind.length < KINDS.length) p.set('kind', st.kind.join(','));
  if (st.year_from) p.set('year_from', st.year_from);
  if (st.year_to) p.set('year_to', st.year_to);
  if (st.journal) p.set('journal', st.journal);
  if (st.sort !== 'newest') p.set('sort', st.sort);
  if (st.page > 1) p.set('page', String(st.page));
  Object.entries(extra).forEach(([k, v]) => p.set(k, String(v)));
  return p;
}

// One response row in the shape the Reader tab's row component reads.
function rowForTab(r) {
  // A cite's note arrives without parentheses; cites is cut at 60 loci and cites_total says how many there are.
  const more = (r.cites_total || 0) - (r.cites || []).length;
  const cites = (r.cites || []).map((c) => `${c.locus}${c.note ? ` (${c.note})` : ''}`).join(', ')
    + (more > 0 ? `, and ${num(more)} more` : '');
  return { ...r, venue: r.venue, cites, cites_note: '', snippet: '', sentences: r.source === 'jstor' ? [] : (r.sentences || []) };
}

// The citation record for the RIS file: the same record the Cite button builds,
// with the fields the index rows carry that the Reader's record leaves out.
export function recordForRow(r) {
  const rec = recordFrom(rowForTab(r), 'index');
  rec.doi = r.doi || '';
  rec.issue = r.issue || '';
  rec.pages = (r.pages || []).slice(0, 1).join('');
  rec.url = r.url || rec.url;
  return rec;
}

const inputCls = 'border border-gray-300 rounded px-2 py-1 text-sm bg-white';

export default function ScholarshipViewerPage() {
  const [st, setSt] = useState(() => stateFromSearch(window.location.search));
  const [qInput, setQInput] = useState(st.q);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [exporting, setExporting] = useState(false);
  const debounce = useRef(null);

  // The back and forward buttons: read the address again.
  useEffect(() => {
    const onPop = () => {
      if (window.location.pathname !== VIEWER_PATH) return;
      const next = stateFromSearch(window.location.search);
      setSt(next); setQInput(next.q);
    };
    window.addEventListener('popstate', onPop);
    return () => window.removeEventListener('popstate', onPop);
  }, []);

  const writeUrl = useCallback((next, push) => {
    const url = `${VIEWER_PATH}?${paramsFromState(next).toString()}`;
    try { window.history[push ? 'pushState' : 'replaceState']({}, '', url); } catch { /* no history */ }
  }, []);

  // A control change: new state, new address entry, page back to 1 unless it is the page.
  const change = (patch, { push = true } = {}) => {
    const next = { ...st, ...patch };
    if (!('page' in patch)) next.page = 1;
    writeUrl(next, push);
    setSt(next);
  };

  const fetchKey = paramsFromState(st, { per_page: PER_PAGE }).toString();
  useEffect(() => {
    if (!st.work) return undefined;
    let cancelled = false;
    setLoading(true); setError(null);
    getJson(`/api/scholarship/list?${fetchKey}`)
      .then((d) => { if (!cancelled) setData(d); })
      .catch(() => { if (!cancelled) { setData(null); setError('The scholarship list did not answer.'); } })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [fetchKey, st.work]);

  const onQInput = (v) => {
    setQInput(v);
    clearTimeout(debounce.current);
    // The address follows each keystroke; the list follows once typing pauses.
    writeUrl({ ...st, q: v, page: 1 }, false);
    debounce.current = setTimeout(() => change({ q: v }, { push: false }), 350);
  };
  useEffect(() => () => clearTimeout(debounce.current), []);
  const submitQ = (e) => {
    e.preventDefault();
    clearTimeout(debounce.current);
    change({ q: qInput });
  };

  const toggle = (field, all, value) => {
    const have = st[field].length ? st[field] : all;
    const next = have.includes(value) ? have.filter((x) => x !== value) : [...have, value];
    if (!next.length) return;
    change({ [field]: next.length === all.length ? [] : all.filter((x) => next.includes(x)) });
  };

  const counts = data?.counts || {};
  const total = data?.total ?? 0;
  const perPage = data?.per_page || PER_PAGE;
  const pages = Math.max(1, Math.ceil(total / perPage));
  const facets = data?.facets || {};
  const workName = useMemo(() => workHeading(st.work, null), [st.work]);
  const scopeButtons = SCOPES.filter(([k]) => k === 'work' || st.lo);

  const exportRis = async () => {
    setExporting(true);
    try {
      const rows = [];
      for (let pg = 1; rows.length < EXPORT_LIMIT; pg += 1) {
        const d = await getJson(`/api/scholarship/list?${paramsFromState({ ...st, page: pg }, { per_page: EXPORT_PAGE }).toString()}`);
        const got = d?.results || [];
        rows.push(...got);
        if (got.length < EXPORT_PAGE || rows.length >= (d?.total ?? 0)) break;
      }
      const list = rows.slice(0, EXPORT_LIMIT).map(recordForRow);
      download(`${safeName(`${st.work} ${data?.scope?.label || ''} articles`, 'scholarship')}.ris`, risList(list), RIS_MIME);
    } catch {
      setError('The export could not be made.');
    } finally {
      setExporting(false);
    }
  };

  if (!st.work) {
    return (
      <div className="bg-white rounded-lg shadow p-6 max-w-4xl mx-auto" data-testid="scholarship-viewer">
        <h2 className="text-xl font-semibold text-gray-900">Scholarship viewer</h2>
        <p className="text-sm text-gray-700 mt-2">
          Open this page from the Scholarship tab of the Reader, an event or the Ask page, which pass the work and passage to it.
        </p>
      </div>
    );
  }

  const decades = Object.entries(facets.decade || {}).sort((a, b) => Number(a[0]) - Number(b[0]));
  const decadeLabel = (d) => `${d}s`;

  return (
    <div className="bg-white rounded-lg shadow p-4 sm:p-6 max-w-5xl mx-auto" data-testid="scholarship-viewer">
      <h2 className="text-xl font-semibold text-gray-900" data-testid="viewer-heading">
        Scholarship on {data?.scope?.label || workName}
      </h2>

      <div className="flex flex-wrap items-center gap-2 mt-3" role="group" aria-label="Scope">
        {scopeButtons.map(([k, label]) => {
          const text = k === 'book' && st.lo ? `Book ${st.lo.split('.')[0]}` : label;
          const on = st.scope === k;
          return (
            <button key={k} type="button" onClick={() => change({ scope: k })} aria-pressed={on} data-testid={`scope-${k}`}
                    className={`px-3 py-1 text-sm rounded border ${on ? 'bg-red-700 text-white border-red-700' : 'bg-white text-gray-800 border-gray-300 hover:bg-gray-50'}`}>
              {text}{counts[k] === null || counts[k] === undefined ? '' : ` (${num(counts[k])})`}
            </button>
          );
        })}
        <span className="text-sm text-gray-700 ml-1" data-testid="viewer-total">
          {data && data.available !== false ? `${num(total)} ${total === 1 ? 'article' : 'articles'}` : ''}
        </span>
      </div>

      <form onSubmit={submitQ} className="mt-4" role="search">
        <div className="flex flex-wrap gap-2">
          <input type="search" value={qInput} onChange={(e) => onQInput(e.target.value)}
                 placeholder="Search titles, authors, journals and the stored sentences"
                 aria-label="Search" className={`${inputCls} flex-1 min-w-[16rem]`} data-testid="viewer-search" />
          <label className="text-sm text-gray-700 flex items-center gap-1">
            Sort
            <select value={st.sort} onChange={(e) => change({ sort: e.target.value })} className={inputCls} data-testid="viewer-sort" aria-label="Sort">
              {SORTS.map(([k, label]) => <option key={k} value={k}>{label}</option>)}
            </select>
          </label>
        </div>
        <p className="text-xs text-gray-600 mt-1">
          For JSTOR articles the search also reads the sentence that cites the passage, but the sentence itself is not shown, at JSTOR&rsquo;s request.
        </p>
      </form>

      <div className="mt-3 flex flex-wrap gap-x-6 gap-y-2 text-sm text-gray-800">
        <fieldset className="flex flex-wrap gap-x-3" aria-label="Source">
          {SOURCES.map(([k, label]) => (
            <label key={k} className="flex items-center gap-1">
              <input type="checkbox" checked={!st.source.length || st.source.includes(k)} onChange={() => toggle('source', SOURCES.map((s) => s[0]), k)} data-testid={`source-${k}`} />
              {label}
            </label>
          ))}
        </fieldset>
        <fieldset className="flex flex-wrap gap-x-3" aria-label="Kind">
          {KINDS.map(([k, label]) => (
            <label key={k} className="flex items-center gap-1">
              <input type="checkbox" checked={!st.kind.length || st.kind.includes(k)} onChange={() => toggle('kind', KINDS.map((s) => s[0]), k)} data-testid={`kind-${k}`} />
              {label}
            </label>
          ))}
        </fieldset>
        <div className="flex items-center gap-1">
          Years
          <input type="number" value={st.year_from} onChange={(e) => change({ year_from: e.target.value }, { push: false })} className={`${inputCls} w-20`} aria-label="From year" data-testid="year-from" />
          to
          <input type="number" value={st.year_to} onChange={(e) => change({ year_to: e.target.value }, { push: false })} className={`${inputCls} w-20`} aria-label="To year" data-testid="year-to" />
        </div>
        <label className="flex items-center gap-1">
          Journal
          <select value={st.journal} onChange={(e) => change({ journal: e.target.value })} className={`${inputCls} max-w-[16rem]`} aria-label="Journal" data-testid="viewer-journal">
            <option value="">All journals</option>
            {st.journal && !(facets.journal || []).some(([j]) => j === st.journal) && <option value={st.journal}>{st.journal}</option>}
            {(facets.journal || []).map(([j, n]) => <option key={j} value={j}>{`${j} (${num(n)})`}</option>)}
          </select>
        </label>
      </div>

      {data && data.available !== false && (
        <div className="mt-3 text-xs text-gray-700 leading-relaxed" data-testid="viewer-summary">
          <p>
            By source:{' '}
            {SOURCES.map(([k]) => `${SOURCE_NAMES[k]} ${num((facets.source || {})[k])}`).join(', ')}.
            {' '}An article held by two indexes is counted under each.
          </p>
          {decades.length > 0 && (
            <p data-testid="viewer-decades">By decade: {decades.map(([d, n]) => `${decadeLabel(d)} ${num(n)}`).join(', ')}.</p>
          )}
        </div>
      )}

      <div className="mt-4">
        {loading && <LoadingSpinner />}
        {error && <p className="text-sm text-amber-700" role="alert">{error}</p>}
        {!loading && data && data.available === false && (
          <p className="text-sm text-gray-700" data-testid="viewer-unavailable">{data.note || 'The citation indexes are not available on this server.'}</p>
        )}
        {!loading && data && data.available !== false && total === 0 && (
          <p className="text-sm text-gray-700" data-testid="viewer-empty">No article in the citation indexes cites this scope with these filters.</p>
        )}
        {!loading && data && data.available !== false && total > 0 && (
          <>
            <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
              <button type="button" onClick={exportRis} disabled={exporting} className="text-sm text-red-700 hover:underline disabled:text-gray-400" data-testid="viewer-export">
                {exporting ? 'Preparing the file...' : 'Export this list (RIS)'}
              </button>
              {total > EXPORT_LIMIT && (
                <span className="text-xs text-gray-600" data-testid="viewer-export-limit">
                  The export holds at most {num(EXPORT_LIMIT)} articles: the first {num(EXPORT_LIMIT)} of this list in the current sort.
                </span>
              )}
            </div>
            <ul className="space-y-3" data-testid="viewer-list">
              {(data.results || []).map((r) => (
                <IndexPieceLI key={r.key || `${r.title}|${r.year}`} r={rowForTab(r)} passage={null} fallbackWords="" />
              ))}
            </ul>
            <div className="flex items-center justify-center gap-4 mt-4 text-sm text-gray-800" data-testid="viewer-paging">
              <button type="button" disabled={st.page <= 1} onClick={() => change({ page: st.page - 1 })} className="text-red-700 hover:underline disabled:text-gray-400 disabled:no-underline">Previous</button>
              <span>page {st.page} of {pages}</span>
              <button type="button" disabled={st.page >= pages} onClick={() => change({ page: st.page + 1 })} className="text-red-700 hover:underline disabled:text-gray-400 disabled:no-underline">Next</button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
