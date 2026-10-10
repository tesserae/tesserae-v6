import { useEffect, useState } from 'react';
import { LoadingSpinner } from '../common';
import CoinMatchCard from '../coins/CoinMatchCard';

/**
 * The Reader's Coins tab. Two lists, kept apart because they mean different
 * things. "Named on coins" is a name link: a person who is named on a coin
 * (authority or obverse portrait) and in the selected lines. It is not an echo.
 * "Related imagery" is the coin descriptions closest in meaning to the gist of
 * the passage's window, about one in three of which is a real parallel.
 */
export default function CoinsTab({ work, language, selection, units }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!selection) return undefined;
    let dead = false;
    setLoading(true);
    setError(null);
    const p = new URLSearchParams({
      work,
      lang: language,
      ref: selection.refStart || '',
      ref_end: selection.refEnd || selection.refStart || '',
    });
    fetch(`/api/coins/for-passage?${p}`)
      .then((r) => { if (!r.ok) throw new Error(`Server answered ${r.status}`); return r.json(); })
      .then((d) => { if (!dead) setData(d); })
      .catch((e) => { if (!dead) setError(e.message); })
      .finally(() => { if (!dead) setLoading(false); });
    return () => { dead = true; };
  }, [work, language, selection, units]);

  if (!selection) {
    return <p className="text-sm text-gray-500">Select a line or a span to see coins that name the same people or show a related scene.</p>;
  }
  if (loading) return <LoadingSpinner />;
  if (error) return <p className="text-sm text-red-700">Coins could not be loaded ({error}).</p>;
  if (!data) return null;
  if (data.available === false) {
    return <p className="text-sm text-gray-600">The coins collection is not installed on this server yet.</p>;
  }
  if (data.unavailable) return <p className="text-sm text-gray-600">{data.error}</p>;

  const names = data.name_links || [];
  const related = data.related || [];
  return (
    <div className="space-y-4">
      <section>
        <h4 className="text-xs font-semibold uppercase tracking-wide text-gray-600"
            title="A name link, not an echo: the coin names the same person, it does not quote the passage.">
          Named on coins
        </h4>
        {names.length === 0 ? (
          <p className="text-sm text-gray-500 mt-1">
            {language === 'la'
              ? 'No person named on a coin is named in these lines.'
              : 'Names are matched in Latin passages only.'}
          </p>
        ) : (
          <>
            <ul className="mt-1 space-y-1">
              {names.map((n) => (
                <li key={n.label} className="text-sm">
                  <a href={n.coins_url} className="text-red-700 hover:underline font-medium">{n.name}</a>
                  <span className="text-xs text-gray-500"> · {n.n_types.toLocaleString('en-US')} coin types</span>
                </li>
              ))}
            </ul>
            <p className="text-[11px] text-gray-500 mt-1">{data.name_links_note}</p>
          </>
        )}
      </section>

      <section>
        <h4 className="text-xs font-semibold uppercase tracking-wide text-gray-600">Related imagery</h4>
        {related.length === 0 ? (
          <p className="text-sm text-gray-500 mt-1">{data.note || 'No related coin imagery was found.'}</p>
        ) : (
          <>
            <p className="text-[11px] text-gray-500 mt-1" data-testid="coins-hit-rate">{data.hit_rate_label}</p>
            <ul className="mt-2 space-y-2">
              {related.map((m) => <CoinMatchCard key={m.description} match={m} />)}
            </ul>
          </>
        )}
      </section>
    </div>
  );
}
