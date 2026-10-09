import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';

vi.mock('../../utils/api', () => ({
  searchTexts: vi.fn(),
  searchTextsStream: vi.fn(),
  searchFusionStream: vi.fn(),
  searchHapax: vi.fn(),
  searchBigrams: vi.fn(),
  searchSemanticCross: vi.fn(),
  createSearchId: () => '00000000-0000-4000-8000-000000000000',
  requestSearchCancellation: vi.fn(),
}));

import * as api from '../../utils/api';
import { useSearch } from '../useSearch';

beforeEach(() => vi.clearAllMocks());

describe('useSearch — server-held result sets', () => {
  it('keeps only the first page and records the result set when the server paged', async () => {
    api.searchFusionStream.mockResolvedValue({
      results: [{ id: 1 }, { id: 2 }], result_id: 'f'.repeat(32), result_total: 4321,
      page_size: 2, aggregates: { distribution: {} }, total_matches: 4321,
    });
    const { result } = renderHook(() => useSearch());
    await act(() => result.current.search({ match_type: 'fusion', page_size: 2 }));
    expect(api.searchFusionStream.mock.calls[0][0].page_size).toBe(2);
    expect(result.current.results).toHaveLength(2);
    expect(result.current.resultSet).toEqual({
      id: 'f'.repeat(32), total: 4321, pageSize: 2,
      firstPage: [{ id: 1 }, { id: 2 }], aggregates: { distribution: {} },
    });
  });

  it('has no result set for an unpaged response, and clears it on a new search', async () => {
    api.searchTextsStream.mockResolvedValueOnce({ results: [{ id: 1 }], result_id: 'e'.repeat(32), result_total: 1, page_size: 50 });
    api.searchTextsStream.mockResolvedValueOnce({ results: [{ id: 9 }] });
    const { result } = renderHook(() => useSearch());
    await act(() => result.current.search({ match_type: 'lemma' }));
    expect(result.current.resultSet?.id).toBe('e'.repeat(32));
    await act(() => result.current.search({ match_type: 'lemma' }));
    expect(result.current.resultSet).toBeNull();
    expect(result.current.results).toEqual([{ id: 9 }]);
  });
});
