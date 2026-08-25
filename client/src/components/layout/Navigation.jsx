import { useState, useEffect } from 'react';

const mainTabs = [
  { code: 'search', label: 'Search' },
  { code: 'read', label: 'Read' },
  { code: 'theme-search', label: 'Theme Search' },
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
          <div className="flex overflow-x-auto scrollbar-hide -mx-3 px-3 sm:mx-0 sm:px-0">
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
            <div className="flex overflow-x-auto scrollbar-hide -mx-3 px-3 sm:mx-0 sm:px-0">
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
