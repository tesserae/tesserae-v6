import { useState, useCallback, useRef, useMemo } from 'react';
import { Button } from '../common';
import { Chart as ChartJS, CategoryScale, LinearScale, BarElement, Title, Tooltip, Legend } from 'chart.js';
import { Bar } from 'react-chartjs-2';
import { formatFullCitation } from '../../utils/textNames';

ChartJS.register(CategoryScale, LinearScale, BarElement, Title, Tooltip, Legend);

const displayGreekWithFinalSigma = (text) => {
  if (!text) return text;
  return text.replace(/σ(?=\s|$|[,.;:!?])/g, 'ς');
};

const normalizeGreek = (text) => {
  if (!text) return '';
  return text
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .replace(/ς/g, 'σ');
};

const highlightLemmasInText = (text, lemmas) => {
  if (!text || !lemmas || lemmas.length === 0) return text;
  
  const normalizedLemmas = lemmas.map(l => normalizeGreek(l));
  const words = text.split(/(\s+)/);
  
  return words.map((word, i) => {
    if (/^\s+$/.test(word)) return <span key={i}>{word}</span>;
    
    const normalizedWord = normalizeGreek(word.replace(/[,.;:!?'"()·]/g, ''));
    if (normalizedWord.length < 2) return <span key={i}>{word}</span>;
    
    const isMatch = normalizedLemmas.some((lemma) => {
      if (normalizedWord === lemma) return true;
      if (normalizedWord.startsWith(lemma) && normalizedWord.length <= lemma.length + 3) return true;
      if (lemma.startsWith(normalizedWord) && lemma.length <= normalizedWord.length + 3) return true;
      return false;
    });
    
    if (isMatch) {
      return <mark key={i} className="bg-yellow-200 px-0.5 rounded">{word}</mark>;
    }
    return <span key={i}>{word}</span>;
  });
};

const highlightByIndices = (text, tokens, highlightIndices) => {
  if (!tokens || !highlightIndices || highlightIndices.length === 0) {
    return text;
  }
  
  const highlightSet = new Set(highlightIndices);
  const tokensToHighlight = new Set(
    highlightIndices.map(idx => tokens[idx]?.toLowerCase()).filter(Boolean)
  );
  
  const words = text.split(/(\s+)/);
  let tokenIdx = 0;
  
  return words.map((word, i) => {
    if (/^\s+$/.test(word)) return <span key={i}>{word}</span>;
    
    const cleanWord = word.replace(/[,.;:!?'"()·\[\]<>]/g, '').toLowerCase();
    const isMatch = tokensToHighlight.has(cleanWord);
    
    tokenIdx++;
    
    if (isMatch) {
      return <mark key={i} className="bg-yellow-200 px-0.5 rounded">{word}</mark>;
    }
    return <span key={i}>{word}</span>;
  });
};

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

export default function CorpusSearchResults({ 
  results, 
  loading, 
  error, 
  query,
  onBack,
  elapsedTime
}) {
  const [displayLimit, setDisplayLimit] = useState(50);
  const [showTimeline, setShowTimeline] = useState(false);
  const [eraFilter, setEraFilter] = useState(null);
  const [authorFilter, setAuthorFilter] = useState(null);
  const [includePoetry, setIncludePoetry] = useState(true);
  const [includeProse, setIncludeProse] = useState(true);
  const chartRef = useRef(null);
  const authorChartRef = useRef(null);

  const renderHighlightedText = (text, tokens, highlightIndices) => {
    if (!text || !tokens || !highlightIndices || highlightIndices.length === 0) return text;
    
    const words = text.split(/(\s+)/);
    let tokenIdx = 0;
    
    return words.map((word, i) => {
      if (/^\s+$/.test(word)) return <span key={i}>{word}</span>;
      
      const isHighlighted = highlightIndices.includes(tokenIdx);
      tokenIdx++;
      
      if (isHighlighted) {
        return <mark key={i} className="bg-yellow-200 px-0.5 rounded">{word}</mark>;
      }
      return <span key={i}>{word}</span>;
    });
  };

  const filteredByGenre = (results || []).filter(r => {
    if (!includePoetry && r.is_poetry) return false;
    if (!includeProse && !r.is_poetry) return false;
    return true;
  });

  const getTimelineData = useCallback(() => {
    if (!filteredByGenre || filteredByGenre.length === 0) return null;
    
    const eraCounts = {};
    filteredByGenre.forEach(r => {
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
  }, [filteredByGenre]);

  const chartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { display: false },
      title: {
        display: true,
        text: eraFilter ? `Showing matches from ${eraFilter} (click to clear)` : 'Chronological Distribution (click bar to filter)'
      }
    },
    scales: { y: { beginAtZero: true, ticks: { stepSize: 1 } } },
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

  const getAuthorTimelineData = useCallback(() => {
    if (!filteredByGenre || filteredByGenre.length === 0) return null;
    
    const authorCounts = {};
    filteredByGenre.forEach(r => {
      const author = r.author || 'Unknown';
      authorCounts[author] = (authorCounts[author] || 0) + 1;
    });
    
    const sortedAuthors = Object.keys(authorCounts).sort((a, b) => {
      const aResult = filteredByGenre.find(r => r.author === a);
      const bResult = filteredByGenre.find(r => r.author === b);
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
  }, [filteredByGenre]);

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

  const exportCSV = useCallback(() => {
    if (!results || results.length === 0) return;
    const headers = ['Author', 'Work', 'Locus', 'Text', 'Era', 'Year'];
    const rows = results.map(r => [
      r.author || '',
      r.work || '',
      r.locus || '',
      (r.text || '').replace(/"/g, '""'),
      r.era || '',
      r.year || ''
    ]);
    const csv = [headers, ...rows].map(row => row.map(cell => `"${cell}"`).join(',')).join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `tesserae_corpus_${query?.lemmas?.join('_') || 'search'}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  }, [results, query]);

  const exportTimelineChart = () => {
    if (!chartRef.current) return;
    const canvas = chartRef.current.canvas;
    if (!canvas) return;
    const link = document.createElement('a');
    link.download = `tesserae_corpus_timeline_${new Date().toISOString().slice(0, 10)}.png`;
    link.href = canvas.toDataURL('image/png');
    link.click();
  };

  const filteredResults = filteredByGenre.filter(r => {
    if (eraFilter && (r.era || 'Unknown') !== eraFilter) return false;
    if (authorFilter && (r.author || 'Unknown') !== authorFilter) return false;
    return true;
  });

  if (loading) {
    return (
      <div className="bg-white rounded-lg shadow p-6">
        <div className="flex flex-col items-center justify-center py-12">
          <div className="w-10 h-10 border-4 border-gray-200 border-t-amber-600 rounded-full animate-spin mb-4"></div>
          <p className="text-gray-600">Searching corpus for matching word combinations...</p>
          {elapsedTime > 0 && (
            <p className="text-sm text-gray-500 mt-2">Elapsed: {elapsedTime}s</p>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-lg shadow">
      <div className="p-4 border-b bg-gray-50">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <button
            onClick={onBack}
            className="text-amber-600 hover:text-amber-800 text-sm flex items-center gap-1"
          >
            ← Back to Search
          </button>
          <h2 className="text-lg font-semibold text-gray-900">
            Corpus-Wide Search
          </h2>
        </div>
      </div>

      {query && (
        <div className="p-4 border-b bg-amber-50">
          {query.source?.ref?.includes('Rare Word') || query.source?.ref?.includes('Rare Pair') ? (
            <div className="mb-3">
              <div className="text-sm font-medium text-gray-700 mb-2">
                Searching corpus for occurrences of:
              </div>
              <div className="flex flex-wrap gap-2">
                {query.lemmas?.map((lemma, i) => (
                  <span key={i} className="text-lg font-semibold bg-amber-200 text-amber-800 px-3 py-1 rounded">
                    {displayGreekWithFinalSigma(lemma)}
                  </span>
                ))}
              </div>
            </div>
          ) : (
            <>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-3">
                <div>
                  {(() => {
                    const citation = formatFullCitation(null, query.source?.ref);
                    return (
                      <div className="text-xs font-bold text-green-700 mb-1">
                        Source: {citation.author}, <span className="italic">{citation.work}</span> {citation.reference}
                      </div>
                    );
                  })()}
                  <div className="text-sm text-gray-700">{highlightLemmasInText(query.source?.text, query.lemmas)}</div>
                </div>
                <div>
                  {(() => {
                    const citation = formatFullCitation(null, query.target?.ref);
                    return (
                      <div className="text-xs font-bold text-red-700 mb-1">
                        Target: {citation.author}, <span className="italic">{citation.work}</span> {citation.reference}
                      </div>
                    );
                  })()}
                  <div className="text-sm text-gray-700">{highlightLemmasInText(query.target?.text, query.lemmas)}</div>
                </div>
              </div>
              <div className="flex flex-wrap gap-1 mt-2">
                <span className="text-xs text-gray-600">Searching for:</span>
                {query.lemmas?.map((lemma, i) => (
                  <span key={i} className="text-xs bg-amber-200 text-amber-800 px-2 py-0.5 rounded font-medium">
                    {displayGreekWithFinalSigma(lemma)}
                  </span>
                ))}
              </div>
            </>
          )}
        </div>
      )}

      {error && (
        <div className="p-4 bg-red-50 text-red-700">
          {error}
        </div>
      )}

      {!loading && !error && results && (
        <div className="p-4">
          <div className="flex flex-wrap items-center justify-between gap-2 mb-4">
            <span className="text-sm text-gray-600">
              Found <strong>{results.length}</strong> occurrences across the corpus
              {results.length > 500 && ' (showing first 500)'}
              {(eraFilter || !includePoetry || !includeProse) && filteredResults.length !== results.length && (
                <span className="text-amber-700"> (showing {filteredResults.length} after filters)</span>
              )}
            </span>
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-3 text-sm">
                <label className="flex items-center gap-1 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={includePoetry}
                    onChange={(e) => setIncludePoetry(e.target.checked)}
                    className="w-4 h-4 text-amber-600 rounded border-gray-300 focus:ring-amber-500"
                  />
                  <span className="text-gray-700">Poetry</span>
                </label>
                <label className="flex items-center gap-1 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={includeProse}
                    onChange={(e) => setIncludeProse(e.target.checked)}
                    className="w-4 h-4 text-amber-600 rounded border-gray-300 focus:ring-amber-500"
                  />
                  <span className="text-gray-700">Prose</span>
                </label>
              </div>
              <button
                onClick={() => setShowTimeline(!showTimeline)}
                className={`text-sm px-3 py-1 rounded ${showTimeline ? 'bg-amber-700 text-white' : 'bg-amber-100 text-amber-700 hover:bg-amber-200'}`}
              >
                {showTimeline ? 'Hide Timeline' : 'Timeline'}
              </button>
              <button
                onClick={exportCSV}
                className="text-sm text-green-600 hover:text-green-800"
              >
                Export CSV
              </button>
            </div>
          </div>

          {showTimeline && results.some(r => r.era) && (
            <div className="p-4 border rounded bg-gray-50 mb-4">
              <div className="mb-4">
                <h4 className="text-sm font-medium text-gray-700 mb-2">Period Timeline</h4>
                <div style={{ height: '180px' }}>
                  <Bar ref={chartRef} data={getTimelineData() || { labels: [], datasets: [] }} options={chartOptions} />
                </div>
              </div>
              <div className="mb-2">
                <h4 className="text-sm font-medium text-gray-700 mb-2">Author Timeline</h4>
                <div style={{ height: '180px' }}>
                  <Bar ref={authorChartRef} data={getAuthorTimelineData() || { labels: [], datasets: [] }} options={authorChartOptions} />
                </div>
              </div>
              <div className="flex justify-end mt-2">
                <button onClick={exportTimelineChart} className="text-xs text-gray-600 hover:text-gray-900">
                  Export PNG
                </button>
              </div>
            </div>
          )}

          {(eraFilter || authorFilter) && (
            <div className="px-4 py-2 bg-amber-50 border border-amber-200 rounded mb-4 flex items-center justify-between">
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

          <div className="divide-y border rounded">
            {filteredResults.slice(0, displayLimit).map((result, i) => (
              <div key={i} className="p-3 hover:bg-gray-50">
                <div className="flex flex-col sm:flex-row sm:items-start gap-2">
                  <div className="sm:w-48 flex-shrink-0">
                    {(() => {
                      const citation = formatFullCitation(result.author, result.locus);
                      return (
                        <>
                          <div className="text-sm font-medium text-gray-900">{citation.author}</div>
                          <div className="text-xs text-gray-500">
                            {citation.work && <span className="italic">{citation.work}</span>}
                            {citation.work && citation.reference && ' '}
                            {citation.reference}
                          </div>
                        </>
                      );
                    })()}
                    {result.era && (
                      <span className="text-xs px-1.5 py-0.5 bg-gray-100 text-gray-600 rounded mt-1 inline-block">
                        {result.era}
                      </span>
                    )}
                  </div>
                  <div className="flex-1 text-sm text-gray-700">
                    {result.tokens && result.highlight_indices && result.highlight_indices.length > 0
                      ? highlightByIndices(result.text, result.tokens, result.highlight_indices)
                      : highlightLemmasInText(result.text, query?.lemmas || result.matched_lemmas || [])}
                  </div>
                </div>
              </div>
            ))}
          </div>

          {filteredResults.length > displayLimit && (
            <div className="text-center mt-4">
              <Button
                variant="neutral"
                onClick={() => setDisplayLimit(prev => prev + 50)}
              >
                Show More ({filteredResults.length - displayLimit} remaining)
              </Button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
