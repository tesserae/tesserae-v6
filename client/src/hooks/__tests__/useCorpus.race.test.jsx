// Clicking Latin, then Greek, then English leaves three requests in the air.
// Whichever landed last used to win, not whichever was asked for last, so the
// author and text pickers could show one language's corpus under another
// language's tab with nothing to say so (code review, 2026-09-21). It is the
// same root cause as the reader timeout of 2026-09-20: a slow answer arriving
// late and being trusted anyway.
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import { act, renderHook, waitFor } from '@testing-library/react';
import { useCorpus } from '../useCorpus';

const TEXTS = {
  la: { texts: [{ id: 'vergil.aeneid.tess', author: 'Vergil' }] },
  grc: { texts: [{ id: 'homer.iliad.tess', author: 'Homer' }] },
};
const AUTHORS = {
  la: [{ name: 'Vergil', works: [{ author_key: 'vergil', work: 'Aeneid', work_key: 'aeneid' }] }],
  grc: [{ name: 'Homer', works: [{ author_key: 'homer', work: 'Iliad', work_key: 'iliad' }] }],
};

/** fetch that hands back a resolver per language, so a test decides the order. */
function controllableFetch() {
  const pending = {};
  const fetchMock = vi.fn((url) => {
    const u = String(url);
    const lang = /language=(\w+)/.exec(u)?.[1] || 'la';
    const kind = u.includes('/authors') ? 'authors' : 'texts';
    return new Promise((resolve) => {
      // api.js's jsonFetch reads .text() and parses it, so the mock answers
      // the way the real endpoint does rather than the way fetch is usually
      // stubbed.
      const body = JSON.stringify(kind === 'authors' ? AUTHORS[lang] : TEXTS[lang]);
      pending[`${lang}:${kind}`] = () => resolve({
        ok: true, status: 200, text: () => Promise.resolve(body),
      });
    });
  });
  return { fetchMock, land: async (lang) => {
    pending[`${lang}:texts`]?.();
    pending[`${lang}:authors`]?.();
    await act(async () => { await Promise.resolve(); await Promise.resolve(); });
  } };
}

beforeEach(() => { vi.useRealTimers(); });
afterEach(() => { vi.restoreAllMocks(); });

describe('switching language tabs quickly', () => {
  it('ignores the answer for a language the reader has left', async () => {
    const { fetchMock, land } = controllableFetch();
    global.fetch = fetchMock;

    const { result, rerender } = renderHook(({ lang }) => useCorpus(lang),
      { initialProps: { lang: 'la' } });

    // the reader moves to Greek before Latin has answered
    rerender({ lang: 'grc' });

    await land('grc');
    await waitFor(() => expect(result.current.corpus.length).toBe(1));
    expect(result.current.corpus[0].author).toBe('Homer');

    // Latin's answer arrives late; it must not replace what is on screen
    await land('la');
    expect(result.current.corpus[0].author).toBe('Homer');
  });

  it('shows the language asked for even when its answer is the slower one', async () => {
    const { fetchMock, land } = controllableFetch();
    global.fetch = fetchMock;

    const { result, rerender } = renderHook(({ lang }) => useCorpus(lang),
      { initialProps: { lang: 'la' } });
    rerender({ lang: 'grc' });

    await land('la');     // the abandoned language answers first
    await land('grc');    // the wanted one second

    await waitFor(() => expect(result.current.corpus.length).toBe(1));
    expect(result.current.corpus[0].author).toBe('Homer');
    expect(result.current.authors[0].name).toBe('Homer');
  });
});
