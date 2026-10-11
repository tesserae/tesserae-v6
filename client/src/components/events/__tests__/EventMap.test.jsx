import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';

const h = vi.hoisted(() => {
  const marker = () => { const m = { bindTooltip: vi.fn(() => m), bindPopup: vi.fn(() => m), addTo: vi.fn(() => m) }; return m; };
  const tiles = { on: vi.fn(), addTo: vi.fn() };
  const map = { fitBounds: vi.fn(), remove: vi.fn(), once: vi.fn(), scrollWheelZoom: { enable: vi.fn() } };
  return {
    map, tiles,
    L: {
      map: vi.fn(() => map),
      tileLayer: vi.fn(() => tiles),
      circleMarker: vi.fn(() => marker()),
    },
  };
});
vi.mock('leaflet', () => ({ default: h.L }));
vi.mock('leaflet/dist/leaflet.css', () => ({}));

import EventMap, { findspotRadius } from '../EventMap';

const POINTS = [
  { kind: 'event', label: 'Corfinium', lat: 42.1, lon: 13.8, n_documents: 0 },
  { kind: 'findspot', label: 'Sulmo', lat: 42.05, lon: 13.93, n_documents: 4 },
  { kind: 'findspot', label: 'Alba', lat: 42.0, lon: 13.4, n_documents: 1 },
];

describe('EventMap', () => {
  beforeEach(() => { vi.clearAllMocks(); });

  it('builds one map with a marker per point, coloured and sized', () => {
    render(<EventMap points={POINTS} />);
    expect(h.L.map).toHaveBeenCalledTimes(1);
    expect(h.L.circleMarker).toHaveBeenCalledTimes(3);
    const opts = h.L.circleMarker.mock.calls.map((c) => c[1]);
    expect(opts[0]).toMatchObject({ radius: 9, fillColor: '#b91c1c', color: '#ffffff' });
    expect(opts[1]).toMatchObject({ radius: 12, fillColor: '#6b7280' });
    expect(opts[2].radius).toBeGreaterThanOrEqual(5);
    expect(opts[2].radius).toBeLessThan(12);
    expect(h.map.fitBounds).toHaveBeenCalledTimes(1);
    expect(h.map.fitBounds.mock.calls[0][1]).toMatchObject({ maxZoom: 10 });
    expect(h.L.tileLayer.mock.calls[0][0]).toBe('https://tile.openstreetmap.org/{z}/{x}/{y}.png');
    expect(h.L.map.mock.calls[0][1]).toMatchObject({ scrollWheelZoom: false });
  });

  it('shows the legend and the table of coordinates', () => {
    render(<EventMap points={POINTS} />);
    expect(screen.getByText(/Red is the event/)).toBeTruthy();
    expect(screen.getByText(/Gray are the findspots, sized by documents/)).toBeTruthy();
    expect(screen.getByRole('link', { name: 'Sulmo' })).toBeTruthy();
    expect(screen.getByText('42.0500, 13.9300')).toBeTruthy();
  });

  it('says so when there are no points and builds no map', () => {
    render(<EventMap points={[]} />);
    expect(screen.getByText('No coordinates are recorded for this event.')).toBeTruthy();
    expect(h.L.map).not.toHaveBeenCalled();
  });

  it('notes a failed base map once', () => {
    render(<EventMap points={POINTS} />);
    const handler = h.tiles.on.mock.calls.find((c) => c[0] === 'tileerror')[1];
    expect(screen.queryByText('The base map could not be loaded.')).toBeNull();
    // eslint-disable-next-line testing-library/no-unnecessary-act
    return import('@testing-library/react').then(({ act }) => {
      act(() => { handler(); handler(); });
      expect(screen.getAllByText('The base map could not be loaded.')).toHaveLength(1);
    });
  });

  it('keeps the radius between 5 and 12', () => {
    expect(findspotRadius(0, 10)).toBe(5);
    expect(findspotRadius(10, 10)).toBe(12);
    expect(findspotRadius(1, 100)).toBeGreaterThan(5);
  });
});
