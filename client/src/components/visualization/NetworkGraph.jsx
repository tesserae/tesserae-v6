import { useState, useEffect, useRef, useCallback } from 'react';
import * as d3 from 'd3';

const ERA_COLORS = {
  'Archaic': '#9b2335',
  'Classical': '#e07b00',
  'Hellenistic': '#c5b358',
  'Republic': '#006994',
  'Augustan': '#7851a9',
  'Early Imperial': '#228b22',
  'Later Imperial': '#1e90ff',
  'Late Antique': '#8b4513',
  'Early Medieval': '#708090',
  'default': '#4a5568'
};

export default function NetworkGraph({ language = 'la', nodeType = 'author' }) {
  const svgRef = useRef(null);
  const containerRef = useRef(null);
  const simulationRef = useRef(null);
  const gRef = useRef(null);
  const zoomRef = useRef(null);
  const [nodes, setNodes] = useState([]);
  const [edges, setEdges] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selectedNode, setSelectedNode] = useState(null);
  const [hoveredNode, setHoveredNode] = useState(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [highlightedEra, setHighlightedEra] = useState(null);
  const [showMethodology, setShowMethodology] = useState(false);
  const [filters, setFilters] = useState({
    minDegree: 0,
    era: 'all',
    minTier: 'all'
  });
  const [dimensions, setDimensions] = useState({ width: 800, height: 600 });

  useEffect(() => {
    const updateDimensions = () => {
      if (containerRef.current) {
        const rect = containerRef.current.getBoundingClientRect();
        setDimensions({
          width: Math.max(rect.width, 400),
          height: Math.max(rect.height, 400)
        });
      }
    };
    updateDimensions();
    window.addEventListener('resize', updateDimensions);
    return () => window.removeEventListener('resize', updateDimensions);
  }, []);

  useEffect(() => {
    fetchNetworkData();
  }, [language, nodeType]);

  const fetchNetworkData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [nodesRes, connectionsRes] = await Promise.all([
        fetch(`/api/batch/network/nodes?language=${language}&type=${nodeType}`),
        fetch(`/api/batch/connections?language=${language}&per_page=500`)
      ]);
      
      const nodesData = await nodesRes.json();
      const connectionsData = await connectionsRes.json();
      
      if (nodesData.nodes) {
        setNodes(nodesData.nodes);
      }
      
      if (connectionsData.connections) {
        const edgeData = connectionsData.connections.map(c => {
          let tier = 'copper';
          if (c.stats.gold_count > 0) tier = 'gold';
          else if (c.stats.silver_count > 0) tier = 'silver';
          else if (c.stats.bronze_count > 0) tier = 'bronze';
          
          return {
            source: nodeType === 'author' ? c.source.author : c.source.text_id,
            target: nodeType === 'author' ? c.target.author : c.target.text_id,
            strength: c.stats.connection_strength,
            goldCount: c.stats.gold_count,
            silverCount: c.stats.silver_count,
            bronzeCount: c.stats.bronze_count,
            totalParallels: c.stats.total_parallels,
            tier: tier
          };
        });
        setEdges(edgeData);
      }
    } catch (err) {
      setError('Failed to load network data');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const filteredNodes = nodes.filter(node => {
    if (node.total_degree < filters.minDegree) return false;
    if (filters.era !== 'all' && node.era !== filters.era) return false;
    return true;
  });

  const filteredNodeIds = new Set(filteredNodes.map(n => n.id));
  
  const filteredEdges = edges.filter(edge => {
    if (!filteredNodeIds.has(edge.source) || !filteredNodeIds.has(edge.target)) return false;
    if (filters.minTier !== 'all') {
      const tierOrder = { gold: 4, silver: 3, bronze: 2, copper: 1 };
      if (tierOrder[edge.tier] < tierOrder[filters.minTier]) return false;
    }
    return true;
  });

  const TIER_COLORS = {
    gold: '#fbbf24',
    silver: '#9ca3af',
    bronze: '#b45309',
    copper: '#c2410c'
  };

  // Build the D3 simulation and bindonce — runs only when data or dimensions change
  useEffect(() => {
    if (!svgRef.current) return;

    const svg = d3.select(svgRef.current);
    svg.selectAll('*').remove();

    const { width, height } = dimensions;
    
    if (filteredNodes.length === 0) {
      svg.append('text')
        .attr('x', width / 2)
        .attr('y', height / 2)
        .attr('text-anchor', 'middle')
        .attr('fill', '#9ca3af')
        .text('No data available. Run a batch job to generate network data.');
      return;
    }
    
    const nodeMap = new Map(filteredNodes.map(n => [n.id, { ...n }]));
    
    const graphNodes = filteredNodes.map(n => ({
      id: n.id,
      era: n.era,
      inDegree: n.in_degree || 0,
      outDegree: n.out_degree || 0,
      totalDegree: n.total_degree || 0,
      goldTotal: n.gold_total || 0,
      author: n.author,
      work: n.work
    }));
    
    const graphEdges = filteredEdges.map(e => ({
      source: e.source,
      target: e.target,
      strength: e.strength || 1,
      goldCount: e.goldCount || 0,
      tier: e.tier || 'bronze'
    })).filter(e => nodeMap.has(e.source) && nodeMap.has(e.target));

    const g = svg.append('g');
    gRef.current = g;

    const zoom = d3.zoom()
      .scaleExtent([0.1, 4])
      .on('zoom', (event) => {
        g.attr('transform', event.transform);
      });
    zoomRef.current = zoom;

    svg.call(zoom);

    const simulation = d3.forceSimulation(graphNodes)
      .force('link', d3.forceLink(graphEdges).id(d => d.id).distance(100))
      .force('charge', d3.forceManyBody().strength(-200))
      .force('center', d3.forceCenter(width / 2, height / 2))
      .force('collision', d3.forceCollide().radius(d => Math.sqrt(d.totalDegree) * 3 + 10));
    simulationRef.current = simulation;

    const maxStrength = d3.max(graphEdges, d => d.strength) || 1;
    const strokeScale = d3.scaleLinear()
      .domain([0, maxStrength])
      .range([0.5, 4]);

    const link = g.append('g')
      .attr('class', 'links')
      .selectAll('line')
      .data(graphEdges)
      .join('line')
      .attr('stroke', d => TIER_COLORS[d.tier] || '#4b5563')
      .attr('stroke-opacity', 0.6)
      .attr('stroke-width', d => strokeScale(d.strength));

    const maxDegree = d3.max(graphNodes, d => d.totalDegree) || 1;
    const sizeScale = d3.scaleSqrt()
      .domain([0, maxDegree])
      .range([4, 30]);

    const node = g.append('g')
      .attr('class', 'nodes')
      .selectAll('circle')
      .data(graphNodes)
      .join('circle')
      .attr('r', d => sizeScale(d.totalDegree))
      .attr('fill', d => ERA_COLORS[d.era] || ERA_COLORS.default)
      .attr('stroke', '#1f2937')
      .attr('stroke-width', 1.5)
      .style('cursor', 'pointer')
      .call(d3.drag()
        .on('start', dragstarted)
        .on('drag', dragged)
        .on('end', dragended))
      .on('click', (event, d) => {
        event.stopPropagation();
        setSelectedNode(d);
      })
      // Double-click: navigate to the search page with this author pre-filled
      .on('dblclick', (event, d) => {
        event.preventDefault();
        event.stopPropagation();
        const authorKey = d.author || d.id;
        const lang = language || 'la';
        window.location.href = `/?source_author=${encodeURIComponent(authorKey)}&lang=${lang}`;
      })
      // Hover: highlight this node + connections
      .on('mouseover', (event, d) => {
        setHoveredNode(d);
      })
      .on('mouseout', () => {
        setHoveredNode(null);
      });

    node.append('title')
      .text(d => `${d.id}\nEra: ${d.era || 'Unknown'}\nIn-degree: ${d.inDegree}\nOut-degree: ${d.outDegree}`);

    const labels = g.append('g')
      .attr('class', 'labels')
      .selectAll('text')
      .data(graphNodes.filter(d => d.totalDegree > maxDegree * 0.2))
      .join('text')
      .attr('text-anchor', 'middle')
      .attr('dy', d => sizeScale(d.totalDegree) + 12)
      .attr('fill', '#d1d5db')
      .attr('font-size', '10px')
      .text(d => d.id.length > 15 ? d.id.substring(0, 12) + '...' : d.id);

    simulation.on('tick', () => {
      link
        .attr('x1', d => d.source.x)
        .attr('y1', d => d.source.y)
        .attr('x2', d => d.target.x)
        .attr('y2', d => d.target.y);

      node
        .attr('cx', d => d.x)
        .attr('cy', d => d.y);

      labels
        .attr('x', d => d.x)
        .attr('y', d => d.y);
    });

    // Click on background to deselect
    svg.on('click', () => {
      setSelectedNode(null);
    });

    function dragstarted(event) {
      if (!event.active) simulation.alphaTarget(0.3).restart();
      event.subject.fx = event.subject.x;
      event.subject.fy = event.subject.y;
    }

    function dragged(event) {
      event.subject.fx = event.x;
      event.subject.fy = event.y;
    }

    function dragended(event) {
      if (!event.active) simulation.alphaTarget(0);
      event.subject.fx = null;
      event.subject.fy = null;
    }

    return () => {
      simulation.stop();
    };
  }, [filteredNodes, filteredEdges, dimensions]);

  // Lightweight highlight effect — runs on hover/select/search/era changes WITHOUT rebuilding simulation
  useEffect(() => {
    if (!gRef.current) return;
    const g = gRef.current;

    const activeNodeId = hoveredNode?.id || selectedNode?.id || null;

    // Build a set of connected node IDs
    const connectedIds = new Set();
    if (activeNodeId) {
      connectedIds.add(activeNodeId);
      g.select('.links').selectAll('line').each(function(d) {
        const sourceId = typeof d.source === 'object' ? d.source.id : d.source;
        const targetId = typeof d.target === 'object' ? d.target.id : d.target;
        if (sourceId === activeNodeId) connectedIds.add(targetId);
        if (targetId === activeNodeId) connectedIds.add(sourceId);
      });
    }

    // Search match set
    const searchMatch = searchTerm.trim().toLowerCase();
    const matchingSearchIds = new Set();
    if (searchMatch) {
      g.select('.nodes').selectAll('circle').each(function(d) {
        if (d.id.toLowerCase().includes(searchMatch)) {
          matchingSearchIds.add(d.id);
        }
      });
    }

    // Determine if any highlight mode is active
    const isHighlighting = activeNodeId || searchMatch || highlightedEra;

    // Transition nodes
    g.select('.nodes').selectAll('circle')
      .transition()
      .duration(200)
      .attr('opacity', d => {
        if (!isHighlighting) return 1;
        if (activeNodeId && connectedIds.has(d.id)) return 1;
        if (searchMatch && matchingSearchIds.has(d.id)) return 1;
        if (highlightedEra && d.era === highlightedEra) return 1;
        return 0.15;
      })
      .attr('stroke-width', d => {
        if (activeNodeId && d.id === activeNodeId) return 3;
        if (searchMatch && matchingSearchIds.has(d.id)) return 3;
        return 1.5;
      });

    // Transition edges
    g.select('.links').selectAll('line')
      .transition()
      .duration(200)
      .attr('stroke-opacity', d => {
        if (!isHighlighting) return 0.6;
        const sourceId = typeof d.source === 'object' ? d.source.id : d.source;
        const targetId = typeof d.target === 'object' ? d.target.id : d.target;
        if (activeNodeId && (sourceId === activeNodeId || targetId === activeNodeId)) return 0.9;
        if (highlightedEra) return 0.6; // keep edges visible during era highlight
        return 0.05;
      })
      .attr('stroke-width', function(d) {
        const sourceId = typeof d.source === 'object' ? d.source.id : d.source;
        const targetId = typeof d.target === 'object' ? d.target.id : d.target;
        if (activeNodeId && (sourceId === activeNodeId || targetId === activeNodeId)) {
          return parseFloat(d3.select(this).attr('stroke-width')) * 1.5;
        }
        return parseFloat(d3.select(this).attr('stroke-width'));
      });

    // Transition labels
    g.select('.labels').selectAll('text')
      .transition()
      .duration(200)
      .attr('opacity', d => {
        if (!isHighlighting) return 1;
        if (activeNodeId && connectedIds.has(d.id)) return 1;
        if (searchMatch && matchingSearchIds.has(d.id)) return 1;
        if (highlightedEra && d.era === highlightedEra) return 1;
        return 0.1;
      });

  }, [hoveredNode, selectedNode, searchTerm, highlightedEra]);

  // Search zoom-to-node effect
  useEffect(() => {
    if (!searchTerm.trim() || !gRef.current || !svgRef.current || !zoomRef.current) return;
    const g = gRef.current;
    const svg = d3.select(svgRef.current);
    const searchLower = searchTerm.trim().toLowerCase();
    
    let targetNode = null;
    g.select('.nodes').selectAll('circle').each(function(d) {
      if (d.id.toLowerCase() === searchLower) {
        targetNode = d;
      }
    });
    // If exact match not found, try partial
    if (!targetNode) {
      g.select('.nodes').selectAll('circle').each(function(d) {
        if (!targetNode && d.id.toLowerCase().includes(searchLower)) {
          targetNode = d;
        }
      });
    }

    if (targetNode && targetNode.x != null && targetNode.y != null) {
      const { width, height } = dimensions;
      const scale = 2;
      const transform = d3.zoomIdentity
        .translate(width / 2, height / 2)
        .scale(scale)
        .translate(-targetNode.x, -targetNode.y);
      
      svg.transition()
        .duration(750)
        .call(zoomRef.current.transform, transform);
    }
  }, [searchTerm, dimensions]);

  const handleUseAs = useCallback((role) => {
    if (!selectedNode) return;
    const authorKey = selectedNode.author || selectedNode.id;
    const lang = language || 'la';
    const param = role === 'source' ? 'source_author' : 'target_author';
    window.location.href = `/?${param}=${encodeURIComponent(authorKey)}&lang=${lang}`;
  }, [selectedNode, language]);

  const uniqueEras = [...new Set(nodes.map(n => n.era).filter(Boolean))].sort();
  const searchMatches = searchTerm.trim()
    ? filteredNodes.filter(n => n.id.toLowerCase().includes(searchTerm.trim().toLowerCase()))
    : [];

  return (
    <div className="bg-gray-800 rounded-lg p-4 h-full flex flex-col">
      {/* Controls row */}
      <div className="flex flex-wrap gap-4 mb-4 items-center">
        <h3 className="text-lg font-semibold text-amber-400">Network Graph</h3>
        
        {/* Search Box */}
        <div className="relative flex-1 min-w-[160px] max-w-[280px]">
          <input
            type="text"
            value={searchTerm}
            onChange={e => setSearchTerm(e.target.value)}
            placeholder="Search node..."
            className="w-full bg-gray-700 text-gray-200 rounded px-3 py-1.5 text-sm placeholder-gray-500 border border-gray-600 focus:border-amber-400 focus:outline-none transition-colors"
          />
          {searchTerm && (
            <button
              onClick={() => setSearchTerm('')}
              className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-200 text-sm"
            >
              ✕
            </button>
          )}
          {searchTerm && searchMatches.length > 0 && (
            <div className="absolute z-50 w-full mt-1 bg-gray-700 border border-gray-600 rounded shadow-lg max-h-32 overflow-y-auto">
              {searchMatches.slice(0, 8).map(n => (
                <button
                  key={n.id}
                  onClick={() => { setSearchTerm(n.id); setSelectedNode({ ...n, totalDegree: n.total_degree || 0, inDegree: n.in_degree || 0, outDegree: n.out_degree || 0, goldTotal: n.gold_total || 0 }); }}
                  className="w-full text-left px-3 py-1.5 text-sm text-gray-200 hover:bg-gray-600"
                >
                  {n.id} <span className="text-gray-500 text-xs">({n.era || 'Unknown'})</span>
                </button>
              ))}
            </div>
          )}
        </div>

        <div className="flex items-center gap-2">
          <label className="text-sm text-gray-400">Min Degree:</label>
          <input
            type="range"
            min="0"
            max={Math.max(...nodes.map(n => n.total_degree || 0), 10)}
            value={filters.minDegree}
            onChange={e => setFilters(f => ({ ...f, minDegree: parseInt(e.target.value) }))}
            className="w-24"
          />
          <span className="text-sm text-gray-300">{filters.minDegree}</span>
        </div>

        <div className="flex items-center gap-2">
          <label className="text-sm text-gray-400">Era:</label>
          <select
            value={filters.era}
            onChange={e => setFilters(f => ({ ...f, era: e.target.value }))}
            className="bg-gray-700 text-gray-200 rounded px-2 py-1 text-sm"
          >
            <option value="all">All Eras</option>
            {uniqueEras.map(era => (
              <option key={era} value={era}>{era}</option>
            ))}
          </select>
        </div>

        <div className="flex items-center gap-2">
          <label className="text-sm text-gray-400">Min Tier:</label>
          <select
            value={filters.minTier}
            onChange={e => setFilters(f => ({ ...f, minTier: e.target.value }))}
            className="bg-gray-700 text-gray-200 rounded px-2 py-1 text-sm"
          >
            <option value="all">All Tiers</option>
            <option value="copper">Copper+</option>
            <option value="bronze">Bronze+</option>
            <option value="silver">Silver+</option>
            <option value="gold">Gold Only</option>
          </select>
        </div>

        <div className="text-sm text-gray-400">
          {filteredNodes.length} nodes, {filteredEdges.length} edges
        </div>

        {/* Methodology help toggle */}
        <button
          onClick={() => setShowMethodology(!showMethodology)}
          className="text-sm text-amber-400 hover:text-amber-300 ml-auto"
          title="What is this graph?"
        >
          ℹ️ What is this?
        </button>
      </div>

      {/* Methodology popup */}
      {showMethodology && (
        <div className="mb-4 p-4 bg-gray-700/80 backdrop-blur rounded-lg border border-gray-600 text-sm text-gray-300 relative">
          <button
            onClick={() => setShowMethodology(false)}
            className="absolute top-2 right-3 text-gray-400 hover:text-gray-200 text-lg"
          >
            ✕
          </button>
          <h4 className="font-semibold text-amber-300 mb-2">Understanding the Network Graph</h4>
          <p className="mb-2">
            This graph maps <strong>literary influence</strong> across the classical corpus. Each 
            <strong> dot (node)</strong> represents an author or work. <strong>Lines (edges)</strong> 
            connecting them show the volume of shared textual parallels detected by Tesserae's 
            multi-signal analysis.
          </p>
          <ul className="list-disc list-inside space-y-1 mb-2">
            <li><strong>Bigger dots</strong> = more connections (higher degree centrality)</li>
            <li><strong>Thicker lines</strong> = stronger textual parallels</li>
            <li><strong>Colors</strong> = historical era (see legend below)</li>
            <li><strong>Edge colors</strong> = confidence tier (Gold ≥ 4 signals, Silver ≥ 3, Bronze ≥ 2, Copper = 1)</li>
          </ul>
          <p className="text-xs text-gray-500">
            <strong>Interactions:</strong> Hover to highlight connections • Click to inspect details • 
            Double-click to start a search with that author • Use the search box to locate nodes
          </p>
        </div>
      )}

      {/* Interactive era legend */}
      <div className="flex gap-4 mb-3 flex-wrap items-center">
        <div className="flex gap-3">
          {Object.entries(ERA_COLORS).filter(([k]) => k !== 'default').map(([era, color]) => (
            <button
              key={era}
              onClick={() => setHighlightedEra(highlightedEra === era ? null : era)}
              className={`flex items-center gap-1 transition-all duration-200 rounded px-1.5 py-0.5 ${
                highlightedEra === era 
                  ? 'ring-1 ring-amber-400 bg-gray-700' 
                  : highlightedEra ? 'opacity-40' : ''
              }`}
              title={`Click to ${highlightedEra === era ? 'un-' : ''}highlight ${era} era`}
            >
              <div className="w-3 h-3 rounded-full flex-shrink-0" style={{ backgroundColor: color }} />
              <span className="text-xs text-gray-400">{era}</span>
            </button>
          ))}
          {highlightedEra && (
            <button
              onClick={() => setHighlightedEra(null)}
              className="text-xs text-amber-400 hover:text-amber-300 ml-1"
            >
              Clear
            </button>
          )}
        </div>
        <div className="border-l border-gray-600 pl-3 flex gap-3">
          <span className="text-xs text-gray-500">Edges:</span>
          <div className="flex items-center gap-1">
            <div className="w-8 h-1 rounded" style={{ backgroundColor: '#fbbf24' }} />
            <span className="text-xs text-gray-400">Gold</span>
          </div>
          <div className="flex items-center gap-1">
            <div className="w-8 h-1 rounded" style={{ backgroundColor: '#9ca3af' }} />
            <span className="text-xs text-gray-400">Silver</span>
          </div>
          <div className="flex items-center gap-1">
            <div className="w-8 h-1 rounded" style={{ backgroundColor: '#b45309' }} />
            <span className="text-xs text-gray-400">Bronze</span>
          </div>
          <div className="flex items-center gap-1">
            <div className="w-8 h-1 rounded" style={{ backgroundColor: '#c2410c' }} />
            <span className="text-xs text-gray-400">Copper</span>
          </div>
        </div>
      </div>

      {/* SVG canvas */}
      <div ref={containerRef} className="flex-1 relative min-h-[400px] bg-gray-900 rounded">
        {loading && (
          <div className="absolute inset-0 flex items-center justify-center bg-gray-900/80 z-10">
            <div className="text-gray-400">Loading network data...</div>
          </div>
        )}
        
        {error && (
          <div className="absolute inset-0 flex items-center justify-center bg-gray-900/80 z-10">
            <div className="text-red-400">{error}</div>
          </div>
        )}

        <svg
          ref={svgRef}
          width={dimensions.width}
          height={dimensions.height}
          className="w-full h-full"
        />
      </div>

      {/* Selected node detail card */}
      {selectedNode && (
        <div className="mt-4 p-4 bg-gray-700 rounded-lg border border-gray-600">
          <div className="flex items-start justify-between mb-3">
            <h4 className="font-semibold text-amber-300 text-lg">{selectedNode.id}</h4>
            <button
              onClick={() => setSelectedNode(null)}
              className="text-gray-400 hover:text-gray-200 text-lg leading-none"
            >
              ✕
            </button>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-sm mb-4">
            <div>
              <span className="text-gray-400 block text-xs">Era</span>
              <span className="text-gray-200 font-medium">{selectedNode.era || 'Unknown'}</span>
            </div>
            <div>
              <span className="text-gray-400 block text-xs">In-degree (cited)</span>
              <span className="text-gray-200 font-medium">{selectedNode.inDegree}</span>
            </div>
            <div>
              <span className="text-gray-400 block text-xs">Out-degree (citing)</span>
              <span className="text-gray-200 font-medium">{selectedNode.outDegree}</span>
            </div>
            <div>
              <span className="text-gray-400 block text-xs">Gold connections</span>
              <span className="text-yellow-400 font-medium">{selectedNode.goldTotal}</span>
            </div>
          </div>
          {/* Action buttons */}
          <div className="flex flex-wrap gap-2">
            <button
              onClick={() => handleUseAs('source')}
              className="px-3 py-1.5 text-sm bg-red-700 text-white rounded hover:bg-red-800 transition-colors"
            >
              Use as Source
            </button>
            <button
              onClick={() => handleUseAs('target')}
              className="px-3 py-1.5 text-sm bg-amber-600 text-white rounded hover:bg-amber-700 transition-colors"
            >
              Use as Target
            </button>
            <span className="text-xs text-gray-500 self-center ml-2">
              or double-click a node to jump to search
            </span>
          </div>
        </div>
      )}
    </div>
  );
}
