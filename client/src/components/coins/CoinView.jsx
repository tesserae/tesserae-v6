import { useEffect, useState } from 'react';
import { LoadingSpinner } from '../common';
import CoinCard from './CoinCard';
import { coinTitle } from './coinsFormat';

/** One coin type on a page of its own (/coins/<id>). */
export default function CoinView({ id, goList }) {
  const [coin, setCoin] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    let dead = false;
    setCoin(null);
    setError(null);
    fetch(`/api/coins/${encodeURIComponent(id)}`)
      .then((r) => {
        if (r.status === 404) throw new Error('No such coin type.');
        if (!r.ok) throw new Error(`Server answered ${r.status}`);
        return r.json();
      })
      .then((d) => { if (!dead) setCoin(d.coin); })
      .catch((e) => { if (!dead) setError(e.message); });
    return () => { dead = true; };
  }, [id]);

  return (
    <div className="max-w-3xl mx-auto px-4 py-6">
      <button type="button" onClick={goList} className="text-sm text-red-700 hover:underline mb-3">
        All coins
      </button>
      {error && <p className="text-sm text-red-700">{error}</p>}
      {!coin && !error && <div className="py-8"><LoadingSpinner text="Loading coin..." /></div>}
      {coin && (
        <>
          <h2 className="sr-only">{coinTitle(coin)}</h2>
          <CoinCard coin={coin} />
          <dl className="mt-4 bg-white border border-gray-200 rounded-lg p-4 text-sm grid sm:grid-cols-2 gap-x-6 gap-y-2">
            {coin.portrait && <div><dt className="text-xs uppercase tracking-wide text-gray-500">Obverse portrait</dt><dd>{coin.portrait}</dd></div>}
            {coin.region && <div><dt className="text-xs uppercase tracking-wide text-gray-500">Region</dt><dd>{coin.region}</dd></div>}
            <div><dt className="text-xs uppercase tracking-wide text-gray-500">Identifier</dt><dd className="break-all">{coin.id}</dd></div>
          </dl>
          <p className="text-xs text-gray-500 mt-3">
            Images are not held here. The type page lists the museum specimens and their photographs.
          </p>
        </>
      )}
    </div>
  );
}
