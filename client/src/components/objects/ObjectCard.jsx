import { objectDate, objectTitle, objectPath, accession } from './objectsFormat';

/**
 * One museum object: title, museum and accession number, date, culture and
 * material, the museum's own catalogue description, the credit line with the
 * licence, a link to the museum's record, and the museum's web image when the
 * record gives one under an open licence. `full` shows the whole description;
 * a list card shows the start of it.
 */
export default function ObjectCard({ object: o, open, full = false }) {
  const text = o.description || '';
  const shown = full || text.length <= 600 ? text : `${text.slice(0, 600).replace(/\s+\S*$/, '')}...`;
  return (
    <article className="bg-white border border-gray-200 rounded-lg p-4" data-testid="object-card">
      <div className="flex gap-4">
        {o.image_url && (
          <img src={o.image_url} alt={objectTitle(o)} loading="lazy"
               className="w-28 h-28 object-contain flex-none bg-gray-50 rounded" />
        )}
        <div className="min-w-0 flex-1">
          <header className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
            <h3 className="text-base font-semibold">
              <a href={objectPath(o)}
                 onClick={open ? (e) => { e.preventDefault(); open(o.id); } : undefined}
                 className="text-red-700 hover:underline">
                {objectTitle(o)}
              </a>
            </h3>
            <span className="text-xs text-gray-600">
              {[objectDate(o), o.culture, o.material].filter(Boolean).join(' · ')}
            </span>
          </header>
          <p className="text-sm text-gray-700 mt-0.5">
            {o.museum_name} · {accession(o)}
            {o.object_type ? ` · ${o.object_type}` : ''}
          </p>
          {shown && <p className="text-sm text-gray-800 mt-2 whitespace-pre-line break-words" data-testid="object-description">{shown}</p>}
        </div>
      </div>
      <footer className="flex flex-wrap items-center gap-x-4 gap-y-1 mt-3 text-xs text-gray-500">
        <span>{o.credit}</span>
        <a href={o.object_url} target="_blank" rel="noopener noreferrer" className="text-red-700 hover:underline ml-auto">
          Object page
        </a>
      </footer>
    </article>
  );
}
