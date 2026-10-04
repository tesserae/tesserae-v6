import { useState, useEffect, useMemo, useRef, useCallback } from 'react';

/**
 * Allowed page sizes for every paginated result view.
 * This is the single source of truth — components must not redeclare it.
 */
export const PAGE_SIZE_OPTIONS = [10, 20, 50, 100];
export const DEFAULT_PAGE_SIZE = 50;
export const MAX_PAGE_SIZE = 100;

/** True only for values that appear verbatim in PAGE_SIZE_OPTIONS. */
export const isValidPageSize = (value) => {
  const n = Number(value);
  return Number.isInteger(n) && PAGE_SIZE_OPTIONS.includes(n);
};

/** Coerce a <select> string to a valid page size, falling back when invalid. */
export const normalizePageSize = (value, fallback = DEFAULT_PAGE_SIZE) =>
  isValidPageSize(value) ? Number(value) : fallback;

/**
 * Client-side pagination over an already-loaded array.
 *
 * Never issues a network request: every page change is a slice of `items`.
 * Pagination is always the last step — callers pass in results that are
 * already sorted and filtered.
 *
 * Page size can be controlled (pass `pageSize` + `onPageSizeChange`, so several
 * views can share one selection) or uncontrolled (pass `initialPageSize`).
 *
 * @param {Array}  items          Full result array.
 * @param {Object} options
 * @param {number} options.initialPageSize  Starting size when uncontrolled.
 * @param {number} options.pageSize         Controlled size; enables controlled mode.
 * @param {Function} options.onPageSizeChange  Called with a number in controlled mode.
 * @param {string} options.resetKey     Any change returns to page 1. Use a value that
 *                                      changes once per new result set, so a fresh
 *                                      search with the same result count still resets.
 * @param {boolean} options.pinToFirstPage  Force page 1 (used while a search streams).
 */
export const usePagination = (items, options = {}) => {
  const {
    initialPageSize = DEFAULT_PAGE_SIZE,
    pageSize: controlledPageSize,
    onPageSizeChange,
    resetKey,
    pinToFirstPage = false,
  } = options;

  const list = Array.isArray(items) ? items : [];
  const totalResults = list.length;

  const isControlled = controlledPageSize !== undefined;
  const [uncontrolledPageSize, setUncontrolledPageSize] = useState(() =>
    normalizePageSize(initialPageSize)
  );
  const pageSize = isControlled
    ? normalizePageSize(controlledPageSize)
    : uncontrolledPageSize;

  const [currentPage, setCurrentPage] = useState(1);

  const totalPages = Math.max(1, Math.ceil(totalResults / pageSize));

  // Return to page 1 when the caller signals a new result set, or when the page
  // size changes. Compared against a ref so it does not fire on mount.
  const resetSignal = `${resetKey ?? ''}|${pageSize}`;
  const prevResetSignal = useRef(resetSignal);
  useEffect(() => {
    if (prevResetSignal.current !== resetSignal) {
      prevResetSignal.current = resetSignal;
      setCurrentPage(1);
    }
  }, [resetSignal]);

  // Keep the stored page valid when the page count shrinks (filters, a smaller
  // result set). The render-time clamp below already guards `visibleItems`;
  // this keeps the persisted state honest for the next interaction.
  useEffect(() => {
    setCurrentPage((page) => Math.min(Math.max(1, page), totalPages));
  }, [totalPages]);

  // Clamp during render, not only in the effect, so a shrinking or growing array
  // can never produce a slice past the end of `items` on the very first pass.
  const effectivePage = pinToFirstPage
    ? 1
    : Math.min(Math.max(1, currentPage), totalPages);

  const startIndex = totalResults === 0 ? 0 : (effectivePage - 1) * pageSize;
  const endIndex = Math.min(startIndex + pageSize, totalResults);

  const visibleItems = useMemo(
    () => list.slice(startIndex, endIndex),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [items, startIndex, endIndex]
  );

  const setPage = useCallback((page) => {
    const n = Number(page);
    if (!Number.isFinite(n)) return;
    setCurrentPage(Math.min(Math.max(1, Math.trunc(n)), totalPages));
  }, [totalPages]);

  // Rejects anything outside PAGE_SIZE_OPTIONS rather than clamping, so a value
  // above MAX_PAGE_SIZE can never take effect.
  const setPageSize = useCallback((value) => {
    if (!isValidPageSize(value)) return;
    const n = Number(value);
    if (isControlled) {
      if (onPageSizeChange) onPageSizeChange(n);
    } else {
      setUncontrolledPageSize(n);
    }
    setCurrentPage(1);
  }, [isControlled, onPageSizeChange]);

  const resetPage = useCallback(() => setCurrentPage(1), []);

  return {
    currentPage: effectivePage,
    pageSize,
    totalPages,
    totalResults,
    visibleItems,
    startIndex,
    endIndex,
    setPage,
    setPageSize,
    resetPage,
  };
};

/**
 * Server-side pagination over a finished search held by the backend
 * (GET /api/search-results/<id>). Same return shape as usePagination, plus
 * `pageLoading` / `pageError`.
 *
 * The browser keeps one page. Sort and filter are sent with each request and
 * applied by the server over the complete stored list before it slices, so a
 * page is never sorted or filtered on its own.
 *
 * @param {Object|null} resultSet  {id, total, firstPage, pageSize} from the
 *                                 search response; null disables the hook.
 * @param {Object} options  pageSize / onPageSizeChange / resetKey as in
 *                          usePagination, plus `sort` and `filter` (the
 *                          SearchResults chartFilter object or null).
 * @param {Function} fetchPage  (id, query, signal) => Promise<{results,total}>
 */
export const useServerPagination = (resultSet, options = {}, fetchPage) => {
  const { pageSize: requested, onPageSizeChange, resetKey, sort = 'score', filter = null } = options;
  const pageSize = normalizePageSize(requested);
  const [currentPage, setCurrentPage] = useState(1);

  const resetSignal = `${resultSet?.id ?? ''}|${resetKey ?? ''}|${pageSize}`;
  const prevResetSignal = useRef(resetSignal);
  useEffect(() => {
    if (prevResetSignal.current !== resetSignal) {
      prevResetSignal.current = resetSignal;
      setCurrentPage(1);
    }
  }, [resetSignal]);

  const query = useMemo(() => {
    const q = { offset: (currentPage - 1) * pageSize, limit: pageSize, sort };
    if (filter) {
      q.filter_view = filter.view;
      if (filter.mode === 'line') {
        q.filter_line_min = filter.lineMin;
        q.filter_line_max = filter.lineMax;
      } else {
        q.filter_book = filter.book;
      }
    }
    return q;
  }, [currentPage, pageSize, sort, filter]);
  const queryKey = resultSet ? `${resultSet.id}?${new URLSearchParams(query)}` : '';

  // The search response already carries page 1 in score order, unfiltered.
  const seedKey = resultSet
    ? `${resultSet.id}?${new URLSearchParams({ offset: 0, limit: resultSet.pageSize, sort: 'score' })}`
    : '';
  const [page, setPageData] = useState({ key: '', results: [], total: 0 });
  const [pageLoading, setPageLoading] = useState(false);
  const [pageError, setPageError] = useState(null);

  useEffect(() => {
    if (!resultSet) return undefined;
    if (queryKey === seedKey) {
      setPageData({ key: queryKey, results: resultSet.firstPage || [], total: resultSet.total });
      setPageError(null);
      return undefined;
    }
    const controller = new AbortController();
    setPageLoading(true);
    setPageError(null);
    fetchPage(resultSet.id, query, controller.signal)
      .then((data) => setPageData({ key: queryKey, results: data.results || [], total: data.total ?? 0 }))
      .catch((err) => { if (err.name !== 'AbortError') setPageError(err.message || 'Could not load page'); })
      .finally(() => { if (!controller.signal.aborted) setPageLoading(false); });
    return () => controller.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [queryKey]);

  // Until the requested page arrives, keep showing the last one we have for
  // this result set; a brand-new set starts from its own first page.
  const shown = resultSet && page.key.startsWith(`${resultSet.id}?`)
    ? page
    : { results: resultSet?.firstPage || [], total: resultSet?.total ?? 0 };
  const totalResults = shown.total;
  const totalPages = Math.max(1, Math.ceil(totalResults / pageSize));
  const effectivePage = Math.min(Math.max(1, currentPage), totalPages);
  const visibleItems = shown.results;
  const startIndex = totalResults === 0 ? 0 : (effectivePage - 1) * pageSize;

  const setPage = useCallback((n) => {
    const v = Number(n);
    if (!Number.isFinite(v)) return;
    setCurrentPage(Math.min(Math.max(1, Math.trunc(v)), totalPages));
  }, [totalPages]);

  const setPageSize = useCallback((value) => {
    if (!isValidPageSize(value)) return;
    if (onPageSizeChange) onPageSizeChange(Number(value));
    setCurrentPage(1);
  }, [onPageSizeChange]);

  return {
    currentPage: effectivePage,
    pageSize,
    totalPages,
    totalResults,
    visibleItems,
    startIndex,
    endIndex: startIndex + visibleItems.length,
    setPage,
    setPageSize,
    resetPage: useCallback(() => setCurrentPage(1), []),
    pageLoading,
    pageError,
  };
};

export default usePagination;
