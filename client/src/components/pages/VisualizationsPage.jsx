import { useState } from 'react';
import NetworkGraph from '../visualization/NetworkGraph';

export default function VisualizationsPage() {
  const [language, setLanguage] = useState('la');
  const [nodeType, setNodeType] = useState('author');
  const [activeViz, setActiveViz] = useState('network');

  return (
    <div className="p-4 sm:p-6 min-h-screen">
      <div className="mb-6">
        <h1 className="text-2xl sm:text-3xl font-bold text-red-700 mb-2">
          Distant Reading Visualizations
        </h1>
        <p className="text-gray-400">
          Explore large-scale patterns of literary influence across the classical corpus.
          These visualizations reveal connections invisible through traditional close reading.
        </p>
      </div>

      <div className="flex flex-wrap gap-2 mb-6">
        <button
          onClick={() => setActiveViz('network')}
          className={`px-4 py-2 rounded ${activeViz === 'network' ? 'bg-amber-600 text-white' : 'bg-gray-700 text-gray-300'}`}
        >
          Network Graph
        </button>
        <button
          onClick={() => setActiveViz('sankey')}
          className={`px-4 py-2 rounded ${activeViz === 'sankey' ? 'bg-amber-600 text-white' : 'bg-gray-700 text-gray-300'}`}
        >
          Era Flow (Coming Soon)
        </button>
        <button
          onClick={() => setActiveViz('rankings')}
          className={`px-4 py-2 rounded ${activeViz === 'rankings' ? 'bg-amber-600 text-white' : 'bg-gray-700 text-gray-300'}`}
        >
          Centrality Rankings (Coming Soon)
        </button>
      </div>

      <div className="flex flex-wrap gap-4 mb-4 p-3 bg-gray-800 rounded-lg">
        <div className="flex items-center gap-2">
          <label className="text-sm text-gray-400">Language:</label>
          <select
            value={language}
            onChange={e => setLanguage(e.target.value)}
            className="bg-gray-700 text-gray-200 rounded px-3 py-1"
          >
            <option value="la">Latin</option>
            <option value="grc">Greek</option>
            <option value="en">English</option>
          </select>
        </div>

        <div className="flex items-center gap-2">
          <label className="text-sm text-gray-400">Node Type:</label>
          <select
            value={nodeType}
            onChange={e => setNodeType(e.target.value)}
            className="bg-gray-700 text-gray-200 rounded px-3 py-1"
          >
            <option value="author">Authors</option>
            <option value="work">Works</option>
          </select>
        </div>

        <div className="flex-1 text-right">
          <a
            href="/api/docs"
            target="_blank"
            className="text-sm text-amber-400 hover:text-amber-300"
          >
            API Documentation
          </a>
        </div>
      </div>

      <div className="bg-gray-900 rounded-lg min-h-[500px]">
        {activeViz === 'network' && (
          <NetworkGraph language={language} nodeType={nodeType} />
        )}
        
        {activeViz === 'sankey' && (
          <div className="flex items-center justify-center h-[500px] text-gray-500">
            <div className="text-center">
              <div className="text-6xl mb-4">&#128200;</div>
              <p>Era-to-Era Flow Diagram</p>
              <p className="text-sm mt-2">Coming soon - will show how literary influence flows across time periods</p>
            </div>
          </div>
        )}
        
        {activeViz === 'rankings' && (
          <div className="flex items-center justify-center h-[500px] text-gray-500">
            <div className="text-center">
              <div className="text-6xl mb-4">&#127942;</div>
              <p>Centrality Rankings</p>
              <p className="text-sm mt-2">Coming soon - will show the most-cited and most-citing works</p>
            </div>
          </div>
        )}
      </div>

      <div className="mt-6 p-4 bg-gray-800 rounded-lg">
        <h3 className="text-lg font-semibold text-amber-300 mb-2">Methodology</h3>
        <p className="text-sm text-gray-400 mb-3">
          Connections are identified using a multi-signal composite scoring system that correlates 
          four independent matching algorithms for high precision:
        </p>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="p-3 bg-gray-700 rounded">
            <div className="font-semibold text-amber-200">Lemma Matching</div>
            <div className="text-sm text-gray-400">Threshold: 7+ shared lemmas</div>
            <div className="text-xs text-gray-500">Dictionary-normalized word comparison</div>
          </div>
          <div className="p-3 bg-gray-700 rounded">
            <div className="font-semibold text-amber-200">Semantic Similarity</div>
            <div className="text-sm text-gray-400">Threshold: 0.7+ cosine similarity</div>
            <div className="text-xs text-gray-500">SPhilBERTa neural embeddings</div>
          </div>
          <div className="p-3 bg-gray-700 rounded">
            <div className="font-semibold text-amber-200">Sound Matching</div>
            <div className="text-sm text-gray-400">Threshold: 0.6+ phonetic similarity</div>
            <div className="text-xs text-gray-500">Phonetic transcription comparison</div>
          </div>
          <div className="p-3 bg-gray-700 rounded">
            <div className="font-semibold text-amber-200">Edit Distance</div>
            <div className="text-sm text-gray-400">Threshold: 0.5+ similarity</div>
            <div className="text-xs text-gray-500">Character-level Levenshtein distance</div>
          </div>
        </div>
        <div className="mt-4 flex flex-wrap gap-4">
          <div className="flex items-center gap-2">
            <span className="px-2 py-1 bg-yellow-600 rounded text-xs font-semibold">GOLD</span>
            <span className="text-sm text-gray-400">4 signals confirm</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="px-2 py-1 bg-gray-500 rounded text-xs font-semibold">SILVER</span>
            <span className="text-sm text-gray-400">3 signals confirm</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="px-2 py-1 bg-amber-800 rounded text-xs font-semibold">BRONZE</span>
            <span className="text-sm text-gray-400">2 signals confirm</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="px-2 py-1 bg-orange-900 rounded text-xs font-semibold">COPPER</span>
            <span className="text-sm text-gray-400">1 signal confirms</span>
          </div>
        </div>
      </div>
    </div>
  );
}
