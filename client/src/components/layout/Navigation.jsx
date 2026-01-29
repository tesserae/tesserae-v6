const mainTabs = [
  { code: 'search', label: 'Search' },
  { code: 'browse', label: 'Browse Corpus' },
  { code: 'repository', label: 'Repository' },
  // DISABLED FOR PRODUCTION - Uncomment to restore Visualizations
  // { code: 'visualizations', label: 'Visualize' },
  { code: 'downloads', label: 'Downloads' },
  { code: 'about', label: 'About' },
  { code: 'help', label: 'Help & Support' },
  { code: 'admin', label: 'Admin' }
];

const languageTabs = [
  { code: 'la', label: 'Latin' },
  { code: 'grc', label: 'Greek' },
  { code: 'cross', label: 'Greek↔Latin' },
  { code: 'en', label: 'English' }
];

const Navigation = ({ 
  pageType, 
  setPageType, 
  activeTab, 
  setActiveTab,
  onLanguageReset,
  showDownloads = false,
  setShowDownloads
}) => {
  const handleLanguageClick = (tabCode) => {
    if (activeTab === tabCode && onLanguageReset) {
      onLanguageReset();
    }
    setActiveTab(tabCode);
  };
  return (
    <nav className="bg-gray-50 border-b sticky top-0 z-40">
      <div className="max-w-7xl mx-auto px-3 sm:px-6">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between">
          <div className="flex overflow-x-auto scrollbar-hide -mx-3 px-3 sm:mx-0 sm:px-0">
            {mainTabs.map(tab => (
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
