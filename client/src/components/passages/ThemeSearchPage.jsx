import { useCallback, useState } from 'react';

/**
 * Theme Search: describe a passage in your own words, get passages that match
 * the DESCRIPTION rather than the wording.
 *
 * This had no interface at all. The route and the MCP tool existed, and content
 * search was called "live" on the strength of them, but no reader could reach
 * it without writing an HTTP request. This is that page.
 *
 * The confidence band is shown because the API reports one and the reader has
 * no other way to tell a real subject from a near miss. "A farmer lifts potatoes
 * out of the ground" scores higher than eight genuine classical subjects,
 * because everything in it but the potato is in the corpus, so the band is
 * doing real work and hiding it would be worse than showing it.
 */

const EXAMPLES = [
  'a warrior arms himself before battle, piece by piece',
  'a city falls and its people are led away captive',
  'a descent into the world of the dead to consult a shade',
  'a storm at sea scatters a fleet and the crew despairs',
];

const BAND = {
  strong: {
    label: 'Strong match',
    className: 'bg-red-50 text-red-800 border-red-200',
  },
  moderate: {
    label: 'Moderate match',
    className: 'bg-amber-50 text-amber-800 border-amber-200',
  },
  low: {
    label: 'Weak match',
    className: 'bg-gray-100 text-gray-700 border-gray-300',
  },
};

const LANG_LABEL = {
  la: 'Latin', grc: 'Greek', he: 'Hebrew', cop: 'Coptic',
  en: 'English', fa: 'Persian', ur: 'Urdu',
};

export default function ThemeSearchPage() {
  const [query, setQuery] = useState('');
  const [data, setData] = useState(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState(null);

  const run = useCallback(async (q) => {
    const text = (q || '').trim();
    if (!text || running) return;
    setRunning(true);
    setError(null);
    setData(null);
    try {
      const res = await fetch(
        `/api/passages/theme-search?query=${encodeURIComponent(text)}&limit=25`);
      const json = await res.json();
      // The API reports trouble in the body rather than by status, so that a
      // missing index degrades this panel instead of breaking the page.
      if (json.error) setError(json.error);
      else setData(json);
    } catch (e) {
      setError(e.message || 'the search could not be run');
    } finally {
      setRunning(false);
    }
  }, [running]);

  const band = data && BAND[data.confidence?.level];

  return (
    <div className="max-w-4xl mx-auto p-6">
      <h1 className="text-2xl font-semibold text-gray-900">Theme Search</h1>
      <p className="mt-2 text-sm text-gray-600 leading-relaxed">
        Describe what happens in a passage and this finds passages that match the
        description, not the words. Because it works from content, results come
        back in every indexed language at once and usually share no vocabulary
        with what you typed, or with each other.
      </p>

      <form
        className="mt-5 flex gap-2"
        onSubmit={(e) => { e.preventDefault(); run(query); }}
      >
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="a warrior arms himself before battle"
          className="flex-1 border border-gray-300 rounded px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-red-600"
        />
        <button
          type="submit"
          disabled={running || !query.trim()}
          className="px-4 py-2 rounded bg-red-700 text-white text-sm font-medium hover:bg-red-800 disabled:opacity-40"
        >
          {running ? 'Searching…' : 'Search'}
        </button>
      </form>

      <div className="mt-3 flex flex-wrap gap-2">
        {EXAMPLES.map((ex) => (
          <button
            key={ex}
            onClick={() => { setQuery(ex); run(ex); }}
            className="text-xs text-red-700 hover:text-red-900 hover:bg-red-50 border border-gray-200 rounded px-2 py-1"
          >
            {ex}
          </button>
        ))}
      </div>

      {running && (
        <p className="mt-6 text-sm text-gray-500 italic">
          Comparing your description against every indexed passage…
        </p>
      )}

      {error && (
        <div className="mt-6 rounded border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">
          {error}
        </div>
      )}

      {data && (
        <div className="mt-6">
          {band && (
            <div className={`rounded border px-3 py-2 text-sm ${band.className}`}>
              <strong className="font-semibold">{band.label}.</strong>{' '}
              {data.note || 'The corpus holds passages of this kind.'}
            </div>
          )}

          {!data.results?.length && (
            <p className="mt-4 text-sm text-gray-600">
              Nothing in the corpus resembles that description.
            </p>
          )}

          <ul className="mt-4 space-y-3">
            {(data.results || []).map((r) => (
              <li key={r.id || `${r.work}-${r.ref_start}`}
                  className="border border-gray-200 rounded p-3 bg-white">
                <div className="flex items-baseline gap-2 flex-wrap">
                  <span className="text-[10px] uppercase tracking-wide text-gray-500">
                    {LANG_LABEL[r.language] || r.language}
                  </span>
                  <span className="font-medium text-gray-900">{r.title || r.work}</span>
                  <span className="text-sm text-gray-500">{r.ref_start}</span>
                  {r.strong === false && (
                    <span className="text-[10px] text-gray-500 border border-gray-300 rounded px-1">
                      weak neighbour
                    </span>
                  )}
                </div>
                {r.gist && (
                  <p className="mt-1 text-sm text-gray-700 leading-snug">{r.gist}</p>
                )}
                {!!(r.themes || []).length && (
                  <div className="mt-2 flex flex-wrap gap-1">
                    {r.themes.slice(0, 5).map((t) => (
                      <span key={t}
                            className="text-[11px] bg-gray-100 text-gray-600 rounded px-1.5 py-0.5">
                        {t}
                      </span>
                    ))}
                  </div>
                )}
              </li>
            ))}
          </ul>

          <p className="mt-5 text-xs text-gray-500 leading-relaxed">
            These summaries are written by a language model from the passage
            itself, and for Coptic from its English translation, so treat them as
            a finding aid rather than as evidence. Read the passage before citing
            it.
          </p>
        </div>
      )}
    </div>
  );
}
