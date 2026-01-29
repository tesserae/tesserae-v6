import { useState, useCallback, useRef, useEffect } from 'react';
import { Button, LoadingSpinner } from '../common';
import { formatReference } from '../../utils/formatting';
import { Chart as ChartJS, CategoryScale, LinearScale, BarElement, Title, Tooltip, Legend } from 'chart.js';
import { Bar } from 'react-chartjs-2';

ChartJS.register(CategoryScale, LinearScale, BarElement, Title, Tooltip, Legend);

const displayGreekWithFinalSigma = (text) => {
  if (!text) return text;
  return text.replace(/σ(?=\s|$|[,.;:!?])/g, 'ς');
};

const SearchResults = ({ 
  results, 
  loading, 
  error, 
  displayLimit,
  setDisplayLimit,
  onRegister,
  onCorpusSearch,
  sortBy,
  setSortBy,
  searchStats,
  sourceTextInfo,
  targetTextInfo,
  elapsedTime = 0,
  progressText = '',
  matchType = 'lemma'
}) => {
  const [expandedResults, setExpandedResults] = useState({});
  const [showDistributionChart, setShowDistributionChart] = useState(false);
  const [distributionChartView, setDistributionChartView] = useState('target');
  const [chartFilter, setChartFilter] = useState(null);
  const chartRef = useRef(null);

  const toggleExpand = (index) => {
    setExpandedResults(prev => ({
      ...prev,
      [index]: !prev[index]
    }));
  };

  const exportCSV = useCallback(() => {
    if (!results || results.length === 0) return;
    
    const headers = ['Source Locus', 'Source Text', 'Target Locus', 'Target Text', 'Score', 'Matched Words'];
    const rows = results.map(r => [
      r.source_locus || r.source?.ref || '',
      (r.source_text || r.source_snippet || r.source?.text || '').replace(/<[^>]*>/g, '').replace(/"/g, '""'),
      r.target_locus || r.target?.ref || '',
      (r.target_text || r.target_snippet || r.target?.text || '').replace(/<[^>]*>/g, '').replace(/"/g, '""'),
      (r.score ?? r.overall_score)?.toFixed(3) || '',
      (r.matched_words || []).map(w => typeof w === 'object' ? (w.lemma || w.word || '') : w).join('; ')
    ]);
    
    const csv = [headers.join(','), ...rows.map(r => r.map(c => `"${c}"`).join(','))].join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `tesserae_results_${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  }, [results]);

  const exportDistributionChart = () => {
    if (!chartRef.current) return;
    const canvas = chartRef.current.canvas;
    if (!canvas) return;
    
    const link = document.createElement('a');
    const isSourceView = distributionChartView === 'source';
    const textInfo = isSourceView ? sourceTextInfo : targetTextInfo;
    const authorName = (textInfo?.author || 'author').replace(/[^a-zA-Z0-9]/g, '_');
    const workName = (textInfo?.title || 'work').replace(/[^a-zA-Z0-9]/g, '_');
    link.download = `tesserae_${authorName}_${workName}_${distributionChartView}_${new Date().toISOString().slice(0, 10)}.png`;
    link.href = canvas.toDataURL('image/png');
    link.click();
  };

  const getDistributionData = useCallback(() => {
    if (!results || results.length === 0) return null;
    
    const bookData = {};
    const isSourceView = distributionChartView === 'source';
    
    results.forEach(r => {
      const locus = isSourceView 
        ? (r.source_locus || r.source?.ref || '') 
        : (r.target_locus || r.target?.ref || '');
      
      const bookMatch = locus.match(/book\s*(\d+)/i) || 
                        locus.match(/(\d+)\.\d+/) ||
                        locus.match(/^([^.]+)/);
      
      const book = bookMatch ? bookMatch[1] : 'Other';
      const bookLabel = `Book ${book}`;
      
      if (!bookData[bookLabel]) {
        bookData[bookLabel] = { count: 0, totalScore: 0 };
      }
      bookData[bookLabel].count++;
      bookData[bookLabel].totalScore += (r.score ?? r.overall_score ?? 0);
    });
    
    const sortedBooks = Object.keys(bookData).sort((a, b) => {
      const numA = parseInt(a.replace(/\D/g, '')) || 0;
      const numB = parseInt(b.replace(/\D/g, '')) || 0;
      return numA - numB;
    });
    
    return {
      labels: sortedBooks,
      datasets: [{
        label: 'Parallels',
        data: sortedBooks.map(book => bookData[book].count),
        backgroundColor: isSourceView ? 'rgba(185, 28, 28, 0.7)' : 'rgba(217, 119, 6, 0.7)',
        borderColor: isSourceView ? 'rgb(185, 28, 28)' : 'rgb(217, 119, 6)',
        borderWidth: 1
      }]
    };
  }, [results, distributionChartView]);

  const chartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        display: false
      },
      title: {
        display: true,
        text: `Distribution of Parallels from ${sourceTextInfo?.title || 'Source'} in ${targetTextInfo?.title || 'Target'}`
      },
      tooltip: {
        callbacks: {
          label: (context) => `${context.parsed.y} parallel${context.parsed.y !== 1 ? 's' : ''}`
        }
      }
    },
    scales: {
      x: {
        title: {
          display: true,
          text: distributionChartView === 'source' 
            ? (sourceTextInfo?.title || 'Source') 
            : (targetTextInfo?.title || 'Target'),
          font: { size: 12 }
        }
      },
      y: {
        beginAtZero: true,
        ticks: {
          stepSize: 1
        },
        title: {
          display: true,
          text: 'Parallels',
          font: { size: 12 }
        }
      }
    },
    onClick: (event, elements) => {
      if (elements.length > 0) {
        const idx = elements[0].index;
        const chartData = getDistributionData();
        if (chartData) {
          const clickedBook = chartData.labels[idx];
          setChartFilter({ book: clickedBook, view: distributionChartView });
        }
      }
    }
  };

  const renderHighlightedText = (textData, language = null, matchedWords = [], isSource = true, otherTextData = null) => {
    if (!textData) return '';
    
    if (typeof textData === 'string') return textData;
    
    const { text, tokens, highlight_indices } = textData;
    
    if (!text) return '';
    
    // Build set of words to highlight from multiple sources
    const wordsToHighlight = new Set();
    // For sound matching: n-grams to search for within words
    const soundNgrams = new Set();
    
    // 1. From highlight_indices (if available)
    if (tokens && highlight_indices && highlight_indices.length > 0) {
      highlight_indices.forEach(i => {
        const token = tokens[i]?.toLowerCase();
        if (token) wordsToHighlight.add(token);
      });
    }
    
    // 2. From matched_words (for semantic and sound matches)
    if (matchedWords && matchedWords.length > 0) {
      matchedWords.forEach(m => {
        // Add the source or target word based on which side we're rendering
        const word = isSource ? m.source_word : m.target_word;
        if (word) wordsToHighlight.add(word.toLowerCase());
        // Also add the lemma (handles cases where lemma differs from token)
        if (m.lemma && !m.lemma.includes('≈') && m.lemma !== 'semantic') {
          // Check if this looks like a sound n-gram match (e.g., "[φά]", "φρον~εὐφρον")
          const lemmaStr = String(m.lemma);
          if (lemmaStr.includes('[') || lemmaStr.includes('~')) {
            // Extract n-grams from sound match format
            // Format: "[ngram1], [ngram2]" or "source~target"
            const ngrams = lemmaStr.split(/[\[\],~\s]+/).filter(s => s.length >= 2);
            ngrams.forEach(ng => soundNgrams.add(ng.toLowerCase()));
          } else {
            wordsToHighlight.add(lemmaStr.toLowerCase());
          }
        }
        // Handle display field for sound matches
        if (m.display) {
          const displayStr = String(m.display);
          if (displayStr.includes('[') || displayStr.includes('~')) {
            const ngrams = displayStr.split(/[\[\],~\s]+/).filter(s => s.length >= 2);
            ngrams.forEach(ng => soundNgrams.add(ng.toLowerCase()));
          }
        }
      });
    }
    
    // 3. Find common word stems between source and target (ONLY for semantic matches)
    // For exact/lemma matches, we trust the backend highlight_indices which respect the stoplist
    const isSemanticMatch = matchedWords?.some(m => m.similarity !== undefined || m.lemma === 'semantic');
    if (isSemanticMatch && otherTextData && otherTextData.tokens && tokens) {
      const thisTokens = new Set(tokens.map(t => t?.toLowerCase()).filter(Boolean));
      const otherTokens = new Set(otherTextData.tokens.map(t => t?.toLowerCase()).filter(Boolean));
      
      // Find tokens that share a common stem (first 4+ chars) - catches hasta/hastam
      thisTokens.forEach(token => {
        if (token.length >= 4) {
          const stem = token.slice(0, Math.min(token.length - 1, 5));
          otherTokens.forEach(otherToken => {
            if (otherToken.length >= 4 && otherToken.startsWith(stem)) {
              wordsToHighlight.add(token);
            }
          });
        }
      });
    }
    
    // Helper to check if a word matches any highlight word or contains sound n-grams
    const shouldHighlight = (word) => {
      const normalized = word.toLowerCase().replace(/[.,;:!?'"()—–-]+$/, '').replace(/^[.,;:!?'"()—–-]+/, '');
      if (wordsToHighlight.has(normalized)) return true;
      
      // For sound matching: check if word contains any of the matched n-grams
      if (soundNgrams.size > 0) {
        for (const ngram of soundNgrams) {
          if (normalized.includes(ngram)) return true;
          // Also check with Greek accent normalization (strip diacritics for matching)
          const normalizedNoAccents = normalized.normalize('NFD').replace(/[\u0300-\u036f]/g, '');
          const ngramNoAccents = ngram.normalize('NFD').replace(/[\u0300-\u036f]/g, '');
          if (normalizedNoAccents.includes(ngramNoAccents)) return true;
        }
      }
      
      // For Latin, also check u/v equivalence
      if (language === 'la') {
        const uvNormalized = normalized.replace(/[uv]/g, 'u');
        for (const hw of wordsToHighlight) {
          if (hw.replace(/[uv]/g, 'u') === uvNormalized) return true;
        }
      }
      return false;
    };
    
    if (wordsToHighlight.size === 0 && soundNgrams.size === 0) return text;
    
    // Split text preserving whitespace and punctuation
    const parts = text.split(/(\s+)/);
    const result = parts.map(part => {
      if (/^\s+$/.test(part)) return part; // whitespace
      if (shouldHighlight(part)) {
        return `<mark class="bg-yellow-200 px-0.5 rounded">${part}</mark>`;
      }
      return part;
    }).join('');
    
    return result;
  };

  const renderScansion = (scansion) => {
    if (!scansion || !scansion.raw) return null;
    const meterAbbr = {
      'hexameter': 'Hx',
      'pentameter': 'P',
      'hendecasyllable': 'Hn',
      'elegiac': 'E'
    };
    return (
      <div className="flex items-center gap-1 mt-1">
        <span className="font-mono text-xs text-gray-500">{scansion.raw}</span>
        <span className="text-xs px-1.5 py-0.5 rounded font-medium bg-gray-100 text-gray-600" title={scansion.meter}>
          {meterAbbr[scansion.meter] || scansion.meter?.charAt(0).toUpperCase() || '?'}
        </span>
      </div>
    );
  };

  if (loading) {
    const isSlowSearch = matchType === 'sound' || matchType === 'edit_distance';
    return (
      <div className="flex flex-col items-center justify-center py-12">
        {isSlowSearch && (
          <div className="text-sm text-gray-600 mb-4 text-center">
            Initial sound or edit distance searches on large texts typically take several minutes.
          </div>
        )}
        <LoadingSpinner 
          size="lg" 
          text="Searching for parallels..." 
          elapsedTime={elapsedTime}
        />
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-red-700">
        {error}
      </div>
    );
  }

  if (!results || results.length === 0) {
    return null;
  }

  const filteredResults = chartFilter 
    ? results.filter(r => {
        const locus = chartFilter.view === 'source' 
          ? (r.source_locus || r.source?.ref || '') 
          : (r.target_locus || r.target?.ref || '');
        const bookMatch = locus.match(/book\s*(\d+)/i) || 
                          locus.match(/(\d+)\.\d+/) ||
                          locus.match(/^([^.]+)/);
        const book = bookMatch ? `Book ${bookMatch[1]}` : 'Other';
        return book === chartFilter.book;
      })
    : results;

  const displayedResults = filteredResults.slice(0, displayLimit);

  return (
    <div className="space-y-4">
      <div className="flex flex-col sm:flex-row sm:justify-between sm:items-center gap-2 mb-4">
        <div>
          <h3 className="text-lg font-semibold text-gray-900">
            {results.length} Parallel{results.length !== 1 ? 's' : ''} Found
            {chartFilter && ` (${filteredResults.length} in ${chartFilter.book})`}
          </h3>
          {searchStats && (
            <p className="text-sm text-gray-500">
              {searchStats.elapsed_time && `Search completed in ${searchStats.elapsed_time.toFixed(2)}s`}
              {searchStats.source_lines && ` | ${searchStats.source_lines} source lines`}
              {searchStats.target_lines && ` | ${searchStats.target_lines} target lines`}
            </p>
          )}
        </div>
        <div className="flex flex-col sm:flex-row gap-2">
          <div className="flex items-center gap-2">
            <button
              onClick={() => setShowDistributionChart(!showDistributionChart)}
              className={`text-xs px-3 py-1.5 rounded whitespace-nowrap ${showDistributionChart ? 'bg-amber-600 text-white' : 'bg-amber-100 text-amber-700 hover:bg-amber-200'}`}
            >
              {showDistributionChart ? 'Hide Chart' : 'Distribution'}
            </button>
            <button
              onClick={exportCSV}
              className="text-xs bg-green-600 text-white px-3 py-1.5 rounded hover:bg-green-700 whitespace-nowrap"
            >
              Export CSV
            </button>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-sm text-gray-600">Sort:</span>
            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value)}
              className="border rounded px-2 py-1 text-sm"
            >
              <option value="score">Score</option>
              <option value="source_locus">Source Location</option>
              <option value="target_locus">Target Location</option>
            </select>
          </div>
        </div>
      </div>

      {showDistributionChart && results.length > 0 && (
        <div className="bg-white border rounded-lg p-4 mb-4">
          <div className="flex flex-wrap items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <span className="text-sm font-medium text-gray-700">View:</span>
              <button 
                onClick={() => { setDistributionChartView('source'); setChartFilter(null); }}
                className={`text-xs px-3 py-1 rounded ${distributionChartView === 'source' ? 'bg-red-700 text-white' : 'bg-red-100 text-red-600 hover:bg-red-200'}`}
              >
                Source
              </button>
              <button 
                onClick={() => { setDistributionChartView('target'); setChartFilter(null); }}
                className={`text-xs px-3 py-1 rounded ${distributionChartView === 'target' ? 'bg-amber-600 text-white' : 'bg-amber-100 text-amber-600 hover:bg-amber-200'}`}
              >
                Target
              </button>
            </div>
            <button
              onClick={exportDistributionChart}
              className="text-xs text-gray-600 hover:text-gray-900"
              title="Export chart as PNG"
            >
              Export PNG
            </button>
          </div>
          <div style={{ height: '200px' }}>
            <Bar ref={chartRef} data={getDistributionData() || { labels: [], datasets: [] }} options={chartOptions} />
          </div>
          {chartFilter && (
            <div className="mt-3 flex items-center justify-between bg-amber-50 border border-amber-200 rounded px-3 py-2">
              <span className="text-sm text-amber-800">
                Filtering to {chartFilter.book} ({filteredResults.length} result{filteredResults.length !== 1 ? 's' : ''})
              </span>
              <button
                onClick={() => setChartFilter(null)}
                className="text-xs text-amber-600 hover:text-amber-800 font-medium"
              >
                Clear Filter
              </button>
            </div>
          )}
          <p className="text-xs text-gray-500 mt-2">Click a bar to filter results to that book/section</p>
        </div>
      )}

      <div className="space-y-3">
        {displayedResults.map((r, i) => (
          <div 
            key={i} 
            className="bg-white border rounded-lg p-4 hover:shadow-md transition-shadow"
          >
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <div className="text-xs text-gray-500 mb-1">Source</div>
                <div className="font-medium text-gray-900">{formatReference(r.source_locus || r.source?.ref, sourceTextInfo?.language)}</div>
                <div 
                  className="text-gray-700 mt-1"
                  dangerouslySetInnerHTML={{ __html: r.source_text || r.source_snippet || renderHighlightedText(r.source, sourceTextInfo?.language, r.matched_words, true, r.target) }}
                />
                {r.features?.source_scansion && renderScansion(r.features.source_scansion)}
              </div>
              <div>
                <div className="text-xs text-gray-500 mb-1">Target</div>
                <div className="font-medium text-gray-900">{formatReference(r.target_locus || r.target?.ref, targetTextInfo?.language)}</div>
                <div 
                  className="text-gray-700 mt-1"
                  dangerouslySetInnerHTML={{ __html: r.target_text || r.target_snippet || renderHighlightedText(r.target, targetTextInfo?.language, r.matched_words, false, r.source) }}
                />
                {r.features?.target_scansion && renderScansion(r.features.target_scansion)}
              </div>
            </div>

            <div className="flex flex-wrap items-center gap-2 mt-3 pt-3 border-t">
              <span className="text-sm text-gray-600">
                Score: <span className="font-medium">{(r.score ?? r.overall_score)?.toFixed(2) || '-'}</span>
              </span>
              {r.features?.meter_score > 0 && (
                <span className="text-xs bg-purple-100 text-purple-700 px-2 py-0.5 rounded">
                  Metrical: {(r.features.meter_score * 100).toFixed(0)}%
                </span>
              )}
              {r.matched_words && r.matched_words.length > 0 && (
                <span className="text-sm text-gray-600">
                  Matches: <span className="font-medium">
                    {r.matched_words.map(w => {
                      const word = typeof w === 'object' ? (w.lemma || w.word || w.display || JSON.stringify(w)) : w;
                      return displayGreekWithFinalSigma(word);
                    }).join(', ')}
                  </span>
                </span>
              )}
              <div className="flex-1"></div>
              {r.match_basis !== 'semantic' && onCorpusSearch && (
                <Button 
                  variant="tertiary" 
                  size="sm"
                  onClick={() => onCorpusSearch(r)}
                  title="Find these words together in other texts"
                >
                  Search Corpus
                </Button>
              )}
              {onRegister && (
                <Button 
                  variant="secondary" 
                  size="sm"
                  onClick={() => onRegister(r)}
                  title="Save this parallel to the Repository"
                >
                  Register
                </Button>
              )}
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
  );
};

export default SearchResults;
