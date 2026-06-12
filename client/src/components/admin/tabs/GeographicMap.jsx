import React, { useState, useEffect, useRef } from 'react';
import * as d3 from 'd3';
import { ZoomIn, ZoomOut, RotateCcw, Search, Map } from 'lucide-react';

const CITY_COORDINATES = {
  // US Cities
  'Buffalo': [-78.8784, 42.8864],
  'Williamsville': [-78.7361, 42.9645],
  'Tallahassee': [-84.2807, 30.4383],
  'Los Angeles': [-118.2437, 34.0522],
  'New York': [-74.0060, 40.7128],
  'Boston': [-71.0589, 42.3601],
  'Chicago': [-87.6298, 41.8781],
  'San Francisco': [-122.4194, 37.7749],
  'Seattle': [-122.3321, 47.6062],
  'Austin': [-97.7431, 30.2672],
  'Washington': [-77.0369, 38.9072],
  'Philadelphia': [-75.1652, 39.9526],
  'Atlanta': [-84.3880, 33.7490],
  // Italian Cities
  'Naples': [14.2681, 40.8518],
  'Milan': [9.1900, 45.4642],
  'Rome': [12.4964, 41.9028],
  'Venice': [12.3155, 45.4408],
  'Florence': [11.2558, 43.7696],
  // Argentina
  'Buenos Aires': [-58.3816, -34.6037],
  // Macau / China
  'Macau': [113.5439, 22.1987],
  'Hong Kong': [114.1694, 22.3193],
  'Beijing': [116.4074, 39.9042],
  'Shanghai': [121.4737, 31.2304],
  // France
  'Paris': [2.3522, 48.8566],
  'Lyon': [4.8357, 45.7640],
  // Greece
  'Athens': [23.7275, 37.9838],
  'Thessaloniki': [22.9444, 40.6401],
  // Germany
  'Berlin': [13.4050, 52.5200],
  'Munich': [11.5820, 48.1351],
  'Frankfurt': [8.6821, 50.1109],
  // Switzerland
  'Zurich': [8.5417, 47.3769],
  'Geneva': [6.1432, 46.2044],
  // Australia
  'Sydney': [151.2093, -33.8688],
  'Melbourne': [144.9631, -37.8136],
  // UK
  'London': [-0.1278, 51.5074],
  'Oxford': [-1.2577, 51.7520],
  'Cambridge': [0.1218, 52.2053],
  // Canada
  'Toronto': [-79.3832, 43.6532],
  'Montreal': [-73.5673, 45.5017],
  'Vancouver': [-123.1207, 49.2827],
};

const COUNTRY_COORDINATES = {
  'US': [-95.7129, 37.0902],
  'United States': [-95.7129, 37.0902],
  'IT': [12.5674, 41.8719],
  'Italy': [12.5674, 41.8719],
  'AR': [-63.6167, -38.4161],
  'Argentina': [-63.6167, -38.4161],
  'DE': [10.4515, 51.1657],
  'Germany': [10.4515, 51.1657],
  'MO': [113.5439, 22.1987],
  'Macau': [113.5439, 22.1987],
  'GR': [21.8243, 39.0742],
  'Greece': [21.8243, 39.0742],
  'FR': [2.2137, 46.2276],
  'France': [2.2137, 46.2276],
  'CH': [8.2275, 46.8182],
  'Switzerland': [8.2275, 46.8182],
  'AU': [133.7751, -25.2744],
  'Australia': [133.7751, -25.2744],
  'GB': [-3.4360, 55.3781],
  'United Kingdom': [-3.4360, 55.3781],
  'UK': [-3.4360, 55.3781],
  'CA': [-106.3468, 56.1304],
  'Canada': [-106.3468, 56.1304],
  'BR': [-51.9253, -14.2350],
  'Brazil': [-51.9253, -14.2350],
  'IN': [78.9629, 20.5937],
  'India': [78.9629, 20.5937],
  'JP': [138.2529, 36.2048],
  'Japan': [138.2529, 36.2048],
  'CN': [104.1954, 35.8617],
  'China': [104.1954, 35.8617],
};

const COUNTRY_NAME_MAP = {
  'US': 'United States',
  'IT': 'Italy',
  'AR': 'Argentina',
  'DE': 'Germany',
  'MO': 'Macau',
  'GR': 'Greece',
  'FR': 'France',
  'CH': 'Switzerland',
  'AU': 'Australia',
  'GB': 'United Kingdom',
  'UK': 'United Kingdom',
  'CA': 'Canada',
  'BR': 'Brazil',
  'IN': 'India',
  'JP': 'Japan',
  'CN': 'China'
};

const resolveCoordinates = (city, country) => {
  if (city && CITY_COORDINATES[city]) {
    return CITY_COORDINATES[city];
  }
  if (country && COUNTRY_COORDINATES[country]) {
    const coords = COUNTRY_COORDINATES[country];
    if (city) {
      let hash = 0;
      for (let i = 0; i < city.length; i++) {
        hash = city.charCodeAt(i) + ((hash << 5) - hash);
      }
      const jitterLng = ((Math.abs(hash) % 100) / 100) * 4 - 2;
      const jitterLat = (((Math.abs(hash) >> 8) % 100) / 100) * 4 - 2;
      return [coords[0] + jitterLng, coords[1] + jitterLat];
    }
    return coords;
  }
  const combined = `${city || ''}, ${country || ''}`;
  let hash = 0;
  for (let i = 0; i < combined.length; i++) {
    hash = combined.charCodeAt(i) + ((hash << 5) - hash);
  }
  const lat = ((Math.abs(hash) % 70) - 20);
  const lng = ((Math.abs(hash >> 8) % 220) - 90);
  return [lng, lat];
};

export default function GeographicMap({ topCities = [], topCountries = [] }) {
  const containerRef = useRef(null);
  const svgRef = useRef(null);
  const tooltipRef = useRef(null);

  const [searchQuery, setSearchQuery] = useState('');
  const [worldGeoData, setWorldGeoData] = useState(null);
  const [tooltip, setTooltip] = useState({ show: false, x: 0, y: 0, content: null });
  const [selectedMarker, setSelectedMarker] = useState(null);

  // Parse markers with coordinates
  const markers = React.useMemo(() => {
    return topCities.map((city, idx) => {
      const coords = resolveCoordinates(city.city, city.country);
      const displayCountry = COUNTRY_NAME_MAP[city.country] || city.country;
      return {
        id: `${city.city}-${city.country}-${idx}`,
        city: city.city,
        country: displayCountry,
        countryCode: city.country,
        count: city.count,
        coordinates: coords
      };
    });
  }, [topCities]);

  // Load geojson world map dataset
  useEffect(() => {
    fetch('/world.geojson')
      .then(res => {
        if (!res.ok) throw new Error('Local World GeoJSON load failed');
        return res.json();
      })
      .catch(() => {
        return fetch('https://raw.githubusercontent.com/holtzy/D3-graph-gallery/master/DATA/world.geojson').then(res => res.json());
      })
      .then(data => {
        setWorldGeoData(data);
      })
      .catch(err => console.error('Failed to load world geojson:', err));
  }, []);
  const [dimensions, setDimensions] = useState({ width: 600, height: 400 });

  // Handle container resizing to keep D3 map responsive
  useEffect(() => {
    if (!containerRef.current) return;

    const updateDimensions = () => {
      if (containerRef.current) {
        setDimensions({
          width: containerRef.current.clientWidth || 600,
          height: 400
        });
      }
    };

    updateDimensions();

    const resizeObserver = new ResizeObserver(() => {
      updateDimensions();
    });
    resizeObserver.observe(containerRef.current);

    window.addEventListener('resize', updateDimensions);
    return () => {
      resizeObserver.disconnect();
      window.removeEventListener('resize', updateDimensions);
    };
  }, []);

  const d3ZoomRef = useRef(null);
  const d3SvgRef = useRef(null);

  // Handle D3 projection rendering
  useEffect(() => {
    if (!worldGeoData || !containerRef.current || !svgRef.current) return;

    const { width, height } = dimensions;

    const svg = d3.select(svgRef.current);
    svg.selectAll('*').remove(); // Clear previous drawings

    // 2D World projection setup
    const projection = d3.geoNaturalEarth1().fitSize([width - 40, height - 40], worldGeoData);
    if (projection) {
      projection.translate([width / 2, height / 2]);
    }

    const path = d3.geoPath().projection(projection);

    // Groups for layout
    const mapGroup = svg.append('g').attr('class', 'map-group');
    const markersGroup = svg.append('g').attr('class', 'markers-group');

    // Subtle background ocean container grid
    const graticule = d3.geoGraticule();
    mapGroup.append('path')
      .datum(graticule)
      .attr('class', 'graticule')
      .attr('d', path)
      .attr('fill', 'none')
      .attr('stroke', 'rgba(185, 28, 28, 0.04)') // Subtle red graticule tint to match theme
      .attr('stroke-width', 0.5);

    // Render Country Boundaries
    mapGroup.selectAll('path.boundary')
      .data(worldGeoData.features)
      .enter()
      .append('path')
      .attr('class', 'boundary')
      .attr('d', path)
      .attr('fill', '#f1f5f9') // Slate 100 landmass (light theme)
      .attr('stroke', '#e2e8f0') // Slate 200 border lines
      .attr('stroke-width', 0.75)
      .style('cursor', 'pointer')
      .on('mouseover', function(event, d) {
        const countryName = d.properties.name;
        // World Country stats
        const stats = topCountries.find(tc => 
          tc.country === countryName || 
          COUNTRY_NAME_MAP[tc.country] === countryName
        );
        const count = stats ? stats.count : 0;
        
        d3.select(this)
          .transition()
          .duration(150)
          .attr('fill', '#fca5a5'); // soft Tesserae Red hover highlight

        setTooltip({
          show: true,
          x: event.clientX,
          y: event.clientY,
          content: (
            <div>
              <div className="font-bold text-gray-900">{countryName}</div>
              <div className="text-xs text-gray-500 mt-0.5 font-medium">
                {count > 0 ? `${count.toLocaleString()} searches logged` : 'No search activity'}
              </div>
            </div>
          )
        });
      })
      .on('mousemove', function(event) {
        setTooltip(prev => ({
          ...prev,
          x: event.clientX,
          y: event.clientY
        }));
      })
      .on('mouseout', function() {
        d3.select(this)
          .transition()
          .duration(150)
          .attr('fill', '#f1f5f9');
        setTooltip(prev => ({ ...prev, show: false }));
      });

    // Draw Pulsing City Markers
    const markerNodes = markersGroup.selectAll('g.marker')
      .data(markers)
      .enter()
      .append('g')
      .attr('class', 'marker')
      .style('cursor', 'pointer')
      .on('mouseover', function(event, d) {
        setTooltip({
          show: true,
          x: event.clientX,
          y: event.clientY,
          content: (
            <div className="text-gray-900">
              <div className="font-bold text-[#b91c1c]">{d.city}</div>
              <div className="text-xs text-gray-500 font-medium">{d.country}</div>
              <div className="text-xs text-gray-600 mt-1 font-bold">
                {d.count.toLocaleString()} searches
              </div>
            </div>
          )
        });
      })
      .on('mousemove', function(event) {
        setTooltip(prev => ({
          ...prev,
          x: event.clientX,
          y: event.clientY
        }));
      })
      .on('mouseout', function() {
        setTooltip(prev => ({ ...prev, show: false }));
      })
      .on('click', function(event, d) {
        event.stopPropagation();
        setSelectedMarker(d);
      });

    // Pulsing outer ring (Tesserae Red)
    markerNodes.append('circle')
      .attr('cx', d => projection(d.coordinates)[0])
      .attr('cy', d => projection(d.coordinates)[1])
      .attr('r', d => Math.max(8, Math.min(22, 5 + d.count * 0.5)))
      .attr('fill', 'none')
      .attr('stroke', '#ef4444')
      .attr('stroke-width', 1.5)
      .attr('opacity', 0.6)
      .append('animate')
      .attr('attributeName', 'r')
      .attr('values', d => {
        const rBase = Math.max(5, Math.min(15, 3 + d.count * 0.3));
        return `${rBase};${rBase * 2.5};${rBase}`;
      })
      .attr('dur', '2.5s')
      .attr('repeatCount', 'indefinite');

    // Central solid dot (Tesserae Red)
    markerNodes.append('circle')
      .attr('cx', d => projection(d.coordinates)[0])
      .attr('cy', d => projection(d.coordinates)[1])
      .attr('r', d => Math.max(4, Math.min(10, 2.5 + d.count * 0.2)))
      .attr('fill', '#b91c1c')
      .attr('stroke', '#ffffff')
      .attr('stroke-width', 1)
      .attr('opacity', 0.95);

    // Setup 2D Zoom/Pan behavior
    const zoom = d3.zoom()
      .scaleExtent([1, 10])
      .on('zoom', (event) => {
        mapGroup.attr('transform', event.transform);
        markersGroup.attr('transform', event.transform);
      });

    svg.call(zoom);
    d3ZoomRef.current = zoom;
    d3SvgRef.current = svg;

  }, [worldGeoData, markers, topCountries, dimensions]);

  // Zoom click handlers
  const handleZoom = (direction) => {
    if (!d3SvgRef.current || !d3ZoomRef.current) return;
    d3SvgRef.current.transition()
      .duration(350)
      .call(d3ZoomRef.current.scaleBy, direction === 'in' ? 1.4 : 0.7);
  };

  const handleReset = () => {
    setSelectedMarker(null);
    if (d3SvgRef.current && d3ZoomRef.current) {
      d3SvgRef.current.transition()
        .duration(450)
        .call(d3ZoomRef.current.transform, d3.zoomIdentity);
    }
  };

  // Search input: Zoom/fly to coordinate location
  const handleSearchSubmit = (e) => {
    e.preventDefault();
    if (!searchQuery.trim()) return;

    const term = searchQuery.toLowerCase().trim();
    const match = markers.find(m => 
      m.city.toLowerCase().includes(term) || 
      m.country.toLowerCase().includes(term)
    );

    if (match) {
      setSelectedMarker(match);
      const { width, height } = dimensions;

      // Resolve screen coordinates on world projection
      const projection = d3.geoNaturalEarth1().fitSize([width - 40, height - 40], worldGeoData);
      if (projection) {
        projection.translate([width / 2, height / 2]);
      }

      const screenCoords = projection(match.coordinates);

      if (screenCoords && !isNaN(screenCoords[0]) && !isNaN(screenCoords[1])) {
        if (d3SvgRef.current && d3ZoomRef.current) {
          d3SvgRef.current.transition()
            .duration(1000)
            .call(
              d3ZoomRef.current.transform, 
              d3.zoomIdentity
                .translate(width / 2, height / 2)
                .scale(4)
                .translate(-screenCoords[0], -screenCoords[1])
            );
        }
      }
    }
  };

  return (
    <div className="lg:col-span-2 bg-white text-gray-900 rounded-xl overflow-hidden relative border border-gray-100 shadow-sm flex flex-col min-h-[420px]">
      
      {/* Header controls */}
      <div className="p-4 bg-slate-50 border-b border-gray-100 flex flex-wrap items-center justify-between gap-3 z-10">
        <div className="flex items-center gap-2">
          <Map className="w-5 h-5 text-[#b91c1c]" />
          <h3 className="font-bold text-gray-800">Geographic Usage Analytics</h3>
        </div>
      </div>

      {/* SVG Canvas Map */}
      <div ref={containerRef} className="flex-1 w-full bg-slate-50 relative overflow-hidden flex items-center justify-center min-h-[350px]">
        
        {!worldGeoData && (
          <div className="absolute inset-0 flex flex-col items-center justify-center bg-white/95 z-20 gap-3">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-[#b91c1c]"></div>
            <div className="text-gray-500 text-sm font-medium">
              Loading World Boundaries...
            </div>
          </div>
        )}

        <svg ref={svgRef} className="w-full h-[380px] select-none block" />

        {/* Floating Zoom Controls Overlay */}
        <div className="absolute bottom-4 left-4 flex flex-col gap-2 z-10">
          <button
            onClick={() => handleZoom('in')}
            className="p-2 bg-white/90 backdrop-blur border border-gray-200 rounded-lg hover:bg-slate-100 text-gray-700 shadow-sm transition-all"
            title="Zoom In"
          >
            <ZoomIn className="w-4 h-4" />
          </button>
          <button
            onClick={() => handleZoom('out')}
            className="p-2 bg-white/90 backdrop-blur border border-gray-200 rounded-lg hover:bg-slate-100 text-gray-700 shadow-sm transition-all"
            title="Zoom Out"
          >
            <ZoomOut className="w-4 h-4" />
          </button>
          <button
            onClick={handleReset}
            className="p-2 bg-white/90 backdrop-blur border border-gray-200 rounded-lg hover:bg-slate-100 text-gray-700 shadow-sm transition-all"
            title="Reset Map View"
          >
            <RotateCcw className="w-4 h-4" />
          </button>
        </div>

        {/* Search Map Bar Overlay */}
        <form 
          onSubmit={handleSearchSubmit} 
          className="absolute top-4 left-4 max-w-[200px] sm:max-w-[240px] flex items-center bg-white/90 backdrop-blur border border-gray-200 rounded-lg px-2.5 py-1.5 z-10 shadow-sm"
        >
          <input
            type="text"
            placeholder="Search Global City..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full bg-transparent text-xs text-gray-800 border-none outline-none focus:ring-0 placeholder-gray-400 pr-1.5"
          />
          <button type="submit" className="text-gray-500 hover:text-[#b91c1c] transition-colors">
            <Search className="w-3.5 h-3.5" />
          </button>
        </form>

        {/* Selected Marker Detail Card */}
        {selectedMarker && (
          <div className="absolute bottom-4 right-4 bg-white/95 backdrop-blur border border-red-100 rounded-xl p-4 max-w-[240px] shadow-lg z-20 animate-fade-in text-xs text-gray-800">
            <div className="flex justify-between items-start gap-3 mb-2">
              <div>
                <h4 className="font-bold text-[#b91c1c] text-sm">{selectedMarker.city}</h4>
                <div className="text-gray-400 font-semibold text-[10px] uppercase tracking-wider">{selectedMarker.country}</div>
              </div>
              <button 
                onClick={() => setSelectedMarker(null)} 
                className="text-gray-400 hover:text-gray-600 transition-colors font-semibold"
              >
                ✕
              </button>
            </div>
            <div className="border-t border-gray-100 pt-2 flex flex-col gap-1 text-[11px] text-gray-600">
              <div className="flex justify-between">
                <span>Searches Count:</span>
                <span className="font-bold text-gray-900">{selectedMarker.count}</span>
              </div>
              <div className="flex justify-between">
                <span>Coordinates:</span>
                <span className="font-mono text-gray-500">
                  {selectedMarker.coordinates[1].toFixed(2)}°, {selectedMarker.coordinates[0].toFixed(2)}°
                </span>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Hover Tooltip */}
      {tooltip.show && (
        <div
          ref={tooltipRef}
          style={{
            position: 'fixed',
            left: `${tooltip.x + 12}px`,
            top: `${tooltip.y - 12}px`,
            pointerEvents: 'none',
            zIndex: 9999
          }}
          className="bg-white/95 backdrop-blur border border-gray-200 px-3 py-2 rounded-lg text-xs shadow-lg animate-fade-in text-gray-800"
        >
          {tooltip.content}
        </div>
      )}
    </div>
  );
}
