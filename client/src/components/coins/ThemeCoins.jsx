import { useEffect, useState } from 'react';
import { LoadingSpinner } from '../common';
import CoinMatchCard from './CoinMatchCard';

/**
 * The Coins option of Theme Search: the coin descriptions nearest the query,
 * on their own, never mixed into the passage ranking. Its confidence label is
 * its own (GET /api/coins/theme says what was measured).
 */
export default function ThemeCoins({ search }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!search?.q) return undefined;
    let dead = false;
    setData(null);
    setError(null);
    fetch(`/api/coins/theme?q=${encodeURIComponent(search.q)}&limit=10`)
      .then((r) => { if (!r.ok) throw new Error(`Server answered ${r.status}`); return r.json(); })
      .then((d) => { if (!dead) setData(d); })
      .catch((e) => { if (!dead) setError(e.message); });
    return () => { dead = true; };
  }, [search]);

  if (!search?.q) {
    return <p className="mt-4 text-sm text-gray-600">Describe an image a coin might carry, then press Search.</p>;
  }
  if (error) return <p className="mt-4 text-sm text-red-700">Coins could not be searched ({error}).</p>;
  if (!data) return <div className="mt-4"><LoadingSpinner text="Searching coin descriptions..." /></div>;
  if (data.available === false) {
    return <p className="mt-4 text-sm text-gray-600">The coins collection is not installed on this server yet.</p>;
  }
  if (data.unavailable) return <p className="mt-4 text-sm text-gray-600">{data.error}</p>;
  return (
    <div className="mt-4" data-testid="theme-coins">
      <p className="text-xs text-gray-500" data-testid="theme-coins-label">{data.label}</p>
      <ul className="mt-2 space-y-2">
        {(data.results || []).map((m) => <CoinMatchCard key={m.description} match={m} />)}
      </ul>
      {(data.results || []).length === 0 && <p className="text-sm text-gray-600">Nothing close was found.</p>}
    </div>
  );
}

