import { useEffect, useState } from 'react';
import { LoadingSpinner } from '../common';
import { dateLabel, centuryLabel } from './eventsFormat';

const PER_PAGE = 20;

/** The Events page: every event in the dossier database, searchable and filterable. */
export default function EventList({ openEvent }) {
  const [q, setQ] = useState('');
  const [typed, setTyped] = useState('');
  const [type, setType] = useState('');
  const [century, setCentury] = useState('');
  const [page, setPage] = useState(1);
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    let dead = false;
    setError(null);
    const p = new URLSearchParams({ page: String(page), per_page: String(PER_PAGE) });
    if (q) p.set('q', q);
    if (type) p.set('type', type);
    if (century) p.set('century', century);
    fetch(`/api/events?${p}`)
      .then((r) => { if (!r.ok) throw new Error(`Server answered ${r.status}`); return r.json(); })
      .then((d) => { if (!dead) setData(d); })
      .catch((e) => { if (!dead) setError(e.message); });
    return () => { dead = true; };
  }, [q, type, century, page]);

  const pages = data ? Math.max(1, Math.ceil(data.total / (data.per_page || PER_PAGE))) : 1;
  const submit = (e) => { e.preventDefault(); setPage(1); setQ(typed.trim()); };

  return (
    <div className="max-w-4xl mx-auto px-4 py-6">
      <h2 className="text-2xl font-bold text-gray-900">Events</h2>
      <p className="text-sm text-gray-600 mt-1 mb-4">
        Battles, sieges and treaties, each with the passages that tell of it, the inscriptions and
        papyri from nearby and from the same years, and the scholarship on those passages. In testing.
      </p>

      <form onSubmit={submit} className="bg-white border border-gray-200 rounded-lg p-3 flex flex-wrap gap-2 items-end">
        <label className="flex-1 min-w-[12rem] text-xs text-gray-600">
          Search by name or place
          <input value={typed} onChange={(e) => setTyped(e.target.value)} placeholder="Cannae"
                 className="mt-1 block w-full border border-gray-300 rounded px-2 py-1.5 text-sm text-gray-900" />
        </label>
        <label className="text-xs text-gray-600">
          Type
          <select value={type} onChange={(e) => { setType(e.target.value); setPage(1); }}
                  className="mt-1 block border border-gray-300 rounded px-2 py-1.5 text-sm text-gray-900">
            <option value="">All types</option>
            {(data?.types || []).map((t) => <option key={t} value={t}>{t}</option>)}
          </select>
        </label>
        <label className="text-xs text-gray-600">
          Century
          <select value={century} onChange={(e) => { setCentury(e.target.value); setPage(1); }}
                  className="mt-1 block border border-gray-300 rounded px-2 py-1.5 text-sm text-gray-900">
            <option value="">Any century</option>
            {(data?.centuries || []).map((c) => <option key={c} value={c}>{centuryLabel(c)}</option>)}
          </select>
        </label>
        <button type="submit" className="px-3 py-1.5 text-sm rounded bg-red-700 text-white hover:bg-red-800">
          Search
        </button>
      </form>

      <div className="mt-4">
        {error && <p className="text-sm text-red-700">Events could not be loaded ({error}).</p>}
        {!data && !error && <div className="py-8"><LoadingSpinner text="Loading events..." /></div>}
        {data && data.available === false && (
          <p className="text-sm text-gray-600 bg-white border border-gray-200 rounded-lg p-4">
            The event dossiers are not installed on this server yet.
          </p>
        )}
        {data && data.available !== false && (
          <>
            <p className="text-xs text-gray-500 mb-2" data-testid="events-total">
              {data.total} {data.total === 1 ? 'event' : 'events'}
            </p>
            {data.events.length === 0 && (
              <p className="text-sm text-gray-600 bg-white border border-gray-200 rounded-lg p-4">
                No event matches. Try a shorter name or clear the filters.
              </p>
            )}
            <ul className="space-y-2">
              {data.events.map((e) => (
                <li key={e.id} className="bg-white border border-gray-200 rounded-lg p-3">
                  <a href={`/events/${encodeURIComponent(e.id)}`}
                     onClick={(ev) => { ev.preventDefault(); openEvent(e.id); }}
                     className="text-red-700 hover:underline font-semibold">
                    {e.label}
                  </a>
                  <p className="text-xs text-gray-600 mt-0.5">
                    {[dateLabel(e.date_start, e.date_end), e.place, e.type].filter(Boolean).join(' · ')}
                  </p>
                  <p className="text-xs text-gray-500 mt-1">
                    {e.n_passages} {e.n_passages === 1 ? 'passage' : 'passages'}
                    {' · '}{e.n_documents} {e.n_documents === 1 ? 'document' : 'documents'}
                    {' · '}{e.n_scholarship} scholarship {e.n_scholarship === 1 ? 'item' : 'items'}
                  </p>
                </li>
              ))}
            </ul>
            {pages > 1 && (
              <div className="flex items-center justify-center gap-3 mt-4 text-sm">
                <button disabled={page <= 1} onClick={() => setPage(page - 1)}
                        className="px-3 py-1 border border-gray-300 rounded disabled:opacity-40">Previous</button>
                <span className="text-gray-600">Page {page} of {pages}</span>
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
