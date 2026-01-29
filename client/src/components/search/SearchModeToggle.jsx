const SearchModeToggle = ({ searchMode, setSearchMode }) => {
  return (
    <div className="flex flex-wrap items-center gap-1 bg-gray-100 p-1 rounded-lg">
      <button
        onClick={() => setSearchMode('parallel')}
        className={`px-2 sm:px-3 py-1 sm:py-1.5 text-xs sm:text-sm font-medium rounded ${
          searchMode === 'parallel' 
            ? 'bg-white shadow text-red-700' 
            : 'text-gray-600 hover:text-gray-800'
        }`}
      >
        Phrases
      </button>
      <button
        onClick={() => setSearchMode('line')}
        className={`px-2 sm:px-3 py-1 sm:py-1.5 text-xs sm:text-sm font-medium rounded ${
          searchMode === 'line' 
            ? 'bg-white shadow text-red-700' 
            : 'text-gray-600 hover:text-gray-800'
        }`}
      >
        Lines
      </button>
      <button
        onClick={() => setSearchMode('string')}
        className={`px-2 sm:px-3 py-1 sm:py-1.5 text-xs sm:text-sm font-medium rounded ${
          searchMode === 'string' 
            ? 'bg-white shadow text-blue-700' 
            : 'text-gray-600 hover:text-gray-800'
        }`}
      >
        String Search
      </button>
      <button
        onClick={() => setSearchMode('bigram')}
        className={`px-2 sm:px-3 py-1 sm:py-1.5 text-xs sm:text-sm font-medium rounded ${
          searchMode === 'bigram' 
            ? 'bg-white shadow text-purple-700' 
            : 'text-gray-600 hover:text-gray-800'
        }`}
      >
        Rare Pairs
      </button>
      <button
        onClick={() => setSearchMode('hapax')}
        className={`px-2 sm:px-3 py-1 sm:py-1.5 text-xs sm:text-sm font-medium rounded ${
          searchMode === 'hapax' 
            ? 'bg-white shadow text-amber-700' 
            : 'text-gray-600 hover:text-gray-800'
        }`}
      >
        Rare Words
      </button>
    </div>
  );
};

export default SearchModeToggle;
