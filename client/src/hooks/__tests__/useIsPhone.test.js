import { describe, expect, it, afterEach } from 'vitest';
import { act, renderHook } from '@testing-library/react';
import { useIsPhone, useIsNarrow } from '../useIsPhone';
import { installPhone } from '../../test/phone';

let env;
afterEach(() => { if (env) env.restore(); env = null; });

describe('useIsPhone', () => {
  it('is true when the narrow-viewport query matches', () => {
    env = installPhone(true);
    const { result } = renderHook(() => useIsPhone());
    expect(result.current).toBe(true);
  });

  it('is false when it does not', () => {
    env = installPhone(false);
    const { result } = renderHook(() => useIsPhone());
    expect(result.current).toBe(false);
  });

  it('updates when the viewport changes', () => {
    env = installPhone(false);
    const { result } = renderHook(() => useIsPhone());
    expect(result.current).toBe(false);
    act(() => env.setPhone(true));
    expect(result.current).toBe(true);
    act(() => env.setPhone(false));
    expect(result.current).toBe(false);
  });

  it('is false without matchMedia', () => {
    const original = window.matchMedia;
    window.matchMedia = undefined;
    try {
      const { result } = renderHook(() => useIsPhone());
      expect(result.current).toBe(false);
    } finally {
      window.matchMedia = original;
    }
  });
});

describe('useIsNarrow', () => {
  it('follows the 640 pixel query, apart from the phone query', () => {
    env = installPhone(true, false);
    const { result } = renderHook(() => useIsNarrow());
    expect(result.current).toBe(false);
    act(() => env.setNarrow(true));
    expect(result.current).toBe(true);
    act(() => env.setNarrow(false));
    expect(result.current).toBe(false);
  });

  it('is false without matchMedia', () => {
    const original = window.matchMedia;
    window.matchMedia = undefined;
    try {
      const { result } = renderHook(() => useIsNarrow());
      expect(result.current).toBe(false);
    } finally {
      window.matchMedia = original;
    }
  });
});
