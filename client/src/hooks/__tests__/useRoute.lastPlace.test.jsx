import { describe, it, expect, beforeEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useRoute } from '../useRoute';
import { isRememberedPath } from '../../utils/lastPlace';

const KEY = 'tesserae_last_place';
const props = { adminSessionChecked: true, adminSessionActive: false };

beforeEach(() => {
  window.localStorage.clear();
  window.history.replaceState({}, '', '/');
});

describe('the return to the last place', () => {
  it('a bare visit to / opens the stored page and rewrites the address', () => {
    window.localStorage.setItem(KEY, '/theme-search?query=storm');
    const { result } = renderHook(() => useRoute(props));
    expect(result.current.pageType).toBe('theme-search');
    expect(window.location.pathname + window.location.search).toBe('/theme-search?query=storm');
  });

  it('a visit with a parameter does not restore', () => {
    window.localStorage.setItem(KEY, '/theme-search?query=storm');
    window.history.replaceState({}, '', '/?view=history');
    const { result } = renderHook(() => useRoute(props));
    // The view home, as before: not the stored place.
    expect(result.current.pageType).not.toBe('theme-search');
    expect(window.location.search).not.toContain('storm');
  });

  it('a visit to another path does not restore', () => {
    window.localStorage.setItem(KEY, '/theme-search?query=storm');
    window.history.replaceState({}, '', '/help');
    const { result } = renderHook(() => useRoute(props));
    expect(result.current.pageType).toBe('help');
  });

  it('with nothing stored a bare visit opens the view home, as before', () => {
    const { result } = renderHook(() => useRoute(props));
    expect(result.current.pageType).toBe('ask-a-work');
  });

  it('never records the admin, downloads, privacy or credits pages', () => {
    ['/admin', '/downloads', '/privacy', '/terms', '/text-credits', '/nowhere'].forEach((p) => {
      expect(isRememberedPath(p)).toBe(false);
    });
    ['/read', '/theme-search', '/events/battle-of-actium', '/coins/abc', '/objects/1', '/mentions'].forEach((p) => {
      expect(isRememberedPath(p)).toBe(true);
    });
  });

  it('a page change records the new address', () => {
    const { result } = renderHook(() => useRoute(props));
    act(() => { result.current.setPageType('browse'); });
    expect(window.localStorage.getItem(KEY)).toBe('/browse');
  });
});
