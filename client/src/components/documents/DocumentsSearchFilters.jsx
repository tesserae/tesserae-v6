// The documents-collection "Search in" control (a Literature/Documents/Both
// style toggle), its date/region/type/material/source filters, and the
// restoration/formula checkboxes. Extracted from LineSearch.jsx (stage
// 3b-2 through stage 3b-3) so the Inscriptions & Papyri page gets the same
// control with a narrower `options` list (no Literature choice -- that
// page's whole purpose is the documents collection).
//
// Pure presentation: every value and setter comes from useDocumentsSearch
// (or the caller's own state), nothing here talks to the network.
import useDocumentFilterOptions from './useDocumentFilterOptions';

export default function DocumentsSearchFilters({
  options,
  collection, setCollection,
  dateFrom, setDateFrom,
  dateTo, setDateTo,
  docKind = '', setDocKind = () => {},
  docRegion, setDocRegion,
  docTextType, setDocTextType,
  docMaterial, setDocMaterial,
  docSource, setDocSource,
  excludeRestored, setExcludeRestored,
  hideFormulas, setHideFormulas,
}) {
  const showFilters = collection !== 'literature';
  const { regions, textTypes, materials, sources } = useDocumentFilterOptions(showFilters);
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
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-7 gap-3 mt-3">
          <div>
            <label htmlFor="doc-kind" className="block text-xs text-gray-500 mb-1">Kind</label>
            <select id="doc-kind" value={docKind} onChange={e => setDocKind(e.target.value)}
                    className="w-full border rounded px-2 py-1.5 text-sm bg-white">
              <option value="inscriptions">Inscriptions</option>
              <option value="papyri">Papyri</option>
              <option value="">Both</option>
            </select>
          </div>
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
          <FilterSelect label="Region" value={docRegion} onChange={setDocRegion} options={regions} />
          <FilterSelect label="Text type" value={docTextType} onChange={setDocTextType} options={textTypes} />
          <FilterSelect label="Material" value={docMaterial} onChange={setDocMaterial} options={materials} />
          <FilterSelect label="Source" value={docSource} onChange={setDocSource} options={sources} />
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

// One drop-down: "Any" first, then each choice with its document count. A
// value that arrives in the URL but is not in the list (a restored link) is
// kept as an extra option so the box still shows what was searched.
function FilterSelect({ label, value, onChange, options }) {
  const id = `doc-filter-${label.toLowerCase().replace(/\s+/g, '-')}`;
  const known = options.some(o => o.value === value);
  return (
    <div>
      <label htmlFor={id} className="block text-xs text-gray-500 mb-1">{label}</label>
      <select id={id} value={value} onChange={e => onChange(e.target.value)}
              className="w-full border rounded px-2 py-1.5 text-sm bg-white">
        <option value="">Any</option>
        {value && !known && <option value={value}>{value}</option>}
        {options.map(o => (
          <option key={o.value} value={o.value}>
            {o.count != null ? `${o.label} (${o.count.toLocaleString('en-US')})` : o.label}
          </option>
        ))}
      </select>
    </div>
  );
}
