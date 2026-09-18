/**
 * fetchCoveredWorks: retrying /api/passages/works past a deploy-reload race.
 *
 * Right after a deploy reload, an Apache worker can take ~90s to load the
 * 2GB passage index on its first request, and /api/passages/works answers
 * slow, empty, or failed during that window. Browse Corpus and Theme Search
 * both used to read that as "this language has zero Theme Search coverage",
 * indistinguishable from a real gap. This retries at +3s and +10s before
 * giving up, so a transient empty answer gets a second and third chance.
 */
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import { fetchCoveredWorks } from './passageCoverage';

beforeEach(() => {
  vi.useFakeTimers();
});

afterEach(() => {
  vi.useRealTimers();
});

describe('fetchCoveredWorks', () => {
  it('returns the works list straight away when the first attempt succeeds', async () => {
    global.fetch = vi.fn(() =>
      Promise.resolve({ json: () => Promise.resolve({ works: ['vergil.aeneid'] }) }));

    const result = await fetchCoveredWorks('la', true);

    expect(result).toEqual(['vergil.aeneid']);
    expect(global.fetch).toHaveBeenCalledTimes(1);
  });

  it('retries at +3s and +10s while the corpus has works, and recovers on the last try', async () => {
    let call = 0;
    global.fetch = vi.fn(() => {
      call += 1;
      if (call < 3) return Promise.resolve({ json: () => Promise.resolve({ works: [] }) });
      return Promise.resolve({ json: () => Promise.resolve({ works: ['vergil.aeneid'] }) });
    });

    const pending = fetchCoveredWorks('la', true);

    // First attempt fires immediately and comes back empty.
    await vi.advanceTimersByTimeAsync(0);
    expect(call).toBe(1);

    // Second attempt fires at +3s, still empty.
    await vi.advanceTimersByTimeAsync(3000);
    expect(call).toBe(2);

    // Third attempt fires at +10s more, and this one succeeds.
    await vi.advanceTimersByTimeAsync(10000);
    expect(call).toBe(3);

    expect(await pending).toEqual(['vergil.aeneid']);
  });

  it('gives up after the third attempt and returns an empty list, not an error', async () => {
    global.fetch = vi.fn(() => Promise.resolve({ json: () => Promise.resolve({ works: [] }) }));

    const pending = fetchCoveredWorks('la', true);
    await vi.advanceTimersByTimeAsync(0);
    await vi.advanceTimersByTimeAsync(3000);
    await vi.advanceTimersByTimeAsync(10000);

    expect(await pending).toEqual([]);
    expect(global.fetch).toHaveBeenCalledTimes(3);
  });

  it('does not retry when the corpus itself has no works', async () => {
    global.fetch = vi.fn(() => Promise.resolve({ json: () => Promise.resolve({ works: [] }) }));

    const result = await fetchCoveredWorks('cop', false);

    expect(result).toEqual([]);
    expect(global.fetch).toHaveBeenCalledTimes(1);
  });

  it('treats a rejected fetch the same as an empty list, and still retries', async () => {
    let call = 0;
    global.fetch = vi.fn(() => {
      call += 1;
      if (call === 1) return Promise.reject(new Error('network down'));
      return Promise.resolve({ json: () => Promise.resolve({ works: ['cicero.orator'] }) });
    });

    const pending = fetchCoveredWorks('la', true);
    await vi.advanceTimersByTimeAsync(0);
    await vi.advanceTimersByTimeAsync(3000);

    expect(await pending).toEqual(['cicero.orator']);
  });
});
