import { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import { LoadingSpinner, SearchableAuthorSelect } from '../common';
import { Chart as ChartJS, CategoryScale, LinearScale, BarElement, Title, Tooltip, Legend } from 'chart.js';
import { Bar } from 'react-chartjs-2';
import { createSearchId, requestSearchCancellation } from '../../utils/api';

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

const LANG_PAIRS = [
  { key: 'grc-la', source: 'grc', target: 'la', label: 'Greek → Latin' },
  { key: 'la-en', source: 'la', target: 'en', label: 'Latin → English' },
  { key: 'grc-en', source: 'grc', target: 'en', label: 'Greek → English' },
  { key: 'he-grc', source: 'he', target: 'grc', label: 'Hebrew → Greek' },
  { key: 'he-la', source: 'he', target: 'la', label: 'Hebrew → Latin' },
];

const LANG_LABELS = {
  grc: { name: 'Greek', color: 'amber', bgClass: 'bg-amber-50', textClass: 'text-amber-700', refClass: 'text-amber-600', btnClass: 'bg-amber-600 text-white' },
  la: { name: 'Latin', color: 'red', bgClass: 'bg-red-50', textClass: 'text-red-700', refClass: 'text-red-600', btnClass: 'bg-red-700 text-white' },
  en: { name: 'English', color: 'red', bgClass: 'bg-red-50', textClass: 'text-red-700', refClass: 'text-red-600', btnClass: 'bg-red-700 text-white' },
  he: { name: 'Hebrew', color: 'red', bgClass: 'bg-red-50', textClass: 'text-red-700', refClass: 'text-red-600', btnClass: 'bg-red-700 text-white' },
};

const LANG_DEFAULTS = {
  grc: { author: 'homer', work: 'iliad', part: '.part.1.' },
  la: { author: 'vergil', work: 'aeneid', part: '.part.1.' },
  en: { author: 'milton', work: 'paradise_lost', part: null },
  he: { author: 'hebrew_bible', work: 'ruth', part: null },
};

export default function CrossLingualSearch() {
  const [hierarchy, setHierarchy] = useState({ grc: [], la: [], en: [] });
  const [loading, setLoading] = useState(true);
  const [searchLoading, setSearchLoading] = useState(false);
  const [results, setResults] = useState([]);
  const [error, setError] = useState(null);

  const [langPair, setLangPair] = useState('grc-la');
  const [sourceAuthor, setSourceAuthor] = useState('');
  const [sourceWork, setSourceWork] = useState('');
  const [sourceSection, setSourceSection] = useState('');
  const [targetAuthor, setTargetAuthor] = useState('');
  const [targetWork, setTargetWork] = useState('');
  const [targetSection, setTargetSection] = useState('');

  const [minMatches, setMinMatches] = useState(2);
  const [displayLimit, setDisplayLimit] = useState(50);
  const [sortBy, setSortBy] = useState('score');
  const [showDistributionChart, setShowDistributionChart] = useState(false);
  const [distributionChartView, setDistributionChartView] = useState('target');
  const [elapsedTime, setElapsedTime] = useState(0);
  const timerRef = useRef(null);
  const [chartFilter, setChartFilter] = useState(null);
  const chartRef = useRef(null);
  const hasSearchedRef = useRef(false);
  const abortRef = useRef(null);
  const activeSearchId = useRef(null);

  const currentPair = LANG_PAIRS.find(p => p.key === langPair) || LANG_PAIRS[0];
  const srcLang = LANG_LABELS[currentPair.source];
  const tgtLang = LANG_LABELS[currentPair.target];

  const doSearch = useCallback(async () => {
    if (!sourceSection || !targetSection) {
      setError('Please select both source and target texts');
      return;
    }
    if (abortRef.current) {
      requestSearchCancellation(activeSearchId.current);
      abortRef.current.abort();
    }
    const controller = new AbortController();
    const searchId = createSearchId();
    abortRef.current = controller;
    activeSearchId.current = searchId;
    setSearchLoading(true);
    setError(null);
    try {
      const res = await fetch('/api/search', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          source: sourceSection,
          target: targetSection,
          source_language: currentPair.source,
          target_language: currentPair.target,
          match_type: 'crosslingual_fusion',
          min_matches: minMatches,
          search_id: searchId,
        }),
        signal: controller.signal
      });
      const data = await res.json();
      if (activeSearchId.current === searchId) {
        if (data.error) {
          setError(data.error);
          setResults([]);
        } else {
          setResults(data.results || []);
        }
      }
    } catch (err) {
      if (err.name === 'AbortError' && activeSearchId.current === searchId) {
        setError(null);
      } else if (activeSearchId.current === searchId) {
        setError('Search failed. Please try again.');
      }
    }
    if (activeSearchId.current === searchId) {
      activeSearchId.current = null;
      abortRef.current = null;
      setSearchLoading(false);
    }
  }, [sourceSection, targetSection, minMatches, currentPair]);

  const cancelSearch = useCallback(() => {
    if (abortRef.current) {
      requestSearchCancellation(activeSearchId.current);
      abortRef.current.abort();
      abortRef.current = null;
      activeSearchId.current = null;
      setSearchLoading(false);
    }
  }, []);

  useEffect(() => () => {
    requestSearchCancellation(activeSearchId.current);
    abortRef.current?.abort();
    activeSearchId.current = null;
    abortRef.current = null;
  }, []);

  useEffect(() => {
    loadHierarchies();
  }, []);

  const prevMinMatchesRef = useRef(minMatches);
  useEffect(() => {
    if (prevMinMatchesRef.current !== minMatches) {
      prevMinMatchesRef.current = minMatches;
      if (hasSearchedRef.current && sourceSection && targetSection && !searchLoading) {
        doSearch();
      }
    }
  }, [minMatches, sourceSection, targetSection, searchLoading, doSearch]);

  useEffect(() => {
    if (searchLoading) {
      const startTime = Date.now();
      setElapsedTime(0);
      timerRef.current = setInterval(() => {
        setElapsedTime(Math.floor((Date.now() - startTime) / 1000));
      }, 1000);
    } else {
      if (timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
    }
    return () => {
      if (timerRef.current) {
        clearInterval(timerRef.current);
      }
    };
  }, [searchLoading]);

  const setDefaultsForLang = useCallback((authors, lang, setSA, setSW, setSS) => {
    if (!authors?.length) return;
    const defaults = LANG_DEFAULTS[lang];
    const author = (defaults && authors.find(a => a.author_key === defaults.author)) || authors[0];
    setSA(author.author_key);
    if (author.works?.length > 0) {
      const work = (defaults && author.works.find(w => w.work_key === defaults.work)) || author.works[0];
      setSW(work.work_key);
      const part = defaults?.part
        ? work.parts?.find(p => p.id?.includes(defaults.part) || p.id?.endsWith('.1.tess'))
        : null;
      setSS(part?.id || work.whole_text || work.parts?.[0]?.id || '');
    }
  }, []);

  const loadHierarchies = async () => {
    setLoading(true);
    try {
      const [grcRes, laRes, enRes, heRes] = await Promise.all([
        fetch('/api/texts/hierarchy?language=grc'),
        fetch('/api/texts/hierarchy?language=la'),
        fetch('/api/texts/hierarchy?language=en'),
        fetch('/api/texts/hierarchy?language=he')
      ]);
      const grcData = await grcRes.json();
      const laData = await laRes.json();
      const enData = await enRes.json();
      const heData = await heRes.json();
      const h = {
        grc: grcData.authors || [],
        la: laData.authors || [],
        en: enData.authors || [],
        he: heData.authors || []
      };
      setHierarchy(h);
      setDefaultsForLang(h[currentPair.source], currentPair.source, setSourceAuthor, setSourceWork, setSourceSection);
      setDefaultsForLang(h[currentPair.target], currentPair.target, setTargetAuthor, setTargetWork, setTargetSection);
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

  const handleLangPairChange = useCallback((newKey) => {
    setLangPair(newKey);
    setResults([]);
    setChartFilter(null);
    hasSearchedRef.current = false;
    const pair = LANG_PAIRS.find(p => p.key === newKey) || LANG_PAIRS[0];
    setDefaultsForLang(hierarchy[pair.source], pair.source, setSourceAuthor, setSourceWork, setSourceSection);
    setDefaultsForLang(hierarchy[pair.target], pair.target, setTargetAuthor, setTargetWork, setTargetSection);
  }, [hierarchy, setDefaultsForLang]);

  const handleSearch = () => {
    hasSearchedRef.current = true;
    doSearch();
  };

  const exportCSV = useCallback(() => {
    const headers = ['Score', 'Channels', `${srcLang.name} Locus`, `${srcLang.name} Text`, `${tgtLang.name} Locus`, `${tgtLang.name} Text`, 'Semantic', 'Matched Words'];
    const rows = results.map(r => [
      (r.overall_score || r.score)?.toFixed(3) || '',
      (r.channels || ''),
      (r.source?.ref || r.source_locus || ''),
      (r.source?.text || r.source_text || '').replace(/"/g, '""'),
      (r.target?.ref || r.target_locus || ''),
      (r.target?.text || r.target_text || '').replace(/"/g, '""'),
      r.features?.semantic_score ? (r.features.semantic_score * 100).toFixed(0) + '%' : '',
      (r.matched_words || []).map(m => m.display || `${m.source_word || m.greek_word}→${m.target_word || m.latin_word}`).join('; ')
    ]);
    const csv = [headers, ...rows].map(row => row.map(cell => `"${cell}"`).join(',')).join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `cross_lingual_${langPair}_results.csv`;
    a.click();
    URL.revokeObjectURL(url);
  }, [results, srcLang, tgtLang, langPair]);

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
        backgroundColor: isSourceView
          ? { amber: 'rgba(217, 119, 6, 0.7)', red: 'rgba(185, 28, 28, 0.7)', blue: 'rgba(37, 99, 235, 0.7)' }[srcLang.color]
          : { amber: 'rgba(217, 119, 6, 0.7)', red: 'rgba(185, 28, 28, 0.7)', blue: 'rgba(37, 99, 235, 0.7)' }[tgtLang.color]
      }]
    };
  }, [results, distributionChartView, langPair]);

  const chartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: { legend: { display: false } },
    scales: {
      x: { title: { display: true, text: distributionChartView === 'source' ? `${srcLang.name} Source` : `${tgtLang.name} Target` } },
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
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h2 className="text-xl font-semibold text-gray-900">
            Cross-Lingual Search
          </h2>
          <p className="text-sm text-gray-500 mt-1">
            Find parallels across languages using AI semantic + dictionary fusion
          </p>
        </div>
        <div className="flex items-center gap-2">
          {LANG_PAIRS.map(p => (
            <button
              key={p.key}
              onClick={() => handleLangPairChange(p.key)}
              className={`text-xs px-2 sm:px-3 py-1.5 rounded border transition-colors ${
                langPair === p.key
                  ? 'bg-gray-800 text-white border-gray-800'
                  : 'bg-white text-gray-600 border-gray-300 hover:bg-gray-50'
              }`}
            >
              {p.label}
            </button>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-white rounded-lg shadow p-4">
          <h3 className={`text-lg font-medium ${srcLang.textClass} mb-4`}>{srcLang.name} Source</h3>
          <div className="space-y-3">
            <div>
              <label className="block text-sm text-gray-600 mb-1">Author</label>
              <SearchableAuthorSelect
                value={sourceAuthor}
                onChange={(key) => {
                  setSourceAuthor(key);
                  setSourceWork('');
                  setSourceSection('');
                }}
                authors={hierarchy[currentPair.source]}
              />
            </div>
            <div>
              <label className="block text-sm text-gray-600 mb-1">Work</label>
              <select
                value={sourceWork}
                onChange={e => {
                  setSourceWork(e.target.value);
                  if (e.target.value) {
                    const { wholeText, parts } = getWorkParts(hierarchy[currentPair.source], sourceAuthor, e.target.value);
                    setSourceSection(wholeText || parts[0]?.id || '');
                  } else {
                    setSourceSection('');
                  }
                }}
                className="w-full border rounded px-3 py-2"
              >
                <option value="">Select a work...</option>
                {getAuthorWorks(hierarchy[currentPair.source], sourceAuthor).map(w => (
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
                  const { wholeText, parts, workName } = getWorkParts(hierarchy[currentPair.source], sourceAuthor, sourceWork);
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
          <h3 className={`text-lg font-medium ${tgtLang.textClass} mb-4`}>{tgtLang.name} Target</h3>
          <div className="space-y-3">
            <div>
              <label className="block text-sm text-gray-600 mb-1">Author</label>
              <SearchableAuthorSelect
                value={targetAuthor}
                onChange={(key) => {
                  setTargetAuthor(key);
                  setTargetWork('');
                  setTargetSection('');
                }}
                authors={hierarchy[currentPair.target]}
              />
            </div>
            <div>
              <label className="block text-sm text-gray-600 mb-1">Work</label>
              <select
                value={targetWork}
                onChange={e => {
                  setTargetWork(e.target.value);
                  if (e.target.value) {
                    const { wholeText, parts } = getWorkParts(hierarchy[currentPair.target], targetAuthor, e.target.value);
                    setTargetSection(wholeText || parts[0]?.id || '');
                  } else {
                    setTargetSection('');
                  }
                }}
                className="w-full border rounded px-3 py-2"
              >
                <option value="">Select a work...</option>
                {getAuthorWorks(hierarchy[currentPair.target], targetAuthor).map(w => (
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
                  const { wholeText, parts, workName } = getWorkParts(hierarchy[currentPair.target], targetAuthor, targetWork);
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

      <div className="bg-white rounded-lg shadow p-4 space-y-3 sm:space-y-0 sm:flex sm:flex-row sm:items-center sm:justify-between sm:gap-4">
        <div className="space-y-2 sm:space-y-0 sm:flex sm:items-center sm:gap-4">
          <span className="text-sm text-gray-500 block">
            Combines AI semantic matching (SPhilBERTa) with cross-lingual dictionary lookup.
            Pairs detected by both channels are boosted.
          </span>
          <div className="flex items-center gap-2">
            <label className="text-sm text-gray-600 whitespace-nowrap">Min Matches:</label>
            <select
              value={minMatches}
              onChange={(e) => setMinMatches(parseInt(e.target.value))}
              className="px-2 py-1.5 border rounded text-sm"
            >
              <option value={1}>Any (include semantic-only)</option>
              <option value={2}>2+ words (default)</option>
              <option value={3}>3+ words</option>
              <option value={4}>4+ words</option>
            </select>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={handleSearch}
            disabled={searchLoading || !sourceSection || !targetSection}
            className="px-4 py-2 text-sm bg-red-700 text-white rounded hover:bg-red-800 disabled:opacity-50"
          >
            {searchLoading ? 'Searching...' : 'Search'}
          </button>
          {searchLoading && (
            <button
              onClick={cancelSearch}
              className="px-3 py-2 text-sm bg-gray-200 text-gray-700 rounded hover:bg-gray-300"
            >
              Cancel
            </button>
          )}
        </div>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded">
          {error}
        </div>
      )}

      {searchLoading && <LoadingSpinner text="Searching for cross-lingual parallels..." elapsedTime={elapsedTime} />}

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
                <option value="source">{srcLang.name} Locus</option>
                <option value="target">{tgtLang.name} Locus</option>
              </select>
            </div>
          </div>
          
          {showDistributionChart && (
            <div className="p-4 border-b bg-gray-50">
              <div className="flex items-center gap-4 mb-3">
                <span className="text-sm text-gray-600">View:</span>
                <button
                  onClick={() => { setDistributionChartView('source'); setChartFilter(null); }}
                  className={`text-xs px-3 py-1 rounded ${distributionChartView === 'source' ? srcLang.btnClass : 'bg-gray-200'}`}
                >
                  {srcLang.name} Source
                </button>
                <button
                  onClick={() => { setDistributionChartView('target'); setChartFilter(null); }}
                  className={`text-xs px-3 py-1 rounded ${distributionChartView === 'target' ? tgtLang.btnClass : 'bg-gray-200'}`}
                >
                  {tgtLang.name} Target
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
                <div className="flex items-center gap-2 mb-2">
                  <span className="text-xs text-gray-400 min-w-[2.5rem] text-right shrink-0 leading-none">
                    {i + 1}.
                  </span>
                  <span className="text-sm font-medium text-gray-500">
                    Score: {(result.overall_score || result.score)?.toFixed(3)}
                  </span>
                  {result.features?.semantic_score > 0 && (
                    <span className="text-xs bg-amber-100 text-amber-700 px-2 py-1 rounded">
                      Semantic: {(result.features.semantic_score * 100).toFixed(0)}%
                    </span>
                  )}
                  {result.features?.n_channels === 2 && (
                    <span className="text-xs bg-blue-100 text-blue-700 px-2 py-1 rounded">
                      2-channel
                    </span>
                  )}
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <div className="text-xs text-gray-500 mb-1">Source</div>
                    <div className="font-medium text-gray-900">{result.source?.ref || result.source_locus}</div>
                    {result.source?.tokens && result.source?.highlight_indices?.length > 0 ? (
                      <div className="text-gray-700 mt-1" dangerouslySetInnerHTML={{ __html: highlightTokens(result.source.tokens, result.source.highlight_indices) }} />
                    ) : (
                      <div className="text-gray-700 mt-1">{result.source?.text || result.source_text || ''}</div>
                    )}
                  </div>
                  <div>
                    <div className="text-xs text-gray-500 mb-1">Target</div>
                    <div className="font-medium text-gray-900">{result.target?.ref || result.target_locus}</div>
                    {result.target?.tokens && result.target?.highlight_indices?.length > 0 ? (
                      <div className="text-gray-700 mt-1" dangerouslySetInnerHTML={{ __html: highlightTokens(result.target.tokens, result.target.highlight_indices) }} />
                    ) : (
                      <div className="text-gray-700 mt-1">{result.target?.text || result.target_text || ''}</div>
                    )}
                  </div>
                </div>
                {result.matched_words?.length > 0 && (
                  <div className="mt-2 text-xs text-gray-500">
                    Matched: {result.matched_words.map(m => m.display || `${m.source_word || m.greek_word} → ${m.target_word || m.latin_word}`).join(', ')}
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
