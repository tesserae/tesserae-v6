import { useEffect, useState } from 'react';
import { LoadingSpinner } from '../common';
import { CoinSides } from './CoinCard';
import { catalogueLine, catalogueName, coinHeading, creditLine } from './coinsFormat';

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

  const issuer = coin && [coin.authority, coin.issuer].filter(Boolean).join(', issued by ');

  return (
    <div className="max-w-3xl mx-auto px-4 py-6">
      <button type="button" onClick={goList} className="text-sm text-red-700 hover:underline mb-3">
        All coins
      </button>
      {error && <p className="text-sm text-red-700">{error}</p>}
      {!coin && !error && <div className="py-8"><LoadingSpinner text="Loading coin..." /></div>}
      {coin && (
        <article className="bg-white border border-gray-200 rounded-lg p-5" data-testid="coin-page">
          <h2 className="text-xl font-semibold text-gray-900">{coinHeading(coin)}</h2>
          <p className="text-sm text-gray-500 mt-0.5">{catalogueLine(coin)}</p>

          <div className="mt-4"><CoinSides coin={coin} /></div>

          <div className="mt-4 text-sm space-y-1">
            <p>
              <span className="text-gray-500">Issued by:</span>{' '}
              {issuer ? <span className="text-gray-900">{issuer}</span>
                : <span className="text-gray-400">not recorded</span>}
            </p>
            {coin.portrait && (
              <p><span className="text-gray-500">Portrait:</span>{' '}
                <span className="text-gray-900">{coin.portrait}</span></p>
            )}
            {coin.mint && (
              <p><span className="text-gray-500">Mint:</span>{' '}
                {coin.pleiades_url
                  ? <a href={coin.pleiades_url} target="_blank" rel="noopener noreferrer"
                       className="text-red-700 hover:underline">{coin.mint}</a>
                  : <span className="text-gray-900">{coin.mint}</span>}
              </p>
            )}
            {coin.region && (
              <p><span className="text-gray-500">Region:</span>{' '}
                <span className="text-gray-900">{coin.region}</span></p>
            )}
          </div>

          <div className="mt-5 flex justify-end">
            <a href={coin.uri || coin.type_url} target="_blank" rel="noopener noreferrer"
               className="inline-block rounded border border-red-700 px-3 py-1.5 text-sm font-medium
                          text-red-700 hover:bg-red-50">
              See coin images at {catalogueName(coin)} &#8599;
            </a>
          </div>
          <p className="text-xs text-gray-500 mt-3">
            Photographs are on the catalogue&rsquo;s page for this type, with the museum specimens.
          </p>
          <p className="text-xs text-gray-400 mt-2">{creditLine(coin)}</p>
        </article>
      )}
    </div>
  );
}
