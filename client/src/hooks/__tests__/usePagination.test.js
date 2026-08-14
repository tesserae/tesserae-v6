import { describe, it, expect } from 'vitest';
import { act, renderHook } from '@testing-library/react';
import {
  usePagination,
  PAGE_SIZE_OPTIONS,
  DEFAULT_PAGE_SIZE,
  MAX_PAGE_SIZE,
  isValidPageSize,
} from '../usePagination';

const makeItems = (n) => Array.from({ length: n }, (_, i) => ({ id: i + 1 }));
const ids = (arr) => arr.map((r) => r.id);

describe('pagination constants', () => {
  it('exposes exactly 10, 20, 50 and 100 as the allowed page sizes', () => {
    expect(PAGE_SIZE_OPTIONS).toEqual([10, 20, 50, 100]);
  });

  it('caps the maximum selectable page size at 100', () => {
    expect(MAX_PAGE_SIZE).toBe(100);
    expect(Math.max(...PAGE_SIZE_OPTIONS)).toBe(100);
  });

  it('defaults to a page size of 50', () => {
    expect(DEFAULT_PAGE_SIZE).toBe(50);
  });

  it('rejects any value outside the allowed options', () => {
    [0, 1, 5, 25, 30, 101, 200, 500, 1000, -10, 'abc', null, undefined, 12.5]
      .forEach((v) => expect(isValidPageSize(v)).toBe(false));
    PAGE_SIZE_OPTIONS.forEach((v) => expect(isValidPageSize(v)).toBe(true));
  });
});

describe('usePagination', () => {
  it('defaults to a page size of 50', () => {
    const { result } = renderHook(() => usePagination(makeItems(237)));
    expect(result.current.pageSize).toBe(50);
    expect(result.current.currentPage).toBe(1);
  });

  it('returns the first 50 items on page 1 of 237 results', () => {
    const { result } = renderHook(() => usePagination(makeItems(237)));
    expect(result.current.visibleItems).toHaveLength(50);
    expect(ids(result.current.visibleItems)[0]).toBe(1);
    expect(ids(result.current.visibleItems)[49]).toBe(50);
    expect(result.current.startIndex).toBe(0);
    expect(result.current.endIndex).toBe(50);
    expect(result.current.totalPages).toBe(5);
    expect(result.current.totalResults).toBe(237);
  });

  it('returns items 51-100 on page 2', () => {
    const { result } = renderHook(() => usePagination(makeItems(237)));
    act(() => result.current.setPage(2));
    expect(ids(result.current.visibleItems)[0]).toBe(51);
    expect(ids(result.current.visibleItems)[49]).toBe(100);
    expect(result.current.startIndex).toBe(50);
    expect(result.current.endIndex).toBe(100);
  });

  it('returns the remaining 37 items on the final page', () => {
    const { result } = renderHook(() => usePagination(makeItems(237)));
    act(() => result.current.setPage(5));
    expect(result.current.visibleItems).toHaveLength(37);
    expect(ids(result.current.visibleItems)[0]).toBe(201);
    expect(ids(result.current.visibleItems)[36]).toBe(237);
    expect(result.current.endIndex).toBe(237);
  });

  it.each([
    [10, 10, 24],
    [20, 20, 12],
    [100, 100, 3],
  ])('shows %i items per page when page size %i is selected', (size, expectedLen, expectedPages) => {
    const { result } = renderHook(() => usePagination(makeItems(237)));
    act(() => result.current.setPageSize(size));
    expect(result.current.pageSize).toBe(size);
    expect(result.current.visibleItems).toHaveLength(expectedLen);
    expect(result.current.totalPages).toBe(expectedPages);
  });

  it('rejects page sizes above 100 and leaves the current size in place', () => {
    const { result } = renderHook(() => usePagination(makeItems(237)));
    [101, 200, 500, 1000].forEach((invalid) => {
      act(() => result.current.setPageSize(invalid));
      expect(result.current.pageSize).toBe(DEFAULT_PAGE_SIZE);
      expect(result.current.visibleItems).toHaveLength(50);
    });
  });

  it('rejects page sizes that are not one of the four options', () => {
    const { result } = renderHook(() => usePagination(makeItems(237)));
    [0, 5, 25, 30, 75, -10, 'lots', null].forEach((invalid) => {
      act(() => result.current.setPageSize(invalid));
      expect(result.current.pageSize).toBe(DEFAULT_PAGE_SIZE);
    });
  });

  it('accepts a numeric string from a <select> element', () => {
    const { result } = renderHook(() => usePagination(makeItems(237)));
    act(() => result.current.setPageSize('20'));
    expect(result.current.pageSize).toBe(20);
    expect(typeof result.current.pageSize).toBe('number');
  });

  it('resets to page 1 when the page size changes', () => {
    const { result } = renderHook(() => usePagination(makeItems(237)));
    act(() => result.current.setPage(4));
    expect(result.current.currentPage).toBe(4);
    act(() => result.current.setPageSize(10));
    expect(result.current.currentPage).toBe(1);
    expect(ids(result.current.visibleItems)[0]).toBe(1);
  });

  it('clamps setPage below page 1', () => {
    const { result } = renderHook(() => usePagination(makeItems(237)));
    act(() => result.current.setPage(0));
    expect(result.current.currentPage).toBe(1);
    act(() => result.current.setPage(-7));
    expect(result.current.currentPage).toBe(1);
  });

  it('clamps setPage beyond the final page', () => {
    const { result } = renderHook(() => usePagination(makeItems(237)));
    act(() => result.current.setPage(99));
    expect(result.current.currentPage).toBe(5);
    expect(result.current.visibleItems).toHaveLength(37);
  });

  it('produces valid empty values for zero results', () => {
    const { result } = renderHook(() => usePagination([]));
    expect(result.current.totalResults).toBe(0);
    expect(result.current.totalPages).toBe(1);
    expect(result.current.visibleItems).toEqual([]);
    expect(result.current.startIndex).toBe(0);
    expect(result.current.endIndex).toBe(0);
    expect(result.current.currentPage).toBe(1);
  });

  it('treats a non-array input as empty', () => {
    const { result } = renderHook(() => usePagination(undefined));
    expect(result.current.totalResults).toBe(0);
    expect(result.current.visibleItems).toEqual([]);
  });

  it('never leaves an out-of-range page when the result array shrinks', () => {
    const { result, rerender } = renderHook(
      ({ items }) => usePagination(items),
      { initialProps: { items: makeItems(237) } }
    );
    act(() => result.current.setPage(5));
    expect(result.current.currentPage).toBe(5);

    rerender({ items: makeItems(12) });

    expect(result.current.currentPage).toBe(1);
    expect(result.current.totalPages).toBe(1);
    expect(result.current.visibleItems).toHaveLength(12);
    expect(result.current.endIndex).toBe(12);
  });

  it('resets to page 1 when resetKey changes even if the length is identical', () => {
    const { result, rerender } = renderHook(
      ({ items, resetKey }) => usePagination(items, { resetKey }),
      { initialProps: { items: makeItems(237), resetKey: 'search-1' } }
    );
    act(() => result.current.setPage(4));
    expect(result.current.currentPage).toBe(4);

    // A brand new result set that happens to have exactly the same count.
    rerender({ items: makeItems(237), resetKey: 'search-2' });

    expect(result.current.currentPage).toBe(1);
    expect(ids(result.current.visibleItems)[0]).toBe(1);
  });

  it('stays on the current page when resetKey is unchanged', () => {
    const { result, rerender } = renderHook(
      ({ items, resetKey }) => usePagination(items, { resetKey }),
      { initialProps: { items: makeItems(237), resetKey: 'search-1' } }
    );
    act(() => result.current.setPage(3));
    rerender({ items: makeItems(237), resetKey: 'search-1' });
    expect(result.current.currentPage).toBe(3);
  });

  it('resetPage returns to the first page on demand', () => {
    const { result } = renderHook(() => usePagination(makeItems(237)));
    act(() => result.current.setPage(3));
    act(() => result.current.resetPage());
    expect(result.current.currentPage).toBe(1);
  });

  it('reproduces the input array exactly when every page is concatenated', () => {
    const items = makeItems(237);
    const { result } = renderHook(() => usePagination(items));
    const collected = [];
    for (let page = 1; page <= result.current.totalPages; page += 1) {
      act(() => result.current.setPage(page));
      collected.push(...result.current.visibleItems);
    }
    expect(ids(collected)).toEqual(ids(items));
  });

  it('preserves order across pages at every page size', () => {
    const items = makeItems(237);
    PAGE_SIZE_OPTIONS.forEach((size) => {
      const { result } = renderHook(() => usePagination(items));
      act(() => result.current.setPageSize(size));
      const collected = [];
      for (let page = 1; page <= result.current.totalPages; page += 1) {
        act(() => result.current.setPage(page));
        collected.push(...result.current.visibleItems);
      }
      expect(ids(collected)).toEqual(ids(items));
    });
  });

  it('honours a controlled page size and reports changes to the owner', () => {
    const onPageSizeChange = vi.fn();
    const { result } = renderHook(() =>
      usePagination(makeItems(237), { pageSize: 20, onPageSizeChange })
    );
    expect(result.current.pageSize).toBe(20);
    expect(result.current.visibleItems).toHaveLength(20);

    act(() => result.current.setPageSize(100));
    expect(onPageSizeChange).toHaveBeenCalledWith(100);
    expect(onPageSizeChange).toHaveBeenCalledTimes(1);
  });

  it('does not notify the owner when a controlled page size is invalid', () => {
    const onPageSizeChange = vi.fn();
    const { result } = renderHook(() =>
      usePagination(makeItems(237), { pageSize: 50, onPageSizeChange })
    );
    act(() => result.current.setPageSize(500));
    expect(onPageSizeChange).not.toHaveBeenCalled();
  });

  it('pins to page 1 while pinToFirstPage is set, then releases it', () => {
    const { result, rerender } = renderHook(
      ({ items, pinToFirstPage }) => usePagination(items, { pinToFirstPage }),
      { initialProps: { items: makeItems(237), pinToFirstPage: true } }
    );
    act(() => result.current.setPage(4));
    expect(result.current.currentPage).toBe(1);
    expect(ids(result.current.visibleItems)[0]).toBe(1);

    rerender({ items: makeItems(237), pinToFirstPage: false });
    act(() => result.current.setPage(4));
    expect(result.current.currentPage).toBe(4);
  });

  it('honours an uncontrolled initialPageSize from the allowed options', () => {
    const { result } = renderHook(() =>
      usePagination(makeItems(237), { initialPageSize: 10 })
    );
    expect(result.current.pageSize).toBe(10);
    expect(result.current.visibleItems).toHaveLength(10);
  });

  it('falls back to 50 when initialPageSize is invalid', () => {
    const { result } = renderHook(() =>
      usePagination(makeItems(237), { initialPageSize: 250 })
    );
    expect(result.current.pageSize).toBe(DEFAULT_PAGE_SIZE);
  });
});
