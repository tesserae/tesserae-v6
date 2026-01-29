import { useState, useCallback, useRef } from 'react';
import { Chart as ChartJS, CategoryScale, LinearScale, BarElement, Title, Tooltip, Legend } from 'chart.js';
import { Bar } from 'react-chartjs-2';

ChartJS.register(CategoryScale, LinearScale, BarElement, Title, Tooltip, Legend);

const displayGreekWithFinalSigma = (text) => {
  if (!text) return text;
  return text.replace(/σ(?=\s|$|[,.;:!?])/g, 'ς');
};

const highlightMatchedWords = (text, matchedWords, lemma1, lemma2) => {
  if (!text || (!matchedWords?.length && !lemma1 && !lemma2)) return text;
  
  // Build list of lemma stems to match against
  const lemmaStems = new Set();
  
  // Add lemma variants (these are the dictionary stems we're matching)
  if (lemma1) {
    const l1 = lemma1.toLowerCase();
    lemmaStems.add(l1);
    lemmaStems.add(l1.replace(/u/g, 'v'));
    lemmaStems.add(l1.replace(/v/g, 'u'));
  }
  if (lemma2) {
    const l2 = lemma2.toLowerCase();
    lemmaStems.add(l2);
    lemmaStems.add(l2.replace(/u/g, 'v'));
    lemmaStems.add(l2.replace(/v/g, 'u'));
  }
  
  // Add surface forms from matched words
  if (matchedWords) {
    matchedWords.forEach(w => {
      if (w) {
        const wl = w.toLowerCase();
        lemmaStems.add(wl);
        lemmaStems.add(wl.replace(/u/g, 'v'));
        lemmaStems.add(wl.replace(/v/g, 'u'));
      }
    });
  }
  
  if (lemmaStems.size === 0) return text;
  
  // Split text into tokens while preserving whitespace and punctuation
  const parts = text.split(/(\s+)/);
  
  return parts.map((part, i) => {
    // Extract word without punctuation for matching
    const wordMatch = part.match(/^([^\w]*)(\w+)([^\w]*)$/);
    if (!wordMatch) return part;
    
    const [, before, word, after] = wordMatch;
    const wordLower = word.toLowerCase();
    const wordNormU = wordLower.replace(/v/g, 'u');
    const wordNormV = wordLower.replace(/u/g, 'v');
    
    // Check if this word matches any of our lemma stems
    let isMatch = false;
    for (const stem of lemmaStems) {
      const stemNormU = stem.replace(/v/g, 'u');
      
      // For short stems (2-3 chars), require exact match or word starts with stem exactly
      // For longer stems, allow prefix matching
      if (stem.length <= 3) {
        // Short stem: word must equal stem OR word must start with stem + have Latin ending
        if (wordNormU === stemNormU || 
            (wordNormU.startsWith(stemNormU) && wordNormU.length <= stemNormU.length + 4)) {
          isMatch = true;
          break;
        }
      } else {
        // Longer stem: prefix match is OK
        if (wordNormU === stemNormU || 
            wordNormU.startsWith(stemNormU) ||
            stemNormU.startsWith(wordNormU)) {
          isMatch = true;
          break;
        }
      }
    }
    
    if (isMatch) {
      return (
        <span key={i}>
          {before}<span className="bg-yellow-200 px-0.5 rounded font-medium">{word}</span>{after}
        </span>
      );
    }
    return part;
  });
};

const formatTextName = (filename) => {
  if (!filename) return '';
  const base = filename.replace('.tess', '');
  const parts = base.split('.');
  const author = parts[0]?.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase()) || '';
  let work = '';
  if (parts.length > 1) {
    if (parts[1] === 'part' && parts[2]) {
      work = `Book ${parts[2]}`;
    } else {
      work = parts[1].replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
      if (parts[2] === 'part' && parts[3]) {
        work += `, Book ${parts[3]}`;
      }
    }
  }
  return work ? `${author}, ${work}` : author;
};

const formatLocationRef = (ref, fullTextName) => {
  if (!ref) return '';
  const lineMatch = ref.match(/(\d+(?:\.\d+)?(?:\s*\([^)]*\))?)$/);
  const lineNum = lineMatch ? lineMatch[1] : ref;
  return `${fullTextName} ${lineNum}`;
};

const RareResultsDisplay = ({
  results,
  loading,
  error,
  displayLimit,
  setDisplayLimit,
  searchMode,
  sourceText,
  targetText,
  onRegister,
  onCorpusSearch,
  elapsedTime = 0
}) => {
  const [showTimeline, setShowTimeline] = useState(false);
  const [timelineView, setTimelineView] = useState('target');
  const chartRef = useRef(null);

  const isHapax = searchMode === 'hapax';
  const title = isHapax ? 'Shared Rare Words' : 'Shared Rare Pairs';

  const exportCSV = useCallback(() => {
    if (!results || results.length === 0) return;

    const headers = isHapax
      ? ['Lemma', 'Display Form', 'Corpus Frequency', 'Source Occurrences', 'Target Occurrences', 'Source Locations', 'Target Locations']
      : ['Word Pair', 'Rarity %', 'Source Occurrences', 'Target Occurrences', 'Source Locations', 'Target Locations'];

    const rows = results.map(r => {
      const srcLocs = (r.source_locations || []).map(loc => loc.ref).join('; ');
      const tgtLocs = (r.target_locations || []).map(loc => loc.ref).join('; ');
      
      if (isHapax) {
        return [
          r.lemma || '',
          r.display_form || '',
          r.corpus_count || r.corpus_frequency || '',
          r.source_occurrences || 0,
          r.target_occurrences || 0,
          srcLocs,
          tgtLocs
        ];
      } else {
        return [
          r.bigram || `${r.word1} + ${r.word2}` || '',
          r.rarity_percent?.toFixed(1) || '',
          r.source_occurrences || 0,
          r.target_occurrences || 0,
          srcLocs,
          tgtLocs
        ];
      }
    });

    const csv = [headers.join(','), ...rows.map(r => r.map(c => `"${String(c).replace(/"/g, '""')}"`).join(','))].join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `tesserae_${isHapax ? 'rare_words' : 'rare_pairs'}_${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  }, [results, isHapax]);

  const exportChart = () => {
    if (!chartRef.current) return;
    const canvas = chartRef.current.canvas;
    if (!canvas) return;
    
    const link = document.createElement('a');
    link.download = `tesserae_${isHapax ? 'rare_words' : 'rare_pairs'}_timeline_${new Date().toISOString().slice(0, 10)}.png`;
    link.href = canvas.toDataURL('image/png');
    link.click();
  };

  const getTimelineData = useCallback(() => {
    if (!results || results.length === 0) return null;

    const bookData = {};
    const isSourceView = timelineView === 'source';

    results.forEach(r => {
      const locations = isSourceView ? r.source_locations : r.target_locations;
      if (!locations) return;

      locations.forEach(loc => {
        const ref = loc.ref || '';
        const bookMatch = ref.match(/book\s*(\d+)/i) ||
                          ref.match(/(\d+)\.\d+/) ||
                          ref.match(/^([^.]+)/);
        
        const book = bookMatch ? bookMatch[1] : 'Other';
        const bookLabel = isNaN(parseInt(book)) ? book : `Book ${book}`;
        
        if (!bookData[bookLabel]) {
          bookData[bookLabel] = 0;
        }
        bookData[bookLabel]++;
      });
    });

    const sortedBooks = Object.keys(bookData).sort((a, b) => {
      const numA = parseInt(a.replace(/\D/g, '')) || 999;
      const numB = parseInt(b.replace(/\D/g, '')) || 999;
      return numA - numB;
    });

    return {
      labels: sortedBooks,
      datasets: [{
        label: `${isHapax ? 'Rare Words' : 'Rare Pairs'} by Location`,
        data: sortedBooks.map(b => bookData[b]),
        backgroundColor: isHapax ? 'rgba(217, 119, 6, 0.7)' : 'rgba(126, 34, 206, 0.7)',
        borderColor: isHapax ? 'rgb(217, 119, 6)' : 'rgb(126, 34, 206)',
        borderWidth: 1
      }]
    };
  }, [results, timelineView, isHapax]);

  const handleRegisterClick = (result) => {
    if (!onRegister) return;
    
    const firstSrcLoc = result.source_locations?.[0];
    const firstTgtLoc = result.target_locations?.[0];
    
    const formattedResult = {
      source_text_id: sourceText,
      target_text_id: targetText,
      source_locus: firstSrcLoc?.ref || '',
      source_text: firstSrcLoc?.text || (isHapax ? result.lemma : result.bigram),
      source_snippet: firstSrcLoc?.text || '',
      target_locus: firstTgtLoc?.ref || '',
      target_text: firstTgtLoc?.text || (isHapax ? result.lemma : result.bigram),
      target_snippet: firstTgtLoc?.text || '',
      score: result.rarity_percent ? (result.rarity_percent / 10) : (10 - (result.corpus_count || 0)),
      matched_words: isHapax 
        ? [{ lemma: result.lemma, display: result.display_form }]
        : [{ lemma: result.word1 }, { lemma: result.word2 }],
      match_type: isHapax ? 'rare_word' : 'rare_pair'
    };
    
    onRegister(formattedResult);
  };

  const handleCorpusSearchClick = (result) => {
    if (!onCorpusSearch) return;
    
    const searchTerm = isHapax 
      ? (result.lemma || result.display_form)
      : (result.bigram || `${result.word1} ${result.word2}`);
    
    onCorpusSearch(searchTerm);
  };

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center py-12">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-red-700 mb-4"></div>
        <p className="text-gray-600">Searching for {isHapax ? 'rare words' : 'rare pairs'}...</p>
        {elapsedTime > 0 && (
          <p className="text-sm text-gray-500 mt-2">{elapsedTime.toFixed(1)}s</p>
        )}
      </div>
    );
  }

  if (error) {
    return (
      <div className="text-red-600 p-4 bg-red-50 rounded-lg">
        <p className="font-medium">Search Error</p>
        <p className="text-sm mt-1">{error}</p>
      </div>
    );
  }

  if (!results || results.length === 0) {
    return (
      <div className="text-center py-8 text-gray-500">
        No shared {isHapax ? 'rare words' : 'rare pairs'} found between these texts.
      </div>
    );
  }

  const timelineData = getTimelineData();

  return (
    <div className="space-y-4">
      <div className="flex flex-col sm:flex-row sm:justify-between sm:items-center gap-2 mb-4">
        <div>
          <h3 className="text-lg font-semibold text-gray-900">
            {results.length} {title.replace('Shared ', '')} Found
          </h3>
          {elapsedTime > 0 && (
            <p className="text-sm text-gray-500">
              Search completed in {elapsedTime.toFixed(2)}s
            </p>
          )}
        </div>
        
        <div className="flex flex-col sm:flex-row gap-2">
          <div className="flex items-center gap-2">
            <button
              onClick={() => setShowTimeline(!showTimeline)}
              className={`text-xs px-3 py-1.5 rounded whitespace-nowrap ${
                showTimeline 
                  ? 'bg-amber-600 text-white'
                  : 'bg-amber-100 text-amber-700 hover:bg-amber-200'
              }`}
            >
              {showTimeline ? 'Hide Chart' : 'Distribution'}
            </button>
            <button
              onClick={exportCSV}
              className="text-xs bg-amber-600 text-white px-3 py-1.5 rounded hover:bg-amber-700 whitespace-nowrap"
            >
              Export CSV
            </button>
          </div>
        </div>
      </div>

      {showTimeline && timelineData && (
        <div className="bg-white border rounded-lg p-4 mb-4">
          <div className="flex flex-wrap items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <span className="text-sm font-medium text-gray-700">View:</span>
              <button
                onClick={() => setTimelineView('source')}
                className={`text-xs px-3 py-1 rounded ${
                  timelineView === 'source' 
                    ? 'bg-red-700 text-white' 
                    : 'bg-red-100 text-red-600 hover:bg-red-200'
                }`}
              >
                Source
              </button>
              <button
                onClick={() => setTimelineView('target')}
                className={`text-xs px-3 py-1 rounded ${
                  timelineView === 'target' 
                    ? 'bg-amber-600 text-white' 
                    : 'bg-amber-100 text-amber-600 hover:bg-amber-200'
                }`}
              >
                Target
              </button>
            </div>
            <button
              onClick={exportChart}
              className="text-xs text-gray-600 hover:text-gray-900"
              title="Export chart as PNG"
            >
              Export PNG
            </button>
          </div>
          <div style={{ height: '200px' }}>
            <Bar
              ref={chartRef}
              data={timelineData}
              options={{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                  legend: { display: false },
                  title: {
                    display: true,
                    text: `Distribution of ${title.replace('Shared ', '')} by Location`
                  }
                },
                scales: {
                  x: {
                    title: {
                      display: true,
                      text: timelineView === 'source' ? 'Source' : 'Target',
                      font: { size: 12 }
                    }
                  },
                  y: { 
                    beginAtZero: true, 
                    ticks: { stepSize: 1 },
                    title: { display: true, text: isHapax ? 'Rare Words' : 'Rare Pairs', font: { size: 12 } } 
                  }
                }
              }}
            />
          </div>
        </div>
      )}

      <div className="space-y-3">
        {results.slice(0, displayLimit).map((r, i) => {
          // Prefer bigram with display forms, otherwise use surface forms from text when available
          let displayName = r.display_form || r.lemma || r.bigram;
          if (!displayName && r.word1 && r.word2) {
            // Try to get actual words from location text that match the lemmas
            const srcText = r.source_locations?.[0]?.text || '';
            const tgtText = r.target_locations?.[0]?.text || '';
            const allText = (srcText + ' ' + tgtText).toLowerCase();
            
            // Use the lemmas directly but capitalize nicely
            displayName = `${r.word1} + ${r.word2}`;
          }
          displayName = displayGreekWithFinalSigma(displayName || '-');
          
          return (
            <div key={i} className="bg-white border rounded-lg p-4 hover:shadow-md transition-shadow">
              <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-semibold text-lg text-amber-700">
                    {displayName}
                  </span>
                  <span className="text-xs px-2 py-0.5 rounded bg-amber-100 text-amber-700">
                    {r.rarity_percent ? `${r.rarity_percent.toFixed(1)}% rare` : 
                     r.corpus_count ? `${r.corpus_count} in corpus` : isHapax ? 'rare' : ''}
                  </span>
                  <span className="text-sm text-gray-500">
                    Source: {r.source_occurrences || 0} | Target: {r.target_occurrences || 0}
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  {onRegister && (
                    <button
                      onClick={() => onRegister(r)}
                      className="text-xs border border-gray-300 text-gray-600 px-2 py-1 rounded hover:bg-gray-50"
                    >
                      Register
                    </button>
                  )}
                  {onCorpusSearch && (
                    <button
                      onClick={() => handleCorpusSearchClick(r)}
                      className="text-xs border border-amber-300 text-amber-700 px-2 py-1 rounded hover:bg-amber-50"
                    >
                      Corpus
                    </button>
                  )}
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <div className="text-xs text-gray-500 mb-1">Source</div>
                  {r.source_locations && r.source_locations.length > 0 ? (
                    <div className="space-y-2">
                      {r.source_locations.slice(0, 3).map((loc, j) => (
                        <div key={j} className="text-sm">
                          <div className="font-medium text-red-700">{formatLocationRef(loc.ref, formatTextName(sourceText))}</div>
                          {loc.text && <div className="text-gray-700">
                            {highlightMatchedWords(displayGreekWithFinalSigma(loc.text), r.matched_words, r.word1, r.word2)}
                          </div>}
                        </div>
                      ))}
                      {r.source_locations.length > 3 && (
                        <div className="text-xs text-gray-500">+{r.source_locations.length - 3} more</div>
                      )}
                    </div>
                  ) : (
                    <div className="text-sm text-gray-400">No locations</div>
                  )}
                </div>
                <div>
                  <div className="text-xs text-gray-500 mb-1">Target</div>
                  {r.target_locations && r.target_locations.length > 0 ? (
                    <div className="space-y-2">
                      {r.target_locations.slice(0, 3).map((loc, j) => (
                        <div key={j} className="text-sm">
                          <div className="font-medium text-amber-700">{formatLocationRef(loc.ref, formatTextName(targetText))}</div>
                          {loc.text && <div className="text-gray-700">
                            {highlightMatchedWords(displayGreekWithFinalSigma(loc.text), r.matched_words, r.word1, r.word2)}
                          </div>}
                        </div>
                      ))}
                      {r.target_locations.length > 3 && (
                        <div className="text-xs text-gray-500">+{r.target_locations.length - 3} more</div>
                      )}
                    </div>
                  ) : (
                    <div className="text-sm text-gray-400">No locations</div>
                  )}
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {results.length > displayLimit && (
        <button
          onClick={() => setDisplayLimit(prev => prev + 50)}
          className="mt-4 px-4 py-2 text-sm text-amber-700 hover:text-amber-800"
        >
          Show more ({results.length - displayLimit} remaining)
        </button>
      )}
    </div>
  );
};

export default RareResultsDisplay;
