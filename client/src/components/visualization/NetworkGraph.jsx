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
  const [nodes, setNodes] = useState([]);
  const [edges, setEdges] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selectedNode, setSelectedNode] = useState(null);
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

    const zoom = d3.zoom()
      .scaleExtent([0.1, 4])
      .on('zoom', (event) => {
        g.attr('transform', event.transform);
      });

    svg.call(zoom);

    const simulation = d3.forceSimulation(graphNodes)
      .force('link', d3.forceLink(graphEdges).id(d => d.id).distance(100))
      .force('charge', d3.forceManyBody().strength(-200))
      .force('center', d3.forceCenter(width / 2, height / 2))
      .force('collision', d3.forceCollide().radius(d => Math.sqrt(d.totalDegree) * 3 + 10));

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
        setSelectedNode(d);
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

  const uniqueEras = [...new Set(nodes.map(n => n.era).filter(Boolean))].sort();

  return (
    <div className="bg-gray-800 rounded-lg p-4 h-full flex flex-col">
      <div className="flex flex-wrap gap-4 mb-4 items-center">
        <h3 className="text-lg font-semibold text-amber-400">Network Graph</h3>
        
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
      </div>

      <div className="flex gap-4 mb-3 flex-wrap items-center">
        <div className="flex gap-3">
          {Object.entries(ERA_COLORS).filter(([k]) => k !== 'default').slice(0, 6).map(([era, color]) => (
            <div key={era} className="flex items-center gap-1">
              <div className="w-3 h-3 rounded-full" style={{ backgroundColor: color }} />
              <span className="text-xs text-gray-400">{era}</span>
            </div>
          ))}
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

      <div ref={containerRef} className="flex-1 relative min-h-[400px] bg-gray-900 rounded">
        {loading && (
          <div className="absolute inset-0 flex items-center justify-center bg-gray-900/80">
            <div className="text-gray-400">Loading network data...</div>
          </div>
        )}
        
        {error && (
          <div className="absolute inset-0 flex items-center justify-center bg-gray-900/80">
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

      {selectedNode && (
        <div className="mt-4 p-3 bg-gray-700 rounded">
          <h4 className="font-semibold text-amber-300 mb-2">{selectedNode.id}</h4>
          <div className="grid grid-cols-2 gap-2 text-sm">
            <div><span className="text-gray-400">Era:</span> <span className="text-gray-200">{selectedNode.era || 'Unknown'}</span></div>
            <div><span className="text-gray-400">In-degree (cited):</span> <span className="text-gray-200">{selectedNode.inDegree}</span></div>
            <div><span className="text-gray-400">Out-degree (citing):</span> <span className="text-gray-200">{selectedNode.outDegree}</span></div>
            <div><span className="text-gray-400">Gold connections:</span> <span className="text-yellow-400">{selectedNode.goldTotal}</span></div>
          </div>
          <button
            onClick={() => setSelectedNode(null)}
            className="mt-2 text-sm text-gray-400 hover:text-gray-200"
          >
            Close
          </button>
        </div>
      )}
    </div>
  );
}
