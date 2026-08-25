const VERDICT_STYLE = {
  verbatim: 'bg-red-100 text-red-800',
  distinctive_lexical: 'bg-red-50 text-red-700',
  moderate_lexical: 'bg-amber-50 text-amber-800',
  thematic: 'bg-violet-50 text-violet-800',
  weak: 'bg-gray-100 text-gray-600',
};

const VERDICT_LABEL = {
  verbatim: 'Verbatim reuse',
  distinctive_lexical: 'Distinctive shared vocabulary',
  moderate_lexical: 'Shared vocabulary, common',
  thematic: 'Thematic resemblance',
  weak: 'Weak',
};

/**
 * The computed part of an analysis, rendered separately from the prose.
 *
 * These figures come from the search engine, not from the model, and the
 * separation is the point: a reader can see which claims are measured and which
 * are narration. They also render the moment the request opens, before any text
 * has been generated, so the panel is useful during the wait rather than blank.
 */
export default function FindingsBlock({ facts }) {
  if (!facts || !facts.n_results) return null;

  const channels = Object.entries(facts.channels_fired || {}).slice(0, 5);
  const verdict = facts.verdict || 'weak';

  return (
    <div className="rounded border border-gray-200 bg-white p-3 space-y-2">
      <div className="flex items-center gap-2 flex-wrap">
        <span className={`px-2 py-0.5 rounded text-[11px] font-semibold ${VERDICT_STYLE[verdict]}`}>
          {VERDICT_LABEL[verdict]}
        </span>
        <span className="text-[11px] text-gray-500">
          measured from {facts.n_results} ranked {facts.n_results === 1 ? 'parallel' : 'parallels'}
        </span>
      </div>

      <p className="text-xs text-gray-600 leading-snug">{facts.verdict_note}</p>

      <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-[11px]">
        <Stat label="Verbatim runs" value={facts.verbatim_pairs} />
        <Stat label="Rare-word pairs" value={facts.rare_word_pairs} />
        <Stat label="Three or more channels" value={facts.multi_channel_pairs} />
        {facts.mean_word_rarity_idf != null && (
          <Stat
            label="Mean word rarity"
            value={`${facts.mean_word_rarity_idf} of 10`}
            title="Corpus-wide inverse document frequency. Higher is rarer."
          />
        )}
      </dl>

      {channels.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {channels.map(([name, count]) => (
            <span key={name} className="px-1.5 py-0.5 rounded bg-gray-100 text-gray-600 text-[10px]">
              {name} · {count}
            </span>
          ))}
        </div>
      )}

      {facts.target_concentration?.length > 0 && (
        <p className="text-[11px] text-gray-500 leading-snug">
          Concentrated in{' '}
          {facts.target_concentration.map(([w, c]) => `${w} (${c})`).join(', ')}.
        </p>
      )}

      {facts.themes_caveat && (
        <p className="text-[11px] text-amber-700 leading-snug">{facts.themes_caveat}</p>
      )}
    </div>
  );
}

function Stat({ label, value, title }) {
  return (
    <div title={title}>
      <dt className="text-gray-500">{label}</dt>
      <dd className="font-semibold text-gray-800 tabular-nums">{value ?? '—'}</dd>
    </div>
  );
}
