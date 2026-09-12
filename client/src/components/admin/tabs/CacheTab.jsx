import { useState } from 'react';
import { LANG_NAMES, CACHE_IMPACT_INFO } from '../adminConstants';

export default function CacheTab({ authHeaders, cacheInfo, bigramStats, onRefresh, onBigramStatsUpdate }) {
  const [confirmModal, setConfirmModal] = useState(null);
  const [clearingCache, setClearingCache] = useState(null);
  const [cacheError, setCacheError] = useState(null);
  const [buildingBigram, setBuildingBigram] = useState(null);
  const [bigramError, setBigramError] = useState(null);
  const [bigramSuccess, setBigramSuccess] = useState(null);

  const showCacheConfirmation = (cacheType) => {
    const info = CACHE_IMPACT_INFO[cacheType];
    if (!info) return;

    const entryCount = cacheType === 'search'
      ? cacheInfo?.search_cache_size
      : cacheType === 'lemma'
        ? cacheInfo?.lemma_cache_size
        : cacheInfo?.frequency_cache_size;

    setCacheError(null);
    setConfirmModal({
      cacheType,
      ...info,
      entryCount: entryCount || 0
    });
  };

  const clearCache = async (cacheType) => {
    setClearingCache(cacheType);
    setCacheError(null);
    try {
      let endpoint;
      switch (cacheType) {
        case 'search':
          endpoint = '/api/admin/search-cache/clear';
          break;
        case 'lemma':
          endpoint = '/api/admin/lemma-cache/clear';
          break;
        case 'frequency':
          endpoint = '/api/admin/frequency-cache/clear';
          break;
        default:
          endpoint = '/api/admin/lemma-cache/clear';
      }

      const response = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeaders },
        body: JSON.stringify({})
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.error || `Failed to clear ${cacheType} cache`);
      }

      await onRefresh();
      setConfirmModal(null);
    } catch (err) {
      console.error('Failed to clear cache:', err);
      setCacheError(`Failed to clear ${cacheType} cache: ${err.message}`);
    }
    setClearingCache(null);
  };

  const recalculateFrequencies = async () => {
    try {
      await fetch('/api/frequencies/recalculate', {
        method: 'POST',
        headers: authHeaders
      });
      alert('Frequency recalculation started');
    } catch (err) {
      console.error('Failed to recalculate frequencies:', err);
    }
  };

  const buildBigramIndex = async (language) => {
    setBuildingBigram(language);
    setBigramError(null);
    setBigramSuccess(null);
    try {
      const res = await fetch('/api/admin/bigram-cache/build', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeaders },
        body: JSON.stringify({ language })
      });
      const data = await res.json();
      if (res.ok) {
        setBigramSuccess(`${LANG_NAMES[language]} bigram index built: ${data.unique_bigrams?.toLocaleString() || 0} unique pairs`);
        const bigramRes = await fetch('/api/admin/bigram-cache/stats', { headers: authHeaders });
        if (bigramRes.ok) {
          onBigramStatsUpdate(await bigramRes.json());
        }
      } else {
        setBigramError(data.error || 'Failed to build bigram index');
      }
    } catch (err) {
      console.error('Failed to build bigram index:', err);
      setBigramError('Failed to build bigram index: ' + err.message);
    }
    setBuildingBigram(null);
  };

  return (
    <>
      <div className="space-y-4">
        <h3 className="font-medium text-gray-900">Cache Management</h3>
        <p className="text-sm text-gray-500">
          Click "Clear" to see what will be affected before confirming.
        </p>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="bg-amber-50 border border-amber-200 p-4 rounded">
            <div className="flex items-center gap-2 mb-1">
              <span className="text-sm text-gray-600">Search Cache</span>
              <span className="text-xs px-1.5 py-0.5 bg-amber-100 text-amber-700 rounded">Low Risk</span>
            </div>
            <div className="text-2xl font-bold text-gray-900">
              {cacheInfo?.search_cache_size || 0} entries
            </div>
            <p className="text-xs text-gray-500 mt-1 mb-2">Cached search results</p>
            <button
              onClick={() => showCacheConfirmation('search')}
              className="text-sm text-red-600 hover:text-red-800 font-medium"
            >
              Clear...
            </button>
          </div>
          <div className="bg-red-50 border border-red-200 p-4 rounded">
            <div className="flex items-center gap-2 mb-1">
              <span className="text-sm text-gray-600">Lemma Cache</span>
              <span className="text-xs px-1.5 py-0.5 bg-red-100 text-red-700 rounded">High Risk</span>
            </div>
            <div className="text-2xl font-bold text-gray-900">
              {cacheInfo?.lemma_cache_size || 0} entries
            </div>
            <p className="text-xs text-gray-500 mt-1 mb-2">Lemmatized text data</p>
            <button
              onClick={() => showCacheConfirmation('lemma')}
              className="text-sm text-red-600 hover:text-red-800 font-medium"
            >
              Clear...
            </button>
          </div>
          <div className="bg-amber-50 border border-amber-200 p-4 rounded">
            <div className="flex items-center gap-2 mb-1">
              <span className="text-sm text-gray-600">Frequency Cache</span>
              <span className="text-xs px-1.5 py-0.5 bg-amber-100 text-amber-700 rounded">Medium Risk</span>
            </div>
            <div className="text-2xl font-bold text-gray-900">
              {cacheInfo?.frequency_cache_size || 0} entries
            </div>
            <p className="text-xs text-gray-500 mt-1 mb-2">Word frequency data</p>
            <button
              onClick={() => showCacheConfirmation('frequency')}
              className="text-sm text-red-600 hover:text-red-800 font-medium"
            >
              Clear...
            </button>
          </div>
        </div>
        <div className="pt-4">
          <button
            onClick={recalculateFrequencies}
            className="px-4 py-2 bg-amber-100 text-amber-700 rounded hover:bg-amber-200"
          >
            Recalculate Corpus Frequencies
          </button>
        </div>

        <div className="pt-6 border-t mt-6">
          <h4 className="font-medium text-gray-900 mb-2">Bigram Index (for Rare Pairs Search)</h4>
          <p className="text-sm text-gray-500 mb-4">
            Build bigram indexes to enable the Rare Pairs search feature. This may take several minutes per language.
          </p>
          {bigramError && (
            <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded text-red-700 text-sm">
              {bigramError}
            </div>
          )}
          {bigramSuccess && (
            <div className="mb-4 p-3 bg-amber-50 border border-amber-200 rounded text-amber-700 text-sm">
              {bigramSuccess}
            </div>
          )}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {['la', 'grc', 'en'].map(lang => (
              <div key={lang} className={`p-4 rounded border ${bigramStats[lang] ? 'bg-amber-50 border-amber-200' : 'bg-gray-50 border-gray-200'}`}>
                <div className="flex items-center justify-between mb-2">
                  <span className="font-medium text-gray-900">{LANG_NAMES[lang]}</span>
                  {bigramStats[lang] && (
                    <span className="text-xs px-1.5 py-0.5 bg-amber-100 text-amber-700 rounded">Built</span>
                  )}
                </div>
                {bigramStats[lang] ? (
                  <div className="text-sm text-gray-600 mb-2">
                    {bigramStats[lang].unique_bigrams?.toLocaleString() || 0} unique pairs
                  </div>
                ) : (
                  <div className="text-sm text-gray-500 mb-2">Not built yet</div>
                )}
                <button
                  onClick={() => buildBigramIndex(lang)}
                  disabled={buildingBigram !== null}
                  className={`w-full px-3 py-1.5 text-sm rounded ${
                    buildingBigram === lang
                      ? 'bg-blue-100 text-blue-700 cursor-wait'
                      : bigramStats[lang]
                        ? 'bg-amber-100 text-amber-700 hover:bg-amber-200'
                        : 'bg-blue-100 text-blue-700 hover:bg-blue-200'
                  } ${buildingBigram !== null && buildingBigram !== lang ? 'opacity-50 cursor-not-allowed' : ''}`}
                >
                  {buildingBigram === lang ? 'Building...' : bigramStats[lang] ? 'Rebuild' : 'Build Index'}
                </button>
              </div>
            ))}
          </div>
        </div>
      </div>

      {confirmModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg shadow-xl max-w-lg w-full max-h-[90vh] overflow-y-auto">
            <div className={`px-6 py-4 border-b ${
              confirmModal.severity === 'high'
                ? 'bg-red-50 border-red-200'
                : confirmModal.severity === 'medium'
                  ? 'bg-amber-50 border-amber-200'
                  : 'bg-amber-50 border-amber-200'
            }`}>
              <h3 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
                {confirmModal.severity === 'high' && <span className="text-red-600">⚠️</span>}
                {confirmModal.severity === 'medium' && <span className="text-amber-600">⚡</span>}
                Clear {confirmModal.title}?
              </h3>
              <p className="text-sm text-gray-600 mt-1">{confirmModal.description}</p>
            </div>

            <div className="px-6 py-4 space-y-4">
              <div className="bg-gray-50 rounded p-3">
                <div className="text-sm font-medium text-gray-700 mb-1">Current Size</div>
                <div className="text-2xl font-bold text-gray-900">{confirmModal.entryCount.toLocaleString()} entries</div>
              </div>

              <div>
                <div className={`text-sm font-medium mb-2 ${
                  confirmModal.severity === 'high'
                    ? 'text-red-700'
                    : confirmModal.severity === 'medium'
                      ? 'text-amber-700'
                      : 'text-gray-700'
                }`}>
                  What will happen if you clear this cache:
                </div>
                <ul className="space-y-2">
                  {confirmModal.impact.map((item, i) => (
                    <li key={i} className="flex items-start gap-2 text-sm text-gray-700">
                      <span className={`mt-1 flex-shrink-0 ${
                        confirmModal.severity === 'high'
                          ? 'text-red-500'
                          : confirmModal.severity === 'medium'
                            ? 'text-amber-500'
                            : 'text-gray-500'
                      }`}>•</span>
                      {item}
                    </li>
                  ))}
                </ul>
              </div>

              <div className="bg-blue-50 border border-blue-200 rounded p-3">
                <div className="text-sm font-medium text-blue-800 mb-1">How to Rebuild</div>
                <p className="text-sm text-blue-700">{confirmModal.rebuildTime}</p>
              </div>

              {cacheError && (
                <div className="bg-red-50 border border-red-300 rounded p-3">
                  <div className="text-sm font-medium text-red-800">Error</div>
                  <p className="text-sm text-red-700">{cacheError}</p>
                </div>
              )}
            </div>

            <div className="px-6 py-4 bg-gray-50 border-t flex justify-end gap-3">
              <button
                onClick={() => setConfirmModal(null)}
                className="px-4 py-2 text-gray-700 bg-white border border-gray-300 rounded hover:bg-gray-50"
                disabled={clearingCache}
              >
                Cancel
              </button>
              <button
                onClick={() => clearCache(confirmModal.cacheType)}
                disabled={clearingCache}
                className={`px-4 py-2 text-white rounded disabled:opacity-50 ${
                  confirmModal.severity === 'high'
                    ? 'bg-red-600 hover:bg-red-700'
                    : confirmModal.severity === 'medium'
                      ? 'bg-amber-600 hover:bg-amber-700'
                      : 'bg-gray-600 hover:bg-gray-700'
                }`}
              >
                {clearingCache ? 'Clearing...' : 'Yes, Clear Cache'}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
