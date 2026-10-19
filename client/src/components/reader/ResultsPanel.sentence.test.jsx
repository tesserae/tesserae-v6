/**
 * The tabs answer for a SENTENCE when the selection is one inside a long prose
 * unit (2026-10-11): Similar sends the character offsets, Parallels and
 * its Inscriptions and papyri section search the sentence's words, Reuse and Translation stay on the unit.
 */
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import { cleanup, render, waitFor } from '@testing-library/react';
import ResultsPanel from './ResultsPanel';
import { setCollection } from '../../collections/collectionsStore';

const UNIT = 'Prima sententia est haec de rebus Romanis. Secunda sententia est illa de rebus Graecis. Tertia sententia est ultima.';
const UNITS = [{ ref: 'tac. ann. 1.1', text: UNIT }];
const SECOND = 'Secunda sententia est illa de rebus Graecis.';
const at = UNIT.indexOf(SECOND);
const SENTENCE = {
  refStart: 'tac. ann. 1.1', refEnd: 'tac. ann. 1.1', startIdx: 0, endIdx: 0, lineCount: 1,
  text: SECOND, sentenceText: SECOND, charStart: at, charEnd: at + SECOND.length,
  sentenceCount: 1, sentenceTotal: 3, startSentence: 1,
};
const WHOLE = { ...SENTENCE, text: UNIT, sentenceText: UNIT, charStart: null, charEnd: null, sentenceCount: 3 };

let calls;
beforeEach(() => {
  calls = [];
  setCollection('inscriptions', true);
  global.fetch = vi.fn((url, init) => {
    calls.push({ url: String(url), body: init?.body ? JSON.parse(init.body) : null });
    return Promise.resolve({ ok: true, json: () => Promise.resolve({ results: [] }) });
  });
});
afterEach(() => { cleanup(); delete global.fetch; });

const mount = (selection, initialTab) => render(
  <ResultsPanel selection={selection} language="la" work="tacitus.annales.part.1.tess"
                units={UNITS} initialTab={initialTab} />);

describe('Similar passages', () => {
  it('sends char_start and char_end for a sentence', async () => {
    mount(SENTENCE, 'similar');
    await waitFor(() => expect(calls.some((c) => c.url.startsWith('/api/passages/similar'))).toBe(true));
    const q = new URL(calls.find((c) => c.url.startsWith('/api/passages/similar')).url, 'http://x').searchParams;
    expect(q.get('char_start')).toBe(String(at));
    expect(q.get('char_end')).toBe(String(at + SECOND.length));
    expect(q.get('ref_start')).toBe('tac. ann. 1.1');
  });

  it('sends neither for the whole unit', async () => {
    mount(WHOLE, 'similar');
    await waitFor(() => expect(calls.some((c) => c.url.startsWith('/api/passages/similar'))).toBe(true));
    const q = new URL(calls.find((c) => c.url.startsWith('/api/passages/similar')).url, 'http://x').searchParams;
    expect(q.has('char_start')).toBe(false);
    expect(q.has('char_end')).toBe(false);
  });
});

describe('Parallels', () => {
  it('searches the sentence and sends no refs', async () => {
    mount(SENTENCE, 'verbal');
    await waitFor(() => expect(calls.some((c) => c.url === '/api/line-search')).toBe(true));
    const b = calls.find((c) => c.url === '/api/line-search').body;
    expect(b.query).toBe(SECOND);
    expect(b.refs).toBeUndefined();
  });

  it('searches the unit by its refs when the whole unit is selected', async () => {
    mount(WHOLE, 'verbal');
    await waitFor(() => expect(calls.some((c) => c.url === '/api/line-search')).toBe(true));
    const b = calls.find((c) => c.url === '/api/line-search').body;
    expect(b.query).toBe(UNIT);
    expect(b.refs).toEqual(['tac. ann. 1.1']);
  });
});

describe('Inscriptions and papyri section', () => {
  it('searches the sentence words', async () => {
    mount(SENTENCE, 'verbal');
    await waitFor(() => expect(calls.some((c) => c.body?.collection === 'documents')).toBe(true));
    expect(calls.find((c) => c.body?.collection === 'documents').body.query).toBe(SECOND);
  });

  it('searches the unit when the whole unit is selected', async () => {
    mount(WHOLE, 'verbal');
    await waitFor(() => expect(calls.some((c) => c.body?.collection === 'documents')).toBe(true));
    expect(calls.find((c) => c.body?.collection === 'documents').body.query).toBe(UNIT);
  });
});

describe('Translation and Reuse', () => {
  it('stay on the unit', async () => {
    mount(SENTENCE, 'translation');
    await waitFor(() => expect(calls.some((c) => c.url.startsWith('/api/translation'))).toBe(true));
    expect(decodeURIComponent(calls.find((c) => c.url.startsWith('/api/translation')).url)).toContain('refs=tac. ann. 1.1');
  });
});
