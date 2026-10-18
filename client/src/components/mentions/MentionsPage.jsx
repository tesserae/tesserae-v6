import { useCallback, useEffect, useState } from 'react';
import { LoadingSpinner } from '../common';
import { languageName } from '../../utils/languageNames';
import { windowLocus, fullRef } from '../reader/refId';
import { entitiesTrialOn } from '../../hooks/useEntitiesTrial';
import { documentDateLabel, documentPlace, documentLabels } from '../documents/documentDisplay';

/** Latin, Greek, English, as everywhere on the site; any other language after them. */
export const LANG_ORDER = ['la', 'grc', 'en'];
const PAGE = 50;

export const TRIAL_NOTE = "Trial. Mentions are found by name and checked by a language model, and a god's name standing for a thing (Mars for war) counts as a mention. Inscriptions and papyri are matched by the name's forms alone, without the model's check.";

const TYPE_LABEL = { place: 'Place', person: 'Person', deity: 'God', people: 'People', name: 'Name in the corpus', other: 'Other' };

/** "Sarpedon · Σαρπηδών": the Latin-script heading with the Greek form beside it, for every source. */
export function headingOf(e) {
  const label = e.display_label || e.label;
  const grc = e.display_label_grc;
  return grc && grc !== label ? `${label} · ${grc}` : label;
}

export function sortedCounts(counts) {
  const keys = Object.keys(counts || {});
  const rank = (k) => { const i = LANG_ORDER.indexOf(k); return i === -1 ? LANG_ORDER.length : i; };
  return keys.sort((a, b) => rank(a) - rank(b) || a.localeCompare(b)).map((k) => [k, counts[k]]);
}

function CountsLine({ counts }) {
  const parts = sortedCounts(counts);
  if (parts.length === 0) return <span>no mentions</span>;
  return (
    <span>
      {parts.map(([lang, n], i) => (
        <span key={lang}>
          {i > 0 && ' · '}
          <span className={lang === 'la' ? 'text-red-700' : 'text-gray-700'}>{languageName(lang)}</span> {n} {n === 1 ? 'line' : 'lines'}
        </span>
      ))}
    </span>
  );
}

/** "Mars and Ares" -> "name shared with Mars and Ares"; the label a shared-name row carries. */
export function sharedLabel(names) {
  if (!names || names.length === 0) return '';
  const list = names.length === 1 ? names[0]
    : `${names.slice(0, -1).join(', ')} and ${names[names.length - 1]}`;
  return `name shared with ${list}`;
}

/** The window text with every occurrence of the matched token marked. */
export function MarkedText({ text, token, ignoreCase = false }) {
  if (!text) return <span className="text-gray-400">[source text unavailable]</span>;
  if (!token) return <>{text}</>;
  const esc = token.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const pieces = text.split(new RegExp(`(${esc})`, ignoreCase ? 'i' : ''));
  const same = (p) => (ignoreCase ? p.toLowerCase() === token.toLowerCase() : p === token);
  return (
    <>
      {pieces.map((p, i) => (same(p)
        ? <mark key={i} className="bg-yellow-100 text-gray-900 px-0.5 rounded">{p}</mark>
        : <span key={i}>{p}</span>))}
    </>
  );
}

/** A link into the Reader at this window, with the Similar Passages tab open. */
export function readerHref(r) {
  const work = String(r.work || '').replace(/\.tess$/, '');
  const params = new URLSearchParams({
    work: `${work}.tess`,
    lang: r.language || 'la',
    ref: r.ref_start || '',
    refEnd: r.ref_end || r.ref_start || '',
    tab: 'similar',
  });
  return `/read?${params.toString()}`;
}

export function MentionRow({ r }) {
  const shared = sharedLabel(r.shared_with);
  return (
    <li className="py-2 border-t border-gray-100 first:border-t-0" data-testid="mention-row">
      <div className="flex flex-wrap items-baseline gap-x-2 text-xs text-gray-500">
        <a href={readerHref(r)} target="_blank" rel="noreferrer"
           className="text-red-700 hover:underline font-semibold text-sm" title={r.window_locus ? `in the passage ${r.window_locus}` : fullRef(r)}>
          {r.locus || windowLocus(r) || 'passage'}
        </a>
        {shared && <span className="text-gray-500" data-testid="shared-label">{shared}</span>}
        {r.restricted && r.credit && <span>{r.credit}</span>}
      </div>
      <p className="text-sm text-gray-900 mt-1 whitespace-pre-line" lang={r.language}>
        <MarkedText text={r.text} token={r.token} />
      </p>
    </li>
  );
}

function WorkGroup({ entityId, w }) {
  const [open, setOpen] = useState(false);
  const [rows, setRows] = useState([]);
  const [total, setTotal] = useState(w.count);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  const load = useCallback((offset) => {
    setBusy(true);
    setError(null);
    const p = new URLSearchParams({ work: w.work, lang: w.language, offset: String(offset), limit: String(PAGE) });
    fetch(`/api/entities/${encodeURIComponent(entityId)}/mentions?${p}`)
      .then((r) => { if (!r.ok) throw new Error(`Server answered ${r.status}`); return r.json(); })
      .then((d) => { setRows((prev) => (offset === 0 ? d.results : prev.concat(d.results))); setTotal(d.total); })
      .catch((e) => setError(e.message))
      .finally(() => setBusy(false));
  }, [entityId, w.work, w.language]);

  const toggle = () => {
    const next = !open;
    setOpen(next);
    if (next && rows.length === 0) load(0);
  };

  return (
    <section className="bg-white border border-gray-200 rounded-lg mb-2" data-testid="work-group">
      <button type="button" onClick={toggle} aria-expanded={open}
              className="w-full text-left px-3 py-2 flex flex-wrap items-baseline gap-x-2">
        <span className="font-semibold text-gray-900">{w.author ? `${w.author}, ` : ''}{w.title || w.work}</span>
        <span className="text-xs text-gray-500">
          <span className="uppercase tracking-wide">{languageName(w.language)}</span>
          {' · '}{w.count} {w.count === 1 ? 'line' : 'lines'}
        </span>
        <span className="ml-auto text-xs text-gray-500">{open ? 'Hide' : 'Show'}</span>
      </button>
      {open && (
        <div className="px-3 pb-2">
          {error && <p className="text-sm text-red-700">Mentions could not be loaded ({error}).</p>}
          <ul>{rows.map((r) => <MentionRow key={r.window_id} r={r} />)}</ul>
          {busy && <LoadingSpinner text="Loading..." />}
          {!busy && rows.length < total && (
            <button type="button" onClick={() => load(rows.length)}
                    className="mt-2 text-sm text-red-700 hover:underline">
              Show more ({total - rows.length} lines left)
            </button>
          )}
        </div>
      )}
    </section>
  );
}

const DOC_PAGE = 50;

export function documentHref(r) {
  return `/document?doc=${encodeURIComponent(r.doc_id)}&lang=${encodeURIComponent(r.language)}&documents=1`;
}

function CreditLine({ credit }) {
  const c = credit || {};
  if (!(c.source_name || c.source_url || c.licence_name)) return <span>Credit not recorded.</span>;
  return (
    <span>
      Text:{' '}
      {c.source_url ? (
        <a href={c.source_url} target="_blank" rel="noopener noreferrer" className="text-red-700 hover:underline">
          {c.source_name || 'source'}
        </a>
      ) : c.source_name}
      {c.licence_name && <span>, {c.licence_name}</span>}
    </span>
  );
}

export function DocumentRow({ r }) {
  const labels = documentLabels(r);
  const place = documentPlace(r);
  const date = documentDateLabel(r);
  return (
    <li className="py-2 border-t border-gray-100 first:border-t-0" data-testid="document-row">
      <div className="flex flex-wrap items-baseline gap-x-2 text-xs text-gray-500">
        <a href={documentHref(r)} className="text-red-700 hover:underline font-semibold text-sm">
          {r.credit?.principal_edition || r.doc_id}
        </a>
        <span>{[date, place, r.region].filter(Boolean).join(' · ')}</span>
        {labels.map((lab) => <span key={lab} className="px-1.5 bg-gray-100 text-gray-600 rounded">{lab}</span>)}
        {r.adjective && <span>(adjective form)</span>}
      </div>
      {r.text && (
        <p className="text-sm text-gray-900 mt-1" lang={r.language}>
          <MarkedText text={r.text} token={r.matched_form} ignoreCase />
        </p>
      )}
      <p className="text-xs text-gray-500 mt-1"><CreditLine credit={r.credit} /></p>
    </li>
  );
}

function DocumentGroup({ entityId, lang, count }) {
  const [open, setOpen] = useState(false);
  const [rows, setRows] = useState([]);
  const [total, setTotal] = useState(count);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  const load = useCallback((offset) => {
    setBusy(true);
    setError(null);
    const p = new URLSearchParams({ lang, offset: String(offset), limit: String(DOC_PAGE) });
    fetch(`/api/entities/${encodeURIComponent(entityId)}/documents?${p}`)
      .then((r) => { if (!r.ok) throw new Error(`Server answered ${r.status}`); return r.json(); })
      .then((d) => { setRows((prev) => (offset === 0 ? d.results : prev.concat(d.results))); setTotal(d.total); })
      .catch((e) => setError(e.message))
      .finally(() => setBusy(false));
  }, [entityId, lang]);

  const toggle = () => {
    const next = !open;
    setOpen(next);
    if (next && rows.length === 0) load(0);
  };

  return (
    <section className="bg-white border border-gray-200 rounded-lg mb-2" data-testid="document-group">
      <button type="button" onClick={toggle} aria-expanded={open}
              className="w-full text-left px-3 py-2 flex flex-wrap items-baseline gap-x-2">
        <span className="font-semibold text-gray-900">Inscriptions and papyri</span>
        <span className="text-xs text-gray-500">
          <span className="uppercase tracking-wide">{languageName(lang)}</span>
          {' · '}{count} {count === 1 ? 'document' : 'documents'}
        </span>
        <span className="ml-auto text-xs text-gray-500">{open ? 'Hide' : 'Show'}</span>
      </button>
      {open && (
        <div className="px-3 pb-2">
          {error && <p className="text-sm text-red-700">Documents could not be loaded ({error}).</p>}
          <ul>{rows.map((r) => <DocumentRow key={`${r.doc_id}`} r={r} />)}</ul>
          {busy && <LoadingSpinner text="Loading..." />}
          {!busy && rows.length < total && (
            <button type="button" onClick={() => load(rows.length)} className="mt-2 text-sm text-red-700 hover:underline">
              Show more ({total - rows.length} left)
            </button>
          )}
        </div>
      )}
    </section>
  );
}

function EntityView({ id, back, open }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    let dead = false;
    setData(null);
    setError(null);
    fetch(`/api/entities/${encodeURIComponent(id)}`)
      .then((r) => { if (!r.ok) throw new Error(r.status === 503 ? 'the mentions store is not installed' : `server answered ${r.status}`); return r.json(); })
      .then((d) => { if (!dead) setData(d); })
      .catch((e) => { if (!dead) setError(e.message); });
    return () => { dead = true; };
  }, [id]);

  return (
    <div>
      <button type="button" onClick={back} className="text-sm text-red-700 hover:underline mb-3">
        Back to the list
      </button>
      {error && <p className="text-sm text-red-700">This entry could not be loaded ({error}).</p>}
      {!data && !error && <LoadingSpinner text="Loading..." />}
      {data && (
        <>
          <h3 className="text-xl font-bold text-gray-900">{headingOf(data)}</h3>
          {data.description && <p className="text-sm text-gray-800 mt-0.5" data-testid="entity-description">{data.description}</p>}
          {data.provenance && <p className="text-xs text-gray-500 mt-0.5" data-testid="entity-provenance">{data.provenance}</p>}
          <p className="text-xs text-gray-600 mt-0.5">
            {TYPE_LABEL[data.type] || 'Other'}
            {data.identifiers?.pleiades?.length > 0 && ` · Pleiades ${data.identifiers.pleiades.slice(0, 3).join(', ')}`}
            {' · '}<CountsLine counts={data.mention_counts} />
          </p>
          {data.label_shared && (
            <p className="text-xs text-gray-500 mt-1">
              {data.label_shared_with?.length > 0
                ? sharedLabel(data.label_shared_with)
                : 'Some mentions share their name with another entry and are marked below.'}
            </p>
          )}
          {data.corpus_names?.length > 0 && (
            <p className="text-xs text-gray-600 mt-1" data-testid="corpus-names">
              Named in the corpus as{' '}
              {data.corpus_names.map((n, i) => (
                <span key={n.id}>
                  {i > 0 && ', '}
                  <a href={`/mentions?e=${encodeURIComponent(n.id)}`}
                     onClick={(ev) => { ev.preventDefault(); open(n.id); }}
                     className="text-red-700 hover:underline">{n.label}</a>
                  {' '}({n.mentions_total}){n.adjective ? ' (adjective)' : ''}
                </span>
              ))}
            </p>
          )}
          <h4 className="text-sm font-semibold text-gray-700 mt-4 mb-2">Mentions by work</h4>
          {data.works.length === 0 && <p className="text-sm text-gray-600">No mentions found.</p>}
          {data.works.map((w) => <WorkGroup key={`${w.work}|${w.language}`} entityId={data.id} w={w} />)}
          {Object.keys(data.document_counts || {}).length > 0 && (
            <>
              <h4 className="text-sm font-semibold text-gray-700 mt-4 mb-2">Inscriptions and papyri</h4>
              {sortedCounts(data.document_counts).map(([lg, n]) => (
                <DocumentGroup key={lg} entityId={data.id} lang={lg} count={n} />
              ))}
            </>
          )}
        </>
      )}
    </div>
  );
}

function EntityResult({ e, open }) {
  return (
    <li className="bg-white border border-gray-200 rounded-lg p-3" data-testid="entity-result">
      <a href={`/mentions?e=${encodeURIComponent(e.id)}`}
         onClick={(ev) => { ev.preventDefault(); open(e.id); }}
         className="text-red-700 hover:underline font-semibold">
        {headingOf(e)}
      </a>
      <p className="text-xs text-gray-600 mt-0.5">
        {TYPE_LABEL[e.type] || 'Other'} · <CountsLine counts={e.mention_counts} />
      </p>
      {e.description && <p className="text-xs text-gray-700 mt-0.5" data-testid="result-description">{e.description}</p>}
      {e.provenance && <p className="text-xs text-gray-500 mt-0.5" data-testid="result-provenance">{e.provenance}</p>}
      {e.label_shared && (
        <p className="text-xs text-gray-500 mt-0.5">
          {e.label_shared_with?.length > 0 ? sharedLabel(e.label_shared_with) : 'some mentions share their name with another entry'}
        </p>
      )}
    </li>
  );
}

function entityFromAddress() {
  return new URLSearchParams(window.location.search).get('e');
}

/** The name a link such as the Reader's "Shared names" carries in ?q=, trimmed. */
function queryFromAddress() {
  return (new URLSearchParams(window.location.search).get('q') || '').trim();
}

/**
 * Mentions (trial, ?entities=1): search a place, person or god by name, then read every
 * passage that names it, grouped by work, each with a link into the Reader.
 * Without the switch the page does not exist: a direct link lands on Search.
 */
export default function MentionsPage({ setPageType }) {
  const allowed = entitiesTrialOn();
  const [typed, setTyped] = useState(queryFromAddress);
  const [q, setQ] = useState(queryFromAddress);
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [entityId, setEntityId] = useState(entityFromAddress);

  useEffect(() => {
    if (!allowed && setPageType) setPageType('search');
  }, [allowed, setPageType]);

  useEffect(() => {
    const onPop = () => setEntityId(entityFromAddress());
    window.addEventListener('popstate', onPop);
    return () => window.removeEventListener('popstate', onPop);
  }, []);

  useEffect(() => {
    if (!allowed || q.length < 2) { setData(null); return undefined; }
    let dead = false;
    setError(null);
    fetch(`/api/entities/search?q=${encodeURIComponent(q)}`)
      .then((r) => r.json().then((d) => ({ ok: r.ok, status: r.status, d })))
      .then(({ ok, status, d }) => {
        if (dead) return;
        if (!ok) throw new Error(status === 503 ? (d.error || 'the mentions store is not installed') : `server answered ${status}`);
        setData(d);
      })
      .catch((e) => { if (!dead) setError(e.message); });
    return () => { dead = true; };
  }, [q, allowed]);

  const open = (id) => {
    const url = `/mentions?e=${encodeURIComponent(id)}`;
    window.history.pushState({}, '', url);
    setEntityId(id);
    window.scrollTo?.(0, 0);
  };
  const back = () => {
    window.history.pushState({}, '', '/mentions');
    setEntityId(null);
  };
  const submit = (e) => { e.preventDefault(); setQ(typed.trim()); };

  if (!allowed) return null;
  return (
    <div className="max-w-4xl mx-auto px-4 py-6">
      <h2 className="text-2xl font-bold text-gray-900">Mentions</h2>
      <p className="text-xs text-gray-500 mt-1 mb-4" data-testid="trial-note">{TRIAL_NOTE}</p>
      {entityId ? <EntityView id={entityId} back={back} open={open} /> : (
        <>
          <form onSubmit={submit} className="bg-white border border-gray-200 rounded-lg p-3 flex gap-2 items-end">
            <label className="flex-1 text-xs text-gray-600">
              A place, person or god
              <input value={typed} onChange={(e) => setTyped(e.target.value)} placeholder="Troy"
                     className="mt-1 block w-full border border-gray-300 rounded px-2 py-1.5 text-sm text-gray-900" />
            </label>
            <button type="submit" className="px-3 py-1.5 text-sm rounded bg-red-700 text-white hover:bg-red-800">
              Search
            </button>
          </form>
          <div className="mt-4">
            {error && <p className="text-sm text-red-700">Mentions could not be searched ({error}).</p>}
            {data && data.results.length === 0 && (
              <div className="text-sm text-gray-600 bg-white border border-gray-200 rounded-lg p-4">
                <p>No place, person or god matches. Try a shorter name or another spelling.</p>
                {data.suggestions?.length > 0 && (
                  <p className="mt-2" data-testid="suggestions">
                    Did you mean{' '}
                    {data.suggestions.map((sg, i) => (
                      <span key={sg.id}>
                        {i > 0 && (i === data.suggestions.length - 1 ? ' or ' : ', ')}
                        <a href={`/mentions?e=${encodeURIComponent(sg.id)}`}
                           onClick={(ev) => { ev.preventDefault(); open(sg.id); }}
                           className="text-red-700 hover:underline font-semibold">{sg.label}</a>
                      </span>
                    ))}
                    ?
                  </p>
                )}
              </div>
            )}
            {data && data.results.length > 0 && (
              <>
                <p className="text-xs text-gray-500 mb-2">
                  {data.total} {data.total === 1 ? 'match' : 'matches'}{data.total > data.results.length ? `, the first ${data.results.length} shown` : ''}
                </p>
                <ul className="space-y-2">
                  {data.results.filter((e) => e.source !== 'corpus').map((e) => <EntityResult key={e.id} e={e} open={open} />)}
                </ul>
                {data.near_spellings?.length > 0 && (
                  <>
                    <h3 className="text-sm font-semibold text-gray-500 mt-4 mb-2" data-testid="near-heading">Near spellings</h3>
                    <ul className="space-y-2">
                      {data.near_spellings.map((e) => <EntityResult key={e.id} e={e} open={open} />)}
                    </ul>
                  </>
                )}
                {data.results.some((e) => e.source === 'corpus') && (
                  <>
                    <h3 className="text-sm font-semibold text-gray-500 mt-4 mb-2" data-testid="corpus-heading">Names in the corpus</h3>
                    <ul className="space-y-2">
                      {data.results.filter((e) => e.source === 'corpus').map((e) => <EntityResult key={e.id} e={e} open={open} />)}
                    </ul>
                  </>
                )}
              </>
            )}
          </div>
        </>
      )}
    </div>
  );
}
