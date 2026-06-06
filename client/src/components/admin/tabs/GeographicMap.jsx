import React, { useState, useEffect, useRef } from 'react';
import * as d3 from 'd3';
import { Globe, MapPin, ZoomIn, ZoomOut, RotateCcw, Play, Pause, Search } from 'lucide-react';

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

  const [mapType, setMapType] = useState('globe'); // 'globe' or 'flat'
  const [autoRotate, setAutoRotate] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [geoData, setGeoData] = useState(null);
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

  // Load geojson data once
  useEffect(() => {
    fetch('/world.geojson')
      .then(res => {
        if (!res.ok) throw new Error('Local GeoJSON load failed');
        return res.json();
      })
      .catch(() => {
        // Fallback to fetch from CDN if local load fails
        return fetch('https://raw.githubusercontent.com/holtzy/D3-graph-gallery/master/DATA/world.geojson').then(res => res.json());
      })
      .then(data => {
        setGeoData(data);
      })
      .catch(err => {
        console.error('Failed to load world map geojson:', err);
      });
  }, []);

  const d3ZoomRef = useRef(null);
  const d3SvgRef = useRef(null);
  const currentRotateRef = useRef([0, 0]);

  // Handle D3 projection rendering & updates
  useEffect(() => {
    if (!geoData || !containerRef.current || !svgRef.current) return;

    const width = containerRef.current.clientWidth || 600;
    const height = 400;

    const svg = d3.select(svgRef.current);
    svg.selectAll('*').remove(); // Clear previous contents

    // Projection Setup
    const projection = mapType === 'globe'
      ? d3.geoOrthographic()
          .scale(175)
          .translate([width / 2, height / 2])
          .clipAngle(90)
          .rotate(currentRotateRef.current)
      : d3.geoNaturalEarth1()
          .scale(120)
          .translate([width / 2, height / 2]);

    const path = d3.geoPath().projection(projection);
    
    // Water background/glow for the globe
    if (mapType === 'globe') {
      svg.append('circle')
        .attr('cx', width / 2)
        .attr('cy', height / 2)
        .attr('r', 175)
        .attr('fill', 'url(#waterGradient)')
        .attr('stroke', '#1e293b')
        .attr('stroke-width', 1.5);
    }

    // Main map container group for zoom/pan
    const mapGroup = svg.append('g').attr('class', 'map-group');

    // Graticules (Subtle Gridlines)
    const graticule = d3.geoGraticule();
    mapGroup.append('path')
      .datum(graticule)
      .attr('class', 'graticule')
      .attr('d', path)
      .attr('fill', 'none')
      .attr('stroke', 'rgba(51, 65, 85, 0.25)')
      .attr('stroke-width', 0.5);

    // Render Landmasses
    const countries = mapGroup.selectAll('path.country')
      .data(geoData.features)
      .enter()
      .append('path')
      .attr('class', 'country')
      .attr('d', path)
      .attr('fill', '#1e293b')
      .attr('stroke', '#0f172a')
      .attr('stroke-width', 0.5)
      .style('cursor', 'pointer')
      .on('mouseover', function(event, d) {
        const countryName = d.properties.name;
        // Find if this country is in topCountries
        const stats = topCountries.find(tc => 
          tc.country === countryName || 
          COUNTRY_NAME_MAP[tc.country] === countryName
        );
        const count = stats ? stats.count : 0;
        
        d3.select(this)
          .transition()
          .duration(150)
          .attr('fill', '#334155');

        setTooltip({
          show: true,
          x: event.clientX,
          y: event.clientY,
          content: (
            <div>
              <div className="font-bold text-gray-100">{countryName}</div>
              <div className="text-xs text-gray-400 mt-0.5">
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
          .attr('fill', '#1e293b');
        setTooltip(prev => ({ ...prev, show: false }));
      });

    // Helper to check if marker coordinate is visible in Orthographic (not on back of globe)
    const isCoordinateVisible = (coords) => {
      if (mapType !== 'globe') return true;
      const r = projection.rotate();
      const center = [-r[0], -r[1]];
      const distance = d3.geoDistance(coords, center);
      return distance < Math.PI / 2;
    };

    // Draw Markers Group
    const markersGroup = svg.append('g').attr('class', 'markers-group');

    const drawMarkers = () => {
      markersGroup.selectAll('*').remove();

      const markerNodes = markersGroup.selectAll('g.marker')
        .data(markers.filter(m => isCoordinateVisible(m.coordinates)))
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
              <div>
                <div className="font-bold text-red-400">{d.city}</div>
                <div className="text-xs text-gray-300">{d.country}</div>
                <div className="text-xs text-gray-400 mt-1 font-semibold">
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

      // Animated pulsing ring around city markers
      markerNodes.append('circle')
        .attr('cx', d => projection(d.coordinates)[0])
        .attr('cy', d => projection(d.coordinates)[1])
        .attr('r', d => Math.max(8, Math.min(20, 4 + d.count * 0.4)))
        .attr('fill', 'none')
        .attr('stroke', '#ef4444')
        .attr('stroke-width', 1.5)
        .attr('opacity', 0.8)
        .append('animate')
        .attr('attributeName', 'r')
        .attr('values', d => {
          const rBase = Math.max(5, Math.min(15, 3 + d.count * 0.3));
          return `${rBase};${rBase * 2.5};${rBase}`;
        })
        .attr('dur', '2s')
        .attr('repeatCount', 'indefinite');

      markerNodes.append('circle')
        .attr('cx', d => projection(d.coordinates)[0])
        .attr('cy', d => projection(d.coordinates)[1])
        .attr('r', d => Math.max(4, Math.min(10, 2 + d.count * 0.2)))
        .attr('fill', '#f87171')
        .attr('stroke', '#ffffff')
        .attr('stroke-width', 1)
        .attr('opacity', 0.95);
    };

    drawMarkers();

    // Map Zooming (Flat Map Only)
    let zoom;
    if (mapType === 'flat') {
      zoom = d3.zoom()
        .scaleExtent([1, 8])
        .on('zoom', (event) => {
          mapGroup.attr('transform', event.transform);
          markersGroup.attr('transform', event.transform);
        });
      svg.call(zoom);
      d3ZoomRef.current = zoom;
      d3SvgRef.current = svg;
    }

    // Globe Drag Rotation
    let drag;
    if (mapType === 'globe') {
      drag = d3.drag()
        .on('drag', (event) => {
          const r = projection.rotate();
          // Adjust rotation velocity by scale/zoom
          const k = 0.35;
          const nextRotate = [r[0] + event.dx * k, r[1] - event.dy * k];
          projection.rotate(nextRotate);
          currentRotateRef.current = nextRotate;
          
          svg.selectAll('path.country').attr('d', path);
          svg.selectAll('path.graticule').attr('d', path);
          drawMarkers();
        });
      svg.call(drag);
    }

    // Auto-Rotation Timer for Globe
    let timer;
    if (mapType === 'globe' && autoRotate) {
      timer = d3.timer(() => {
        const r = projection.rotate();
        const nextRotate = [r[0] + 0.15, r[1]];
        projection.rotate(nextRotate);
        currentRotateRef.current = nextRotate;

        svg.selectAll('path.country').attr('d', path);
        svg.selectAll('path.graticule').attr('d', path);
        drawMarkers();
      });
    }

    // Cleanup timer/zoom
    return () => {
      if (timer) timer.stop();
    };

  }, [geoData, mapType, autoRotate, markers, topCountries]);

  // Zoom Button Handlers (Flat Map only)
  const handleZoom = (direction) => {
    if (mapType !== 'flat' || !d3SvgRef.current || !d3ZoomRef.current) return;
    const svg = d3SvgRef.current;
    const zoom = d3ZoomRef.current;

    svg.transition()
      .duration(350)
      .call(zoom.scaleBy, direction === 'in' ? 1.4 : 0.7);
  };

  const handleReset = () => {
    setSelectedMarker(null);
    if (mapType === 'flat' && d3SvgRef.current && d3ZoomRef.current) {
      d3SvgRef.current.transition()
        .duration(450)
        .call(d3ZoomRef.current.transform, d3.zoomIdentity);
    } else if (mapType === 'globe') {
      currentRotateRef.current = [0, 0];
      setAutoRotate(true);
      // Re-trigger render
      setMapType(prev => prev);
    }
  };

  // Search function - zoom/fly to coordinate
  const handleSearchSubmit = (e) => {
    e.preventDefault();
    if (!searchQuery.trim()) return;

    const term = searchQuery.toLowerCase().trim();
    // Search markers by city or country
    const match = markers.find(m => 
      m.city.toLowerCase().includes(term) || 
      m.country.toLowerCase().includes(term)
    );

    if (match) {
      setSelectedMarker(match);
      if (mapType === 'globe') {
        setAutoRotate(false);
        // Fly rotation to coordinates
        const targetRotate = [-match.coordinates[0], -match.coordinates[1]];
        
        d3.transition()
          .duration(1000)
          .tween('rotate', () => {
            const rInterpolator = d3.interpolate(currentRotateRef.current, targetRotate);
            return (t) => {
              currentRotateRef.current = rInterpolator(t);
              // Set the type state or force refresh by changing map type or triggering re-render
              setMapType(prev => prev);
            };
          });
      } else {
        // Zoom/pan to flat coordinate
        // Flat mapping to screen coords: need the SVG dimensions
        if (d3SvgRef.current && d3ZoomRef.current) {
          const width = containerRef.current.clientWidth || 600;
          const height = 400;
          const projection = d3.geoNaturalEarth1().scale(120).translate([width / 2, height / 2]);
          const screenCoords = projection(match.coordinates);
          
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
    <div className="lg:col-span-2 bg-[#090d16] text-white rounded-xl overflow-hidden relative border border-gray-800 shadow-xl flex flex-col min-h-[420px]">
      
      {/* Header controls */}
      <div className="p-4 bg-slate-950/80 backdrop-blur-md border-b border-gray-800 flex flex-wrap items-center justify-between gap-3 z-10">
        <div className="flex items-center gap-2">
          <Globe className="w-5 h-5 text-red-500 animate-spin" style={{ animationDuration: '8s' }} />
          <h3 className="font-bold text-gray-200">Interactive Geographic Analytics</h3>
        </div>
        
        {/* Toggle Controls */}
        <div className="flex items-center gap-3">
          {/* Map Type Switch */}
          <div className="bg-[#111726] border border-gray-800 rounded-lg p-0.5 flex">
            <button
              onClick={() => { setMapType('globe'); setSelectedMarker(null); }}
              className={`px-3 py-1 rounded-md text-xs font-semibold transition-all ${
                mapType === 'globe' 
                  ? 'bg-red-700 text-white shadow-sm' 
                  : 'text-gray-400 hover:text-gray-200'
              }`}
            >
              3D Globe
            </button>
            <button
              onClick={() => { setMapType('flat'); setSelectedMarker(null); }}
              className={`px-3 py-1 rounded-md text-xs font-semibold transition-all ${
                mapType === 'flat' 
                  ? 'bg-red-700 text-white shadow-sm' 
                  : 'text-gray-400 hover:text-gray-200'
              }`}
            >
              2D Map
            </button>
          </div>

          {/* Auto rotate switch for globe */}
          {mapType === 'globe' && (
            <button
              onClick={() => setAutoRotate(!autoRotate)}
              className="p-1.5 bg-[#111726] border border-gray-800 rounded-lg hover:bg-slate-800 text-gray-400 hover:text-gray-200 transition-colors"
              title={autoRotate ? 'Pause Rotation' : 'Auto Rotate Globe'}
            >
              {autoRotate ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}
            </button>
          )}
        </div>
      </div>

      {/* SVG Canvas Map */}
      <div ref={containerRef} className="flex-1 w-full bg-[#070b12] relative overflow-hidden flex items-center justify-center min-h-[350px]">
        
        {!geoData && (
          <div className="absolute inset-0 flex flex-col items-center justify-center bg-[#070b12]/95 z-20 gap-3">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-red-500"></div>
            <div className="text-gray-400 text-sm font-medium">Initializing World Projection...</div>
          </div>
        )}

        <svg ref={svgRef} className="w-full h-[380px] select-none block">
          <defs>
            {/* Water gradient definition for globe */}
            <radialGradient id="waterGradient" cx="50%" cy="50%" r="50%" fx="30%" fy="30%">
              <stop offset="0%" stopColor="#111c33" />
              <stop offset="70%" stopColor="#080e1a" />
              <stop offset="100%" stopColor="#04070d" />
            </radialGradient>
          </defs>
        </svg>

        {/* Floating Controls Overlay */}
        <div className="absolute bottom-4 left-4 flex flex-col gap-2 z-10">
          {mapType === 'flat' && (
            <>
              <button
                onClick={() => handleZoom('in')}
                className="p-2 bg-[#111726]/90 backdrop-blur border border-gray-800 rounded-lg hover:bg-slate-800 text-gray-300 shadow-md transition-all"
                title="Zoom In"
              >
                <ZoomIn className="w-4 h-4" />
              </button>
              <button
                onClick={() => handleZoom('out')}
                className="p-2 bg-[#111726]/90 backdrop-blur border border-gray-800 rounded-lg hover:bg-slate-800 text-gray-300 shadow-md transition-all"
                title="Zoom Out"
              >
                <ZoomOut className="w-4 h-4" />
              </button>
            </>
          )}
          <button
            onClick={handleReset}
            className="p-2 bg-[#111726]/90 backdrop-blur border border-gray-800 rounded-lg hover:bg-slate-800 text-gray-300 shadow-md transition-all"
            title="Reset Map View"
          >
            <RotateCcw className="w-4 h-4" />
          </button>
        </div>

        {/* Search Map Bar Overlay */}
        <form 
          onSubmit={handleSearchSubmit} 
          className="absolute top-4 left-4 max-w-[200px] sm:max-w-[240px] flex items-center bg-slate-950/80 backdrop-blur border border-gray-800 rounded-lg px-2.5 py-1 z-10 shadow-lg"
        >
          <input
            type="text"
            placeholder="Search city/country..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full bg-transparent text-xs text-white border-none outline-none focus:ring-0 placeholder-gray-500 pr-1.5"
          />
          <button type="submit" className="text-gray-400 hover:text-red-400 transition-colors">
            <Search className="w-3.5 h-3.5" />
          </button>
        </form>

        {/* Selected Marker Detail Card */}
        {selectedMarker && (
          <div className="absolute bottom-4 right-4 bg-slate-950/90 backdrop-blur border border-red-900/50 rounded-xl p-4 max-w-[240px] shadow-2xl z-20 animate-fade-in text-xs">
            <div className="flex justify-between items-start gap-3 mb-2">
              <div>
                <h4 className="font-bold text-red-400 text-sm">{selectedMarker.city}</h4>
                <div className="text-gray-400 font-medium text-[10px] uppercase tracking-wider">{selectedMarker.country}</div>
              </div>
              <button 
                onClick={() => setSelectedMarker(null)} 
                className="text-gray-500 hover:text-gray-300 transition-colors font-semibold"
              >
                ✕
              </button>
            </div>
            <div className="border-t border-gray-800 pt-2 flex flex-col gap-1 text-[11px] text-gray-300">
              <div className="flex justify-between">
                <span className="text-gray-500">Searches Count:</span>
                <span className="font-bold text-white">{selectedMarker.count}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-500">Coordinates:</span>
                <span className="font-mono text-gray-400">
                  {selectedMarker.coordinates[1].toFixed(2)}°, {selectedMarker.coordinates[0].toFixed(2)}°
                </span>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Hover Tooltip Portalled */}
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
          className="bg-slate-950/95 backdrop-blur-md border border-gray-800 px-3 py-2 rounded-lg text-xs shadow-2xl animate-fade-in"
        >
          {tooltip.content}
        </div>
      )}
    </div>
  );
}
