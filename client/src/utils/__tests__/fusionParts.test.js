import { describe, it, expect, vi, afterEach } from 'vitest';
import { LARGE_QUEUE_TEXT, largeComparisonText, progressWithParts } from '../fusionParts';
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

describe('large comparison wording', () => {
  it('names the parts and the current part', () => {
    expect(largeComparisonText({ part: 2, total_parts: 10 }))
      .toBe('Large comparison: running in 10 parts, part 2');
  });

  it('says nothing for an ordinary search', () => {
    expect(largeComparisonText(null)).toBe('');
    expect(progressWithParts('Running lemma (1/9 channels)', '', null))
      .toBe('Running lemma (1/9 channels)');
  });

  it('puts the parts wording before the step', () => {
    expect(progressWithParts('Running lemma (1/9 channels)', '', { part: 1, total_parts: 10 }))
      .toBe('Large comparison: running in 10 parts, part 1. Running lemma (1/9 channels)');
  });

  it('uses the waiting message for the queue', () => {
    expect(LARGE_QUEUE_TEXT).toBe('Waiting for another large comparison to finish');
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
