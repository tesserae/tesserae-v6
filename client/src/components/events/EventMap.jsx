import { useEffect, useRef, useState } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';

const EVENT_COLOUR = '#b91c1c';
const FINDSPOT_COLOUR = '#6b7280';
const TILE_URL = 'https://tile.openstreetmap.org/{z}/{x}/{y}.png';
const ATTRIBUTION = '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener noreferrer">OpenStreetMap</a> contributors';

/** Radius 5 to 12 pixels, growing with the number of documents found at the place. */
export function findspotRadius(n, max) {
  if (!n || n < 1 || !max || max < 1) return 5;
  return 5 + 7 * (Math.sqrt(n) / Math.sqrt(max));
}

function popupNode(p) {
  const box = document.createElement('div');
  const title = document.createElement('strong');
  title.textContent = p.label;
  box.appendChild(title);
  const lines = [p.kind === 'event' ? 'The event' : 'Findspot of documents', `${p.lat.toFixed(4)}, ${p.lon.toFixed(4)}`];
  if (p.kind === 'findspot') lines.push(`${p.n_documents} ${p.n_documents === 1 ? 'document' : 'documents'}`);
  lines.forEach((t) => {
    const d = document.createElement('div');
    d.textContent = t;
    box.appendChild(d);
  });
  return box;
}

/**
 * The event and its documents' findspots on a Leaflet map (OpenStreetMap tiles,
 * Leaflet bundled from npm), above a table of the same coordinates, each with a
 * link to OpenStreetMap.
 */
export default function EventMap({ points }) {
  const holder = useRef(null);
  const [tilesFailed, setTilesFailed] = useState(false);
  const has = !!points && points.length > 0;

  useEffect(() => {
    if (!has || !holder.current) return undefined;
    const map = L.map(holder.current, { scrollWheelZoom: false });
    const tiles = L.tileLayer(TILE_URL, { attribution: ATTRIBUTION, maxZoom: 18 });
    let failed = false;
    tiles.on('tileerror', () => {
      if (!failed) { failed = true; setTilesFailed(true); }
    });
    tiles.addTo(map);
    map.once('click', () => map.scrollWheelZoom.enable());
    const maxDocs = Math.max(0, ...points.filter((p) => p.kind === 'findspot').map((p) => p.n_documents || 0));
    const latlngs = [];
    points.forEach((p) => {
      const isEvent = p.kind === 'event';
      const m = L.circleMarker([p.lat, p.lon], {
        radius: isEvent ? 9 : findspotRadius(p.n_documents, maxDocs),
        color: '#ffffff', weight: 2, fillColor: isEvent ? EVENT_COLOUR : FINDSPOT_COLOUR,
        fillOpacity: 0.9,
      });
      m.bindTooltip(p.label);
      m.bindPopup(popupNode(p));
      m.addTo(map);
      latlngs.push([p.lat, p.lon]);
    });
    map.fitBounds(latlngs, { padding: [30, 30], maxZoom: 10 });
    return () => { map.remove(); };
  }, [points, has]);

  if (!has) {
    return <p className="text-sm text-gray-600">No coordinates are recorded for this event.</p>;
  }
  const hasFindspots = points.some((p) => p.kind === 'findspot');

  return (
    <div>
      <div ref={holder} role="region" aria-label="Map of the event and the findspots of documents"
           className="w-full h-80 sm:h-[420px] rounded-lg border border-gray-200 bg-gray-50 z-0" />
      {tilesFailed && <p className="text-xs text-gray-600 mt-1">The base map could not be loaded.</p>}
      <p className="text-xs text-gray-500 mt-1 flex flex-wrap items-center gap-x-4 gap-y-1">
        <span className="inline-flex items-center gap-1">
          <span className="inline-block w-3 h-3 rounded-full" style={{ background: EVENT_COLOUR }} /> Red is the event
        </span>
        <span className="inline-flex items-center gap-1">
          <span className="inline-block w-3 h-3 rounded-full" style={{ background: FINDSPOT_COLOUR }} /> Gray are the findspots, sized by documents
        </span>
        <span>Click the map to zoom with the scroll wheel.</span>
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
