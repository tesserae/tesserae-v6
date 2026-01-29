import { useState, useCallback, useRef, useMemo, useEffect } from 'react';
import { wildcardSearch } from '../../utils/api';
import { Chart as ChartJS, CategoryScale, LinearScale, BarElement, Title, Tooltip, Legend } from 'chart.js';
import { Bar } from 'react-chartjs-2';

ChartJS.register(CategoryScale, LinearScale, BarElement, Title, Tooltip, Legend);

const ERA_ORDER = ['Archaic', 'Classical', 'Hellenistic', 'Republic', 'Augustan', 'Early Imperial', 'Later Imperial', 'Late Antique', 'Early Medieval', 'Unknown'];
const ERA_COLORS = {
  'Archaic': 'rgba(155, 35, 53, 0.7)',
  'Classical': 'rgba(224, 123, 0, 0.7)',
  'Hellenistic': 'rgba(197, 179, 88, 0.7)',
  'Republic': 'rgba(0, 105, 148, 0.7)',
  'Augustan': 'rgba(120, 81, 169, 0.7)',
  'Early Imperial': 'rgba(34, 139, 34, 0.7)',
  'Later Imperial': 'rgba(30, 144, 255, 0.7)',
  'Late Antique': 'rgba(139, 69, 19, 0.7)',
  'Early Medieval': 'rgba(112, 128, 144, 0.7)',
  'Unknown': 'rgba(128, 128, 128, 0.7)'
};

const WildcardSearch = ({ language }) => {
  const [query, setQuery] = useState(() => {
    const gotoQuery = sessionStorage.getItem('tesserae_goto_query');
    if (gotoQuery) {
      sessionStorage.removeItem('tesserae_goto_query');
      return gotoQuery;
    }
    return '';
  });
  const [results, setResults] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [caseSensitive, setCaseSensitive] = useState(false);
  const [maxResults, setMaxResults] = useState(200);
  const [targetText, setTargetText] = useState('');
  const [showPoetry, setShowPoetry] = useState(true);
  const [showProse, setShowProse] = useState(true);
  const [showTimeline, setShowTimeline] = useState(false);
  const [sortOrder, setSortOrder] = useState('chronological');
  const [eraFilter, setEraFilter] = useState(null);
  const [authorFilter, setAuthorFilter] = useState(null);
  const [displayLimit, setDisplayLimit] = useState(50);
  const chartRef = useRef(null);
  const authorChartRef = useRef(null);

  // Clear results when language changes
  useEffect(() => {
    setResults(null);
    setError(null);
    setEraFilter(null);
    setAuthorFilter(null);
  }, [language]);

  const handleSearch = async () => {
    if (!query.trim()) return;
    
    setLoading(true);
    setError(null);
    setEraFilter(null);
    setAuthorFilter(null);
    setDisplayLimit(50);
    
    try {
      const data = await wildcardSearch({
        query: query.trim(),
        language,
        target_text: targetText || null,
        case_sensitive: caseSensitive,
        max_results: maxResults
      });
      
      if (data.error) {
        setError(data.error);
      } else {
        setResults(data);
      }
    } catch (e) {
      setError('Search failed: ' + e.message);
    }
    
    setLoading(false);
  };

  const filteredResults = useMemo(() => {
    if (!results?.results) return [];
    
    let filtered = results.results.filter(r => {
      if (eraFilter && (r.era || 'Unknown') !== eraFilter) return false;
      if (authorFilter && r.author !== authorFilter) return false;
      const isPoetry = r.is_poetry !== false;
      if (!showPoetry && isPoetry) return false;
      if (!showProse && !isPoetry) return false;
      return true;
    });
    
    if (sortOrder === 'alphabetical') {
      return [...filtered].sort((a, b) => {
        const authorCmp = (a.author || '').localeCompare(b.author || '');
        if (authorCmp !== 0) return authorCmp;
        return (a.title || '').localeCompare(b.title || '');
      });
    }
    return [...filtered].sort((a, b) => {
      const aYear = a.year || 9999;
      const bYear = b.year || 9999;
      if (aYear !== bYear) return aYear - bYear;
      return (a.author || '').localeCompare(b.author || '');
    });
  }, [results, eraFilter, authorFilter, showPoetry, showProse, sortOrder]);

  const allResults = results?.results || [];

  const getTimelineData = useCallback(() => {
    if (!allResults || allResults.length === 0) return null;
    
    const eraCounts = {};
    allResults.forEach(r => {
      const era = r.era || 'Unknown';
      eraCounts[era] = (eraCounts[era] || 0) + 1;
    });
    
    const sortedEras = ERA_ORDER.filter(era => eraCounts[era]);
    return {
      labels: sortedEras,
      datasets: [{
        label: 'Matches by Era',
        data: sortedEras.map(era => eraCounts[era] || 0),
        backgroundColor: sortedEras.map(era => ERA_COLORS[era] || 'rgba(128,128,128,0.7)')
      }]
    };
  }, [allResults]);

  const getAuthorTimelineData = useCallback(() => {
    if (!allResults || allResults.length === 0) return null;
    
    const authorCounts = {};
    allResults.forEach(r => {
      const author = r.author || 'Unknown';
      authorCounts[author] = (authorCounts[author] || 0) + 1;
    });
    
    const sortedAuthors = Object.keys(authorCounts).sort((a, b) => {
      const aResult = allResults.find(r => r.author === a);
      const bResult = allResults.find(r => r.author === b);
      const aYear = aResult?.year || 9999;
      const bYear = bResult?.year || 9999;
      if (aYear !== bYear) return aYear - bYear;
      return a.localeCompare(b);
    });
    
    return {
      labels: sortedAuthors,
      datasets: [{
        label: 'Matches by Author',
        data: sortedAuthors.map(a => authorCounts[a] || 0),
        backgroundColor: 'rgba(155, 35, 53, 0.7)'
      }]
    };
  }, [allResults]);

  const exportCSV = useCallback(() => {
    if (!filteredResults || filteredResults.length === 0) return;
    
    const headers = ['Author', 'Title', 'Era', 'Locus', 'Text', 'Poetry/Prose'];
    const rows = filteredResults.map(r => [
      r.author || '',
      r.title || '',
      r.era || 'Unknown',
      r.locus || '',
      (r.text || '').replace(/<[^>]*>/g, '').replace(/"/g, '""'),
      r.is_poetry !== false ? 'Poetry' : 'Prose'
    ]);
    
    const csv = [headers.join(','), ...rows.map(r => r.map(c => `"${c}"`).join(','))].join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `tesserae_wildcard_${query.replace(/[^a-zA-Z0-9]/g, '_')}_${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  }, [filteredResults, query]);

  const chartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    onClick: (event, elements) => {
      if (elements.length > 0) {
        const chartData = getTimelineData();
        if (chartData) {
          const idx = elements[0].index;
          const clickedEra = chartData.labels[idx];
          setEraFilter(eraFilter === clickedEra ? null : clickedEra);
          setAuthorFilter(null);
        }
      }
    },
    plugins: { legend: { display: false } },
    scales: { y: { beginAtZero: true, ticks: { precision: 0 } } }
  };

  const authorChartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    onClick: (event, elements) => {
      if (elements.length > 0) {
        const chartData = getAuthorTimelineData();
        if (chartData) {
          const idx = elements[0].index;
          const clickedAuthor = chartData.labels[idx];
          setAuthorFilter(authorFilter === clickedAuthor ? null : clickedAuthor);
          setEraFilter(null);
        }
      }
    },
    plugins: { legend: { display: false } },
    scales: { y: { beginAtZero: true, ticks: { precision: 0 } } }
  };

  const languageLabel = language === 'la' ? 'Latin' : language === 'grc' ? 'Greek' : 'English';

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-xl font-bold mb-2">String Search</h2>
        <p className="text-gray-600 text-sm">
          Search for words and patterns across the entire {languageLabel} corpus using wildcards and boolean operators.
        </p>
      </div>

      <div className="bg-gray-50 rounded-lg p-4 text-sm">
        <h4 className="font-medium mb-2">Search Syntax</h4>
        <ul className="space-y-1 text-gray-600">
          <li><code className="bg-gray-200 px-1 rounded">*</code> matches any characters (e.g., <code>am*</code> finds amor, amicus, etc.)</li>
          <li><code className="bg-gray-200 px-1 rounded">?</code> matches single character (e.g., <code>am?r</code> finds amor, amer)</li>
          <li><code className="bg-gray-200 px-1 rounded">AND</code> both terms required (e.g., <code>amor AND bellum</code>)</li>
          <li><code className="bg-gray-200 px-1 rounded">OR</code> either term (e.g., <code>rex OR regina</code>)</li>
          <li><code className="bg-gray-200 px-1 rounded">~</code> proximity search (e.g., <code>amor ~ dolor</code> finds words within ~100 characters)</li>
          <li><code className="bg-gray-200 px-1 rounded">"..."</code> exact phrase (e.g., <code>"arma virumque"</code>)</li>
        </ul>
      </div>

      <div className="space-y-3">
        <div className="flex gap-2">
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && query.trim() && handleSearch()}
            placeholder="Enter search query..."
            className="flex-1 border rounded px-3 py-2"
          />
          <button
            onClick={handleSearch}
            disabled={loading || !query.trim()}
            className="px-4 py-2 bg-red-700 text-white rounded hover:bg-red-800 disabled:opacity-50"
          >
            {loading ? 'Searching...' : 'Search'}
          </button>
        </div>

        <div className="flex flex-wrap gap-4 text-sm">
          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={caseSensitive}
              onChange={(e) => setCaseSensitive(e.target.checked)}
              className="rounded"
            />
            Case sensitive
          </label>
          
          <div className="flex items-center gap-2">
            <span className="text-gray-600">Max results:</span>
            <input
              type="number"
              value={maxResults}
              onChange={(e) => setMaxResults(parseInt(e.target.value) || 200)}
              className="w-20 border rounded px-2 py-1"
            />
          </div>
          
          <div className="flex items-center gap-2">
            <span className="text-gray-600">Limit to text:</span>
            <input
              type="text"
              value={targetText}
              onChange={(e) => setTargetText(e.target.value)}
              placeholder="e.g., vergil.aeneid"
              className="w-40 border rounded px-2 py-1"
            />
          </div>
        </div>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded">
          {error}
        </div>
      )}

      {loading && (
        <div className="flex items-center justify-center py-12">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-red-700"></div>
          <span className="ml-3 text-gray-600">Searching corpus...</span>
        </div>
      )}

      {!loading && results && (
        <div className="bg-white rounded-lg shadow overflow-hidden">
          <div className="px-4 py-3 bg-gray-50 flex flex-wrap items-center justify-between gap-2">
            <span className="text-sm text-gray-600">
              Found {results.total_matches} match{results.total_matches !== 1 ? 'es' : ''}
              {results.truncated && (
                <span className="text-amber-600 ml-1">(showing first {results.results?.length})</span>
              )}
              {filteredResults.length !== results.results?.length && (
                <span className="text-amber-600 ml-1">(showing {filteredResults.length} after filters)</span>
              )}
              <span className="text-gray-400 ml-2">
                ({results.texts_searched}/{results.total_texts} texts in {results.search_time}s)
              </span>
            </span>
            <div className="flex items-center gap-3">
              <label className="flex items-center gap-1 text-sm text-gray-600">
                <input
                  type="checkbox"
                  checked={showPoetry}
                  onChange={e => setShowPoetry(e.target.checked)}
                  className="rounded"
                />
                Poetry
              </label>
              <label className="flex items-center gap-1 text-sm text-gray-600">
                <input
                  type="checkbox"
                  checked={showProse}
                  onChange={e => setShowProse(e.target.checked)}
                  className="rounded"
                />
                Prose
              </label>
              <select
                value={sortOrder}
                onChange={e => setSortOrder(e.target.value)}
                className="text-sm border rounded px-2 py-1"
              >
                <option value="chronological">By Era</option>
                <option value="alphabetical">A-Z</option>
              </select>
              <button
                onClick={() => setShowTimeline(!showTimeline)}
                className={`text-sm px-3 py-1 rounded ${showTimeline ? 'bg-amber-700 text-white' : 'bg-amber-100 text-amber-700 hover:bg-amber-200'}`}
              >
                {showTimeline ? 'Hide Timelines' : 'Show Timelines'}
              </button>
              <button
                onClick={exportCSV}
                className="text-sm bg-green-600 text-white px-3 py-1 rounded hover:bg-green-700"
              >
                Export CSV
              </button>
            </div>
          </div>

          {showTimeline && allResults.some(r => r.era) && (
            <div className="p-4 border-b bg-gray-50 space-y-6">
              <div>
                <h4 className="text-sm font-medium text-gray-700 mb-2">Period Timeline</h4>
                <div style={{ height: '180px' }}>
                  <Bar ref={chartRef} data={getTimelineData() || { labels: [], datasets: [] }} options={chartOptions} />
                </div>
              </div>
              <div>
                <h4 className="text-sm font-medium text-gray-700 mb-2">Author Timeline</h4>
                <div style={{ height: '180px' }}>
                  <Bar ref={authorChartRef} data={getAuthorTimelineData() || { labels: [], datasets: [] }} options={authorChartOptions} />
                </div>
              </div>
            </div>
          )}

          {(eraFilter || authorFilter) && (
            <div className="px-4 py-2 bg-amber-50 border-b flex items-center justify-between">
              <span className="text-sm text-amber-800">
                Showing {filteredResults.length} matches from {eraFilter || authorFilter}
              </span>
              <button
                onClick={() => { setEraFilter(null); setAuthorFilter(null); }}
                className="text-xs text-amber-600 hover:text-amber-800 font-medium"
              >
                Clear Filter
              </button>
            </div>
          )}

          <div className="divide-y divide-gray-200 max-h-[600px] overflow-y-auto">
            {filteredResults.slice(0, displayLimit).map((r, i) => {
              const refParts = r.reference?.split(/\s+/) || [];
              const locus = refParts[refParts.length - 1] || r.reference || '';
              
              return (
                <div key={i} className="p-4 hover:bg-gray-50">
                  <div className="flex flex-col sm:flex-row sm:items-start gap-2">
                    <div className="sm:w-48 flex-shrink-0">
                      <div className="text-sm font-medium text-gray-900">
                        {r.author || r.display_name}
                      </div>
                      <div className="text-xs text-gray-500">
                        {r.title && <span className="italic">{r.title}</span>}
                        {locus && <span>, {locus}</span>}
                      </div>
                      {r.era && (
                        <span className="text-xs px-1.5 py-0.5 bg-gray-100 text-gray-600 rounded mt-1 inline-block">
                          {r.era}
                        </span>
                      )}
                    </div>
                    <div 
                      className="flex-1 text-gray-700"
                      dangerouslySetInnerHTML={{ __html: r.highlighted_text || r.text }}
                    />
                  </div>
                </div>
              );
            })}
          </div>

          {filteredResults.length > displayLimit && (
            <div className="px-4 py-3 bg-gray-50 text-center">
              <button
                onClick={() => setDisplayLimit(displayLimit + 50)}
                className="text-amber-600 hover:text-amber-800 text-sm"
              >
                Show more ({displayLimit} of {filteredResults.length})
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default WildcardSearch;
