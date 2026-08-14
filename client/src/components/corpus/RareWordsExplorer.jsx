import { useState, useEffect, useCallback, useRef } from 'react';
import { LoadingSpinner, Modal } from '../common';
import { getDictionaryUrl } from '../../utils/linkUtils';

function capitalizeWords(text) {
  if (!text) return '';
  return text.split(' ').map(w => w.charAt(0).toUpperCase() + w.slice(1).toLowerCase()).join(' ');
}

function getWorkTitle(firstWork, firstAuthor) {
  if (!firstWork) return '';
  const workLower = firstWork.toLowerCase();
  const authorLower = (firstAuthor || '').toLowerCase();
  
  if (authorLower && workLower.startsWith(authorLower + ' ')) {
    return capitalizeWords(firstWork.slice(authorLower.length + 1));
  }
  return capitalizeWords(firstWork);
}

function extractLineNumber(ref) {
  if (!ref) return '';
  const match = ref.match(/(\d+[\d.]*\d*)$/);
  return match ? match[1] : ref;
}

export default function RareWordsExplorer() {
  const [language, setLanguage] = useState('la');
  const [words, setWords] = useState([]);
  const [totalWords, setTotalWords] = useState(0);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [loadError, setLoadError] = useState('');
  const [maxOccurrences, setMaxOccurrences] = useState(3);
  const [pageSize, setPageSize] = useState(50);
  const [sortBy, setSortBy] = useState('frequency');
  const [sortOrder, setSortOrder] = useState('asc');
  const [expandedWord, setExpandedWord] = useState(null);
  const [expandedDetails, setExpandedDetails] = useState({});
  
  const [viewerOpen, setViewerOpen] = useState(false);
  const [viewerLoading, setViewerLoading] = useState(false);
  const [viewerLines, setViewerLines] = useState([]);
  const [viewerWord, setViewerWord] = useState('');
  const [viewerForms, setViewerForms] = useState([]);
  const [viewerTitle, setViewerTitle] = useState('');
  const [viewerTargetRef, setViewerTargetRef] = useState('');
  const highlightedLineRef = useRef(null);
  const queryVersionRef = useRef(0);

  const openTextViewer = async (textId, word, ref, author, work) => {
    setViewerWord(word);
    setViewerTitle(`${capitalizeWords(author)} - ${getWorkTitle(work, author)}`);
    setViewerTargetRef(ref);
    setViewerOpen(true);
    setViewerLoading(true);
    setViewerForms([word.toLowerCase()]);
    
    try {
      const [linesRes, formsRes] = await Promise.all([
        fetch(`/api/text/${textId}/lines?language=${language}`),
        fetch(`/api/lemma-forms/${encodeURIComponent(word)}?language=${language}`)
      ]);
      
      const linesData = await linesRes.json();
      setViewerLines(linesData.lines || []);
      
      const formsData = await formsRes.json();
      setViewerForms(formsData.forms || [word.toLowerCase()]);
    } catch (err) {
      console.error('Failed to load text:', err);
      setViewerLines([]);
    }
    setViewerLoading(false);
  };

  useEffect(() => {
    if (viewerOpen && !viewerLoading && highlightedLineRef.current) {
      highlightedLineRef.current.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  }, [viewerOpen, viewerLoading, viewerLines]);

  const languageTabs = [
    { code: 'la', label: 'Latin' },
    { code: 'grc', label: 'Greek' },
    { code: 'en', label: 'English' },
    { code: 'cop', label: 'Coptic' }
  ];

  useEffect(() => {
    const controller = new AbortController();
    let cancelled = false;
    const queryVersion = queryVersionRef.current + 1;
    queryVersionRef.current = queryVersion;

    setWords([]);
    setTotalWords(0);
    setLoading(true);
    setLoadingMore(false);
    setLoadError('');
    setExpandedWord(null);
    setExpandedDetails({});
    
    const fetchWords = async () => {
      try {
        const params = new URLSearchParams({
          language,
          max_occurrences: String(maxOccurrences),
          limit: String(pageSize),
          offset: '0',
          sort_by: sortBy,
          sort_order: sortOrder
        });
        const url = `/api/rare-lemmata-full?${params.toString()}`;
        const res = await fetch(url, {
          cache: 'no-store',
          headers: { 'Cache-Control': 'no-cache' },
          signal: controller.signal
        });
        if (!res.ok) throw new Error('Failed to load rare words');
        const data = await res.json();
        if (data.error) throw new Error(data.error);
        
        if (!cancelled && queryVersionRef.current === queryVersion) {
          setWords(data.words || []);
          setTotalWords(data.total || 0);
          setLoading(false);
        }
      } catch (err) {
        if (!cancelled && queryVersionRef.current === queryVersion && err.name !== 'AbortError') {
          console.error('Failed to load rare words:', err);
          setLoadError('Unable to load rare words. Please try again.');
          setLoading(false);
        }
      }
    };
    
    fetchWords();
    
    return () => {
      cancelled = true;
      controller.abort();
    };
  }, [language, maxOccurrences, pageSize, sortBy, sortOrder]);

  const loadMoreWords = async () => {
    if (loadingMore || loading || words.length >= totalWords) return;

    const queryVersion = queryVersionRef.current;
    setLoadingMore(true);
    setLoadError('');
    try {
      const params = new URLSearchParams({
        language,
        max_occurrences: String(maxOccurrences),
        limit: String(pageSize),
        offset: String(words.length),
        sort_by: sortBy,
        sort_order: sortOrder
      });
      const res = await fetch(`/api/rare-lemmata-full?${params.toString()}`, {
        cache: 'no-store',
        headers: { 'Cache-Control': 'no-cache' }
      });
      if (!res.ok) throw new Error('Failed to load more rare words');
      const data = await res.json();
      if (data.error) throw new Error(data.error);
      if (queryVersionRef.current === queryVersion) {
        setWords(prev => [...prev, ...(data.words || [])]);
        setTotalWords(data.total || 0);
      }
    } catch (err) {
      console.error('Failed to load more rare words:', err);
      if (queryVersionRef.current === queryVersion) {
        setLoadError('Unable to load more rare words. Please try again.');
      }
    }
    if (queryVersionRef.current === queryVersion) setLoadingMore(false);
  };

  const toggleWordExpand = async (lemma) => {
    if (expandedWord === lemma) {
      setExpandedWord(null);
      return;
    }
    setExpandedWord(lemma);
    if (!expandedDetails[lemma]) {
      try {
        const res = await fetch(`/api/rare-word-locations/${encodeURIComponent(lemma)}?language=${language}`);
        const data = await res.json();
        setExpandedDetails(prev => ({
          ...prev,
          [lemma]: {
            locations: data.locations || [],
            definition: data.definition,
            count: data.corpus_count
          }
        }));
      } catch (err) {
        console.error('Failed to load word details:', err);
      }
    }
  };

  const handleSort = (field) => {
    if (sortBy === field) {
      setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc');
    } else {
      setSortBy(field);
      setSortOrder('asc');
    }
  };

  const exportCSV = useCallback(() => {
    const params = new URLSearchParams({
      language,
      max_occurrences: String(maxOccurrences),
      sort_by: sortBy,
      sort_order: sortOrder
    });
    const a = document.createElement('a');
    a.href = `/api/rare-lemmata-full/export?${params.toString()}`;
    a.click();
  }, [language, maxOccurrences, sortBy, sortOrder]);

  const getLanguageName = (lang) => {
    const names = { la: 'Latin', grc: 'Greek', en: 'English', cop: 'Coptic' };
    return names[lang] || lang;
  };

  const getDictionaryName = (lang) => {
    if (lang === 'en') return 'Wiktionary';
    if (lang === 'cop') return 'Coptic Dictionary';
    return 'Logeion';
  };

  const SortIcon = ({ field }) => {
    if (sortBy !== field) return <span className="text-gray-300 ml-1">↕</span>;
    return <span className="text-red-600 ml-1">{sortOrder === 'asc' ? '↑' : '↓'}</span>;
  };

  return (
    <div className="space-y-4">
      <div className="flex overflow-x-auto scrollbar-hide border-b mb-4">
        {languageTabs.map(tab => (
          <button
            key={tab.code}
            onClick={() => setLanguage(tab.code)}
            className={`px-4 py-2 text-sm font-medium whitespace-nowrap ${
              language === tab.code 
                ? 'text-red-700 border-b-2 border-red-700' 
                : 'text-gray-600 hover:text-red-600'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      <div className="flex flex-col sm:flex-row gap-4 items-start sm:items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold text-gray-900">
            Rare Words Explorer ({getLanguageName(language)})
          </h2>
          <p className="text-sm text-gray-500 mt-1">
            Find rare vocabulary across the corpus
          </p>
        </div>
        <div className="flex flex-wrap gap-3">
          <select
            value={maxOccurrences}
            onChange={e => setMaxOccurrences(parseInt(e.target.value))}
            className="border rounded px-3 py-2 text-sm"
          >
            <option value="1">Hapax only (1 occurrence)</option>
            <option value="2">Up to 2 occurrences</option>
            <option value="3">Up to 3 occurrences</option>
            <option value="5">Up to 5 occurrences</option>
            <option value="10">Up to 10 occurrences</option>
          </select>
          <select
            value={pageSize}
            onChange={e => setPageSize(parseInt(e.target.value))}
            aria-label="Words at a time"
            className="border rounded px-3 py-2 text-sm"
          >
            <option value="25">25 words at a time</option>
            <option value="50">50 words at a time</option>
            <option value="100">100 words at a time</option>
            <option value="500">500 words at a time</option>
          </select>
          <button
            onClick={exportCSV}
            className="px-3 py-2 bg-gray-100 text-gray-700 border rounded hover:bg-gray-200 text-sm"
          >
            Export CSV
          </button>
        </div>
      </div>

      {loading ? (
        <LoadingSpinner text="Loading rare words..." />
      ) : (
        <div className="bg-white border rounded-lg">
          {loadError && (
            <div className="m-4 rounded border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
              {loadError}
            </div>
          )}
          <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-gray-50">
              <tr>
                <th
                  className="px-2 sm:px-4 py-2 sm:py-3 text-left text-xs sm:text-sm font-medium text-gray-700 cursor-pointer hover:bg-gray-100"
                  onClick={() => handleSort('lemma')}
                >
                  Lemma <SortIcon field="lemma" />
                </th>
                <th
                  className="px-2 sm:px-4 py-2 sm:py-3 text-left text-xs sm:text-sm font-medium text-gray-700 cursor-pointer hover:bg-gray-100 whitespace-nowrap"
                  onClick={() => handleSort('frequency')}
                >
                  <span className="hidden sm:inline">Frequency</span><span className="sm:hidden">Freq</span> <SortIcon field="frequency" />
                </th>
                <th
                  className="px-2 sm:px-4 py-2 sm:py-3 text-left text-xs sm:text-sm font-medium text-gray-700 cursor-pointer hover:bg-gray-100"
                  onClick={() => handleSort('author')}
                >
                  <span className="hidden sm:inline">First Author</span><span className="sm:hidden">Author</span> <SortIcon field="author" />
                </th>
                <th className="px-2 sm:px-4 py-2 sm:py-3 text-left text-xs sm:text-sm font-medium text-gray-700 hidden sm:table-cell">
                  First Work
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {words.map(word => (
                <>
                  <tr
                    key={word.lemma}
                    className={`hover:bg-gray-50 cursor-pointer ${expandedWord === word.lemma ? 'bg-amber-50' : ''}`}
                    onClick={() => toggleWordExpand(word.lemma)}
                  >
                    <td className="px-2 sm:px-4 py-2 sm:py-3 text-xs sm:text-sm font-medium text-amber-700 hover:text-amber-900">
                      <span className="flex items-center gap-1">
                        {word.lemma}
                        <span className="text-gray-400 text-xs">{expandedWord === word.lemma ? '▼' : '▶'}</span>
                        {getDictionaryUrl(word.lemma, language) && (
                          <a
                            href={getDictionaryUrl(word.lemma, language)}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-gray-400 hover:text-amber-600 text-xs ml-1"
                            title={`Look up "${word.lemma}" in ${getDictionaryName(language)}`}
                            onClick={(e) => e.stopPropagation()}
                          >
                            📖
                          </a>
                        )}
                      </span>
                    </td>
                    <td className="px-2 sm:px-4 py-2 sm:py-3 text-xs sm:text-sm text-gray-600">
                      {word.count}
                    </td>
                    <td className="px-2 sm:px-4 py-2 sm:py-3 text-xs sm:text-sm text-gray-600">
                      {capitalizeWords(word.first_author)}
                    </td>
                    <td className="px-2 sm:px-4 py-2 sm:py-3 text-xs sm:text-sm text-gray-600 hidden sm:table-cell">
                      {getWorkTitle(word.first_work, word.first_author)}
                    </td>
                  </tr>
                  {expandedWord === word.lemma && expandedDetails[word.lemma] && (
                    <tr key={`${word.lemma}-details`}>
                      <td colSpan="100" className="px-4 py-3 bg-gray-50">
                        <div className="space-y-2">
                          <div className="flex items-center gap-2">
                            {getDictionaryUrl(word.lemma, language) && (
                              <a
                                href={getDictionaryUrl(word.lemma, language)}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="text-gray-400 hover:text-amber-600 text-sm"
                                title={`Look up "${word.lemma}" in ${getDictionaryName(language)}`}
                              >
                                📖 {getDictionaryName(language)}
                              </a>
                            )}
                          </div>
                          {expandedDetails[word.lemma].definition && (
                            <div className="text-sm">
                              <span className="font-medium">Definition: </span>
                              {expandedDetails[word.lemma].definition}
                            </div>
                          )}
                          <div className="text-sm">
                            <span className="font-medium">Locations: </span>
                            <ul className="mt-1 space-y-1">
                              {expandedDetails[word.lemma].locations.map((loc, i) => (
                                <li key={i} className="text-gray-600 flex items-center gap-2">
                                  <span>{capitalizeWords(loc.author)} - {getWorkTitle(loc.work, loc.author)} {extractLineNumber(loc.ref)}</span>
                                  {loc.text_id && (
                                    <button
                                      className="text-amber-600 hover:text-amber-800 text-xs underline"
                                      onClick={(e) => {
                                        e.stopPropagation();
                                        openTextViewer(loc.text_id, word.lemma, loc.ref, loc.author, loc.work);
                                      }}
                                    >
                                      view in text
                                    </button>
                                  )}
                                </li>
                              ))}
                            </ul>
                          </div>
                        </div>
                      </td>
                    </tr>
                  )}
                </>
              ))}
            </tbody>
          </table>
          </div>
          <div className="px-4 py-3 bg-gray-50 text-sm text-gray-500">
            Showing {words.length} of {totalWords} words
          </div>
          {words.length < totalWords && (
            <div className="px-4 pb-4 bg-gray-50 text-center">
              <button
                onClick={loadMoreWords}
                disabled={loadingMore}
                className="px-3 py-2 bg-white text-amber-700 border border-amber-200 rounded hover:bg-amber-50 text-sm disabled:opacity-50"
              >
                {loadingMore ? 'Loading...' : `Show more (${totalWords - words.length} remaining)`}
              </button>
            </div>
          )}
        </div>
      )}

      <Modal
        isOpen={viewerOpen}
        onClose={() => setViewerOpen(false)}
        title={viewerTitle}
        maxWidth="max-w-4xl"
      >
        {viewerLoading ? (
          <LoadingSpinner text="Loading text..." />
        ) : viewerLines.length === 0 ? (
          <p className="text-gray-500">No lines found in this text.</p>
        ) : (
          <div className="space-y-1 font-mono text-sm">
            {viewerLines.map((line, idx) => {
              const isTargetLine = line.locus === viewerTargetRef || 
                extractLineNumber(line.locus) === extractLineNumber(viewerTargetRef);
              
              const formsPattern = viewerForms.map(f => f.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|');
              const formsRegex = new RegExp(`\\b(${formsPattern})\\b`, 'gi');
              const hasWord = formsRegex.test(line.text);
              
              const highlightText = (text) => {
                const regex = new RegExp(`\\b(${formsPattern})\\b`, 'gi');
                return text.replace(regex, '<mark class="bg-amber-300 px-0.5 rounded font-semibold">$1</mark>');
              };
              
              return (
                <div
                  key={idx}
                  ref={isTargetLine ? highlightedLineRef : null}
                  className={`flex gap-3 py-1 px-2 rounded ${
                    isTargetLine 
                      ? 'bg-amber-100 border-l-4 border-amber-500' 
                      : hasWord 
                        ? 'bg-yellow-50' 
                        : ''
                  }`}
                >
                  <span className="text-gray-400 w-16 flex-shrink-0 text-right">
                    {extractLineNumber(line.locus)}
                  </span>
                  <span 
                    className="text-gray-800"
                    dangerouslySetInnerHTML={{
                      __html: highlightText(line.text)
                    }}
                  />
                </div>
              );
            })}
          </div>
        )}
      </Modal>
    </div>
  );
}
