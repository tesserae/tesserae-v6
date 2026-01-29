import { useState, useCallback, useRef, useEffect, useMemo } from 'react';
import { LoadingSpinner } from '../common';
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

export default function LineSearch({ language }) {
  const [mode, setMode] = useState('browse');
  const [query, setQuery] = useState('');
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [searchType, setSearchType] = useState('lemma');
  const [displayLimit, setDisplayLimit] = useState(50);
  const [showTimeline, setShowTimeline] = useState(false);
  const [eraFilter, setEraFilter] = useState(null);
  const [authorFilter, setAuthorFilter] = useState(null);
  const [showPoetry, setShowPoetry] = useState(true);
  const [showProse, setShowProse] = useState(true);
  const [sortOrder, setSortOrder] = useState('chronological');
  const chartRef = useRef(null);
  const authorChartRef = useRef(null);
  
  const [texts, setTexts] = useState([]);
  const [authors, setAuthors] = useState([]);
  const [works, setWorks] = useState([]);
  const [selectedAuthor, setSelectedAuthor] = useState('');
  const [selectedWork, setSelectedWork] = useState('');
  const [selectedWorkLabel, setSelectedWorkLabel] = useState('');
  const [lineStart, setLineStart] = useState('');
  const [lineEnd, setLineEnd] = useState('');
  const [loadingTexts, setLoadingTexts] = useState(true);
  
  const [browseLines, setBrowseLines] = useState([]);
  const [browseLoading, setBrowseLoading] = useState(false);
  const [elapsedTime, setElapsedTime] = useState(0);
  const timerRef = useRef(null);

  useEffect(() => {
    if (loading) {
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
  }, [loading]);
  const [browseDisplayLimit, setBrowseDisplayLimit] = useState(100);
  const [showAuthorDropdown, setShowAuthorDropdown] = useState(false);
  const [showWorkDropdown, setShowWorkDropdown] = useState(false);
  
  const [sourceInfo, setSourceInfo] = useState(null);

  useEffect(() => {
    loadTexts();
    setSelectedAuthor('');
    setSelectedWork('');
    setSelectedWorkLabel('');
    setBrowseLines([]);
    setQuery('');
    setResults([]);
    setError(null);
    setSourceInfo(null);
  }, [language]);

  useEffect(() => {
    const gotoQuery = sessionStorage.getItem('tesserae_goto_query');
    const gotoText = sessionStorage.getItem('tesserae_goto_text');
    
    if (gotoQuery || gotoText) {
      sessionStorage.removeItem('tesserae_goto_query');
      sessionStorage.removeItem('tesserae_goto_text');
      
      if (gotoQuery) {
        setQuery(gotoQuery);
        setMode('search');
      }
      
      if (gotoText && texts.length > 0) {
        const text = texts.find(t => t.id === gotoText);
        if (text) {
          setSelectedAuthor(text.author);
          setSelectedWork(text.id);
          setSelectedWorkLabel(text.title || text.work || text.display_name);
        }
      }
    }
  }, [texts]);

  useEffect(() => {
    if (selectedAuthor) {
      const authorTexts = texts
        .filter(t => t.author === selectedAuthor)
        .map(t => ({ 
          id: t.id, 
          label: t.title || t.work || t.display_name,
          display: t.display_name || `${t.author}, ${t.title || t.work}`
        }))
        .sort((a, b) => {
          const extractNum = (s) => {
            const match = s.match(/(\d+)/);
            return match ? parseInt(match[1], 10) : 0;
          };
          const aBase = a.label.replace(/,?\s*(Book|Part)?\s*\d+$/, '');
          const bBase = b.label.replace(/,?\s*(Book|Part)?\s*\d+$/, '');
          if (aBase !== bBase) return aBase.localeCompare(bBase);
          return extractNum(a.label) - extractNum(b.label);
        });
      setWorks(authorTexts);
      if (!authorTexts.find(w => w.id === selectedWork)) {
        setSelectedWork('');
        setSelectedWorkLabel('');
      }
    } else {
      setWorks([]);
      setSelectedWork('');
      setSelectedWorkLabel('');
    }
  }, [selectedAuthor, texts]);

  const loadTexts = async () => {
    setLoadingTexts(true);
    try {
      const res = await fetch(`/api/texts?language=${language}`);
      const data = await res.json();
      const textList = Array.isArray(data) ? data : (data.texts || []);
      setTexts(textList);
      
      const uniqueAuthors = [...new Set(textList.map(t => t.author))].filter(Boolean).sort();
      setAuthors(uniqueAuthors);
    } catch (err) {
      console.error('Failed to load texts:', err);
    }
    setLoadingTexts(false);
  };

  const handleSearch = async () => {
    if (!query.trim()) return;
    setLoading(true);
    setError(null);
    setEraFilter(null);
    try {
      const searchParams = {
        query: query.trim(),
        language,
        search_type: searchType
      };
      
      if (selectedAuthor) searchParams.author = selectedAuthor;
      if (selectedWork) searchParams.work = selectedWork;
      if (lineStart) searchParams.line_start = parseInt(lineStart);
      if (lineEnd) searchParams.line_end = parseInt(lineEnd);
      
      const res = await fetch('/api/line-search', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(searchParams)
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
      setResults([]);
    }
    setLoading(false);
  };

  const handleBrowseLines = async () => {
    if (!selectedAuthor || !selectedWork) return;
    setBrowseLoading(true);
    setBrowseLines([]);
    try {
      const res = await fetch(`/api/text/${selectedWork}/lines`);
      const data = await res.json();
      if (data.lines) {
        setBrowseLines(data.lines);
      }
    } catch (err) {
      console.error('Failed to load lines:', err);
    }
    setBrowseLoading(false);
  };

  const selectLineForSearch = async (line) => {
    const lineText = line.text || '';
    setQuery(lineText);
    setMode('search');
    
    // Track source info for display and exclusion
    const workInfo = works.find(w => w.id === selectedWork);
    const source = {
      author: selectedAuthor,
      work: workInfo?.label || selectedWork,
      text_id: selectedWork,
      locus: line.locus || line.ref || '',
      text: lineText
    };
    setSourceInfo(source);
    
    if (!lineText.trim()) return;
    setLoading(true);
    setError(null);
    setEraFilter(null);
    try {
      const searchParams = {
        query: lineText.trim(),
        language,
        search_type: searchType,
        exclude_text_id: selectedWork,
        exclude_locus: line.locus || line.ref || ''
      };
      
      const res = await fetch('/api/line-search', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(searchParams)
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
      setResults([]);
    }
    setLoading(false);
  };

  const clearFilters = () => {
    setSelectedAuthor('');
    setSelectedWork('');
    setLineStart('');
    setLineEnd('');
  };

  const deduplicatedResults = useMemo(() => {
    return results.filter((r, index, self) => {
      if (query && r.text === query) {
        return false;
      }
      return index === self.findIndex(t => t.text === r.text && t.locus === r.locus);
    });
  }, [results, query]);

  const exportCSV = useCallback(() => {
    const headers = ['Author', 'Work', 'Locus', 'Text', 'Era'];
    const rows = results.map(r => [
      r.author || '',
      r.work || '',
      r.locus || '',
      r.text?.replace(/"/g, '""') || '',
      r.era || ''
    ]);
    const csv = [headers, ...rows].map(row => row.map(cell => `"${cell}"`).join(',')).join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `line_search_${query}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  }, [results, query]);

  const exportTimelineChart = () => {
    if (!chartRef.current) return;
    const canvas = chartRef.current.canvas;
    if (!canvas) return;
    const link = document.createElement('a');
    link.download = `tesserae_timeline_${query}_${new Date().toISOString().slice(0, 10)}.png`;
    link.href = canvas.toDataURL('image/png');
    link.click();
  };

  const getTimelineData = useCallback(() => {
    if (!deduplicatedResults || deduplicatedResults.length === 0) return null;
    
    const eraCounts = {};
    deduplicatedResults.forEach(r => {
      const era = r.era || 'Unknown';
      eraCounts[era] = (eraCounts[era] || 0) + 1;
    });
    
    const sortedEras = ERA_ORDER.filter(era => eraCounts[era] > 0);
    
    return {
      labels: sortedEras,
      datasets: [{
        label: 'Matches',
        data: sortedEras.map(era => eraCounts[era]),
        backgroundColor: sortedEras.map(era => ERA_COLORS[era] || ERA_COLORS['Unknown']),
        borderColor: sortedEras.map(era => (ERA_COLORS[era] || ERA_COLORS['Unknown']).replace('0.7', '1')),
        borderWidth: 1
      }]
    };
  }, [deduplicatedResults]);

  const getAuthorTimelineData = useCallback(() => {
    if (!deduplicatedResults || deduplicatedResults.length === 0) return null;
    
    const authorCounts = {};
    deduplicatedResults.forEach(r => {
      const author = r.author || 'Unknown';
      authorCounts[author] = (authorCounts[author] || 0) + 1;
    });
    
    const sortedAuthors = Object.keys(authorCounts).sort((a, b) => {
      const aResult = deduplicatedResults.find(r => r.author === a);
      const bResult = deduplicatedResults.find(r => r.author === b);
      const aYear = aResult?.year || 9999;
      const bYear = bResult?.year || 9999;
      if (aYear !== bYear) return aYear - bYear;
      return a.localeCompare(b);
    });
    
    return {
      labels: sortedAuthors,
      datasets: [{
        label: 'Matches',
        data: sortedAuthors.map(author => authorCounts[author]),
        backgroundColor: 'rgba(120, 81, 169, 0.7)',
        borderColor: 'rgba(120, 81, 169, 1)',
        borderWidth: 1
      }]
    };
  }, [deduplicatedResults]);

  const chartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { display: false },
      title: {
        display: true,
        text: eraFilter ? `Showing matches from ${eraFilter} (click to clear)` : 'Period Timeline (click bar to filter)'
      },
      tooltip: {
        callbacks: {
          label: (context) => `${context.parsed.y} match${context.parsed.y !== 1 ? 'es' : ''}`
        }
      }
    },
    scales: {
      y: { beginAtZero: true, ticks: { stepSize: 1 } }
    },
    onClick: (event, elements) => {
      if (elements.length > 0) {
        const idx = elements[0].index;
        const chartData = getTimelineData();
        if (chartData) {
          const clickedEra = chartData.labels[idx];
          setEraFilter(eraFilter === clickedEra ? null : clickedEra);
          setAuthorFilter(null);
        }
      }
    }
  };

  const authorChartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { display: false },
      title: {
        display: true,
        text: authorFilter ? `Showing matches from ${authorFilter} (click to clear)` : 'Author Timeline (click bar to filter)'
      },
      tooltip: {
        callbacks: {
          label: (context) => `${context.parsed.y} match${context.parsed.y !== 1 ? 'es' : ''}`
        }
      }
    },
    scales: {
      y: { beginAtZero: true, ticks: { stepSize: 1 } },
      x: { ticks: { maxRotation: 45, minRotation: 45 } }
    },
    onClick: (event, elements) => {
      if (elements.length > 0) {
        const idx = elements[0].index;
        const chartData = getAuthorTimelineData();
        if (chartData) {
          const clickedAuthor = chartData.labels[idx];
          setAuthorFilter(authorFilter === clickedAuthor ? null : clickedAuthor);
          setEraFilter(null);
        }
      }
    }
  };

  const getLanguageName = (lang) => {
    const names = { la: 'Latin', grc: 'Greek', en: 'English' };
    return names[lang] || lang;
  };

  const extractLineNumber = (locus) => {
    if (!locus) return '';
    const match = locus.match(/[\d]+(?:[.\-:]+[\d\w]+)*$/);
    return match ? match[0] : locus.trim().split(/\s+/).pop() || locus;
  };

  const cleanWorkTitle = (work, locus) => {
    if (!work) return work;
    const lineNum = extractLineNumber(locus);
    if (!lineNum) return work;
    const match = work.match(/^(.+?)\s+(\d+)$/);
    if (match) {
      const [, baseName, bookNum] = match;
      if (lineNum.startsWith(bookNum + '.') || lineNum.startsWith(bookNum + ':')) {
        return baseName;
      }
    }
    return work;
  };

  const highlightMatches = (text, matchedWords) => {
    if (!text) return text;
    if (!matchedWords || matchedWords.length === 0) return text;
    
    const normalizeGreek = (s) => {
      if (!s) return '';
      return s.toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '');
    };
    
    const normalizeWord = (s) => {
      if (!s) return '';
      let normalized = s.toLowerCase();
      if (language === 'la') {
        normalized = normalized.replace(/v/g, 'u').replace(/j/g, 'i');
      } else if (language === 'grc') {
        normalized = normalizeGreek(s);
      }
      return normalized;
    };
    
    const matchSet = new Set(matchedWords.map(w => normalizeWord(w)));
    const words = text.split(/(\s+)/);
    
    return words.map((word, i) => {
      if (/^\s+$/.test(word)) {
        return <span key={i}>{word}</span>;
      }
      
      let wordClean;
      if (language === 'grc') {
        const nfd = word.normalize('NFD');
        const noDiacritics = nfd.replace(/[\u0300-\u036f]/g, '');
        wordClean = noDiacritics.replace(/[^\u0370-\u03FF\u1F00-\u1FFFa-zA-Z]/g, '');
      } else {
        wordClean = word.replace(/[^a-zA-Z\u0370-\u03FF\u1F00-\u1FFF]/g, '');
      }
      
      const wordNorm = normalizeWord(wordClean);
      if (wordNorm && matchSet.has(wordNorm)) {
        return <mark key={i} className="bg-amber-200 px-0.5 rounded">{word}</mark>;
      }
      return <span key={i}>{word}</span>;
    });
  };

  const filteredResults = useMemo(() => {
    const filtered = deduplicatedResults.filter(r => {
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
        return (a.work || '').localeCompare(b.work || '');
      });
    }
    return [...filtered].sort((a, b) => {
      const aYear = a.year || 9999;
      const bYear = b.year || 9999;
      if (aYear !== bYear) return aYear - bYear;
      return (a.author || '').localeCompare(b.author || '');
    });
  }, [deduplicatedResults, eraFilter, authorFilter, showPoetry, showProse, sortOrder]);

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2 bg-gray-100 p-1 rounded-lg inline-flex">
        <button
          onClick={() => setMode('browse')}
          className={`px-3 py-1.5 text-sm font-medium rounded ${
            mode === 'browse' ? 'bg-white shadow text-red-700' : 'text-gray-600 hover:text-gray-800'
          }`}
        >
          Find Text to Search
        </button>
        <button
          onClick={() => setMode('search')}
          className={`px-3 py-1.5 text-sm font-medium rounded ${
            mode === 'search' ? 'bg-white shadow text-red-700' : 'text-gray-600 hover:text-gray-800'
          }`}
        >
          Input Search Text
        </button>
      </div>

      {mode === 'search' ? (
        <>
          <div className="bg-white rounded-lg shadow p-4 sm:p-6 space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Search Terms
              </label>
              <div className="flex flex-col sm:flex-row gap-3">
                <input
                  type="text"
                  value={query}
                  onChange={e => setQuery(e.target.value)}
                  onKeyDown={e => e.key === 'Enter' && handleSearch()}
                  placeholder="Enter word or phrase..."
                  className="flex-1 border rounded px-4 py-2"
                />
                <select
                  value={searchType}
                  onChange={e => setSearchType(e.target.value)}
                  className="border rounded px-3 py-2 text-sm"
                >
                  <option value="lemma">Lemma (dictionary form)</option>
                  <option value="exact">Exact match</option>
                  <option value="regex">Regular expression</option>
                </select>
              </div>
              {sourceInfo && (
                <div className="mt-2 flex items-center justify-between text-sm text-gray-600 bg-gray-50 rounded px-3 py-2">
                  <span>
                    <span className="font-medium">{sourceInfo.author}</span>
                    {sourceInfo.work && <span className="italic">, {cleanWorkTitle(sourceInfo.work, sourceInfo.locus)}</span>}
                    {sourceInfo.locus && <span>, {extractLineNumber(sourceInfo.locus)}</span>}
                  </span>
                  <button
                    onClick={() => setSourceInfo(null)}
                    className="text-gray-400 hover:text-gray-600 ml-2"
                  >
                    Clear
                  </button>
                </div>
              )}
            </div>

            <div className="border-t pt-4">
              <div className="flex items-center justify-between mb-3">
                <span className="text-sm font-medium text-gray-700">Filter by Text (Optional)</span>
                {(selectedAuthor || selectedWork || lineStart || lineEnd) && (
                  <button
                    onClick={clearFilters}
                    className="text-xs text-red-600 hover:text-red-800"
                  >
                    Clear Filters
                  </button>
                )}
              </div>
              
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
                <div>
                  <label className="block text-xs text-gray-500 mb-1">Author</label>
                  <select
                    value={selectedAuthor}
                    onChange={e => setSelectedAuthor(e.target.value)}
                    className="w-full border rounded px-3 py-2 text-sm"
                    disabled={loadingTexts}
                  >
                    <option value="">All Authors</option>
                    {authors.map(author => (
                      <option key={author} value={author}>{author}</option>
                    ))}
                  </select>
                </div>
                
                <div>
                  <label className="block text-xs text-gray-500 mb-1">Work</label>
                  <select
                    value={selectedWork}
                    onChange={e => setSelectedWork(e.target.value)}
                    className="w-full border rounded px-3 py-2 text-sm"
                    disabled={!selectedAuthor || loadingTexts}
                  >
                    <option value="">All Works</option>
                    {works.map(work => (
                      <option key={work.id} value={work.id}>{work.label}</option>
                    ))}
                  </select>
                </div>
                
                <div>
                  <label className="block text-xs text-gray-500 mb-1">Line Start</label>
                  <input
                    type="number"
                    value={lineStart}
                    onChange={e => setLineStart(e.target.value)}
                    placeholder="e.g., 1"
                    className="w-full border rounded px-3 py-2 text-sm"
                    min="1"
                  />
                </div>
                
                <div>
                  <label className="block text-xs text-gray-500 mb-1">Line End</label>
                  <input
                    type="number"
                    value={lineEnd}
                    onChange={e => setLineEnd(e.target.value)}
                    placeholder="e.g., 100"
                    className="w-full border rounded px-3 py-2 text-sm"
                    min="1"
                  />
                </div>
              </div>
            </div>

            <div className="border-t pt-4 flex justify-end">
              <button
                onClick={handleSearch}
                disabled={!query.trim() || loading}
                className="px-6 py-2 bg-red-700 text-white rounded hover:bg-red-800 disabled:opacity-50"
              >
                {loading ? 'Searching...' : 'Search Lines'}
              </button>
            </div>
          </div>

          {loading && <LoadingSpinner text="Searching corpus..." elapsedTime={elapsedTime} step="Finding matching lines" />}

          {error && (
            <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded">
              {error}
            </div>
          )}

          {results.length > 0 && (
            <div className="bg-white rounded-lg shadow overflow-hidden">
              <div className="px-4 py-3 bg-gray-50 flex flex-wrap items-center justify-between gap-2">
                <span className="text-sm text-gray-600">
                  Found {results.length} parallel lines
                  {filteredResults.length !== results.length && (
                    <span className="text-amber-600"> (showing {filteredResults.length} after filters)</span>
                  )}
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
                    className="text-sm text-amber-600 hover:text-amber-800"
                  >
                    Export CSV
                  </button>
                </div>
              </div>

              {showTimeline && deduplicatedResults.some(r => r.era) && (
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
                  <div className="flex justify-end">
                    <button
                      onClick={exportTimelineChart}
                      className="text-xs text-gray-600 hover:text-gray-900"
                    >
                      Export PNG
                    </button>
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

              <div className="divide-y divide-gray-200">
                {filteredResults.slice(0, displayLimit).map((result, i) => (
                  <div key={i} className="p-4 hover:bg-gray-50">
                    <div className="flex flex-col sm:flex-row sm:items-start gap-2">
                      <div className="sm:w-48 flex-shrink-0">
                        <div className="text-sm font-medium text-gray-900">
                          {result.author}
                        </div>
                        <div className="text-xs text-gray-500">
                          {result.work}, {result.locus}
                        </div>
                        {result.era && (
                          <span className="text-xs px-1.5 py-0.5 bg-gray-100 text-gray-600 rounded mt-1 inline-block">
                            {result.era}
                          </span>
                        )}
                      </div>
                      <div className="flex-1 text-gray-700">
                        {highlightMatches(result.text, result.matched_words || query.split(/\s+/))}
                      </div>
                    </div>
                  </div>
                ))}
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
        </>
      ) : (
        <div className="bg-white rounded-lg shadow p-4 sm:p-6 space-y-4">
          <div>
            <h3 className="text-lg font-medium text-gray-900 mb-2">Find Text to Search</h3>
            <p className="text-sm text-gray-500 mb-4">
              Select an author and work to view all lines. Click any line to use it as a search term.
            </p>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="relative">
              <label className="block text-sm font-medium text-gray-700 mb-1">Author</label>
              <input
                type="text"
                value={selectedAuthor}
                onChange={e => { 
                  setSelectedAuthor(e.target.value); 
                  setSelectedWork('');
                  setSelectedWorkLabel('');
                  setBrowseLines([]); 
                  setShowAuthorDropdown(true);
                }}
                onFocus={() => setShowAuthorDropdown(true)}
                onBlur={() => setTimeout(() => setShowAuthorDropdown(false), 200)}
                placeholder="Type to search authors..."
                className="w-full border rounded px-3 py-2"
                disabled={loadingTexts}
              />
              {showAuthorDropdown && selectedAuthor !== '' && (
                <div className="absolute z-10 w-full mt-1 bg-white border rounded-lg shadow-lg max-h-60 overflow-y-auto">
                  {authors
                    .filter(a => a.toLowerCase().includes(selectedAuthor.toLowerCase()))
                    .slice(0, 20)
                    .map(author => (
                      <div
                        key={author}
                        className="px-3 py-2 hover:bg-amber-50 cursor-pointer text-sm"
                        onMouseDown={() => { setSelectedAuthor(author); setShowAuthorDropdown(false); }}
                      >
                        {author}
                      </div>
                    ))}
                  {authors.filter(a => a.toLowerCase().includes(selectedAuthor.toLowerCase())).length === 0 && (
                    <div className="px-3 py-2 text-gray-500 text-sm">No authors found</div>
                  )}
                </div>
              )}
              {showAuthorDropdown && selectedAuthor === '' && (
                <div className="absolute z-10 w-full mt-1 bg-white border rounded-lg shadow-lg max-h-60 overflow-y-auto">
                  {authors.slice(0, 20).map(author => (
                    <div
                      key={author}
                      className="px-3 py-2 hover:bg-amber-50 cursor-pointer text-sm"
                      onMouseDown={() => { setSelectedAuthor(author); setShowAuthorDropdown(false); }}
                    >
                      {author}
                    </div>
                  ))}
                </div>
              )}
            </div>
            
            <div className="relative">
              <label className="block text-sm font-medium text-gray-700 mb-1">Work</label>
              <input
                type="text"
                value={selectedWorkLabel}
                onChange={e => { 
                  setSelectedWorkLabel(e.target.value); 
                  setSelectedWork('');
                  setBrowseLines([]); 
                  setShowWorkDropdown(true);
                }}
                onFocus={() => setShowWorkDropdown(true)}
                onBlur={() => setTimeout(() => setShowWorkDropdown(false), 200)}
                placeholder={selectedAuthor ? "Type to search works..." : "Select author first"}
                className="w-full border rounded px-3 py-2"
                disabled={!selectedAuthor || loadingTexts}
              />
              {showWorkDropdown && selectedAuthor && (
                <div className="absolute z-10 w-full mt-1 bg-white border rounded-lg shadow-lg max-h-60 overflow-y-auto">
                  {works
                    .filter(w => w.label.toLowerCase().includes(selectedWorkLabel.toLowerCase()))
                    .map(work => (
                      <div
                        key={work.id}
                        className="px-3 py-2 hover:bg-amber-50 cursor-pointer text-sm"
                        onMouseDown={() => { setSelectedWork(work.id); setSelectedWorkLabel(work.label); setShowWorkDropdown(false); }}
                      >
                        {work.label}
                      </div>
                    ))}
                  {works.filter(w => w.label.toLowerCase().includes(selectedWorkLabel.toLowerCase())).length === 0 && (
                    <div className="px-3 py-2 text-gray-500 text-sm">No works found</div>
                  )}
                </div>
              )}
            </div>
          </div>

          <div className="flex justify-end">
            <button
              onClick={handleBrowseLines}
              disabled={!selectedAuthor || !selectedWork || browseLoading}
              className="px-4 py-2 bg-red-700 text-white rounded hover:bg-red-800 disabled:opacity-50"
            >
              {browseLoading ? 'Loading...' : 'Load Lines'}
            </button>
          </div>

          {browseLoading && <LoadingSpinner text="Loading lines..." />}

          {browseLines.length > 0 && (
            <div className="border rounded-lg overflow-hidden">
              <div className="px-4 py-2 bg-gray-50 border-b flex justify-between items-center">
                <span className="text-sm text-gray-600">
                  {browseLines.length} lines found
                </span>
              </div>
              <div className="max-h-96 overflow-y-auto divide-y">
                {browseLines.slice(0, browseDisplayLimit).map((line, i) => (
                  <div
                    key={i}
                    className="p-3 hover:bg-amber-50 cursor-pointer flex gap-3"
                    onClick={() => selectLineForSearch(line)}
                  >
                    <span className="text-xs text-gray-400 w-16 flex-shrink-0 text-right">
                      {line.locus}
                    </span>
                    <span className="text-sm text-gray-700 flex-1">{line.text}</span>
                  </div>
                ))}
              </div>
              {browseLines.length > browseDisplayLimit && (
                <div className="px-4 py-2 bg-gray-50 border-t text-center">
                  <button
                    onClick={() => setBrowseDisplayLimit(browseDisplayLimit + 100)}
                    className="text-amber-600 hover:text-amber-800 text-sm"
                  >
                    Show more ({browseDisplayLimit} of {browseLines.length})
                  </button>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
