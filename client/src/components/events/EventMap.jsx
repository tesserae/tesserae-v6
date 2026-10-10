

const W = 560;
const H = 320;
const PAD = 28;

/**
 * The event and its documents' findspots. No map library is installed, so the
 * points are drawn on a plain scaled plot (no coastlines) beside a table of the
 * same coordinates, each with a link to OpenStreetMap.
 */
export default function EventMap({ points }) {
  if (!points || points.length === 0) {
    return <p className="text-sm text-gray-600">No coordinates are recorded for this event.</p>;
  }
  const lats = points.map((p) => p.lat);
  const lons = points.map((p) => p.lon);
  const midLat = (Math.min(...lats) + Math.max(...lats)) / 2;
  const k = Math.cos((midLat * Math.PI) / 180) || 1;  // a degree of longitude is shorter away from the equator
  const xs = lons.map((l) => l * k);
  const [x0, x1] = [Math.min(...xs), Math.max(...xs)];
  const [y0, y1] = [Math.min(...lats), Math.max(...lats)];
  const span = Math.max(x1 - x0, y1 - y0, 0.01);
  const scale = (Math.min(W, H) - 2 * PAD) / span;
  const px = (lon) => W / 2 + (lon * k - (x0 + x1) / 2) * scale;
  const py = (lat) => H / 2 - (lat - (y0 + y1) / 2) * scale;
  const hasFindspots = points.some((p) => p.kind === 'findspot');

  return (
    <div>
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Event location and document findspots"
           className="w-full max-w-xl bg-white border border-gray-200 rounded-lg">
        {points.map((p, i) => (
          <g key={`${p.label}-${i}`}>
            <circle cx={px(p.lon)} cy={py(p.lat)} r={p.kind === 'event' ? 7 : 5}
                    fill={p.kind === 'event' ? '#b91c1c' : '#6b7280'} />
            <text x={px(p.lon) + 9} y={py(p.lat) + 4} fontSize="11" fill="#374151">{p.label}</text>
          </g>
        ))}
      </svg>
      <p className="text-xs text-gray-500 mt-1">
        Red is the event, gray the findspots of documents. A scaled plot of the coordinates, without a base map.
      </p>
      {!hasFindspots && (
        <p className="text-xs text-gray-500 mt-1">No document findspots to show for this event.</p>
      )}
      <table className="mt-3 text-sm w-full max-w-xl">
        <thead>
          <tr className="text-left text-xs text-gray-500">
            <th className="font-medium py-1">Place</th><th className="font-medium">Kind</th>
            <th className="font-medium">Latitude, longitude</th><th className="font-medium">Documents</th>
          </tr>
        </thead>
        <tbody>
          {points.map((p, i) => (
            <tr key={i} className="border-t border-gray-100">
              <td className="py-1">
                <a href={`https://www.openstreetmap.org/?mlat=${p.lat}&mlon=${p.lon}#map=9/${p.lat}/${p.lon}`}
                   target="_blank" rel="noopener noreferrer" className="text-red-700 hover:underline">{p.label}</a>
              </td>
              <td className="text-gray-600">{p.kind === 'event' ? 'event' : 'findspot'}</td>
              <td className="text-gray-600 tabular-nums">{p.lat.toFixed(4)}, {p.lon.toFixed(4)}</td>
              <td className="text-gray-600">{p.kind === 'findspot' ? p.n_documents : ''}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
