import { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { Header, Navigation } from './components/layout';
import { SearchModeToggle, TextSelector, SearchSettings, SearchResults, LineSearch, CrossLingualSearch, WildcardSearch, SavedSearches, CorpusSearchResults, RarePairsSettings } from './components/search';
import RareResultsDisplay from './components/search/RareResultsDisplay';
import SearchDescription from './components/search/SearchDescription';
import { Modal, LoadingSpinner } from './components/common';
import { CorpusBrowser, RareWordsExplorer } from './components/corpus';
import { ReaderPage } from './components/reader';
import { Repository } from './components/repository';
import { AdminPanel } from './components/admin';
import { AboutPage, HelpPage, DownloadsPage, PrivacyPage, ResearchPage, BlogArchivePage } from './components/pages';
import TextCredits from './components/about/TextCredits';
import AiAnnouncement from './components/AiAnnouncement';
import VisualizationsPage from './components/pages/VisualizationsPage';
import { useCorpus, useSearch, DEFAULT_PAGE_SIZE } from './hooks';
import { getSessionValue, setSessionValue } from './utils/storage';

const pathToPageType = {
  '/': 'search',
  '/read': 'read',
  '/browse': 'browse',
  '/repository': 'repository',
  '/line-search': 'line-search',
  '/string-search': 'string-search',
  '/visualize': 'visualizations',
  '/downloads': 'downloads',
  '/about': 'about',
  '/help': 'help',
  '/privacy': 'privacy',
  '/research': 'research',
  '/blog-archive': 'blog-archive',
  '/text-credits': 'text-credits',
  '/admin': 'admin'
};

const pageTypeToPath = {
  'search': '/',
  'read': '/read',
  'browse': '/browse',
  'repository': '/repository',
  'line-search': '/line-search',
  'string-search': '/string-search',
  'visualizations': '/visualize',
  'downloads': '/downloads',
  'about': '/about',
  'help': '/help',
  'privacy': '/privacy',
  'research': '/research',
  'text-credits': '/text-credits',
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
  const [adminSessionActive, setAdminSessionActive] = useState(false);
  const [adminSessionChecked, setAdminSessionChecked] = useState(false);
  const [pageType, setPageType] = useState(() => {
    const path = window.location.pathname;
    return pathToPageType[path] || 'search';
  });
  // When set, HelpPage opens to this section (used by the "use your own AI" flag).
  const [helpSection, setHelpSection] = useState(null);
  const [activeTab, setActiveTab] = useState(() => {
    const params = new URLSearchParams(window.location.search);
    const lang = params.get('lang') || params.get('language');
    if (lang && ['la', 'grc', 'en', 'cop', 'he', 'cross'].includes(lang)) {
      return lang;
    }
    const sessionLang = getSessionValue('activeTab', '');
    if (sessionLang && ['la', 'grc', 'en', 'cop', 'he', 'cross'].includes(sessionLang)) {
      return sessionLang;
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
    match_type: 'fusion',
    min_matches: 2,
    stoplist_basis: 'source_target',
    stoplist_size: 0,
    custom_stopwords: '',
    source_unit_type: 'line',
    target_unit_type: 'line',
    max_distance: 999,
    max_results: 0,
    bigram_boost: false,
    stoplist: false,
    use_meter: true,
    exclude_proper_nouns: false,
    freq_basis: 'corpus',
    // Advanced: user-overridden fusion channel weights. Contains only the
    // channels the user has explicitly changed; empty => use tuned defaults.
    channel_weights: {},
    // Advanced: fusion channels the user has turned OFF via the on/off
    // switches. Empty => every channel runs (default). Only sent to the
    // backend when non-empty (see request-building below).
    disabled_channels: []
  });
  const [showAdvancedSettings, setShowAdvancedSettings] = useState(false);
  
  // Page size is shared by every result renderer so the choice survives a new
  // search and a switch between parallel and rare-word results. Purely local:
  // it is never sent to the backend and never persisted to browser storage.
  const [pageSize, setPageSize] = useState(DEFAULT_PAGE_SIZE);
  // Bumped once per search invocation. Renderers use it to return to page 1,
  // which array length alone cannot detect when two searches return the same count.
  const [searchRunId, setSearchRunId] = useState(0);
  const [sortBy, setSortBy] = useState('score');
  
  const [showRegisterModal, setShowRegisterModal] = useState(false);
  const [registerPending, setRegisterPending] = useState(null);
  const [registerScore, setRegisterScore] = useState(0);
  const [registerNotes, setRegisterNotes] = useState('');
  const [registerVisibility, setRegisterVisibility] = useState('private');
  
  const [corpusSearchResults, setCorpusSearchResults] = useState(null);
  const [corpusSearchLoading, setCorpusSearchLoading] = useState(false);
  const [corpusSearchQuery, setCorpusSearchQuery] = useState(null);
  const [corpusSearchError, setCorpusSearchError] = useState(null);
  const [corpusSearchElapsed, setCorpusSearchElapsed] = useState(0);
  const [showCorpusSearch, setShowCorpusSearch] = useState(false);
  
  const { corpus, authors, hierarchy, loading: corpusLoading, error: corpusError, retry: retryCorpus, getTextsForAuthor } = useCorpus(activeTab);
  const {
    results,
    loading: searchLoading,
    error: searchError,
    searchStats,
    progressText: searchProgressText,
    elapsedTime: searchElapsedTime,
    fusionProgress,
    hasSearched,
    isQueued,
    queuedMessage,
    search,
    searchRareWords,
    searchWordPairs,
    cancel: cancelSearch,
    clearResults
  } = useSearch();

  const sortedResults = useMemo(() => (
    Array.isArray(results) ? [...results].sort((a, b) => {
      if (sortBy === 'score') return (b.fused_score ?? b.score ?? b.overall_score ?? 0) - (a.fused_score ?? a.score ?? a.overall_score ?? 0);
      if (sortBy === 'source_locus') return (a.source_locus || a.source?.ref || '').localeCompare(b.source_locus || b.source?.ref || '', undefined, { numeric: true });
      if (sortBy === 'target_locus') return (a.target_locus || a.target?.ref || '').localeCompare(b.target_locus || b.target?.ref || '', undefined, { numeric: true });
      return 0;
    }) : []
  ), [results, sortBy]);

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
    let mounted = true;

    const checkAdminSession = async () => {
      try {
        const res = await fetch('/api/admin/me', { credentials: 'include' });
        if (mounted) {
          setAdminSessionActive(res.ok);
          setAdminSessionChecked(true);
        }
      } catch (_err) {
        if (mounted) {
          setAdminSessionActive(false);
          setAdminSessionChecked(true);
        }
      }
    };

    const handleAdminAuthChanged = () => {
      checkAdminSession();
    };

    checkAdminSession();
    window.addEventListener('focus', handleAdminAuthChanged);
    window.addEventListener('admin-auth-changed', handleAdminAuthChanged);

    return () => {
      mounted = false;
      window.removeEventListener('focus', handleAdminAuthChanged);
      window.removeEventListener('admin-auth-changed', handleAdminAuthChanged);
    };
  }, []);

  useEffect(() => {
    const urlParams = parseSearchParams();
    if (urlParams.lang && ['la', 'grc', 'en', 'cop', 'he', 'cross'].includes(urlParams.lang)) {
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
    if (adminSessionChecked && adminSessionActive && pageType !== 'admin') {
      setPageType('admin');
    }
  }, [adminSessionChecked, adminSessionActive, pageType]);

  useEffect(() => {
    const handlePopState = () => {
      const path = window.location.pathname;
      if (adminSessionChecked && adminSessionActive) {
        setPageType('admin');
      } else {
        setPageType(pathToPageType[path] || 'search');
      }
    };
    window.addEventListener('popstate', handlePopState);
    return () => window.removeEventListener('popstate', handlePopState);
  }, [adminSessionChecked, adminSessionActive]);

  const setPageTypeWithGuard = useCallback((nextPageType) => {
    if (adminSessionChecked && adminSessionActive && nextPageType !== 'admin') {
      setPageType('admin');
      return;
    }
    setPageType(nextPageType);
  }, [adminSessionChecked, adminSessionActive]);

  // Open the Help page at the "Use with your AI" section.
  const openAiHelp = useCallback(() => {
    setHelpSection('ai-guide');
    setPageTypeWithGuard('help');
    window.history.pushState({}, '', '/help');
  }, [setPageTypeWithGuard]);

  const appLockedToAdmin = adminSessionChecked && adminSessionActive;

  const handleAdminSessionLogout = useCallback(async () => {
    try {
      await fetch('/api/admin/logout', {
        method: 'POST',
        credentials: 'include',
      });
    } catch (_err) {}
    window.dispatchEvent(new Event('admin-auth-changed'));
    setPageType('search');
    window.history.pushState({}, '', '/');
  }, []);

  // Track previous activeTab and corpus loading state to detect when to apply defaults
  const prevActiveTabRef = useRef(null);
  const corpusLoadedForTabRef = useRef(null);
  
  useEffect(() => {
    const tabChanged = prevActiveTabRef.current !== null && prevActiveTabRef.current !== activeTab;
    prevActiveTabRef.current = activeTab;
    
    // Clear results AND text selections when tab changes
    if (tabChanged) {
      clearResults();
      setCorpusSearchResults(null);
      setCorpusSearchQuery(null);
      setCorpusSearchElapsed(0);
      setShowCorpusSearch(false);
      // Clear text selections so defaults can be applied for new language
      setSourceAuthor('');
      setSourceText('');
      setTargetAuthor('');
      setTargetText('');
      // Reset corpus tracking so defaults will be applied when new corpus loads
      corpusLoadedForTabRef.current = null;
      // Exit early - let the next render cycle apply defaults with new corpus data
      return;
    }
    
    // Corpus is ready when not loading and has data
    const corpusReady = !corpusLoading && corpus.length > 0;
    const corpusJustLoaded = corpusReady && corpusLoadedForTabRef.current !== activeTab;
    
    if (corpusJustLoaded) {
      corpusLoadedForTabRef.current = activeTab;
    }
    
    // Preserve transferred selections from Browse if they exist in this corpus.
    const sourceExists = Boolean(sourceText) && corpus.some(t => t.id === sourceText);
    const targetExists = Boolean(targetText) && corpus.some(t => t.id === targetText);
    const hasValidSelection = sourceExists && targetExists;

    // Set defaults only when we do not already have valid selections.
    const shouldSetDefaults = corpusReady && !hasValidSelection && (corpusJustLoaded || (!sourceAuthor && !sourceText && !targetAuthor && !targetText));
    
    if (shouldSetDefaults) {
      let defaultSourceId, defaultTargetId;
      if (activeTab === 'grc') {
        defaultSourceId = 'homer.iliad.part.1.tess';
        defaultTargetId = 'apollonius_rhodius.argonautica.part.1.tess';
      } else if (activeTab === 'en') {
        defaultSourceId = 'milton.paradise_lost.part.1.tess';
        defaultTargetId = 'keats.hyperion.tess';
      } else if (activeTab === 'cop') {
        defaultSourceId = 'sahidic.bible.tess';
        defaultTargetId = 'shenoute.abraham.tess';
      } else if (activeTab === 'he') {
        defaultSourceId = 'hebrew_bible.ruth.tess';
        defaultTargetId = 'hebrew_bible.1_samuel.tess';
      } else {
        defaultSourceId = 'vergil.aeneid.part.1.tess';
        defaultTargetId = 'lucan.bellum_civile.part.1.tess';
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

  // Auto-enable meter when both texts are poetry, auto-disable when not
  useEffect(() => {
    if (!sourceText || !targetText) return;
    fetch(`/api/check-meter?source=${encodeURIComponent(sourceText)}&target=${encodeURIComponent(targetText)}&language=${activeTab}`)
      .then(res => res.json())
      .then(data => {
        setSettings(prev => ({ ...prev, use_meter: data.available }));
      })
      .catch(() => {});
  }, [sourceText, targetText, activeTab]);

  const handleSearch = useCallback(async () => {
    if (!sourceText || !targetText) {
      return;
    }

    // Guard: ensure selected texts belong to the current language corpus.
    // Prevents stale text IDs from being sent after tab switches or during corpus loading.
    if (corpusLoading) {
      return;
    }

    if (corpus.length > 0) {
      const sourceValid = corpus.some(t => t.id === sourceText);
      const targetValid = corpus.some(t => t.id === targetText);
      if (!sourceValid || !targetValid) {
        setSourceText('');
        setTargetText('');
        return;
      }
    }

    setSearchRunId(n => n + 1);

    const params = {
      source: sourceText,
      target: targetText,
      language: activeTab,
      ...settings
    };
    // Only send disabled_channels when the user has actually turned a channel
    // off, so a default search's request body is unchanged from today.
    if (!params.disabled_channels || params.disabled_channels.length === 0) {
      delete params.disabled_channels;
    }

    if (searchMode === 'parallel') {
      await search(params);
    } else if (searchMode === 'hapax') {
      await searchRareWords(params);
    } else if (searchMode === 'bigram') {
      await searchWordPairs(params);
    }
  }, [sourceText, targetText, activeTab, corpus, corpusLoading, settings, searchMode, search, searchRareWords, searchWordPairs]);

  // Deep link: /?source=<id>&target=<id>&lang=<lang> — once the corpus for the
  // URL's language has loaded, fill both pickers (resolving each text's author,
  // which the URL doesn't carry) and run the comparison, so an agent's web_url
  // lands on results instead of a blank form. The pair an agent just ran is
  // cached, so this returns immediately. Runs once.
  const deepLinkHandledRef = useRef(false);
  const [deepLinkRun, setDeepLinkRun] = useState(false);
  useEffect(() => {
    if (deepLinkHandledRef.current) return;
    const p = parseSearchParams();
    if (!p.source || !p.target) { deepLinkHandledRef.current = true; return; }
    if (corpusLoading || !corpus || corpus.length === 0) return;   // wait for the corpus
    const src = corpus.find(t => t.id === p.source);
    const tgt = corpus.find(t => t.id === p.target);
    if (!src || !tgt) return;   // ids not in this corpus yet; wait (or never, if wrong)
    deepLinkHandledRef.current = true;
    setSourceAuthor(src.author_key || src.author?.toLowerCase().replace(/\s+/g, '_') || '');
    setSourceText(src.id);
    setTargetAuthor(tgt.author_key || tgt.author?.toLowerCase().replace(/\s+/g, '_') || '');
    setTargetText(tgt.id);
    setSearchMode('parallel');
    setDeepLinkRun(true);
  }, [corpus, corpusLoading]);

  useEffect(() => {
    if (deepLinkRun && sourceText && targetText && !corpusLoading) {
      setDeepLinkRun(false);
      handleSearch();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [deepLinkRun, sourceText, targetText, corpusLoading]);

  const handleRerunFresh = useCallback(async () => {
    if (!sourceText || !targetText) return;
    setSearchRunId(n => n + 1);
    const params = {
      source: sourceText,
      target: targetText,
      language: activeTab,
      ...settings,
      skip_cache: true,
    };
    if (!params.disabled_channels || params.disabled_channels.length === 0) {
      delete params.disabled_channels;
    }
    if (searchMode === 'parallel') {
      await search(params);
    }
  }, [sourceText, targetText, activeTab, settings, searchMode, search]);

  const handleRegister = useCallback((result) => {
    if (!user) {
      window.dispatchEvent(new CustomEvent('open-public-auth-modal', {
        detail: {
          mode: 'login',
          message: 'Need to sign in to add to repository',
        }
      }));
      return;
    }
    setRegisterPending(result);
    setRegisterScore(0);
    setRegisterVisibility('private');
    setShowRegisterModal(true);
  }, [user]);

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
      // Prefer the clean matched_lemmas list (real content words, markup and
      // function words removed). Fall back to parsing matched_words for older
      // results that predate the field.
      lemmas = (Array.isArray(result.matched_lemmas) && result.matched_lemmas.length)
        ? result.matched_lemmas.slice()
        : (result.matched_words || []).map(w =>
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
    if (!Number.isInteger(registerScore) || registerScore < 1 || registerScore > 5) {
      alert('Please select a star rating before saving.');
      return;
    }
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

      const res = await fetch('/api/intertexts/my', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          source: {
            text_id: sourceTextId,
            author: registerPending.source_author || registerPending.source?.author || '',
            work: registerPending.source_work || registerPending.source?.work || '',
            reference: sourceLocus,
            snippet: sourceText,
            language: activeTab
          },
          target: {
            text_id: targetTextId,
            author: registerPending.target_author || registerPending.target?.author || '',
            work: registerPending.target_work || registerPending.target?.work || '',
            reference: targetLocus,
            snippet: targetText,
            language: activeTab
          },
          matched_lemmas: matchedLemmas,
          tesserae_score: registerPending.score || registerPending.overall_score || 0,
          intertext_score: registerScore,
          notes: registerNotes.trim().slice(0, 500),
          share_to_public: registerVisibility === 'public',
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
      setRegisterVisibility('private');
      setPageType('repository');
      window.history.pushState({}, '', '/repository');
    } catch (err) {
      console.error('Failed to register intertext:', err);
      alert('Failed to register intertext: ' + err.message);
    }
  }, [registerPending, activeTab, registerScore, registerNotes, registerVisibility]);


  return (
    <div className="min-h-screen bg-gray-100">
      <Header user={user} setUser={setUser} onLogoClick={() => {
        if (appLockedToAdmin) {
          setPageType('admin');
          window.history.pushState({}, '', '/admin');
          return;
        }
        setPageTypeWithGuard('search');
        setActiveTab('la');
        setSourceAuthor('');
        setSourceText('');
        setTargetAuthor('');
        setTargetText('');
        setSearchMode('parallel');
        clearResults();
        setShowCorpusSearch(false);
        window.history.pushState({}, '', '/');
      }} />
      <Navigation 
        pageType={appLockedToAdmin ? 'admin' : pageType}
        setPageType={setPageTypeWithGuard}
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        lockedToAdmin={appLockedToAdmin}
        onAdminLogout={handleAdminSessionLogout}
        onLanguageReset={() => {
          setSourceAuthor('');
          setSourceText('');
          setTargetAuthor('');
          setTargetText('');
          setSearchMode('parallel');
          clearResults();
          setShowCorpusSearch(false);
        }}
      />
      
      <main className="max-w-7xl mx-auto px-3 sm:px-6 py-4 sm:py-6">
        {appLockedToAdmin ? (
          <AdminPanel />
        ) : (
          <>
        {pageType !== 'help' && <AiAnnouncement onOpen={openAiHelp} />}
        {pageType === 'search' && activeTab !== 'cross' && (
          <div className="space-y-6">
            <div className="bg-white rounded-lg shadow p-4 sm:p-6">
              <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-6">
                <div className="flex items-center gap-4">
                  <h2 className="text-xl font-semibold text-gray-900">
                    Search {activeTab === 'la' ? 'Latin' : activeTab === 'grc' ? 'Greek' : activeTab === 'cop' ? 'Coptic' : activeTab === 'he' ? 'Hebrew' : 'English'} Texts
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
              </div>

              <div className="mb-6">
                <SearchModeToggle searchMode={searchMode} setSearchMode={setSearchMode} />
                <SearchDescription mode={searchMode} className="mt-2 px-1" />
              </div>

              {searchMode === 'line' ? (
                <LineSearch key={activeTab} language={activeTab} />
              ) : searchMode === 'string' ? (
                <WildcardSearch language={activeTab} />
              ) : corpusError ? (
                <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-center">
                  <p className="text-red-700 mb-2">Failed to load corpus data: {corpusError}</p>
                  <button
                    onClick={retryCorpus}
                    className="px-4 py-2 bg-red-700 text-white rounded hover:bg-red-800 text-sm"
                  >
                    Retry
                  </button>
                </div>
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

                  {(searchMode === 'bigram' || searchMode === 'hapax') && (
                    <RarePairsSettings
                      settings={settings}
                      setSettings={setSettings}
                      searchMode={searchMode}
                      language={activeTab}
                    />
                  )}

                  <div className="flex flex-col items-center mt-6 gap-1">
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
                    {!searchLoading && (!sourceText || !targetText) && (
                      <p className="text-sm text-amber-700">Please select both source and target texts</p>
                    )}
                  </div>
                </>
              )}
            </div>

            {(results.length > 0 || searchLoading || searchError || hasSearched) && !showCorpusSearch && (
              <div className="bg-white rounded-lg shadow p-4 sm:p-6">
                {searchMode === 'hapax' || searchMode === 'bigram' ? (
                  <RareResultsDisplay
                    results={results}
                    loading={searchLoading}
                    error={searchError}
                    pageSize={pageSize}
                    onPageSizeChange={setPageSize}
                    searchRunId={searchRunId}
                    searchMode={searchMode}
                    sourceText={sourceText}
                    targetText={targetText}
                    onRegister={handleRegister}
                    onCorpusSearch={handleCorpusSearch}
                    language={activeTab}
                    elapsedTime={searchElapsedTime}
                  />
                ) : (
                  <SearchResults
                    results={sortedResults}
                    loading={searchLoading}
                    error={searchError}
                    pageSize={pageSize}
                    onPageSizeChange={setPageSize}
                    searchRunId={searchRunId}
                    onRegister={handleRegister}
                    onCorpusSearch={handleCorpusSearch}
                    onRerunFresh={handleRerunFresh}
                    sortBy={sortBy}
                    setSortBy={setSortBy}
                    searchStats={searchStats}
                    language={activeTab}
                    sourceTextInfo={corpus.find(t => t.id === sourceText)}
                    targetTextInfo={corpus.find(t => t.id === targetText)}
                    elapsedTime={searchElapsedTime}
                    progressText={searchProgressText}
                    matchType={settings.match_type}
                    fusionProgress={fusionProgress}
                    isQueued={isQueued}
                    queuedMessage={queuedMessage}
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
                language={activeTab}
              />
            )}
          </div>
        )}

        {pageType === 'search' && activeTab === 'cross' && (
          <div className="space-y-3">
            <SearchDescription mode="cross" className="px-1" />
            <CrossLingualSearch />
          </div>
        )}

        {pageType === 'read' && (
          <ReaderPage />
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
            <SearchDescription mode="line" className="mb-4" />
            <LineSearch key={activeTab} language={activeTab} />
          </div>
        )}

        {pageType === 'string-search' && (
          <div className="bg-white rounded-lg shadow p-4 sm:p-6">
            <SearchDescription mode="string" className="mb-4" />
            <WildcardSearch language={activeTab} />
          </div>
        )}

        {pageType === 'about' && (
          <AboutPage onNavigate={setPageTypeWithGuard} />
        )}

        {pageType === 'text-credits' && (
          <TextCredits />
        )}

        {pageType === 'help' && (
          <HelpPage initialSection={helpSection} onSectionConsumed={() => setHelpSection(null)} />
        )}

        {pageType === 'downloads' && (
          <DownloadsPage />
        )}

        {pageType === 'privacy' && (
          <PrivacyPage />
        )}

        {pageType === 'research' && (
          <ResearchPage setPageType={setPageTypeWithGuard} />
        )}

        {pageType === 'blog-archive' && (
          <BlogArchivePage setPageType={setPageTypeWithGuard} />
        )}

        {pageType === 'admin' && (
          <AdminPanel />
        )}

        {pageType === 'visualizations' && (
          <VisualizationsPage />
        )}

          </>
        )}
      </main>

      <Modal
        isOpen={showRegisterModal}
        onClose={() => {
          setShowRegisterModal(false);
          setRegisterPending(null);
          setRegisterScore(0);
          setRegisterNotes('');
          setRegisterVisibility('private');
        }}
        title="Save Parallel"
      >
        {registerPending && (() => {
          const sourceLocus = registerPending.source_locus || registerPending.source?.ref || '';
          const sourceText = registerPending.source_text || registerPending.source_snippet || registerPending.source?.text || '';
          const targetLocus = registerPending.target_locus || registerPending.target?.ref || '';
          const targetText = registerPending.target_text || registerPending.target_snippet || registerPending.target?.text || '';
          return (
          <div className="space-y-4">
            <p className="text-gray-600">
              Save this parallel to your repository, with the option to keep it private or make it public.
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
              <div className="text-sm text-gray-600 mb-2">Visibility:</div>
              <div className="inline-flex rounded-lg border border-gray-200 bg-gray-50 p-1">
                <button
                  type="button"
                  onClick={() => setRegisterVisibility('private')}
                  className={`px-3 py-1.5 text-sm rounded ${
                    registerVisibility === 'private'
                      ? 'bg-white text-gray-900 shadow-sm'
                      : 'text-gray-600 hover:text-gray-800'
                  }`}
                >
                  Private
                </button>
                <button
                  type="button"
                  onClick={() => setRegisterVisibility('public')}
                  className={`px-3 py-1.5 text-sm rounded ${
                    registerVisibility === 'public'
                      ? 'bg-white text-red-700 shadow-sm'
                      : 'text-gray-600 hover:text-gray-800'
                  }`}
                >
                  Make Public
                </button>
              </div>
              <p className="text-xs text-gray-500 mt-2">
                {registerVisibility === 'public'
                  ? 'This parallel will appear in the public repository and stay in your personal repository.'
                  : 'This parallel will only appear in your personal repository.'}
              </p>
            </div>
            <div className="mt-4">
              <div className="text-sm text-gray-600 mb-2">Rate this parallel:</div>
              <div className="flex gap-1">
                {[1,2,3,4,5].map(star => (
                  <button
                    key={star}
                    type="button"
                    onClick={() => setRegisterScore(star)}
                    className={`text-2xl ${star <= registerScore ? 'text-yellow-500' : 'text-gray-300'} hover:text-yellow-400 transition-colors`}
                  >
                    ★
                  </button>
                ))}
                <span className="ml-2 text-sm text-gray-500 self-center">
                  {registerScore > 0 ? `${registerScore}/5` : 'Required'}
                </span>
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
                onClick={() => {
                  setShowRegisterModal(false);
                  setRegisterPending(null);
                  setRegisterScore(0);
                  setRegisterNotes('');
                  setRegisterVisibility('private');
                }}
                className="px-4 py-2 bg-gray-100 text-gray-700 border border-gray-300 rounded hover:bg-gray-200"
              >
                Cancel
              </button>
              <button
                onClick={handleSubmitRegister}
                disabled={registerScore < 1}
                className="px-4 py-2 bg-red-700 text-white rounded hover:bg-red-800 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Save Parallel
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
