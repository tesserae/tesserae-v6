import { useEffect, useState } from 'react';
import { LoadingSpinner } from '../common';
import { YearBox } from '../coins/CoinList';
import ObjectCard from './ObjectCard';
import { signedYear, MUSEUM_NAMES } from './objectsFormat';

const PER_PAGE = 24;
const FILTERS = [
  ['museum', 'Museum'],
  ['object_type', 'Object type'],
  ['culture', 'Culture'],
  ['material', 'Material'],
];

/** The Objects page: every object, searched over title, description, label and inscription, and filtered. */
export default function ObjectList({ openObject }) {
  const [typed, setTyped] = useState('');
  const [q, setQ] = useState('');
  const [sel, setSel] = useState({});
  const [fromText, setFromText] = useState('');
  const [fromEra, setFromEra] = useState('BCE');
  const [toText, setToText] = useState('');
  const [toEra, setToEra] = useState('CE');
  const [dates, setDates] = useState({});
  const [sort, setSort] = useState('');
  const [page, setPage] = useState(1);
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    let dead = false;
    setError(null);
    const p = new URLSearchParams({ page: String(page), per_page: String(PER_PAGE) });
    if (q) p.set('q', q);
    Object.entries(sel).forEach(([k, v]) => { if (v) p.set(k, v); });
    if (dates.from != null) p.set('date_from', String(dates.from));
    if (dates.to != null) p.set('date_to', String(dates.to));
    if (sort) p.set('sort', sort);
    fetch(`/api/objects?${p}`)
      .then((r) => { if (!r.ok) throw new Error(`Server answered ${r.status}`); return r.json(); })
      .then((d) => { if (!dead) setData(d); })
      .catch((e) => { if (!dead) setError(e.message); });
    return () => { dead = true; };
  }, [q, sel, dates, sort, page]);

  const pages = data ? Math.max(1, Math.ceil(data.total / (data.per_page || PER_PAGE))) : 1;
  const submit = (e) => {
    e.preventDefault();
    setPage(1);
    setQ(typed.trim());
    setDates({ from: signedYear(fromText, fromEra), to: signedYear(toText, toEra) });
  };
  const choose = (k, v) => { setSel((s) => ({ ...s, [k]: v })); setPage(1); };
  const clear = () => {
    setTyped(''); setQ(''); setSel({}); setFromText(''); setToText(''); setDates({}); setSort(''); setPage(1);
  };
  const anyFilter = q || Object.values(sel).some(Boolean) || dates.from != null || dates.to != null;

  return (
    <div className="max-w-5xl mx-auto px-4 py-6">
      <h2 className="text-2xl font-bold text-gray-900">Objects</h2>
      <p className="text-sm text-gray-600 mt-1 mb-4">
        Greek, Roman and Etruscan objects from the Cleveland Museum of Art, the Art Institute of Chicago and
        the Smithsonian, searchable by the museums&rsquo; own catalogue descriptions. In testing.
      </p>

      <form onSubmit={submit} className="bg-white border border-gray-200 rounded-lg p-3 space-y-3">
        <div className="flex flex-wrap gap-2 items-end">
          <label className="flex-1 min-w-[12rem] text-xs text-gray-600">
            Search titles and descriptions
            <input value={typed} onChange={(e) => setTyped(e.target.value)} placeholder="Amazons"
                   className="mt-1 block w-full border border-gray-300 rounded px-2 py-1.5 text-sm text-gray-900" />
          </label>
          <button type="submit" className="px-3 py-1.5 text-sm rounded bg-red-700 text-white hover:bg-red-800">
            Search
          </button>
          {anyFilter && (
            <button type="button" onClick={clear} className="px-3 py-1.5 text-sm rounded border border-gray-300 text-gray-700">
              Clear
            </button>
          )}
        </div>
        <div className="flex flex-wrap gap-2 items-end">
          {FILTERS.map(([key, label]) => (
            <label key={key} className="text-xs text-gray-600">
              {label}
              <select value={sel[key] || ''} onChange={(e) => choose(key, e.target.value)} aria-label={label}
                      className="mt-1 block max-w-[14rem] border border-gray-300 rounded px-2 py-1.5 text-sm text-gray-900">
                <option value="">Any</option>
                {(data?.facets?.[key] || []).map((f) => (
                  <option key={f.value} value={f.value}>
                    {(key === 'museum' ? MUSEUM_NAMES[f.value] || f.value : f.value)} ({f.count})
                  </option>
                ))}
              </select>
            </label>
          ))}
          <YearBox label="From" text={fromText} era={fromEra} setText={setFromText} setEra={setFromEra} />
          <YearBox label="To" text={toText} era={toEra} setText={setToText} setEra={setToEra} />
          <label className="text-xs text-gray-600">
            Order
            <select value={sort} onChange={(e) => { setSort(e.target.value); setPage(1); }} aria-label="Order"
                    className="mt-1 block border border-gray-300 rounded px-2 py-1.5 text-sm text-gray-900">
              <option value="">{q ? 'Best match' : 'Date'}</option>
              {q && <option value="date">Date</option>}
            </select>
          </label>
        </div>
      </form>

      <div className="mt-4">
        {error && <p className="text-sm text-red-700">Objects could not be loaded ({error}).</p>}
        {!data && !error && <div className="py-8"><LoadingSpinner text="Loading objects..." /></div>}
        {data && data.available === false && (
          <p className="text-sm text-gray-600 bg-white border border-gray-200 rounded-lg p-4">
            The objects collection is not installed on this server yet.
          </p>
        )}
        {data && data.available !== false && (
          <>
            <p className="text-xs text-gray-500 mb-2" data-testid="objects-total">
              {data.total.toLocaleString('en-US')} {data.total === 1 ? 'object' : 'objects'}
            </p>
            {data.objects.length === 0 && (
              <p className="text-sm text-gray-600 bg-white border border-gray-200 rounded-lg p-4">
                No object matches. Try a shorter word or clear the filters.
              </p>
            )}
            <div className="space-y-3">
              {data.objects.map((o) => <ObjectCard key={o.id} object={o} open={openObject} />)}
            </div>
            {pages > 1 && (
              <div className="flex items-center justify-center gap-3 mt-4 text-sm">
                <button disabled={page <= 1} onClick={() => setPage(page - 1)}
                        className="px-3 py-1 border border-gray-300 rounded disabled:opacity-40">Previous</button>
                <span className="text-gray-600">Page {page} of {pages.toLocaleString('en-US')}</span>
                <button disabled={page >= pages} onClick={() => setPage(page + 1)}
                        className="px-3 py-1 border border-gray-300 rounded disabled:opacity-40">Next</button>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
