import { coinDate, coinTitle, coinPath, catalogueName } from './coinsFormat';

const OBVERSE_TIP = 'Catalogues call the front of a coin the obverse and the back the reverse.';

function Line({ label, text, empty = 'none recorded' }) {
  return (
    <p className="break-words">
      <span className="text-gray-500">{label}:</span>{' '}
      {text
        ? <span className="text-gray-900">{text}</span>
        : <span className="text-gray-400">{empty}</span>}
    </p>
  );
}

/** One side of a coin: what it shows and what is written on it. */
function Side({ name, term, description, inscription }) {
  return (
    <div className="text-sm space-y-1">
      <h4 className="font-semibold text-gray-900" title={OBVERSE_TIP}>
        {name} <span className="text-xs font-normal text-gray-500">({term})</span>
      </h4>
      <Line label="Shows" text={description} />
      <Line label="Inscription" text={inscription} empty="none recorded" />
    </div>
  );
}

/** Front and back, side by side. */
export function CoinSides({ coin }) {
  return (
    <div className="grid sm:grid-cols-2 gap-x-6 gap-y-3">
      <Side name="Front" term="obverse" description={coin.obverse_description}
            inscription={coin.obverse_legend} />
      <Side name="Back" term="reverse" description={coin.reverse_description}
            inscription={coin.reverse_legend} />
    </div>
  );
}

/**
 * One coin type in the list: front and back with what each shows and says,
 * mint (with a Pleiades link when the id exists), date, authority, the credit
 * line, and one link out to the catalogue's page for the type, where the
 * museum specimens and their photographs are. Images are never fetched or
 * stored here.
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
      <div className="mt-3"><CoinSides coin={coin} /></div>
      <footer className="flex flex-wrap items-center gap-x-4 gap-y-1 mt-3 text-xs text-gray-500">
        <span>{coin.credit}</span>
        <a href={coin.type_url} target="_blank" rel="noopener noreferrer"
           title={`Photographs are on ${catalogueName(coin)}'s page for this type`}
           className="text-red-700 hover:underline ml-auto">
          See images &#8599;
        </a>
      </footer>
    </article>
  );
}
