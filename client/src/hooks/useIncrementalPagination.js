import { useCallback, useEffect, useRef, useState } from 'react';
import { DEFAULT_PAGE_SIZE } from './usePagination';

// Preserve the established batch sizes; local result pages use PAGE_SIZE_OPTIONS.
export const BATCH_PAGE_SIZE_OPTIONS = [25, 50, 100, 500];

/** Accumulate server batches. The adapter returns {items, total} and translates
 * logical pages into its API's parameters. No sorting, filtering or API names
 * belong here. Aborted or superseded requests cannot update the current list.
 */
export default function useIncrementalPagination({ fetchPage, resetKey, initialPageSize = DEFAULT_PAGE_SIZE }) {
  const [pageSize, setSize] = useState(() => BATCH_PAGE_SIZE_OPTIONS.includes(Number(initialPageSize))
    ? Number(initialPageSize) : DEFAULT_PAGE_SIZE);
  const [state, setState] = useState({ items: [], total: 0, page: 0, loading: true, error: '' });
  const active = useRef(null);
  const inFlight = useRef(false);
  const snapshot = useRef(state);
  snapshot.current = state;

  const request = useCallback(async (page, append, controller) => {
    inFlight.current = true;
    setState(previous => ({ ...previous, loading: true, error: '' }));
    try {
      const data = await fetchPage({ page, pageSize, signal: controller.signal });
      if (controller.signal.aborted || active.current !== controller) return;
      setState(previous => ({
        items: append ? [...previous.items, ...data.items] : data.items,
        total: data.total,
        page,
        loading: false,
        error: '',
      }));
    } catch (error) {
      if (controller.signal.aborted || active.current !== controller) return;
      setState(previous => ({ ...previous, loading: false, error: error.message || 'Could not load items' }));
    } finally {
      if (active.current === controller) inFlight.current = false;
    }
  }, [fetchPage, pageSize]);

  useEffect(() => {
    const controller = new AbortController();
    active.current = controller;
    setState({ items: [], total: 0, page: 0, loading: true, error: '' });
    request(1, false, controller);
    return () => { active.current?.abort(); };
  }, [request, resetKey]);

  const loadMore = useCallback(() => {
    const previous = snapshot.current;
    if (previous.loading || previous.items.length >= previous.total) return;
    // State updates are asynchronous; the ref also guards same-tick clicks.
    if (inFlight.current) return;
    const controller = new AbortController();
    active.current = controller;
    request(previous.page + 1, true, controller);
  }, [request]);

  const setPageSize = useCallback(value => {
    const size = Number(value);
    if (BATCH_PAGE_SIZE_OPTIONS.includes(size)) setSize(size);
  }, []);

  return {
    visibleItems: state.items,
    totalResults: state.total,
    currentPage: Math.max(1, state.page),
    totalPages: Math.max(1, Math.ceil(state.total / pageSize)),
    pageSize,
    setPageSize,
    hasNextPage: state.items.length < state.total,
    // Accumulation has no backwards transition: earlier items remain visible.
    hasPreviousPage: false,
    loading: state.loading,
    pageError: state.error,
    loadMore,
  };
}
