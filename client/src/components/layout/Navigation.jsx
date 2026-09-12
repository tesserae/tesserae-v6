import { useState, useEffect, useRef, useCallback } from 'react';

/** Tells a horizontally scrolling strip whether there is more to its right.
 *
 *  The tab strips hide their scrollbar, which looks clean on a laptop where
 *  every tab fits and hides half the site on a phone where three or four do.
 *  This sets data-more on the container; index.css paints a fade while it is
 *  true (2026-09-08). Watches scrolling, resizing and content changes, because
 *  the language row appears and disappears with the page.
 */
function useScrollHint(contentKey) {
  const ref = useRef(null);
  const [more, setMore] = useState(false);
  const measure = useCallback(() => {
    const el = ref.current;
    if (!el) return;
    setMore(el.scrollWidth - el.clientWidth - el.scrollLeft > 4);
  }, []);
  useEffect(() => {
    const el = ref.current;
    if (!el) return undefined;
    // contentKey re-measures when the tabs themselves change: adding a tab
    // changes scrollWidth but not the container's own box, so a ResizeObserver
    // alone would not notice.
    measure();
    el.addEventListener('scroll', measure, { passive: true });
    window.addEventListener('resize', measure);
    const ro = typeof ResizeObserver !== 'undefined' ? new ResizeObserver(measure) : null;
    if (ro) ro.observe(el);
    return () => {
      el.removeEventListener('scroll', measure);
      window.removeEventListener('resize', measure);
      if (ro) ro.disconnect();
    };
  }, [measure, contentKey]);
  return [ref, more];
}

const mainTabs = [
  { code: 'search', label: 'Search' },
  { code: 'read', label: 'Read', beta: true },
  { code: 'theme-search', label: 'Theme Search', beta: true },
  { code: 'browse', label: 'Browse Corpus' },
  { code: 'repository', label: 'Repository' },
  // DISABLED FOR PRODUCTION - Uncomment to restore Visualizations
  // { code: 'visualizations', label: 'Visualize' },
  { code: 'downloads', label: 'Downloads' },
  { code: 'research', label: 'Research' },
  { code: 'about', label: 'About' },
  { code: 'help', label: 'Help & Support' },
  { code: 'admin', label: 'Admin' }
];

const defaultLanguageTabs = [
  { code: 'la', label: 'Latin' },
  { code: 'grc', label: 'Greek' },
  { code: 'en', label: 'English' },
  { code: 'cross', label: 'Cross-Language' }
];

const Navigation = ({
  pageType,
  setPageType,
  activeTab,
  setActiveTab,
  onLanguageReset,
  lockedToAdmin = false,
  onAdminLogout,
  showDownloads = false,
  setShowDownloads
}) => {
  const [languageTabs, setLanguageTabs] = useState(defaultLanguageTabs);
  const [mainRef, mainMore] = useScrollHint(showDownloads);
  const [langRef, langMore] = useScrollHint(languageTabs.length + ':' + pageType);

  useEffect(() => {
    fetch('/api/languages')
      .then(r => r.json())
      .then(data => {
        if (data.languages) {
          const tabs = data.languages.map(l => ({ code: l.code, label: l.label }));
          tabs.push({ code: 'cross', label: 'Cross-Language' });
          setLanguageTabs(tabs);
        }
      })
      .catch(() => {}); // fall back to defaults
  }, []);
  const handleLanguageClick = (tabCode) => {
    if (onLanguageReset) {
      onLanguageReset();
    }
    setActiveTab(tabCode);
  };

  if (lockedToAdmin) {
    return (
      <nav className="bg-gray-50 border-b sticky top-0 z-40">
        <div className="max-w-7xl mx-auto px-3 sm:px-6 py-2">
          <div className="flex items-center justify-between">
            <button
              onClick={() => setPageType('admin')}
              className="px-3 py-2 font-medium text-sm border-b-2 border-red-700 text-red-700"
            >
              Admin Panel
            </button>
            <div className="text-xs text-gray-600 flex items-center gap-1">
              <span>Admin session active. Public tabs are restricted until</span>
              <button
                onClick={onAdminLogout}
                className="text-red-700 hover:text-red-800 underline"
              >
                logout
              </button>
              <span>.</span>
            </div>
          </div>
        </div>
      </nav>
    );
  }

  return (
    <nav className="bg-gray-50 border-b sticky top-0 z-40">
      <div className="max-w-7xl mx-auto px-3 sm:px-6">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between">
          <div
            ref={mainRef}
            data-more={mainMore}
            className="scroll-hint flex overflow-x-auto scrollbar-hide -mx-3 px-3 sm:mx-0 sm:px-0"
          >
            {mainTabs
              .filter(tab => tab.code !== 'admin')
              .map(tab => (
              <button
                key={tab.code}
                onClick={() => setPageType(tab.code)}
                className={`px-2 sm:px-4 py-2 sm:py-3 font-medium text-xs sm:text-sm border-b-2 whitespace-nowrap ${
                  pageType === tab.code 
                    ? 'border-red-700 text-red-700' 
                    : 'border-transparent text-gray-500 hover:text-red-600'
                }`}
              >
                {tab.label}
                {/* Said plainly rather than in a tooltip. The Reader, Theme
                    Search and Tessa are all new and all still changing, and a
                    scholar deciding whether to cite something needs to know
                    that before they rely on it, not afterwards. */}
                {tab.beta && (
                  <span className="ml-1 align-super text-[9px] font-semibold uppercase tracking-wide text-amber-700">
                    beta
                  </span>
                )}
              </button>
            ))}
            {showDownloads && setShowDownloads && (
              <button
                onClick={() => setShowDownloads(true)}
                className={`px-2 sm:px-4 py-2 sm:py-3 font-medium text-xs sm:text-sm border-b-2 whitespace-nowrap hidden sm:block ${
                  pageType === 'downloads' 
                    ? 'border-red-700 text-red-700' 
                    : 'border-transparent text-gray-500 hover:text-red-600'
                }`}
              >
                Downloads
              </button>
            )}
          </div>
        </div>
        
        {pageType === 'search' && (
          <div className="py-2 border-t">
            <div
              ref={langRef}
              data-more={langMore}
              className="scroll-hint flex overflow-x-auto scrollbar-hide -mx-3 px-3 sm:mx-0 sm:px-0"
            >
              {languageTabs.map(tab => (
                <button
                  key={tab.code}
                  onClick={() => handleLanguageClick(tab.code)}
                  className={`px-3 sm:px-4 py-2 text-xs sm:text-sm font-medium rounded-t whitespace-nowrap ${
                    activeTab === tab.code 
                      ? 'bg-white text-red-700 border-t border-l border-r border-gray-200' 
                      : 'text-gray-600 hover:text-red-600'
                  }`}
                >
                  {tab.label}
                </button>
              ))}
            </div>
          </div>
        )}
      </div>
    </nav>
  );
};

export default Navigation;
