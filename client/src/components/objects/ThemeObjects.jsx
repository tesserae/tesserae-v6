import { useEffect, useState } from 'react';
import { LoadingSpinner } from '../common';
import { objectDate, objectTitle, objectPath, accession } from './objectsFormat';

/**
 * The Objects option of Theme Search: the museum descriptions nearest the
 * query, on their own, never mixed into the passage ranking. Its label is its
 * own (GET /api/objects/theme says what has and has not been measured).
 */
export default function ThemeObjects({ search }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!search?.q) return undefined;
    let dead = false;
    setData(null);
    setError(null);
    fetch(`/api/objects/theme?q=${encodeURIComponent(search.q)}&limit=10`)
      .then((r) => { if (!r.ok) throw new Error(`Server answered ${r.status}`); return r.json(); })
      .then((d) => { if (!dead) setData(d); })
      .catch((e) => { if (!dead) setError(e.message); });
    return () => { dead = true; };
  }, [search]);

  if (!search?.q) {
    return <p className="mt-4 text-sm text-gray-600">Describe what a museum object might show or how it was used, then press Search.</p>;
  }
  if (error) return <p className="mt-4 text-sm text-red-700">Objects could not be searched ({error}).</p>;
  if (!data) return <div className="mt-4"><LoadingSpinner text="Searching object descriptions..." /></div>;
  if (data.available === false) {
    return <p className="mt-4 text-sm text-gray-600">The objects collection is not installed on this server yet.</p>;
  }
  if (data.unavailable) return <p className="mt-4 text-sm text-gray-600">{data.error}</p>;
  return (
    <div className="mt-4" data-testid="theme-objects">
      <p className="text-xs text-gray-500" data-testid="theme-objects-label">{data.label}</p>
      <ul className="mt-2 space-y-2">
        {(data.results || []).map((m) => (
          <li key={m.id} className="bg-white border border-gray-200 rounded-lg p-3" data-testid="object-match">
            <p className="text-sm font-semibold">
              <a href={objectPath(m)} className="text-red-700 hover:underline">{objectTitle(m)}</a>
            </p>
            <p className="text-sm text-gray-900 mt-0.5">{m.snippet}</p>
            <p className="text-xs text-gray-600 mt-1">
              {[m.museum_name, accession(m), objectDate(m), m.culture].filter(Boolean).join(' · ')}
            </p>
            <p className="text-[11px] text-gray-500 mt-0.5">{m.credit}</p>
          </li>
        ))}
      </ul>
      {(data.results || []).length === 0 && <p className="text-sm text-gray-600">Nothing close was found.</p>}
    </div>
  );
}
