import { coinDate, coinTitle, coinPath } from './coinsFormat';

function Legend({ label, text }) {
  return (
    <div>
      <dt className="text-xs uppercase tracking-wide text-gray-500">{label}</dt>
      <dd className="text-gray-900 font-medium break-words">{text || <span className="text-gray-400 font-normal">none recorded</span>}</dd>
    </div>
  );
}

function Describe({ label, text }) {
  return (
    <div>
      <dt className="text-xs uppercase tracking-wide text-gray-500">{label}</dt>
      <dd className="text-gray-800 break-words">{text || <span className="text-gray-400">none recorded</span>}</dd>
    </div>
  );
}

/**
 * One coin type: both legends, both descriptions, mint (with a Pleiades link
 * when the id exists), date, authority, the licence line, and a link to the
 * type's own page where the specimens and their images are listed. Images are
 * never fetched or stored here.
 */
export default function CoinCard({ coin, open }) {
  const issuer = [coin.authority, coin.issuer].filter(Boolean).join(', issued by ');
  return (
    <article className="bg-white border border-gray-200 rounded-lg p-4" data-testid="coin-card">
      <header className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <h3 className="text-base font-semibold">
          <a href={coinPath(coin)}
             onClick={open ? (e) => { e.preventDefault(); open(coin.id); } : undefined}
             className="text-red-700 hover:underline">
            {coinTitle(coin)}
          </a>
        </h3>
        <span className="text-xs text-gray-600">
          {[coinDate(coin), coin.denomination, coin.material].filter(Boolean).join(' · ')}
        </span>
      </header>
      <p className="text-sm text-gray-700 mt-0.5">
        {issuer || 'Authority not recorded'}
        {coin.mint && (
          <>
            {' · minted at '}
            {coin.pleiades_url
              ? <a href={coin.pleiades_url} target="_blank" rel="noopener noreferrer" className="text-red-700 hover:underline">{coin.mint}</a>
              : coin.mint}
          </>
        )}
      </p>
      <dl className="grid sm:grid-cols-2 gap-x-6 gap-y-2 mt-3 text-sm">
        <Legend label="Obverse legend" text={coin.obverse_legend} />
        <Legend label="Reverse legend" text={coin.reverse_legend} />
        <Describe label="Obverse" text={coin.obverse_description} />
        <Describe label="Reverse" text={coin.reverse_description} />
      </dl>
      <footer className="flex flex-wrap items-center gap-x-4 gap-y-1 mt-3 text-xs text-gray-500">
        <span>{coin.credit}</span>
        <a href={coin.type_url} target="_blank" rel="noopener noreferrer" className="text-red-700 hover:underline ml-auto">
          Type page and specimens
        </a>
      </footer>
    </article>
  );
}
