// The documents-collection "Search in" control (a Literature/Documents/Both
// style toggle), its date/region/type/material/source filters, and the
// restoration/formula checkboxes. Extracted from LineSearch.jsx (stage
// 3b-2 through stage 3b-3) so the Inscriptions & Papyri page gets the same
// control with a narrower `options` list (no Literature choice -- that
// page's whole purpose is the documents collection).
//
// Pure presentation: every value and setter comes from useDocumentsSearch
// (or the caller's own state), nothing here talks to the network.
export default function DocumentsSearchFilters({
  options,
  collection, setCollection,
  dateFrom, setDateFrom,
  dateTo, setDateTo,
  docRegion, setDocRegion,
  docTextType, setDocTextType,
  docMaterial, setDocMaterial,
  docSource, setDocSource,
  excludeRestored, setExcludeRestored,
  hideFormulas, setHideFormulas,
}) {
  const showFilters = collection !== 'literature';
  return (
    <div>
      <label className="block text-sm font-medium text-gray-700 mb-1">Search in</label>
      <div className="flex items-center gap-2 bg-gray-100 p-1 rounded-lg inline-flex">
        {options.map(opt => (
          <button
            key={opt.key}
            onClick={() => setCollection(opt.key)}
            className={`px-3 py-1.5 text-sm font-medium rounded ${
              collection === opt.key ? 'bg-white shadow text-red-700' : 'text-gray-600 hover:text-gray-800'
            }`}
          >
            {opt.label}
          </button>
        ))}
      </div>
      {showFilters && (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3 mt-3">
          <div>
            <label className="block text-xs text-gray-500 mb-1">Date from</label>
            <input type="number" value={dateFrom} onChange={e => setDateFrom(e.target.value)}
                   placeholder="e.g., -100" className="w-full border rounded px-2 py-1.5 text-sm" />
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">Date to</label>
            <input type="number" value={dateTo} onChange={e => setDateTo(e.target.value)}
                   placeholder="e.g., 200" className="w-full border rounded px-2 py-1.5 text-sm" />
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">Region</label>
            <input type="text" value={docRegion} onChange={e => setDocRegion(e.target.value)}
                   placeholder="e.g., Latium" className="w-full border rounded px-2 py-1.5 text-sm" />
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">Text type</label>
            <input type="text" value={docTextType} onChange={e => setDocTextType(e.target.value)}
                   placeholder="e.g., epitaph" className="w-full border rounded px-2 py-1.5 text-sm" />
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">Material</label>
            <input type="text" value={docMaterial} onChange={e => setDocMaterial(e.target.value)}
                   placeholder="e.g., marble" className="w-full border rounded px-2 py-1.5 text-sm" />
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">Source</label>
            <input type="text" value={docSource} onChange={e => setDocSource(e.target.value)}
                   placeholder="e.g., edh" className="w-full border rounded px-2 py-1.5 text-sm" />
          </div>
        </div>
      )}
      {showFilters && (
        <div className="flex flex-col sm:flex-row sm:items-center gap-3 mt-3">
          <label className="flex items-center gap-2 text-sm text-gray-700">
            <input type="checkbox" checked={excludeRestored}
                   onChange={e => setExcludeRestored(e.target.checked)} />
            Leave out matches on restored words
          </label>
          <label className="flex items-center gap-2 text-sm text-gray-700">
            <input type="checkbox" checked={hideFormulas}
                   onChange={e => setHideFormulas(e.target.checked)} />
            Hide stock formulas
          </label>
        </div>
      )}
    </div>
  );
}
