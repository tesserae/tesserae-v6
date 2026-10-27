import { describe, it, expect, vi, afterEach } from 'vitest';
import {
  LARGE_QUEUE_TEXT, queuedText, largeComparisonWarning, minutesLeft, partsProgressText, progressWithParts,
} from '../fusionParts';
import { searchFusionStream } from '../api';

afterEach(() => vi.unstubAllGlobals());

const streamOf = (events) => {
  const bytes = new TextEncoder().encode(events.map((e) => `data: ${JSON.stringify(e)}\n\n`).join(''));
  let sent = false;
  return {
    ok: true,
    body: {
      getReader: () => ({
        read: async () => (sent ? { done: true } : ((sent = true), { done: false, value: bytes })),
      }),
    },
  };
};

const THEBAID_AENEID = { pairs: 96298976, in_parts: true, parts: 20, estimated_seconds: 1637 };

describe('the warning before a large comparison', () => {
  it('words the estimate as the owner asked', () => {
    expect(largeComparisonWarning('Statius, Thebaid', 'Vergil, Aeneid', THEBAID_AENEID)).toBe(
      'Large comparison. Statius, Thebaid against Vergil, Aeneid is about 96 million line pairs '
      + 'and will take about 27 minutes. The results fill in part by part, and you can leave '
      + 'the page open. Comparing selected books finishes in a minute or two.');
  });

  it('says one minute in the singular', () => {
    expect(largeComparisonWarning('A', 'B', { pairs: 4500000, estimated_seconds: 60 }))
      .toContain('about 5 million line pairs and will take about 1 minute.');
  });
});

describe('the progress line while a comparison runs in parts', () => {
  const parts = (part) => ({ part, total_parts: 20 });

  it('uses the estimate before the first part has finished', () => {
    expect(partsProgressText(parts(1), 30, { 1: 0 }, 1637))
      .toBe('Large comparison: part 1 of 20, about 27 minutes left');
  });

  it('uses the measured time of the parts done once there is one', () => {
    // parts took 60 s each: at the start of part 6, 15 parts remain = 15 minutes
    const starts = { 1: 0, 2: 60, 3: 120, 4: 180, 5: 240, 6: 300 };
    expect(minutesLeft(parts(6), 300, starts, 1637)).toBe(15);
    expect(partsProgressText(parts(6), 300, starts, 1637))
      .toBe('Large comparison: part 6 of 20, about 15 minutes left');
  });

  it('counts the time already spent in the current part', () => {
    const starts = { 1: 0, 2: 60, 3: 120 };
    expect(minutesLeft(parts(3), 170, starts, null)).toBe(17);   // 18 parts x 60 s - 50 s
  });

  it('never says zero minutes and names none when nothing is known', () => {
    expect(minutesLeft({ part: 20, total_parts: 20 }, 1500, { 1: 0, 19: 1400, 20: 1460 }, 1637)).toBe(1);
    expect(partsProgressText(parts(1), 5, { 1: 0 }, undefined)).toBe('Large comparison: part 1 of 20');
  });

  it('leaves an ordinary search alone', () => {
    expect(progressWithParts('Running lemma (1/9 channels)', '', null, 3, {}, 100))
      .toBe('Running lemma (1/9 channels)');
    expect(progressWithParts('Loading', 'x', undefined)).toBe('Loading: x');
    expect(progressWithParts('Running lemma', '', parts(2), 100, { 1: 0, 2: 90 }, 1637))
      .toMatch(/^Large comparison: part 2 of 20, about \d+ minutes left$/);
  });
});

describe('the queued message', () => {
  it('names the other comparison', () => {
    expect(LARGE_QUEUE_TEXT).toBe(
      'Waiting to start: another large comparison is running first. Yours starts as soon as that one finishes.');
  });
});

describe('the fusion stream carries the new fields', () => {
  it('hands the parts and the queue flag to the page', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(streamOf([
      { type: 'queued', step: 'Search queued', detail: '', wait_time: 0, large_queue: true, position: 1 },
      { type: 'progress', step: 'Running lemma (1/9 channels)', detail: '', elapsed: 1,
        fusion_parts: { part: 1, total_parts: 10 } },
      { type: 'complete', results: [] },
    ])));
    const onProgress = vi.fn();
    const onQueued = vi.fn();
    await searchFusionStream({}, onProgress, undefined, vi.fn(), onQueued);
    expect(onQueued.mock.calls[0][2].large_queue).toBe(true);
    expect(onProgress.mock.calls[0][3].fusion_parts).toEqual({ part: 1, total_parts: 10 });
  });
});

describe('queuedText', () => {
  it('shows the sentence the server sent', () => {
    expect(queuedText({ status: 'queued', message: 'Waiting to start: 3 comparisons are ahead of yours.' }))
      .toBe('Waiting to start: 3 comparisons are ahead of yours.');
  });
  it('builds the line from the numbers of a poll answer', () => {
    expect(queuedText({ status: 'queued', kind: 'slots', running: 2, position: 1, wait_seconds: 100 }))
      .toBe('Waiting to start: 2 comparisons are ahead of yours. Waiting for 1:40 so far.');
    expect(queuedText({ kind: 'memory', wait_seconds: 5 }))
      .toBe("Waiting to start: the server's memory is in use by other searches. Waiting for 0:05 so far.");
  });
});
