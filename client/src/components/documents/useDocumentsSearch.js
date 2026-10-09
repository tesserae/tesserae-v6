import { useState, useRef } from 'react';
import { DOC_PAGE_SIZE, DOCUMENTS_FORMULA_DEFAULT_N } from './documentsConstants';

/**
 * Documents-collection search state and /api/line-search plumbing, shared
 * by LineSearch.jsx's "Documents"/"Both" option and the Inscriptions &
 * Papyri page. Extracted from LineSearch.jsx (stage 3b-2 through stage 4)
 * with the same logic, so a request this hook builds, or a response it
 * parses, is byte-for-byte what LineSearch.jsx always sent and read.
 *
 * The hook owns everything specific to the documents collection: the
 * collection toggle and its filters, the paged/sorted result set, and the
 * century/region distribution. It does NOT own the query text, search
 * type, or the literary result list -- those stay with the caller (they
 * are shared with the literature side of a search), and the caller is
 * responsible for the loading/error UI around a call into this hook.
 *
 * @param {Object} options
 * @param {boolean} options.documentsEnabled  Server + trial flag together
 *   (see LineSearch.jsx's own `documentsEnabled`). While false, every
 *   function here is a no-op that clears state, matching the guarded
 *   behavior LineSearch.jsx already has.
 * @param {string} options.defaultCollection  'literature' for LineSearch
 *   (its existing default), 'documents' for the Inscriptions & Papyri page.
 * @param {Function} [options.setError]  Called with a message string (or
 *   null to clear) on a documents-page request. Shared with the caller's
 *   own error banner, as in LineSearch.jsx's fetchDocumentsPage.
 */
export function useDocumentsSearch({ documentsEnabled, defaultCollection = 'literature', setError }) {
  const [collection, setCollection] = useState(defaultCollection);
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [docRegion, setDocRegion] = useState('');
  const [docTextType, setDocTextType] = useState('');
  const [docMaterial, setDocMaterial] = useState('');
  const [docSource, setDocSource] = useState('');
  // Leave out a hit whose match rests entirely on restored text, and hide
  // stock formulas (matched words shared by more documents than
  // DOCUMENTS_FORMULA_DEFAULT_N).
  const [excludeRestored, setExcludeRestored] = useState(false);
  const [hideFormulas, setHideFormulas] = useState(false);

  // Document results are paged and sorted SERVER-SIDE (no 500-row
  // ceiling). `documentPageResults` holds only the current page (at most
  // DOC_PAGE_SIZE rows); `docTotal`/`docOffset`/`docSort` drive the server
  // request, and `docDistribution` carries the century/region breakdown
  // computed over every match, not just the page.
  const [documentPageResults, setDocumentPageResults] = useState([]);
  const [docTotal, setDocTotal] = useState(0);
  const [docOffset, setDocOffset] = useState(0);
  const [docSort, setDocSort] = useState('relevance');
  const [docDistribution, setDocDistribution] = useState({ by_century: [], by_source_region: [] });
  const [docPageLoading, setDocPageLoading] = useState(false);

  // The filters/query a documents page request needs to repeat on every
  // page or sort change, captured once per search (see recordSearch below)
  // so paging never re-derives them from state that may have moved on
  // since (e.g. the query box).
  const lastDocSearchRef = useRef(null);

  // Adds collection + the documents-only filters to a search params object,
  // only when the documents control is actually on and set away from plain
  // Literature. With the control untouched (or the server switch off) this
  // adds nothing, so a request is byte-for-byte what it always was.
  const addCollectionParams = (params, sortOverride) => {
    if (!documentsEnabled || collection === 'literature') return params;
    params.collection = collection;
    if (dateFrom.trim()) params.date_from = parseInt(dateFrom, 10);
    if (dateTo.trim()) params.date_to = parseInt(dateTo, 10);
    if (docRegion.trim()) params.region = docRegion.trim();
    if (docTextType.trim()) params.text_type = docTextType.trim();
    if (docMaterial.trim()) params.material = docMaterial.trim();
    if (docSource.trim()) params.source = docSource.trim();
    if (excludeRestored) params.exclude_restored = true;
    if (hideFormulas) params.hide_formulas = DOCUMENTS_FORMULA_DEFAULT_N;
    // Every documents/both request is explicit about paging from the
    // first page, at the fixed DOC_PAGE_SIZE page size, in the caller's
    // current sort choice (falls back to this hook's own `docSort` state
    // when the caller does not override it -- a fresh search keeps
    // whatever sort the reader last picked rather than silently resetting
    // to 'relevance').
    params.offset = 0;
    params.limit = DOC_PAGE_SIZE;
    params.sort = sortOverride || docSort;
    return params;
  };

  // Pulls the document-collection fields out of a /api/line-search
  // response (shared by every code path that can start a documents/both
  // search) so they never drift out of sync on what a fresh search
  // resets. `opts.collection`, when given, is used for the "is this even
  // a documents search" guard INSTEAD OF the hook's own `collection`
  // state -- a caller that just called setCollection(...) in the same
  // tick (an example-search button) cannot rely on that state having
  // updated yet, since React batches it; passing the intended collection
  // explicitly sidesteps the stale read. `opts.force` skips the guard
  // outright, for a caller that already knows the response is a
  // documents/both one (the example buttons, which never target plain
  // Literature).
  const applyDocumentsResponse = (data, opts = {}) => {
    const { sortUsed, collection: collectionArg = collection, force = false } = opts;
    if (!force && (!documentsEnabled || collectionArg === 'literature')) {
      setDocumentPageResults([]);
      setDocTotal(0);
      setDocOffset(0);
      setDocDistribution({ by_century: [], by_source_region: [] });
      return;
    }
    const docRows = (data.results || []).filter(r => r.collection === 'documents');
    setDocumentPageResults(docRows);
    setDocTotal(data.collection === 'documents' ? (data.total ?? 0) : (data.documents_total ?? 0));
    setDocOffset(0);
    if (sortUsed) setDocSort(sortUsed);
    setDocDistribution({
      by_century: data.documents_by_century || [],
      by_source_region: data.documents_by_source_region || [],
    });
  };

  // Captures the exact params a documents/both search just sent, for
  // fetchDocumentsPage to replay on a later page or sort change.
  const recordSearch = (params) => {
    lastDocSearchRef.current = { ...params };
  };

  // Re-runs the LAST documents/both search at a new offset and/or sort,
  // without touching the literary results already on screen (the query
  // box, filters, etc. may have moved on since; this replays the exact
  // params captured at search time in `lastDocSearchRef`).
  const fetchDocumentsPage = async ({ offset = 0, sort = docSort } = {}) => {
    const base = lastDocSearchRef.current;
    if (!base) return;
    setDocPageLoading(true);
    if (setError) setError(null);
    try {
      const params = { ...base, offset, limit: DOC_PAGE_SIZE, sort };
      const res = await fetch('/api/line-search', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(params)
      });
      const data = await res.json();
      if (data.error) {
        if (setError) setError(data.error);
      } else {
        const docRows = (data.results || []).filter(r => r.collection === 'documents');
        setDocumentPageResults(docRows);
        setDocTotal(data.collection === 'documents' ? (data.total ?? 0) : (data.documents_total ?? 0));
        setDocOffset(offset);
        setDocSort(sort);
        setDocDistribution({
          by_century: data.documents_by_century || [],
          by_source_region: data.documents_by_source_region || [],
        });
      }
    } catch (err) {
      if (setError) setError('Search failed. Please try again.');
    }
    setDocPageLoading(false);
  };

  const docCurrentPage = Math.floor(docOffset / DOC_PAGE_SIZE) + 1;
  const docTotalPages = Math.max(1, Math.ceil(docTotal / DOC_PAGE_SIZE));
  // Documents are paged by the SERVER (docTotal/docOffset, DOC_PAGE_SIZE
  // fixed), not sliced locally the way usePagination does for literature.
  // This small shim gives the shared <Pagination> component the same prop
  // shape (`onPageSizeChange` is a no-op: the page size here is fixed, so
  // the "Show" selector is restricted to the single option [DOC_PAGE_SIZE]).
  const docPagination = {
    currentPage: docCurrentPage,
    totalPages: docTotalPages,
    totalResults: docTotal,
    pageSize: DOC_PAGE_SIZE,
    startIndex: docTotal === 0 ? 0 : docOffset,
    onPageChange: (page) => fetchDocumentsPage({ offset: (page - 1) * DOC_PAGE_SIZE, sort: docSort }),
    onPageSizeChange: () => {},
    loading: docPageLoading,
  };

  return {
    collection, setCollection,
    dateFrom, setDateFrom,
    dateTo, setDateTo,
    docRegion, setDocRegion,
    docTextType, setDocTextType,
    docMaterial, setDocMaterial,
    docSource, setDocSource,
    excludeRestored, setExcludeRestored,
    hideFormulas, setHideFormulas,
    documentPageResults,
    docTotal,
    docOffset,
    docSort, setDocSort,
    docDistribution,
    docPageLoading,
    docPagination,
    addCollectionParams,
    applyDocumentsResponse,
    recordSearch,
    fetchDocumentsPage,
  };
}

export default useDocumentsSearch;
