// NC, 2026-09-21, after waiting on the Reader before a demo: "can we have a
// note that says it takes a few minutes the first time to load a text?"
//
// The violet gutter column is computed against the whole corpus, so the first
// open of any text costs between 80 seconds and about four minutes; every
// open after that is instant. The gutter reports the slow case upward and the
// page shows a notice. Nothing is said for the first four seconds, because a
// warm text answers in well under one and a notice that flashes on every page
// open would be worse than none.
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import { render, act } from '@testing-library/react';
import ConnectionGutter from './ConnectionGutter';

const UNITS = [{ ref: 'verg. aen. 1.1', text: 'arma virumque cano' }];

function neverResolves() {
  return new Promise(() => {});
}

beforeEach(() => {
  vi.useFakeTimers();
});

afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
});

describe('the first-load notice', () => {
  it('says nothing for the first seconds, then reports the wait', () => {
    global.fetch = vi.fn(() => neverResolves());
    const onSlowLoad = vi.fn();
    render(<ConnectionGutter work="vergil.aeneid.part.1" units={UNITS} onSlowLoad={onSlowLoad} />);

    act(() => { vi.advanceTimersByTime(3000); });
    expect(onSlowLoad).not.toHaveBeenCalledWith(true);

    act(() => { vi.advanceTimersByTime(2000); });
    expect(onSlowLoad).toHaveBeenCalledWith(true);
  });

  it('stays quiet when the answer arrives quickly, as a warm text does', async () => {
    global.fetch = vi.fn(() => Promise.resolve({
      ok: true, json: () => Promise.resolve({ windows: [] }) }));
    const onSlowLoad = vi.fn();
    render(<ConnectionGutter work="vergil.aeneid.part.1" units={UNITS} onSlowLoad={onSlowLoad} />);

    // Let the answer land first. Four seconds of real time is far longer than
    // a cached answer takes, so this is the true ordering; advancing the fake
    // clock before flushing the fetch would model a race that cannot happen.
    await act(async () => { await Promise.resolve(); await Promise.resolve(); });
    await act(async () => { await vi.advanceTimersByTimeAsync(10000); });

    expect(onSlowLoad).not.toHaveBeenCalledWith(true);
    expect(onSlowLoad).toHaveBeenLastCalledWith(false);
  });

  it('takes the notice down once the answer arrives', async () => {
    // Two requests go out, content density and lexical density. Hold only
    // the content one: it is the slow one and the only one the notice
    // depends on. Resolving whichever came last would resolve the wrong one.
    let land;
    global.fetch = vi.fn((url) => new Promise((r) => {
      if (String(url).startsWith('/api/passages/density')) {
        land = () => r({ ok: true, json: () => Promise.resolve({ windows: [] }) });
      }
    }));
    const onSlowLoad = vi.fn();
    render(<ConnectionGutter work="vergil.aeneid.part.1" units={UNITS} onSlowLoad={onSlowLoad} />);

    await act(async () => { await vi.advanceTimersByTimeAsync(5000); });
    expect(onSlowLoad).toHaveBeenCalledWith(true);

    await act(async () => { land(); await vi.advanceTimersByTimeAsync(100); });
    expect(onSlowLoad).toHaveBeenLastCalledWith(false);
  });
});
