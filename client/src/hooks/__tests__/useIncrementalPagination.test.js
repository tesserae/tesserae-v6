import { describe, it, expect, vi } from 'vitest';
import { act, renderHook, waitFor } from '@testing-library/react';
import useIncrementalPagination from '../useIncrementalPagination';

const deferred = () => { let resolve, reject; const promise = new Promise((a, b) => { resolve = a; reject = b; }); return { promise, resolve, reject }; };
const ready = result => waitFor(() => expect(result.current.loading).toBe(false));
const adapter = vi.fn(async ({ page, pageSize }) => ({ items: Array.from({ length: pageSize }, (_, i) => (page - 1) * pageSize + i), total: 120 }));

describe('useIncrementalPagination', () => {
  it('loads page 1 and appends the next logical page with an abort signal', async () => {
    const fetchPage = vi.fn(adapter);
    const { result } = renderHook(() => useIncrementalPagination({ fetchPage }));
    expect(result.current.loading).toBe(true);
    await ready(result);
    expect(result.current.visibleItems).toHaveLength(50);
    expect(result.current.currentPage).toBe(1);
    expect(result.current.totalPages).toBe(3);
    expect(fetchPage).toHaveBeenCalledWith({ page: 1, pageSize: 50, signal: expect.any(AbortSignal) });
    act(() => result.current.loadMore());
    await ready(result);
    expect(result.current.visibleItems).toEqual(Array.from({ length: 100 }, (_, i) => i));
    expect(result.current.currentPage).toBe(2);
    expect(result.current.hasPreviousPage).toBe(false);
  });
  it('resets on key changes and preserves the selected batch size', async () => {
    const fetchPage = vi.fn(adapter);
    const { result, rerender } = renderHook(({ resetKey }) => useIncrementalPagination({ fetchPage, resetKey }), { initialProps: { resetKey: 'a' } });
    await ready(result);
    act(() => result.current.loadMore());
    await ready(result);
    rerender({ resetKey: 'b' });
    await ready(result);
    expect(result.current.visibleItems).toHaveLength(50);
    expect(result.current.currentPage).toBe(1);
    act(() => result.current.setPageSize('25'));
    await ready(result);
    expect(result.current.visibleItems).toHaveLength(25);
    expect(result.current.pageSize).toBe(25);
    expect(result.current.totalPages).toBe(5);
    act(() => result.current.setPageSize(7));
    expect(result.current.pageSize).toBe(25);
  });
  it('ignores stale responses even when the adapter ignores abort', async () => {
    const stale = deferred();
    const fetchPage = vi.fn().mockResolvedValueOnce({ items: ['old'], total: 100 }).mockReturnValueOnce(stale.promise).mockResolvedValueOnce({ items: ['new'], total: 1 });
    const { result, rerender } = renderHook(({ resetKey }) => useIncrementalPagination({ fetchPage, resetKey }), { initialProps: { resetKey: 'a' } });
    await ready(result);
    act(() => result.current.loadMore());
    const signal = fetchPage.mock.calls[1][0].signal;
    rerender({ resetKey: 'b' });
    await ready(result);
    expect(signal.aborted).toBe(true);
    await act(async () => stale.resolve({ items: ['stale'], total: 200 }));
    expect(result.current.visibleItems).toEqual(['new']);
    expect(result.current.totalResults).toBe(1);
  });
  it('guards concurrent clicks and disables loading until the batch resolves', async () => {
    const pending = deferred();
    const fetchPage = vi.fn().mockResolvedValueOnce({ items: ['first'], total: 100 }).mockReturnValueOnce(pending.promise);
    const { result } = renderHook(() => useIncrementalPagination({ fetchPage }));
    await ready(result);
    act(() => { result.current.loadMore(); result.current.loadMore(); });
    expect(fetchPage).toHaveBeenCalledTimes(2);
    expect(result.current.loading).toBe(true);
    expect(result.current.visibleItems).toEqual(['first']);
    await act(async () => pending.resolve({ items: ['second'], total: 2 }));
    expect(result.current.hasNextPage).toBe(false);
    act(() => result.current.loadMore());
    expect(fetchPage).toHaveBeenCalledTimes(2);
  });
  it('keeps loaded items after errors and retries the same page', async () => {
    const fetchPage = vi.fn().mockResolvedValueOnce({ items: ['first'], total: 2 }).mockRejectedValueOnce(new Error('offline')).mockResolvedValueOnce({ items: ['second'], total: 2 });
    const { result } = renderHook(() => useIncrementalPagination({ fetchPage }));
    await ready(result);
    act(() => result.current.loadMore());
    await ready(result);
    expect(result.current.pageError).toBe('offline');
    expect(result.current.visibleItems).toEqual(['first']);
    act(() => result.current.loadMore());
    await ready(result);
    expect(result.current.pageError).toBe('');
    expect(fetchPage.mock.calls.map(([args]) => args.page)).toEqual([1, 2, 2]);
  });
  it('exposes first-page errors and handles empty totals', async () => {
    const fetchPage = vi.fn().mockRejectedValueOnce(new Error('failed'));
    const { result } = renderHook(() => useIncrementalPagination({ fetchPage }));
    await ready(result);
    expect(result.current.pageError).toBe('failed');
    expect(result.current.visibleItems).toEqual([]);
    expect(result.current.hasNextPage).toBe(false);
  });
  it('aborts requests on unmount', async () => {
    const pending = deferred();
    const fetchPage = vi.fn(() => pending.promise);
    const { unmount } = renderHook(() => useIncrementalPagination({ fetchPage }));
    const signal = fetchPage.mock.calls[0][0].signal;
    unmount();
    expect(signal.aborted).toBe(true);
    await act(async () => pending.reject(new Error('late error')));
  });
  it.each(['offset-limit', 'page-per-page'])('allows a %s adapter without depending on its API names', async strategy => {
    const transport = vi.fn(async () => ({ items: ['row'], total: 1 }));
    const fetchPage = ({ page, pageSize }) => transport(strategy === 'offset-limit'
      ? { offset: (page - 1) * pageSize, limit: pageSize }
      : { page, per_page: pageSize });
    const { result } = renderHook(() => useIncrementalPagination({ fetchPage }));
    await ready(result);
    expect(transport).toHaveBeenCalledWith(strategy === 'offset-limit' ? { offset: 0, limit: 50 } : { page: 1, per_page: 50 });
  });
});
