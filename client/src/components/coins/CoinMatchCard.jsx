import { dateLabel } from './coinsFormat';

const LEVEL_TEXT = {
  higher: ['Closer match', 'In our test of ten passages, about 7 in 10 of the matches this close were right.'],
  usual: ['Usual match', 'In our test of ten passages, about 1 in 4 of the matches this far down were right.'],
};

/**
 * One related-imagery card: a coin description close in meaning to the
 * passage, with the date span, issuers and mint of the types that carry it,
 * its measured confidence, and a link to one of those types. The cosine
 * stays out of sight: the level and its tested rate are what a reader can use.
 */
export default function CoinMatchCard({ match }) {
  const level = LEVEL_TEXT[match.confidence?.level];
  const when = dateLabel(match.date_start, match.date_end);
  const who = (match.authorities || []).join(', ')
    + (match.authorities_total > (match.authorities || []).length
      ? ` and ${match.authorities_total - match.authorities.length} more` : '');
  return (
    <li className="bg-white border border-gray-200 rounded-lg p-3" data-testid="coin-match">
      <p className="text-sm text-gray-900">{match.reverse_description || match.description}</p>
      {match.obverse_description && match.reverse_description && (
        <p className="text-[11px] text-gray-500 mt-0.5">Obverse: {match.obverse_description}</p>
      )}
      <p className="text-xs text-gray-600 mt-1">
        {[who, when, match.mint, match.denomination].filter(Boolean).join(' · ')}
      </p>
      <p className="text-[11px] text-gray-500 mt-1 flex flex-wrap items-center gap-x-3">
        {level && (
          <span title={level[1]} className="px-1.5 py-0.5 rounded bg-gray-100 text-gray-700">{level[0]}</span>
        )}
        <span>{match.n_types} {match.n_types === 1 ? 'coin type carries' : 'coin types carry'} this description</span>
        {match.coin_url && (
          <a href={match.coin_url} className="text-red-700 hover:underline ml-auto">
            Open {match.n_types > 1 ? 'the earliest' : 'the coin type'}
          </a>
        )}
      </p>
    </li>
  );
}
