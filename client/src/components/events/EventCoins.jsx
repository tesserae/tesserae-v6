import { useEffect, useState } from 'react';
import { LoadingSpinner } from '../common';
import CoinMatchCard from '../coins/CoinMatchCard';

/**
 * Fetch an event's coins. The event page calls this when it opens, so the
 * tab can show its count, and hands the result to EventCoins.
 */
export function useEventCoins(eventId) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    let dead = false;
    setData(null);
    setError(null);
    if (!eventId) return () => { dead = true; };
    fetch(`/api/events/${encodeURIComponent(eventId)}/coins`)
      .then(async (r) => {
        const d = await r.json().catch(() => ({}));
        if (!r.ok) throw new Error(d.reason || d.error || `Server answered ${r.status}`);
        return d;
      })
      .then((d) => { if (!dead) setData(d); })
      .catch((e) => { if (!dead) setError(e.message); });
    return () => { dead = true; };
  }, [eventId]);

  return { data, error };
}

/** The number for the tab label, or undefined while loading or when none can be shown. */
export function eventCoinsCount({ data }) {
  return data?.available ? (data.results || []).length : undefined;
}

/**
 * An event's Coins tab: the coin types struck around the event's date,
 * nearest in meaning to it, those whose model-written account names the
 * place first. Given `coins` (from useEventCoins) it shows that; alone it
 * fetches for itself.
 */
export default function EventCoins({ eventId, coins }) {
  const own = useEventCoins(coins ? null : eventId);
  const { data, error } = coins || own;

  if (error) return <p className="text-sm text-red-700">{error}</p>;
  if (!data) return <LoadingSpinner text="Finding coins..." />;
  if (!data.available) return <p className="text-sm text-gray-600">{data.reason || 'No coins can be shown for this event.'}</p>;
  const results = data.results || [];
  return (
    <div data-testid="event-coins">
      <p className="text-xs text-gray-500 mb-3">{data.label}</p>
      {results.length === 0
        ? <p className="text-sm text-gray-600">No coin type is dated to these years.</p>
        : (
          <ul className="space-y-2">
            {results.map((m) => <CoinMatchCard key={m.coin_id || m.description} match={m} showLevel={false} />)}
          </ul>
        )}
    </div>
  );
}
