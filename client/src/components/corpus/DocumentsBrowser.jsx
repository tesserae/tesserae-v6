import { useState, useEffect, useMemo } from 'react';
import { LoadingSpinner } from '../common';
import Pagination from '../common/Pagination';
import { languageName } from '../../utils/languageNames';

const PAGE_SIZE = 50;

// Documents section of Browse Corpus (behind the documents trial -- see
// CorpusBrowser.jsx). Drills a facet tree (kind -> region -> century) built
// server-side from metadata.db (GET /api/documents/browse), plus the flat
// filters (text type, material, object type, language), down to a paged
// list of documents that each open the existing document Reader view.
export default function DocumentsBrowser({ documentsTrial }) {
  const [kind, setKind] = useState('');
  const [region, setRegion] = useState('');
  const [findspot, setFindspot] = useState('');
  const [century, setCentury] = useState('');
  const [textType, setTextType] = useState('');
  const [material, setMaterial] = useState('');
  const [objectType, setObjectType] = useState('');
  const [docLanguage, setDocLanguage] = useState('');
  const [page, setPage] = useState(1);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    const params = new URLSearchParams({ page: String(page), page_size: String(PAGE_SIZE) });
    if (kind) params.set('kind', kind);
    if (region) params.set('region', region);
    if (findspot) params.set('findspot', findspot);
    if (century) params.set('century', century);
    if (textType) params.set('text_type', textType);
    if (material) params.set('material', material);
    if (objectType) params.set('object', objectType);
    if (docLanguage) params.set('language', docLanguage);
    fetch(`/api/documents/browse?${params.toString()}`)
      .then((r) => {
        if (!r.ok) throw new Error('Failed to load documents.');
        return r.json();
      })
      .then(setData)
      .catch((err) => setError(err.message || 'Failed to load documents.'))
      .finally(() => setLoading(false));
  }, [kind, region, findspot, century, textType, material, objectType, docLanguage, page]);

  // Picking a different kind clears everything below it; picking a
  // different region (for papyri, the nome) clears findspot (the town
  // within it) and century; picking a findspot clears century; any change
  // resets to page 1, since the previous page number is almost never still
  // valid for a narrower selection.
  const selectKind = (k) => {
    setKind((prev) => (prev === k ? '' : k));
    setRegion('');
    setFindspot('');
    setCentury('');
    setPage(1);
  };
  const selectRegion = (r) => {
    setRegion((prev) => (prev === r ? '' : r));
    setFindspot('');
    setCentury('');
    setPage(1);
  };
  const selectFindspot = (f) => {
    setFindspot((prev) => (prev === f ? '' : f));
    setCentury('');
    setPage(1);
  };
  const selectCentury = (c) => {
    setCentury((prev) => (prev === c ? '' : c));
    setPage(1);
  };
  const onFilterChange = (setter) => (value) => {
    setter(value);
    setPage(1);
  };

  const totalPages = data ? Math.max(1, Math.ceil(data.total / PAGE_SIZE)) : 1;

  const documentViewUrl = (docId, lang) => {
    const params = new URLSearchParams({ doc: docId, lang: lang || 'la' });
    if (documentsTrial) params.set('documents', '1');
    return `/document?${params.toString()}`;
  };

  // Papyri's region facet is the Egyptian nome (e.g. "Arsinoites"); every
  // other kind's region is a province/Augustan region. The label below the
  // facet list, and the breadcrumb, read "Nome" only for papyri so the
  // second level (findspot, the town within it -- e.g. "Karanis") reads as
  // what it is rather than an unlabeled region-within-a-region.
  const regionLabel = kind === 'papyri' ? 'Nome' : 'Region';

  const breadcrumb = useMemo(() => {
    const parts = [];
    if (kind) parts.push((data?.kind_counts || []).find((k) => k.value === kind)?.label || kind);
    if (region) parts.push(region);
    if (findspot) parts.push(findspot);
    if (century) parts.push(century);
    return parts;
  }, [kind, region, findspot, century, data]);

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-lg font-semibold text-gray-900">Documents</h2>
        <p className="text-sm text-gray-500">
          Inscriptions and papyri, by kind, region (nome and findspot for papyri), and century.
          {data && <> {data.total.toLocaleString()} documents in the current selection.</>}
        </p>
      </div>

      <div className="flex flex-wrap gap-2">
        {(data?.kind_counts || []).map((k) => (
          <button
            key={k.value}
            onClick={() => selectKind(k.value)}
            className={`px-3 py-1.5 text-sm font-medium rounded border ${
              kind === k.value
                ? 'bg-red-700 text-white border-red-700'
                : 'bg-white text-gray-700 border-gray-300 hover:bg-gray-50'
            }`}
          >
            {k.label} ({k.count.toLocaleString()})
          </button>
        ))}
      </div>

      {breadcrumb.length > 0 && (
        <div className="text-xs text-gray-500">
          <button onClick={() => selectKind(kind)} className="hover:underline">All documents</button>
          {breadcrumb.map((part, i) => (
            <span key={i}> &rsaquo; {part}</span>
          ))}
        </div>
      )}

      {loading && !data ? (
        <LoadingSpinner text="Loading documents..." />
      ) : error ? (
        <div className="bg-white rounded-lg shadow p-6 text-gray-600">{error}</div>
      ) : data ? (
        <div className="flex flex-col lg:flex-row gap-4">
          <div className="lg:w-72 flex-shrink-0 space-y-4">
            <FacetList
              title={regionLabel}
              entries={data.region_counts}
              selected={region}
              onSelect={selectRegion}
              getLabel={(e) => e.value}
            />
            <FacetList
              title="Findspot"
              entries={data.findspot_counts}
              selected={findspot}
              onSelect={selectFindspot}
              getLabel={(e) => e.value}
            />
            <FacetList
              title="Century"
              entries={data.century_counts}
              selected={century}
              onSelect={selectCentury}
              getLabel={(e) => e.label}
              getValue={(e) => e.label}
            />
            <FilterSelect
              label="Text type"
              value={textType}
              onChange={onFilterChange(setTextType)}
              entries={data.filters.text_types}
            />
            <FilterSelect
              label="Material"
              value={material}
              onChange={onFilterChange(setMaterial)}
              entries={data.filters.materials}
            />
            <FilterSelect
              label="Object"
              value={objectType}
              onChange={onFilterChange(setObjectType)}
              entries={data.filters.objects}
            />
            <FilterSelect
              label="Language"
              value={docLanguage}
              onChange={onFilterChange(setDocLanguage)}
              entries={data.filters.languages}
              formatLabel={(v) => languageName(v) || v}
            />
          </div>

          <div className="flex-1 min-w-0">
            <div className="border rounded bg-white divide-y">
              {data.documents.map((doc) => (
                <div key={doc.doc_id} className="p-3 hover:bg-gray-50">
                  <div className="flex flex-col sm:flex-row sm:items-start gap-2">
                    <div className="sm:w-56 flex-shrink-0 min-w-0 break-words">
                      <a
                        href={documentViewUrl(doc.doc_id, doc.language)}
                        className="text-sm font-medium text-gray-900 hover:underline"
                      >
                        {doc.title}
                      </a>
                      <div className="text-xs text-gray-500">
                        {[doc.date_label, doc.findspot, doc.region].filter(Boolean).join(' · ')}
                      </div>
                      <div className="mt-1 flex flex-wrap gap-1">
                        {[doc.text_type, doc.material, doc.object_type].filter(Boolean).map((lab, li) => (
                          <span key={li} className="text-xs px-1.5 py-0.5 bg-gray-100 text-gray-600 rounded">
                            {lab}
                          </span>
                        ))}
                      </div>
                    </div>
                    <div className="flex-1 min-w-0 break-words text-sm text-gray-700 italic">
                      {doc.first_line || <span className="text-gray-400">No preview available.</span>}
                    </div>
                  </div>
                </div>
              ))}
              {data.documents.length === 0 && (
                <div className="text-center py-6 text-gray-500 text-sm">
                  No documents match this selection.
                </div>
              )}
            </div>
            <div className="mt-2">
              <Pagination
                currentPage={page}
                totalPages={totalPages}
                totalResults={data.total}
                pageSize={PAGE_SIZE}
                onPageChange={setPage}
                variant="nav"
                idPrefix="documents-browse"
                itemLabel="documents"
              />
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}

function FacetList({ title, entries, selected, onSelect, getLabel, getValue }) {
  const value = getValue || getLabel;
  if (!entries || entries.length === 0) return null;
  return (
    <div>
      <h3 className="text-xs font-semibold uppercase tracking-wide text-gray-500 mb-1">{title}</h3>
      <div className="border rounded bg-white divide-y max-h-56 overflow-y-auto text-sm">
        {entries.map((e, i) => {
          const v = value(e);
          const isSelected = selected === v;
          return (
            <button
              key={i}
              onClick={() => onSelect(v)}
              className={`w-full flex items-center justify-between gap-2 px-2 py-1 text-left ${
                isSelected ? 'bg-red-50 text-red-800' : 'hover:bg-gray-50 text-gray-700'
              }`}
            >
              <span className="truncate">{getLabel(e)}</span>
              <span className="text-xs text-gray-500 flex-shrink-0">{e.count.toLocaleString()}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}

function FilterSelect({ label, value, onChange, entries, formatLabel }) {
  if (!entries || entries.length === 0) return null;
  const id = `documents-browse-filter-${label.toLowerCase().replace(/\s+/g, '-')}`;
  return (
    <div>
      <label htmlFor={id} className="block text-xs font-semibold uppercase tracking-wide text-gray-500 mb-1">
        {label}
      </label>
      <select
        id={id}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full border rounded px-2 py-1.5 text-sm"
      >
        <option value="">All</option>
        {entries.map((e) => (
          <option key={e.value} value={e.value}>
            {(formatLabel ? formatLabel(e.value) : e.value)} ({e.count.toLocaleString()})
          </option>
        ))}
      </select>
    </div>
  );
}
