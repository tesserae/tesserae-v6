import { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import { LoadingSpinner, SearchableAuthorSelect } from '../common';
import { Chart as ChartJS, CategoryScale, LinearScale, BarElement, Title, Tooltip, Legend } from 'chart.js';
import { Bar } from 'react-chartjs-2';

ChartJS.register(CategoryScale, LinearScale, BarElement, Title, Tooltip, Legend);

const highlightTokens = (tokens, highlightIndices) => {
  if (!tokens || tokens.length === 0) return '';
  const indexSet = new Set(highlightIndices || []);
  return tokens.map((token, i) => 
    indexSet.has(i) 
      ? `<mark class="bg-yellow-200 px-0.5 rounded">${token}</mark>` 
      : token
  ).join(' ');
};

export default function CrossLingualSearch() {
  const [hierarchy, setHierarchy] = useState({ grc: [], la: [] });
  const [loading, setLoading] = useState(true);
  const [searchLoading, setSearchLoading] = useState(false);
  const [results, setResults] = useState([]);
  const [error, setError] = useState(null);

  const [sourceAuthor, setSourceAuthor] = useState('');
  const [sourceWork, setSourceWork] = useState('');
  const [sourceSection, setSourceSection] = useState('');
  const [targetAuthor, setTargetAuthor] = useState('');
  const [targetWork, setTargetWork] = useState('');
  const [targetSection, setTargetSection] = useState('');

  const [matchMode, setMatchMode] = useState('ai');
  const [minMatches, setMinMatches] = useState(2);
  const [displayLimit, setDisplayLimit] = useState(50);
  const [sortBy, setSortBy] = useState('score');
  const [showDistributionChart, setShowDistributionChart] = useState(false);
  const [distributionChartView, setDistributionChartView] = useState('target');
  const [chartFilter, setChartFilter] = useState(null);
  const chartRef = useRef(null);
  const hasSearchedRef = useRef(false);
  const prevMatchModeRef = useRef(matchMode);

  const doSearch = useCallback(async (mode) => {
    if (!sourceSection || !targetSection) {
      setError('Please select both source and target texts');
      return;
    }
    setSearchLoading(true);
    setError(null);
    try {
      const matchType = mode === 'ai' ? 'semantic_cross' : 'dictionary_cross';
      const res = await fetch('/api/search', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          source: sourceSection,
          target: targetSection,
          source_language: 'grc',
          target_language: 'la',
          match_type: matchType,
          min_matches: minMatches
        })
      });
      const data = await res.json();
      if (data.error) {
        setError(data.error);
        setResults([]);
      } else {
        setResults(data.results || []);
      }
    } catch (err) {
      setError('Search failed. Please try again.');
    }
    setSearchLoading(false);
  }, [sourceSection, targetSection, minMatches]);

  useEffect(() => {
    loadHierarchies();
  }, []);

  useEffect(() => {
    if (prevMatchModeRef.current !== matchMode) {
      prevMatchModeRef.current = matchMode;
      if (hasSearchedRef.current && sourceSection && targetSection && !searchLoading) {
        doSearch(matchMode);
      }
    }
  }, [matchMode, sourceSection, targetSection, searchLoading, doSearch]);

  const loadHierarchies = async () => {
    setLoading(true);
    try {
      const [grcRes, laRes] = await Promise.all([
        fetch('/api/texts/hierarchy?language=grc'),
        fetch('/api/texts/hierarchy?language=la')
      ]);
      const grcData = await grcRes.json();
      const laData = await laRes.json();
      setHierarchy({
        grc: grcData.authors || [],
        la: laData.authors || []
      });
      if (grcData.authors?.length > 0) {
        const homer = grcData.authors.find(a => a.author_key === 'homer') || grcData.authors[0];
        setSourceAuthor(homer.author_key);
        if (homer.works?.length > 0) {
          const iliad = homer.works.find(w => w.work_key === 'iliad') || homer.works[0];
          setSourceWork(iliad.work_key);
          const book1 = iliad.parts?.find(p => p.id?.includes('.part.1.') || p.id?.endsWith('.1.tess'));
          setSourceSection(book1?.id || iliad.whole_text || iliad.parts?.[0]?.id || '');
        }
      }
      if (laData.authors?.length > 0) {
        const vergil = laData.authors.find(a => a.author_key === 'vergil') || laData.authors[0];
        setTargetAuthor(vergil.author_key);
        if (vergil.works?.length > 0) {
          const aeneid = vergil.works.find(w => w.work_key === 'aeneid') || vergil.works[0];
          setTargetWork(aeneid.work_key);
          const book1 = aeneid.parts?.find(p => p.id?.includes('.part.1.') || p.id?.endsWith('.1.tess'));
          setTargetSection(book1?.id || aeneid.whole_text || aeneid.parts?.[0]?.id || '');
        }
      }
    } catch (err) {
      console.error('Failed to load text hierarchies:', err);
    }
    setLoading(false);
  };

  const getAuthorWorks = (authors, authorKey) => {
    const author = authors.find(a => a.author_key === authorKey);
    return author ? author.works : [];
  };

  const getWorkParts = (authors, authorKey, workKey) => {
    const works = getAuthorWorks(authors, authorKey);
    const work = works.find(w => w.work_key === workKey);
    if (!work) return { wholeText: null, parts: [], workName: '' };
    return { wholeText: work.whole_text, parts: work.parts || [], workName: work.work };
  };

  const handleSearch = () => {
    hasSearchedRef.current = true;
    doSearch(matchMode);
  };

  const exportCSV = useCallback(() => {
    const headers = ['Score', 'Greek Locus', 'Greek Text', 'Latin Locus', 'Latin Text', 'Similarity', 'Matched Words'];
    const rows = results.map(r => [
      (r.overall_score || r.score)?.toFixed(3) || '',
      (r.source?.ref || r.source_locus || ''),
      (r.source?.text || r.source_text || '').replace(/"/g, '""'),
      (r.target?.ref || r.target_locus || ''),
      (r.target?.text || r.target_text || '').replace(/"/g, '""'),
      (r.features?.semantic_score || r.similarity)?.toFixed(3) || '',
      (r.matched_words || []).map(m => m.display || `${m.greek_word}→${m.latin_word}`).join('; ')
    ]);
    const csv = [headers, ...rows].map(row => row.map(cell => `"${cell}"`).join(',')).join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'cross_lingual_results.csv';
    a.click();
    URL.revokeObjectURL(url);
  }, [results]);

  const sortedResults = useMemo(() => {
    if (!results || results.length === 0) return [];
    let filtered = chartFilter 
      ? results.filter(r => {
          const locus = chartFilter.view === 'source' 
            ? (r.source?.ref || r.source_locus || '') 
            : (r.target?.ref || r.target_locus || '');
          const bookMatch = locus.match(/(\d+)\.\d+/) || locus.match(/book\s*(\d+)/i);
          const book = bookMatch ? `Book ${bookMatch[1]}` : 'Other';
          return book === chartFilter.book;
        })
      : results;
    
    if (sortBy === 'score') {
      return [...filtered].sort((a, b) => (b.overall_score || b.score || 0) - (a.overall_score || a.score || 0));
    } else if (sortBy === 'source') {
      return [...filtered].sort((a, b) => (a.source?.ref || a.source_locus || '').localeCompare(b.source?.ref || b.source_locus || ''));
    } else {
      return [...filtered].sort((a, b) => (a.target?.ref || a.target_locus || '').localeCompare(b.target?.ref || b.target_locus || ''));
    }
  }, [results, sortBy, chartFilter]);

  const getDistributionData = useCallback(() => {
    if (!results || results.length === 0) return null;
    
    const bookData = {};
    const isSourceView = distributionChartView === 'source';
    
    results.forEach(r => {
      const locus = isSourceView 
        ? (r.source?.ref || r.source_locus || '') 
        : (r.target?.ref || r.target_locus || '');
      
      const bookMatch = locus.match(/(\d+)\.\d+/) || locus.match(/book\s*(\d+)/i);
      const book = bookMatch ? bookMatch[1] : 'Other';
      const bookLabel = `Book ${book}`;
      
      if (!bookData[bookLabel]) {
        bookData[bookLabel] = { count: 0, totalScore: 0 };
      }
      bookData[bookLabel].count++;
      bookData[bookLabel].totalScore += (r.overall_score || r.score || 0);
    });
    
    const sortedBooks = Object.keys(bookData).sort((a, b) => {
      const numA = parseInt(a.replace('Book ', '')) || 999;
      const numB = parseInt(b.replace('Book ', '')) || 999;
      return numA - numB;
    });
    
    return {
      labels: sortedBooks,
      datasets: [{
        label: 'Parallels',
        data: sortedBooks.map(b => bookData[b].count),
        backgroundColor: isSourceView ? 'rgba(217, 119, 6, 0.7)' : 'rgba(185, 28, 28, 0.7)'
      }]
    };
  }, [results, distributionChartView]);

  const chartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: { legend: { display: false } },
    scales: {
      x: { title: { display: true, text: distributionChartView === 'source' ? 'Greek Source' : 'Latin Target' } },
      y: { beginAtZero: true, ticks: { precision: 0 } }
    },
    onClick: (event, elements) => {
      if (elements.length > 0) {
        const chartData = getDistributionData();
        if (chartData) {
          const clickedBook = chartData.labels[elements[0].index];
          setChartFilter(chartFilter?.book === clickedBook ? null : { book: clickedBook, view: distributionChartView });
        }
      }
    }
  };

  if (loading) {
    return <LoadingSpinner text="Loading text data..." />;
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-semibold text-gray-900">
          Cross-Lingual Search (Greek ↔ Latin)
        </h2>
        <p className="text-sm text-gray-500 mt-1">
          Find semantic parallels between Greek and Latin texts using AI-powered matching
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-white rounded-lg shadow p-4">
          <h3 className="text-lg font-medium text-amber-700 mb-4">Greek Source</h3>
          <div className="space-y-3">
            <div>
              <label className="block text-sm text-gray-600 mb-1">Author</label>
              <SearchableAuthorSelect
                value={sourceAuthor}
                onChange={(key) => {
                  setSourceAuthor(key);
                  const works = getAuthorWorks(hierarchy.grc, key);
                  if (works.length > 0) {
                    setSourceWork(works[0].work_key);
                    setSourceSection(works[0].whole_text || works[0].parts?.[0]?.id || '');
                  }
                }}
                authors={hierarchy.grc}
              />
            </div>
            <div>
              <label className="block text-sm text-gray-600 mb-1">Work</label>
              <select
                value={sourceWork}
                onChange={e => {
                  setSourceWork(e.target.value);
                  const { wholeText, parts } = getWorkParts(hierarchy.grc, sourceAuthor, e.target.value);
                  setSourceSection(wholeText || parts[0]?.id || '');
                }}
                className="w-full border rounded px-3 py-2"
              >
                {getAuthorWorks(hierarchy.grc, sourceAuthor).map(w => (
                  <option key={w.work_key} value={w.work_key}>{w.work}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm text-gray-600 mb-1">Section</label>
              <select
                value={sourceSection}
                onChange={e => setSourceSection(e.target.value)}
                className="w-full border rounded px-3 py-2"
              >
                {(() => {
                  const { wholeText, parts, workName } = getWorkParts(hierarchy.grc, sourceAuthor, sourceWork);
                  return (
                    <>
                      {wholeText && <option value={wholeText}>{workName} (Complete)</option>}
                      {parts.map(p => <option key={p.id} value={p.id}>{p.display}</option>)}
                    </>
                  );
                })()}
              </select>
            </div>
          </div>
        </div>

        <div className="bg-white rounded-lg shadow p-4">
          <h3 className="text-lg font-medium text-red-700 mb-4">Latin Target</h3>
          <div className="space-y-3">
            <div>
              <label className="block text-sm text-gray-600 mb-1">Author</label>
              <SearchableAuthorSelect
                value={targetAuthor}
                onChange={(key) => {
                  setTargetAuthor(key);
                  const works = getAuthorWorks(hierarchy.la, key);
                  if (works.length > 0) {
                    setTargetWork(works[0].work_key);
                    setTargetSection(works[0].whole_text || works[0].parts?.[0]?.id || '');
                  }
                }}
                authors={hierarchy.la}
              />
            </div>
            <div>
              <label className="block text-sm text-gray-600 mb-1">Work</label>
              <select
                value={targetWork}
                onChange={e => {
                  setTargetWork(e.target.value);
                  const { wholeText, parts } = getWorkParts(hierarchy.la, targetAuthor, e.target.value);
                  setTargetSection(wholeText || parts[0]?.id || '');
                }}
                className="w-full border rounded px-3 py-2"
              >
                {getAuthorWorks(hierarchy.la, targetAuthor).map(w => (
                  <option key={w.work_key} value={w.work_key}>{w.work}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm text-gray-600 mb-1">Section</label>
              <select
                value={targetSection}
                onChange={e => setTargetSection(e.target.value)}
                className="w-full border rounded px-3 py-2"
              >
                {(() => {
                  const { wholeText, parts, workName } = getWorkParts(hierarchy.la, targetAuthor, targetWork);
                  return (
                    <>
                      {wholeText && <option value={wholeText}>{workName} (Complete)</option>}
                      {parts.map(p => <option key={p.id} value={p.id}>{p.display}</option>)}
                    </>
                  );
                })()}
              </select>
            </div>
          </div>
        </div>
      </div>

      <div className="bg-white rounded-lg shadow p-4 flex flex-col sm:flex-row items-center justify-between gap-4">
        <div className="flex items-center gap-4">
          <label className="text-sm text-gray-600">Match Mode:</label>
          <div className="flex gap-2">
            <button
              onClick={() => {
                if (matchMode !== 'ai') {
                  setMatchMode('ai');
                  if (hasSearchedRef.current && sourceSection && targetSection) {
                    doSearch('ai');
                  }
                }
              }}
              disabled={true}
              title="Coming soon - AI semantic matching will be available in a future update"
              className={`px-4 py-2 rounded text-sm bg-gray-100 text-gray-400 cursor-not-allowed`}
            >
              AI Semantic (Coming Soon)
            </button>
            <button
              onClick={() => {
                if (matchMode !== 'dictionary') {
                  setMatchMode('dictionary');
                  if (hasSearchedRef.current && sourceSection && targetSection) {
                    doSearch('dictionary');
                  }
                }
              }}
              disabled={searchLoading}
              className={`px-4 py-2 rounded text-sm ${matchMode === 'dictionary' ? 'bg-red-700 text-white' : 'bg-gray-100 text-gray-700 hover:bg-gray-200'} disabled:opacity-50`}
            >
              Dictionary
            </button>
          </div>
          <div className="flex items-center gap-2 ml-4">
            <label className="text-sm text-gray-600">Min Word Matches:</label>
            <select
              value={minMatches}
              onChange={(e) => setMinMatches(parseInt(e.target.value))}
              className="px-2 py-1 border rounded text-sm"
            >
              <option value={2}>2</option>
              <option value={3}>3</option>
              <option value={4}>4</option>
              <option value={5}>5</option>
            </select>
          </div>
        </div>
        <button
          onClick={handleSearch}
          disabled={searchLoading || !sourceSection || !targetSection}
          className="px-6 py-2 bg-red-700 text-white rounded hover:bg-red-800 disabled:opacity-50"
        >
          {searchLoading ? 'Searching...' : 'Find Cross-Lingual Parallels'}
        </button>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded">
          {error}
        </div>
      )}

      {searchLoading && <LoadingSpinner text="Searching for cross-lingual parallels..." />}

      {results.length > 0 && (
        <div className="bg-white rounded-lg shadow overflow-hidden">
          <div className="px-4 py-3 bg-gray-50 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
            <span className="text-sm text-gray-600">
              Found {results.length} cross-lingual parallels
              {chartFilter && ` (${sortedResults.length} in ${chartFilter.book})`}
            </span>
            <div className="flex flex-wrap items-center gap-2">
              <button
                onClick={() => setShowDistributionChart(!showDistributionChart)}
                className={`text-xs px-3 py-1.5 rounded ${showDistributionChart ? 'bg-amber-600 text-white' : 'bg-amber-100 text-amber-700 hover:bg-amber-200'}`}
              >
                {showDistributionChart ? 'Hide Chart' : 'Distribution'}
              </button>
              <button
                onClick={exportCSV}
                className="text-xs bg-red-700 text-white px-3 py-1.5 rounded hover:bg-red-800"
              >
                Export CSV
              </button>
              <span className="text-xs text-gray-500">Sort:</span>
              <select
                value={sortBy}
                onChange={e => setSortBy(e.target.value)}
                className="text-xs border rounded px-2 py-1"
              >
                <option value="score">Score</option>
                <option value="source">Greek Locus</option>
                <option value="target">Latin Locus</option>
              </select>
            </div>
          </div>
          
          {showDistributionChart && (
            <div className="p-4 border-b bg-gray-50">
              <div className="flex items-center gap-4 mb-3">
                <span className="text-sm text-gray-600">View:</span>
                <button
                  onClick={() => { setDistributionChartView('source'); setChartFilter(null); }}
                  className={`text-xs px-3 py-1 rounded ${distributionChartView === 'source' ? 'bg-amber-600 text-white' : 'bg-gray-200'}`}
                >
                  Greek Source
                </button>
                <button
                  onClick={() => { setDistributionChartView('target'); setChartFilter(null); }}
                  className={`text-xs px-3 py-1 rounded ${distributionChartView === 'target' ? 'bg-red-700 text-white' : 'bg-gray-200'}`}
                >
                  Latin Target
                </button>
                {chartFilter && (
                  <button
                    onClick={() => setChartFilter(null)}
                    className="text-xs text-red-600 hover:text-red-800"
                  >
                    Clear Filter
                  </button>
                )}
              </div>
              <div style={{ height: '200px' }}>
                <Bar ref={chartRef} data={getDistributionData() || { labels: [], datasets: [] }} options={chartOptions} />
              </div>
            </div>
          )}
          
          <div className="divide-y divide-gray-200">
            {sortedResults.slice(0, displayLimit).map((result, i) => (
              <div key={i} className="p-4">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm font-medium text-gray-500">
                    Score: {(result.overall_score || result.score)?.toFixed(3)}
                  </span>
                  {(result.features?.semantic_score || result.similarity) && (
                    <span className="text-xs bg-amber-100 text-amber-700 px-2 py-1 rounded">
                      Similarity: {((result.features?.semantic_score || result.similarity) * 100).toFixed(1)}%
                    </span>
                  )}
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="bg-amber-50 p-3 rounded">
                    <div className="text-xs text-amber-600 mb-1">{result.source?.ref || result.source_locus}</div>
                    {result.source?.tokens && result.source?.highlight_indices?.length > 0 ? (
                      <div className="text-gray-800" dangerouslySetInnerHTML={{ __html: highlightTokens(result.source.tokens, result.source.highlight_indices) }} />
                    ) : (
                      <div className="text-gray-800">{result.source?.text || result.source_text || ''}</div>
                    )}
                  </div>
                  <div className="bg-red-50 p-3 rounded">
                    <div className="text-xs text-red-600 mb-1">{result.target?.ref || result.target_locus}</div>
                    {result.target?.tokens && result.target?.highlight_indices?.length > 0 ? (
                      <div className="text-gray-800" dangerouslySetInnerHTML={{ __html: highlightTokens(result.target.tokens, result.target.highlight_indices) }} />
                    ) : (
                      <div className="text-gray-800">{result.target?.text || result.target_text || ''}</div>
                    )}
                  </div>
                </div>
                {result.matched_words?.length > 0 && (
                  <div className="mt-2 text-xs text-gray-500">
                    Matched: {result.matched_words.map(m => m.display || `${m.greek_word} → ${m.latin_word}`).join(', ')}
                  </div>
                )}
              </div>
            ))}
          </div>
          {sortedResults.length > displayLimit && (
            <div className="px-4 py-3 bg-gray-50 text-center">
              <button
                onClick={() => setDisplayLimit(displayLimit + 50)}
                className="text-amber-600 hover:text-amber-800 text-sm"
              >
                Show more ({displayLimit} of {sortedResults.length})
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
