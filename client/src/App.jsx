import { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { captureUrlOverrides, setProfile, getView } from './collections/collectionsStore';
import { viewById } from './collections/collectionsConfig';
import useCollections from './hooks/useCollections';
import { languageName } from './utils/languageNames';
import { Header, Navigation } from './components/layout';
import { SearchModeToggle, TextSelector, SearchSettings, SearchResults, LineSearch, CrossLingualSearch, WildcardSearch, SavedSearches, CorpusSearchResults, RarePairsSettings, LargeComparisonPanel } from './components/search';
import RareResultsDisplay from './components/search/RareResultsDisplay';
import StartHere from './components/search/StartHere';
import { addressHasQuery, FRONT_DOOR_OPEN_EVENT } from './components/search/frontDoor';
import ScopeBox from './components/common/ScopeBox';
import { Modal, LoadingSpinner, UpdateBanner, RequestDialog } from './components/common';
import { CorpusBrowser, RareWordsExplorer } from './components/corpus';
import { ReaderPage } from './components/reader';
import DocumentView from './components/documents/DocumentView';
import InscriptionsPapyriPage from './components/documents/InscriptionsPapyriPage';
import EventsPage from './components/events/EventsPage';
import { entitiesTrialOn } from './hooks/useEntitiesTrial';
import MentionsPage from './components/mentions/MentionsPage';
import CoinsPage from './components/coins/CoinsPage';
import ObjectsPage from './components/objects/ObjectsPage';
import ThemeSearchPage from './components/passages/ThemeSearchPage';
import AskAWorkPage from './components/ask/AskAWorkPage';
import { Repository } from './components/repository';
import { AdminPanel } from './components/admin';
import RegisterParallelModal, { useRegisterParallel } from './components/register/RegisterParallelModal';
import { useRoute, pageForPath } from './hooks/useRoute';
import { defaultSearchSettings } from './utils/searchDefaults';
import { parseSearchParams, buildShareableUrl } from './utils/searchUrl';
import { useCorpusSearchPanel } from './hooks/useCorpusSearchPanel';
import { useDefaultTexts } from './hooks/useDefaultTexts';
import { useAdminSession } from './hooks/useAdminSession';
import { AboutPage, HelpPage, DownloadsPage, PrivacyPage, ResearchPage, BlogArchivePage, RequestsPage, ScholarshipSourcesPage } from './components/pages';
import TextCredits from './components/about/TextCredits';
import { AssistantDock } from './components/assistant';
import VisualizationsPage from './components/pages/VisualizationsPage';
import { useCorpus, useSearch, DEFAULT_PAGE_SIZE } from './hooks';
import { getSessionValue, setSessionValue } from './utils/storage';
import { startLanguage } from './utils/languagePreference';
import { recordPageView } from './lib/pageViews';
import { fetchLanguages, getJson } from './utils/api';

const textLabel = (info, id) => info?.display_name || info?.name
  || (info?.title ? `${info.author ? `${info.author}, ` : ''}${info.title}` : id);

function App() {
  const [user, setUser] = useState(null);
  // The header's Suggest a change button sends this event; the dialog it
  // opens lives here. The setter it called was lost with the footer on
  // 2026-10-12, so the button did nothing for an afternoon; the linter's
  // no-undef found it.
  const [suggestOpen, setSuggestOpen] = useState(false);
  useEffect(() => {
    const open = () => setSuggestOpen(true);
    window.addEventListener('tesserae:open-suggest', open);
    return () => window.removeEventListener('tesserae:open-suggest', open);
  }, []);
  // Trial switches (?documents=1, ?scholarship=1) are remembered for the
  // rest of the visit in sessionStorage, but LineSearch and ResultsPanel
  // only wrote that key when THEY mounted with the query string still on
  // the address -- so a link that set the flag on some other page (/read,
  // the homepage) lost it the moment the visitor navigated to Line Search
  // or the Reader without carrying the param along. Captured here once, at
  // the app's own first load, the flag holds for the visit regardless of
  // which page set it or which page is opened next.
  useEffect(() => {
    captureUrlOverrides();
    entitiesTrialOn();   // the Mentions trial (?entities=1) is captured the same way
  }, []);
  const { adminSessionActive, adminSessionChecked } = useAdminSession();
  const { pageType, setPageType, setPageTypeWithGuard, goViewHome } = useRoute({ adminSessionChecked, adminSessionActive });
  const { view } = useCollections();
  // When set, HelpPage opens to this section (used by the "use your own AI" flag).
  const [helpSection, setHelpSection] = useState(null);
  // When set alongside helpSection, HelpPage scrolls to this id within it (a
  // result card's InfoBadge "More" link, result card tidy, 2026-10-08).
  const [helpAnchor, setHelpAnchor] = useState(null);
  // When set, AboutPage scrolls to this id (the Cite popup's "How to cite
  // Tesserae" link, crosslingual parity, 2026-10-08).
  const [aboutAnchor, setAboutAnchor] = useState(null);
  // Confirms a copied search link on the button itself, for 2.5 seconds.
  const [shareCopied, setShareCopied] = useState(false);
  const [activeTab, setActiveTab] = useState(() => {
    const params = new URLSearchParams(window.location.search);
    const lang = params.get('lang') || params.get('language');
    const known = ['la', 'grc', 'en', 'cop', 'he', 'fa', 'ur', 'ar', 'cross'];
    if (lang && known.includes(lang)) {
      return lang;
    }
    const sessionLang = getSessionValue('activeTab', '');
    if (sessionLang && known.includes(sessionLang)) {
      return sessionLang;
    }
    // A new visit opens in the reader's chosen start language, or the one they
    // used last (utils/languagePreference.js, kept in this browser only).
    return startLanguage(known) || 'la';
  });
  // The languages this server actually serves (2026-09-06). A preview that
  // holds only some languages reports them, and a tab for a language it
  // cannot serve is swapped for the first it can, instead of hanging on
  // "Loading corpus".
  const [servedLanguages, setServedLanguages] = useState(null);
  useEffect(() => {
    fetchLanguages().then(data => {
      const codes = (data.languages || []).map(l => l.code);
      if (codes.length) setServedLanguages(codes);
    }).catch(() => {});
  }, []);
  useEffect(() => {
    if (!servedLanguages) return;
    if (activeTab !== 'cross' && !servedLanguages.includes(activeTab)) {
      setActiveTab(servedLanguages[0]);
    }
  }, [servedLanguages, activeTab]);
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
  
  const [settings, setSettings] = useState(defaultSearchSettings);
  const [showAdvancedSettings, setShowAdvancedSettings] = useState(false);
  
  // Page size is shared by every result renderer so the choice survives a new
  // search and a switch between parallel and rare-word results. A parallel
  // search sends it as page_size, so the server keeps the full result list and
  // returns one page (backend/result_pages.py). Never persisted to storage.
  const [pageSize, setPageSize] = useState(DEFAULT_PAGE_SIZE);
  // Bumped once per search invocation. Renderers use it to return to page 1,
  // which array length alone cannot detect when two searches return the same count.
  const [searchRunId, setSearchRunId] = useState(0);
  const [rareSearchParams, setRareSearchParams] = useState(null);
  const [sortBy, setSortBy] = useState('score');
  
  const register = useRegisterParallel({ user, activeTab, setPageType });
  const { handleRegister } = register;
  
  const {
    corpusSearchResults, setCorpusSearchResults, corpusSearchLoading, corpusSearchQuery, setCorpusSearchQuery,
    corpusSearchError, corpusSearchElapsed, setCorpusSearchElapsed, showCorpusSearch, setShowCorpusSearch,
    handleCorpusSearch,
  } = useCorpusSearchPanel({ activeTab });
  
  
  
  const { corpus, authors, hierarchy, loading: corpusLoading, error: corpusError, retry: retryCorpus, getTextsForAuthor } = useCorpus(activeTab);
  const {
    results,
    resultSet,
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
    getJson('/api/auth/user')
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


  // First-party page views: one record per page opened, so paths through the
  // site can be followed (admin Analytics tab). Never blocks and never throws.
  useEffect(() => {
    if (pageType === 'admin') return;
    recordPageView({
      path: window.location.pathname + window.location.search,
      page: pageType,
      language: activeTab,
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pageType]);


  // The "Start here" panel on the Search page (first-time visitors, and the
  // header's "Start here" link). The address is read once, at load: a visitor
  // who arrived with a search in it already knows where they are going.
  const [frontDoorSuppressed] = useState(() => addressHasQuery());
  const [frontDoorForced, setFrontDoorForced] = useState(false);
  useEffect(() => {
    const open = () => {
      setFrontDoorForced(true);
      if (pageType !== 'search') setPageTypeWithGuard('search');
    };
    window.addEventListener(FRONT_DOOR_OPEN_EVENT, open);
    return () => window.removeEventListener(FRONT_DOOR_OPEN_EVENT, open);
  }, [pageType, setPageTypeWithGuard]);
  // One of the seven answers: move inside the app, with no page reload.
  const goFrontDoor = useCallback((choice) => {
    setFrontDoorForced(false);
    const url = new URL(choice.href, window.location.origin);
    if (url.pathname === '/') {
      const tab = url.searchParams.get('tab');
      if (activeTab === 'cross') {
        setActiveTab(startLanguage(['la', 'grc', 'en', 'cop', 'he', 'fa', 'ur', 'ar']) || 'la');
      }
      if (tab) setSearchMode(tab);
      return;
    }
    const profile = url.searchParams.get('profile');
    if (profile) setProfile(profile);
    setPageTypeWithGuard(pageForPath(url.pathname));
  }, [activeTab, setPageTypeWithGuard]);

  // Open the Help page at the "Use with your AI" section.
  const openAiHelp = useCallback(() => {
    setHelpSection('ai-guide');
    setPageTypeWithGuard('help');
    window.history.pushState({}, '', '/help');
  }, [setPageTypeWithGuard]);

  // Open the Help page at a given section, optionally scrolled to one of
  // its id anchors (a result card's InfoBadge "More" link, result card
  // tidy, 2026-10-08).
  const openHelpSection = useCallback((section, anchor = null) => {
    setHelpSection(section);
    setHelpAnchor(anchor);
    setPageTypeWithGuard('help');
    window.history.pushState({}, '', '/help');
  }, [setPageTypeWithGuard]);

  // Open the About page scrolled to one of its id anchors (the Cite popup's
  // "How to cite Tesserae" link and the matching Help sentence, crosslingual
  // parity, 2026-10-08).
  const openAboutAnchor = useCallback((anchor) => {
    setAboutAnchor(anchor);
    setPageTypeWithGuard('about');
    window.history.pushState({}, '', '/about');
  }, [setPageTypeWithGuard]);

  // CiteButton and the Help page dispatch this rather than taking a
  // navigation prop, since both are mounted far from this component and a
  // custom event is the existing pattern here for that (see
  // 'open-public-auth-modal').
  useEffect(() => {
    const handleOpenHowToCite = () => openAboutAnchor('how-to-cite');
    window.addEventListener('tesserae:open-how-to-cite', handleOpenHowToCite);
    return () => window.removeEventListener('tesserae:open-how-to-cite', handleOpenHowToCite);
  }, [openAboutAnchor]);

  // The Reader's Scholarship tab dispatches this for the same reason: it is
  // mounted several components below this one, with no onOpenHelp prop
  // threaded down to it (ScholarshipTab fix, 2026-10-08).
  useEffect(() => {
    const handleOpenHelp = (e) => openHelpSection(e.detail?.section, e.detail?.anchor ?? null);
    window.addEventListener('tesserae:open-help', handleOpenHelp);
    return () => window.removeEventListener('tesserae:open-help', handleOpenHelp);
  }, [openHelpSection]);

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
  }, [setPageType]);


  useDefaultTexts({
    activeTab, corpus, corpusLoading, sourceAuthor, sourceText, targetAuthor, targetText, view, clearResults,
    setSourceAuthor, setSourceText, setTargetAuthor, setTargetText,
    setCorpusSearchResults, setCorpusSearchQuery, setCorpusSearchElapsed, setShowCorpusSearch,
  });

  useEffect(() => {
    clearResults();
    setCorpusSearchResults(null);
    setCorpusSearchQuery(null);
    setCorpusSearchElapsed(0);
    setShowCorpusSearch(false);
  }, [searchMode, clearResults,
    setCorpusSearchResults, setCorpusSearchQuery, setCorpusSearchElapsed, setShowCorpusSearch]);

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
    getJson(`/api/check-meter?source=${encodeURIComponent(sourceText)}&target=${encodeURIComponent(targetText)}&language=${activeTab}`)
      .then(data => {
        setSettings(prev => ({ ...prev, use_meter: data.available }));
      })
      .catch(() => {});
  }, [sourceText, targetText, activeTab]);

  // The warning shown before a large comparison: {estimate, params} while open.
  const [largeComparison, setLargeComparison] = useState(null);
  useEffect(() => {
    setLargeComparison(null);
  }, [sourceText, targetText, activeTab, searchMode]);

  const runLargeComparison = useCallback(async () => {
    if (!largeComparison) return;
    const { estimate, params } = largeComparison;
    setLargeComparison(null);
    setSearchRunId(n => n + 1);
    await search({ ...params, page_size: pageSize }, { estimatedSeconds: estimate.estimated_seconds });
  }, [largeComparison, search, pageSize]);

  const chooseBooksInstead = useCallback(() => {
    setLargeComparison(null);
    const first = document.querySelector('[aria-label="Source Work"], [aria-label="Source Text"], [aria-label="Source author"]');
    if (first) first.focus();
  }, []);

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

    // A comparison of two long works runs in parts and takes a long time: ask
    // what it will cost first, and let the reader decide. A failed estimate
    // never blocks the search.
    setLargeComparison(null);
    let estimatedSeconds;
    if (searchMode === 'parallel' && settings.match_type === 'fusion') {
      try {
        const q = new URLSearchParams({
          source: sourceText, target: targetText, language: activeTab,
          source_unit_type: settings.source_unit_type || 'line',
          target_unit_type: settings.target_unit_type || 'line',
        });
        const estimate = await getJson(`/api/fusion-estimate?${q}`);
        if (estimate?.in_parts) {
          setLargeComparison({ estimate, params });
          return;
        }
        estimatedSeconds = estimate?.estimated_seconds;
      } catch {
        estimatedSeconds = undefined;
      }
    }

    setSearchRunId(n => n + 1);

    if (searchMode === 'parallel') {
      await search({ ...params, page_size: pageSize }, { estimatedSeconds });
    } else if (searchMode === 'hapax') {
      setRareSearchParams(params);
      await searchRareWords(params);
    } else if (searchMode === 'bigram') {
      await searchWordPairs(params);
    }
  }, [sourceText, targetText, activeTab, corpus, corpusLoading, settings, searchMode, search, searchRareWords, searchWordPairs, pageSize]);

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
      await search({ ...params, page_size: pageSize });
    }
  }, [sourceText, targetText, activeTab, settings, searchMode, search, pageSize]);





  return (
    <div className="min-h-screen bg-gray-100">
      {/* Above everything, because a page running old code can be wrong in ways
          the reader cannot see. */}
      <UpdateBanner />
      <Header user={user} setUser={setUser} onLogoClick={() => {
        if (appLockedToAdmin) {
          setPageType('admin');
          window.history.pushState({}, '', '/admin');
          return;
        }
        setPageTypeWithGuard('search');
        setActiveTab(startLanguage(['la', 'grc', 'en', 'cop', 'he', 'fa', 'ur', 'ar', 'cross']) || 'la');
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
        onViewChange={goViewHome}
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
      
      <main className={`max-w-7xl mx-auto ${pageType === 'read' ? 'px-2' : 'px-3'} sm:px-6 py-4 sm:py-6`}>
        {appLockedToAdmin ? (
          <AdminPanel />
        ) : (
          <>
        {/* The Start here panel opens on the Intertextual Search page and on
            whichever page is the current view's home (Search One Text in
            Literature since 2026-10-12), so a first visit still sees it. */}
        {(pageType === 'search' || pageType === viewById(getView()).home.page) && (
          <StartHere
            onChoose={goFrontDoor}
            onDismiss={() => setFrontDoorForced(false)}
            forceOpen={frontDoorForced}
            suppressed={frontDoorSuppressed}
          />
        )}
        {pageType === 'search' && activeTab !== 'cross' && (
          <div className="space-y-6">
            <div className="bg-white rounded-lg shadow p-4 sm:p-6">
              <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-6">
                <div className="flex items-center gap-4">
                  <h2 className="text-xl font-semibold text-gray-900">
                    Search {languageName(activeTab)} Texts
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
                        // Confirmed on the button itself. A browser alert stops
                        // the page and has to be dismissed, which is a lot of
                        // ceremony for a copied link (2026-09-08).
                        navigator.clipboard.writeText(url)
                          .then(() => {
                            setShareCopied(true);
                            setTimeout(() => setShareCopied(false), 2500);
                          })
                          .catch(() => {});
                      }}
                      className={`text-sm flex items-center gap-1 ${shareCopied ? 'text-red-700 font-medium' : 'text-gray-500 hover:text-red-600'}`}
                      title="Copy a link that reproduces this search"
                    >
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8.684 13.342C8.886 12.938 9 12.482 9 12c0-.482-.114-.938-.316-1.342m0 2.684a3 3 0 110-2.684m0 2.684l6.632 3.316m-6.632-6l6.632-3.316m0 0a3 3 0 105.367-2.684 3 3 0 00-5.367 2.684zm0 9.316a3 3 0 105.368 2.684 3 3 0 00-5.368-2.684z" />
                      </svg>
                      {shareCopied ? 'Link copied' : 'Share'}
                    </button>
                  )}
                </div>
              </div>

              <div className="mb-6">
                <SearchModeToggle searchMode={searchMode} setSearchMode={setSearchMode} />
                <ScopeBox id={searchMode} className="mt-2" />
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

                  {largeComparison && !searchLoading && (
                    <div className="mt-4">
                      <LargeComparisonPanel
                        sourceName={textLabel(corpus.find(t => t.id === sourceText), sourceText)}
                        targetName={textLabel(corpus.find(t => t.id === targetText), targetText)}
                        estimate={largeComparison.estimate}
                        onRun={runLargeComparison}
                        onChoose={chooseBooksInstead}
                      />
                    </div>
                  )}
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
                    searchParams={searchMode === 'hapax' ? rareSearchParams : null}
                  />
                ) : (
                  <SearchResults
                    results={sortedResults}
                    resultSet={resultSet}
                    loading={searchLoading}
                    error={searchError}
                    pageSize={pageSize}
                    onPageSizeChange={setPageSize}
                    searchRunId={searchRunId}
                    onRegister={handleRegister}
                    onCorpusSearch={handleCorpusSearch}
                    onOpenHelp={openHelpSection}
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
                language={corpusSearchQuery?.language || activeTab}
              />
            )}
          </div>
        )}

        {/* This tab's own showCorpusSearch branch, separate from the one
            inside the `activeTab !== 'cross'` block above: the two
            conditions are mutually exclusive on activeTab, so exactly one
            of the two CorpusSearchResults renders ever mounts, never both
            (crosslingual parity, 2026-10-08). */}
        {pageType === 'search' && activeTab === 'cross' && (
          showCorpusSearch ? (
            <CorpusSearchResults
              results={corpusSearchResults}
              loading={corpusSearchLoading}
              error={corpusSearchError}
              query={corpusSearchQuery}
              elapsedTime={corpusSearchElapsed}
              onBack={() => setShowCorpusSearch(false)}
              language={corpusSearchQuery?.language || activeTab}
            />
          ) : (
            <CrossLingualSearch
              onOpenHelp={openHelpSection}
              onRegister={handleRegister}
              onCorpusSearch={handleCorpusSearch}
            />
          )
        )}

        {pageType === 'theme-search' && <ThemeSearchPage />}
        {pageType === 'ask-a-work' && <AskAWorkPage />}

        {pageType === 'read' && (
          <ReaderPage />
        )}

        {pageType === 'document' && (
          <DocumentView />
        )}

        {pageType === 'inscriptions-papyri' && (
          <InscriptionsPapyriPage setPageType={setPageTypeWithGuard} />
        )}

        {pageType === 'mentions' && (
          <MentionsPage setPageType={setPageTypeWithGuard} />
        )}

        {pageType === 'events' && (
          <EventsPage setPageType={setPageTypeWithGuard} />
        )}

        {pageType === 'coins' && (
          <CoinsPage setPageType={setPageTypeWithGuard} />
        )}

        {pageType === 'objects' && (
          <ObjectsPage setPageType={setPageTypeWithGuard} />
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
            <ScopeBox id="line" className="mb-4" />
            <LineSearch key={activeTab} language={activeTab} />
          </div>
        )}

        {pageType === 'string-search' && (
          <div className="bg-white rounded-lg shadow p-4 sm:p-6">
            <ScopeBox id="string" className="mb-4" />
            <WildcardSearch language={activeTab} />
          </div>
        )}

        {pageType === 'about' && (
          <AboutPage
            onNavigate={setPageTypeWithGuard}
            initialAnchor={aboutAnchor}
            onAnchorConsumed={() => setAboutAnchor(null)}
          />
        )}

        {pageType === 'text-credits' && (
          <TextCredits />
        )}

        {pageType === 'help' && (
          <HelpPage
            initialSection={helpSection}
            initialAnchor={helpAnchor}
            onSectionConsumed={() => { setHelpSection(null); setHelpAnchor(null); }}
          />
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

        {pageType === 'requests' && (
          <RequestsPage />
        )}

        {pageType === 'scholarship-sources' && (
          <ScholarshipSourcesPage />
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

      <RegisterParallelModal register={register} />

      {/* Tessa is mounted ONCE, after the footer. A second copy sat here
          from 2026-08 until 2026-09-21: two docks fetched their own session
          on every page load and shared one sessionStorage key, and the
          floating button was drawn twice on top of itself. */}

      <footer className="bg-gray-100 border-t mt-8 py-4">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 text-center text-sm text-gray-500">
          <p>Tesserae V6</p>
          {/* The requests workflow (2026-10-08) is reached from the header's
              "Suggest a change" button; the list of requests made so far is
              linked from inside that dialog (owner, 2026-10-12: no separate
              link on the page). */}
        </div>
      </footer>

      <RequestDialog isOpen={suggestOpen} onClose={() => setSuggestOpen(false)} type="suggestion" />
      <AssistantDock />
    </div>
  );
}

export default App;
