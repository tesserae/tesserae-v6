import { useState, useEffect, useCallback, useRef } from 'react';
import { Header, Navigation } from './components/layout';
import { SearchModeToggle, TextSelector, SearchSettings, SearchResults, LineSearch, CrossLingualSearch, WildcardSearch, SavedSearches, CorpusSearchResults } from './components/search';
import RareResultsDisplay from './components/search/RareResultsDisplay';
import { Modal, LoadingSpinner } from './components/common';
import { CorpusBrowser, RareWordsExplorer } from './components/corpus';
import { Repository } from './components/repository';
import { AdminPanel } from './components/admin';
import { AboutPage, HelpPage, DownloadsPage, PrivacyPage } from './components/pages';
import VisualizationsPage from './components/pages/VisualizationsPage';
import { useCorpus, useSearch } from './hooks';
import { getSessionValue, setSessionValue } from './utils/storage';

const pathToPageType = {
  '/': 'search',
  '/browse': 'browse',
  '/repository': 'repository',
  '/line-search': 'line-search',
  '/string-search': 'string-search',
  '/visualize': 'visualizations',
  '/downloads': 'downloads',
  '/about': 'about',
  '/help': 'help',
  '/privacy': 'privacy',
  '/admin': 'admin'
};

const pageTypeToPath = {
  'search': '/',
  'browse': '/browse',
  'repository': '/repository',
  'line-search': '/line-search',
  'string-search': '/string-search',
  'visualizations': '/visualize',
  'downloads': '/downloads',
  'about': '/about',
  'help': '/help',
  'privacy': '/privacy',
  'admin': '/admin'
};

const parseSearchParams = () => {
  const params = new URLSearchParams(window.location.search);
  return {
    source: params.get('source') || '',
    target: params.get('target') || '',
    source_author: params.get('source_author') || '',
    target_author: params.get('target_author') || '',
    lang: params.get('lang') || params.get('language') || '',
    tab: params.get('tab') || '',
    match_type: params.get('match_type') || '',
    min_matches: params.get('min_matches') ? parseInt(params.get('min_matches')) : null
  };
};

const buildShareableUrl = (sourceText, targetText, sourceAuthor, targetAuthor, language, settings) => {
  const params = new URLSearchParams();
  if (sourceText) params.set('source', sourceText);
  if (targetText) params.set('target', targetText);
  if (sourceAuthor) params.set('source_author', sourceAuthor);
  if (targetAuthor) params.set('target_author', targetAuthor);
  if (language) params.set('lang', language);
  if (settings.match_type) params.set('match_type', settings.match_type);
  if (settings.min_matches) params.set('min_matches', settings.min_matches);
  return `${window.location.origin}/?${params.toString()}`;
};

function App() {
  const [user, setUser] = useState(null);
  const [pageType, setPageType] = useState(() => {
    const path = window.location.pathname;
    return pathToPageType[path] || 'search';
  });
  const [activeTab, setActiveTab] = useState(() => {
    const params = new URLSearchParams(window.location.search);
    const lang = params.get('lang') || params.get('language');
    if (lang && ['la', 'grc', 'en', 'cross'].includes(lang)) {
      return lang;
    }
    return 'la';
  });
  const [searchMode, setSearchMode] = useState(() => {
    const gotoTab = sessionStorage.getItem('tesserae_goto_tab');
    if (gotoTab && ['parallel', 'line', 'string', 'hapax', 'bigram'].includes(gotoTab)) {
      sessionStorage.removeItem('tesserae_goto_tab');
      return gotoTab;
    }
    const params = new URLSearchParams(window.location.search);
    const tab = params.get('tab');
    if (tab && ['parallel', 'line', 'string', 'hapax', 'bigram'].includes(tab)) {
      return tab;
    }
    return 'parallel';
  });
  const [browseSubTab, setBrowseSubTab] = useState('texts');
  
  const [sourceAuthor, setSourceAuthor] = useState(() => getSessionValue('sourceAuthor', ''));
  const [sourceText, setSourceText] = useState(() => getSessionValue('sourceText', ''));
  const [targetAuthor, setTargetAuthor] = useState(() => getSessionValue('targetAuthor', ''));
  const [targetText, setTargetText] = useState(() => getSessionValue('targetText', ''));
  
  const [settings, setSettings] = useState({
    match_type: 'lemma',
    min_matches: 2,
    stoplist_basis: 'source_target',
    stoplist_size: 0,
    custom_stopwords: '',
    source_unit_type: 'line',
    target_unit_type: 'line',
    max_distance: 999,
    max_results: 0,
    bigram_boost: false
  });
  const [showAdvancedSettings, setShowAdvancedSettings] = useState(false);
  
  const [displayLimit, setDisplayLimit] = useState(50);
  const [sortBy, setSortBy] = useState('score');
  
  const [showRegisterModal, setShowRegisterModal] = useState(false);
  const [registerPending, setRegisterPending] = useState(null);
  const [registerScore, setRegisterScore] = useState(0);
  const [registerNotes, setRegisterNotes] = useState('');
  
  const [corpusSearchResults, setCorpusSearchResults] = useState(null);
  const [corpusSearchLoading, setCorpusSearchLoading] = useState(false);
  const [corpusSearchQuery, setCorpusSearchQuery] = useState(null);
  const [corpusSearchError, setCorpusSearchError] = useState(null);
  const [corpusSearchElapsed, setCorpusSearchElapsed] = useState(0);
  const [showCorpusSearch, setShowCorpusSearch] = useState(false);
  
  const { corpus, authors, hierarchy, loading: corpusLoading, getTextsForAuthor } = useCorpus(activeTab);
  const { 
    results, 
    loading: searchLoading, 
    error: searchError, 
    searchStats,
    progressText: searchProgressText,
    elapsedTime: searchElapsedTime,
    search, 
    searchRareWords,
    searchWordPairs,
    cancel: cancelSearch,
    clearResults 
  } = useSearch();

  useEffect(() => {
    fetch('/api/auth/user')
      .then(res => res.json())
      .then(data => {
        if (data.user) {
          const firstName = data.user.first_name || '';
          const lastName = data.user.last_name || '';
          data.user.name = data.user.orcid_name || `${firstName} ${lastName}`.trim() || 'Account';
        }
        setUser(data.user);
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    const urlParams = parseSearchParams();
    if (urlParams.lang && ['la', 'grc', 'en', 'cross'].includes(urlParams.lang)) {
      setActiveTab(urlParams.lang);
    }
    if (urlParams.tab && ['parallel', 'line', 'string', 'hapax', 'bigram'].includes(urlParams.tab)) {
      setSearchMode(urlParams.tab);
    }
    if (urlParams.source_author) setSourceAuthor(urlParams.source_author);
    if (urlParams.target_author) setTargetAuthor(urlParams.target_author);
    if (urlParams.source) setSourceText(urlParams.source);
    if (urlParams.target) setTargetText(urlParams.target);
    if (urlParams.match_type) {
      setSettings(prev => ({ ...prev, match_type: urlParams.match_type }));
    }
    if (urlParams.min_matches) {
      setSettings(prev => ({ ...prev, min_matches: urlParams.min_matches }));
    }
  }, []);

  useEffect(() => {
    const newPath = pageTypeToPath[pageType] || '/';
    if (window.location.pathname !== newPath) {
      window.history.pushState({}, '', newPath + window.location.search);
    }
  }, [pageType]);

  useEffect(() => {
    const handlePopState = () => {
      const path = window.location.pathname;
      setPageType(pathToPageType[path] || 'search');
    };
    window.addEventListener('popstate', handlePopState);
    return () => window.removeEventListener('popstate', handlePopState);
  }, []);

  // Track previous activeTab and corpus loading state to detect when to apply defaults
  const prevActiveTabRef = useRef(null);
  const corpusLoadedForTabRef = useRef(null);
  
  useEffect(() => {
    const tabChanged = prevActiveTabRef.current !== null && prevActiveTabRef.current !== activeTab;
    prevActiveTabRef.current = activeTab;
    
    // Clear results when tab changes
    if (tabChanged) {
      clearResults();
      setCorpusSearchResults(null);
      setCorpusSearchQuery(null);
      setCorpusSearchElapsed(0);
      setShowCorpusSearch(false);
    }
    
    // Corpus is ready when not loading and has data
    const corpusReady = !corpusLoading && corpus.length > 0;
    const corpusJustLoaded = corpusReady && corpusLoadedForTabRef.current !== activeTab;
    
    if (corpusJustLoaded) {
      corpusLoadedForTabRef.current = activeTab;
    }
    
    // Set defaults when corpus loads for current tab OR when selections are empty
    const shouldSetDefaults = corpusReady && (corpusJustLoaded || !sourceText || !targetText);
    
    if (shouldSetDefaults) {
      let defaultSourceId, defaultTargetId;
      if (activeTab === 'grc') {
        defaultSourceId = 'homer.iliad.tess';
        defaultTargetId = 'apollonius_rhodius.argonautica.tess';
      } else if (activeTab === 'en') {
        defaultSourceId = 'shakespeare.hamlet.tess';
        defaultTargetId = 'cowper.task.tess';
      } else {
        defaultSourceId = 'vergil.aeneid.tess';
        defaultTargetId = 'lucan.bellum_civile.tess';
      }
      
      const defaultSource = corpus.find(t => t.id === defaultSourceId) || corpus[0];
      const defaultTarget = corpus.find(t => t.id === defaultTargetId) || corpus[1] || corpus[0];
      
      if (defaultSource) {
        setSourceAuthor(defaultSource.author_key || defaultSource.author?.toLowerCase().replace(/\s+/g, '_') || '');
        setSourceText(defaultSource.id);
      }
      if (defaultTarget) {
        setTargetAuthor(defaultTarget.author_key || defaultTarget.author?.toLowerCase().replace(/\s+/g, '_') || '');
        setTargetText(defaultTarget.id);
      }
    }
  }, [activeTab, corpus, corpusLoading, sourceText, targetText, clearResults]);

  useEffect(() => {
    clearResults();
    setCorpusSearchResults(null);
    setCorpusSearchQuery(null);
    setCorpusSearchElapsed(0);
    setShowCorpusSearch(false);
  }, [searchMode, clearResults]);

  useEffect(() => {
    setSessionValue('sourceAuthor', sourceAuthor);
  }, [sourceAuthor]);

  useEffect(() => {
    setSessionValue('sourceText', sourceText);
  }, [sourceText]);

  useEffect(() => {
    setSessionValue('targetAuthor', targetAuthor);
  }, [targetAuthor]);

  useEffect(() => {
    setSessionValue('targetText', targetText);
  }, [targetText]);

  const handleSearch = useCallback(async () => {
    if (!sourceText || !targetText) {
      return;
    }

    const params = {
      source: sourceText,
      target: targetText,
      language: activeTab,
      ...settings
    };

    if (searchMode === 'parallel') {
      await search(params);
    } else if (searchMode === 'hapax') {
      await searchRareWords(params);
    } else if (searchMode === 'bigram') {
      await searchWordPairs(params);
    }
  }, [sourceText, targetText, activeTab, settings, searchMode, search, searchRareWords, searchWordPairs]);

  const handleRegister = useCallback((result) => {
    setRegisterPending(result);
    setRegisterScore(0);
    setShowRegisterModal(true);
  }, []);

  const handleCorpusSearch = useCallback(async (result) => {
    let lemmas;
    let queryInfo;
    
    if (typeof result === 'string') {
      lemmas = result.split(/\s*\+\s*|\s+/).filter(Boolean);
      queryInfo = {
        source: { ref: 'Rare Word/Pair Search', text: result },
        target: { ref: '', text: '' },
        lemmas
      };
    } else {
      lemmas = (result.matched_words || []).map(w => 
        typeof w === 'object' ? (w.lemma || w.word || '') : w
      ).filter(Boolean);
      queryInfo = {
        source: { ref: result.source_locus || result.source?.ref, text: result.source_text || result.source?.text },
        target: { ref: result.target_locus || result.target?.ref, text: result.target_text || result.target?.text },
        lemmas
      };
    }
    
    if (lemmas.length < 1) {
      alert('At least 1 word is required for corpus search');
      return;
    }
    
    setCorpusSearchQuery(queryInfo);
    setCorpusSearchResults(null);
    setCorpusSearchError(null);
    setCorpusSearchLoading(true);
    setShowCorpusSearch(true);
    setCorpusSearchElapsed(0);
    
    const startTime = Date.now();
    const timerInterval = setInterval(() => {
      setCorpusSearchElapsed(Math.floor((Date.now() - startTime) / 1000));
    }, 1000);
    
    try {
      const res = await fetch('/api/corpus-search', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          lemmas,
          language: activeTab,
          exclude_texts: [sourceText, targetText].filter(Boolean)
        })
      });
      const data = await res.json();
      clearInterval(timerInterval);
      if (data.error) {
        setCorpusSearchError(data.error);
      } else {
        setCorpusSearchResults(data.results || []);
      }
    } catch (err) {
      clearInterval(timerInterval);
      setCorpusSearchError('Corpus search failed. Please try again.');
    }
    setCorpusSearchLoading(false);
  }, [activeTab, sourceText, targetText]);

  const handleSubmitRegister = useCallback(async () => {
    if (!registerPending) return;
    try {
      const sourceLocus = registerPending.source_locus || registerPending.source?.ref || '';
      const sourceText = registerPending.source_text || registerPending.source_snippet || registerPending.source?.text || '';
      const targetLocus = registerPending.target_locus || registerPending.target?.ref || '';
      const targetText = registerPending.target_text || registerPending.target_snippet || registerPending.target?.text || '';
      const sourceTextId = registerPending.source_text_id || registerPending.source?.text_id || sourceText?.split(' ')[0] || 'unknown';
      const targetTextId = registerPending.target_text_id || registerPending.target?.text_id || targetText?.split(' ')[0] || 'unknown';
      
      const matchedLemmas = (registerPending.matched_words || []).map(w => 
        typeof w === 'object' ? (w.lemma || w.word || '') : w
      ).filter(Boolean);

      const res = await fetch('/api/intertexts', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          source: {
            text_id: sourceTextId,
            reference: sourceLocus,
            snippet: sourceText,
            language: activeTab
          },
          target: {
            text_id: targetTextId,
            reference: targetLocus,
            snippet: targetText,
            language: activeTab
          },
          matched_lemmas: matchedLemmas,
          tesserae_score: registerPending.score || registerPending.overall_score || 0,
          user_score: registerScore,
          notes: registerNotes.trim().slice(0, 500)
        })
      });
      
      if (!res.ok) {
        const err = await res.json();
        alert('Failed to register: ' + (err.error || 'Unknown error'));
        return;
      }
      
      setShowRegisterModal(false);
      setRegisterPending(null);
      setRegisterScore(0);
      setRegisterNotes('');
      setPageType('repository');
      window.history.pushState({}, '', '/repository');
    } catch (err) {
      console.error('Failed to register intertext:', err);
      alert('Failed to register intertext: ' + err.message);
    }
  }, [registerPending, activeTab, registerScore, registerNotes]);


  return (
    <div className="min-h-screen bg-gray-100">
      <Header user={user} setUser={setUser} />
      <Navigation 
        pageType={pageType} 
        setPageType={setPageType}
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        onLanguageReset={() => {
          setSourceAuthor('');
          setSourceText('');
          setTargetAuthor('');
          setTargetText('');
          setSearchMode('parallel');
        }}
      />
      
      <main className="max-w-7xl mx-auto px-3 sm:px-6 py-4 sm:py-6">
        {pageType === 'search' && activeTab !== 'cross' && (
          <div className="space-y-6">
            <div className="bg-white rounded-lg shadow p-4 sm:p-6">
              <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-6">
                <div className="flex items-center gap-4">
                  <h2 className="text-xl font-semibold text-gray-900">
                    Search {activeTab === 'la' ? 'Latin' : activeTab === 'grc' ? 'Greek' : 'English'} Texts
                  </h2>
                  <SavedSearches
                    sourceAuthor={sourceAuthor}
                    sourceText={sourceText}
                    targetAuthor={targetAuthor}
                    targetText={targetText}
                    settings={settings}
                    activeTab={activeTab}
                    onLoad={(search) => {
                      setActiveTab(search.language);
                      setSourceAuthor(search.sourceAuthor);
                      setSourceText(search.sourceText);
                      setTargetAuthor(search.targetAuthor);
                      setTargetText(search.targetText);
                      if (search.settings) setSettings(search.settings);
                    }}
                  />
                  {sourceText && targetText && (
                    <button
                      onClick={() => {
                        const url = buildShareableUrl(sourceText, targetText, sourceAuthor, targetAuthor, activeTab, settings);
                        navigator.clipboard.writeText(url);
                        alert('Search link copied to clipboard!');
                      }}
                      className="text-sm text-gray-500 hover:text-red-600 flex items-center gap-1"
                      title="Copy shareable link"
                    >
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8.684 13.342C8.886 12.938 9 12.482 9 12c0-.482-.114-.938-.316-1.342m0 2.684a3 3 0 110-2.684m0 2.684l6.632 3.316m-6.632-6l6.632-3.316m0 0a3 3 0 105.367-2.684 3 3 0 00-5.367 2.684zm0 9.316a3 3 0 105.368 2.684 3 3 0 00-5.368-2.684z" />
                      </svg>
                      Share
                    </button>
                  )}
                </div>
                <SearchModeToggle searchMode={searchMode} setSearchMode={setSearchMode} />
              </div>

              {searchMode === 'line' ? (
                <LineSearch key={activeTab} language={activeTab} />
              ) : searchMode === 'string' ? (
                <WildcardSearch language={activeTab} />
              ) : corpusLoading ? (
                <LoadingSpinner text="Loading corpus..." />
              ) : (
                <>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-6 mb-6">
                    <TextSelector
                      label="Source"
                      language={activeTab}
                      authors={authors}
                      selectedAuthor={sourceAuthor}
                      setSelectedAuthor={setSourceAuthor}
                      selectedText={sourceText}
                      setSelectedText={setSourceText}
                      hierarchy={hierarchy}
                      fetchTexts={getTextsForAuthor}
                    />
                    <TextSelector
                      label="Target"
                      language={activeTab}
                      authors={authors}
                      selectedAuthor={targetAuthor}
                      setSelectedAuthor={setTargetAuthor}
                      selectedText={targetText}
                      setSelectedText={setTargetText}
                      hierarchy={hierarchy}
                      fetchTexts={getTextsForAuthor}
                    />
                  </div>

                  {searchMode === 'parallel' && (
                    <SearchSettings 
                      settings={settings}
                      setSettings={setSettings}
                      showAdvanced={showAdvancedSettings}
                      setShowAdvanced={setShowAdvancedSettings}
                      language={activeTab}
                    />
                  )}

                  <div className="flex justify-center mt-6">
                    {searchLoading ? (
                      <button
                        onClick={cancelSearch}
                        className="px-6 py-2 bg-gray-100 text-gray-700 border border-gray-300 rounded-lg hover:bg-gray-200"
                      >
                        Cancel Search
                      </button>
                    ) : (
                      <button
                        onClick={handleSearch}
                        disabled={!sourceText || !targetText}
                        className="px-6 py-2 bg-red-700 text-white rounded-lg hover:bg-red-800 disabled:opacity-50 disabled:cursor-not-allowed"
                      >
                        {searchMode === 'parallel' ? 'Find Parallels' : 
                         searchMode === 'hapax' ? 'Find Rare Words' : 
                         'Find Rare Pairs'}
                      </button>
                    )}
                  </div>
                </>
              )}
            </div>

            {(results.length > 0 || searchLoading || searchError) && !showCorpusSearch && (
              <div className="bg-white rounded-lg shadow p-4 sm:p-6">
                {searchMode === 'hapax' || searchMode === 'bigram' ? (
                  <RareResultsDisplay
                    results={results}
                    loading={searchLoading}
                    error={searchError}
                    displayLimit={displayLimit}
                    setDisplayLimit={setDisplayLimit}
                    searchMode={searchMode}
                    sourceText={sourceText}
                    targetText={targetText}
                    onRegister={handleRegister}
                    onCorpusSearch={handleCorpusSearch}
                    elapsedTime={searchElapsedTime}
                  />
                ) : (
                  <SearchResults
                    results={results}
                    loading={searchLoading}
                    error={searchError}
                    displayLimit={displayLimit}
                    setDisplayLimit={setDisplayLimit}
                    onRegister={handleRegister}
                    onCorpusSearch={handleCorpusSearch}
                    sortBy={sortBy}
                    setSortBy={setSortBy}
                    searchStats={searchStats}
                    sourceTextInfo={corpus.find(t => t.id === sourceText)}
                    targetTextInfo={corpus.find(t => t.id === targetText)}
                    elapsedTime={searchElapsedTime}
                    progressText={searchProgressText}
                    matchType={settings.match_type}
                  />
                )}
              </div>
            )}

            {showCorpusSearch && (
              <CorpusSearchResults
                results={corpusSearchResults}
                loading={corpusSearchLoading}
                error={corpusSearchError}
                query={corpusSearchQuery}
                elapsedTime={corpusSearchElapsed}
                onBack={() => setShowCorpusSearch(false)}
              />
            )}
          </div>
        )}

        {pageType === 'search' && activeTab === 'cross' && (
          <CrossLingualSearch />
        )}

        {pageType === 'browse' && (
          <div className="space-y-4">
            <div className="flex gap-2 mb-4">
              <button
                onClick={() => setBrowseSubTab('texts')}
                className={`px-4 py-2 rounded text-sm ${browseSubTab === 'texts' ? 'bg-red-700 text-white' : 'bg-white text-gray-700 hover:bg-gray-100'}`}
              >
                Browse Texts
              </button>
              <button
                onClick={() => setBrowseSubTab('rare')}
                className={`px-4 py-2 rounded text-sm ${browseSubTab === 'rare' ? 'bg-red-700 text-white' : 'bg-white text-gray-700 hover:bg-gray-100'}`}
              >
                Rare Words Explorer
              </button>
            </div>
            <div className="bg-white rounded-lg shadow p-4 sm:p-6">
              {browseSubTab === 'texts' ? (
                <CorpusBrowser />
              ) : (
                <RareWordsExplorer />
              )}
            </div>
          </div>
        )}

        {pageType === 'repository' && (
          <Repository user={user} />
        )}

        {pageType === 'line-search' && (
          <div className="bg-white rounded-lg shadow p-4 sm:p-6">
            <LineSearch key={activeTab} language={activeTab} />
          </div>
        )}

        {pageType === 'string-search' && (
          <div className="bg-white rounded-lg shadow p-4 sm:p-6">
            <WildcardSearch language={activeTab} />
          </div>
        )}

        {pageType === 'about' && (
          <AboutPage />
        )}

        {pageType === 'help' && (
          <HelpPage />
        )}

        {pageType === 'downloads' && (
          <DownloadsPage />
        )}

        {pageType === 'privacy' && (
          <PrivacyPage />
        )}

        {pageType === 'admin' && (
          <AdminPanel />
        )}

        {pageType === 'visualizations' && (
          <VisualizationsPage />
        )}
      </main>

      <Modal
        isOpen={showRegisterModal}
        onClose={() => { setShowRegisterModal(false); setRegisterPending(null); setRegisterNotes(''); }}
        title="Register Intertext"
      >
        {registerPending && (() => {
          const sourceLocus = registerPending.source_locus || registerPending.source?.ref || '';
          const sourceText = registerPending.source_text || registerPending.source_snippet || registerPending.source?.text || '';
          const targetLocus = registerPending.target_locus || registerPending.target?.ref || '';
          const targetText = registerPending.target_text || registerPending.target_snippet || registerPending.target?.text || '';
          return (
          <div className="space-y-4">
            <p className="text-gray-600">
              Register this parallel to the Intertext Repository for future reference and sharing.
            </p>
            <div className="bg-gray-50 p-4 rounded">
              <div className="text-sm text-gray-500 mb-1">Source</div>
              <div className="font-medium text-red-700">{sourceLocus}</div>
              <div className="text-sm text-gray-700 mt-1">{sourceText?.substring(0, 100)}{sourceText?.length > 100 ? '...' : ''}</div>
              <div className="text-sm text-gray-500 mt-3 mb-1">Target</div>
              <div className="font-medium text-amber-600">{targetLocus}</div>
              <div className="text-sm text-gray-700 mt-1">{targetText?.substring(0, 100)}{targetText?.length > 100 ? '...' : ''}</div>
            </div>
            <div className="mt-4">
              <div className="text-sm text-gray-600 mb-2">Rate this parallel (optional):</div>
              <div className="flex gap-1">
                {[1,2,3,4,5].map(star => (
                  <button
                    key={star}
                    type="button"
                    onClick={() => setRegisterScore(star === registerScore ? 0 : star)}
                    className={`text-2xl ${star <= registerScore ? 'text-yellow-500' : 'text-gray-300'} hover:text-yellow-400 transition-colors`}
                  >
                    ★
                  </button>
                ))}
                {registerScore > 0 && (
                  <span className="ml-2 text-sm text-gray-500 self-center">{registerScore}/5</span>
                )}
              </div>
            </div>
            <div className="mt-4">
              <label className="text-sm text-gray-600 mb-2 block">
                Notes (optional, max 500 characters):
              </label>
              <textarea
                value={registerNotes}
                onChange={(e) => setRegisterNotes(e.target.value.slice(0, 500))}
                placeholder="Add scholarly commentary, interpretation, or notes about this parallel..."
                className="w-full px-3 py-2 border border-gray-300 rounded focus:outline-none focus:ring-2 focus:ring-red-500 focus:border-transparent resize-none"
                rows={3}
                maxLength={500}
              />
              <div className="text-xs text-gray-400 text-right mt-1">
                {registerNotes.length}/500
              </div>
            </div>
            <div className="flex gap-3 justify-end">
              <button
                onClick={() => { setShowRegisterModal(false); setRegisterPending(null); setRegisterScore(0); setRegisterNotes(''); }}
                className="px-4 py-2 bg-gray-100 text-gray-700 border border-gray-300 rounded hover:bg-gray-200"
              >
                Cancel
              </button>
              <button
                onClick={handleSubmitRegister}
                className="px-4 py-2 bg-red-700 text-white rounded hover:bg-red-800"
              >
                Register
              </button>
            </div>
          </div>
          );
        })()}
      </Modal>

      <footer className="bg-gray-100 border-t mt-8 py-4">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 text-center text-sm text-gray-500">
          <p>Tesserae V6</p>
        </div>
      </footer>
    </div>
  );
}

export default App;
