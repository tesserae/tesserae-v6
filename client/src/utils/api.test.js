import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import * as api from './api';

// The request each exported function sends: URL, method, body and the JSON
// content type. The table was recorded from the code before the functions were
// routed through one helper, and must stay the same.
const JSON_HEADERS = { 'Content-Type': 'application/json' };
const params = { source: 'a', target: 'b', language: 'la' };

const okBody = '{"ok":true}';

const sseResponse = () => {
  const chunk = new TextEncoder().encode('data: {"type":"complete","results":[]}\n');
  let sent = false;
  return {
    ok: true,
    status: 200,
    body: { getReader: () => ({ read: async () => (sent ? { done: true } : ((sent = true), { done: false, value: chunk })) }) },
  };
};

const jsonResponse = (text = okBody, status = 200) => ({
  ok: status >= 200 && status < 300,
  status,
  text: async () => text,
  json: async () => JSON.parse(text),
});

// [export name, call, expected url, method, body (parsed), has JSON content type]
const SHAPES = [
  ['fetchCorpus', () => api.fetchCorpus('la'), '/api/texts?language=la', 'GET'],
  ['fetchAuthors', () => api.fetchAuthors('grc'), '/api/authors?language=grc', 'GET'],
  ['fetchFusionDefaultWeights', () => api.fetchFusionDefaultWeights('la'), '/api/fusion-default-weights?language=la', 'GET'],
  ['fetchTexts', () => api.fetchTexts('vergil'), '/api/texts?author=vergil', 'GET'],
  ['fetchTextContent', () => api.fetchTextContent('t1'), '/api/text/t1', 'GET'],
  ['fetchProvenanceInfo', () => api.fetchProvenanceInfo('t1'), '/api/text/t1/provenance', 'GET'],
  ['searchTexts', () => api.searchTexts(params), '/api/search', 'POST', params],
  ['fetchResultPage', () => api.fetchResultPage('r 1', { offset: 0, limit: 50 }), '/api/search-results/r%201?offset=0&limit=50', 'GET'],
  ['fetchAllResults', () => api.fetchAllResults('r1'), '/api/search-results/r1/export', 'GET'],
  ['searchSemanticCross', () => api.searchSemanticCross(params), '/api/search', 'POST', { ...params, match_type: 'semantic_cross' }],
  ['searchHapax', () => api.searchHapax(params), '/api/hapax-search', 'POST', params],
  ['searchBigrams', () => api.searchBigrams(params), '/api/rare-bigram-search', 'POST', params],
  ['fetchCorpusRareWords', () => api.fetchCorpusRareWords('la', 5), '/api/rare-lemmata?language=la&max_occurrences=5', 'GET'],
  ['fetchCorpusRareBigrams', () => api.fetchCorpusRareBigrams('la'), '/api/rare-bigrams?language=la&max_occurrences=10', 'GET'],
  ['fetchWordOccurrences', () => api.fetchWordOccurrences('arma virum', 'la'), '/api/rare-word-locations/arma%20virum?language=la', 'GET'],
  ['fetchWordDefinition', () => api.fetchWordDefinition('arma', 'la'), '/api/rare-lemmata?lemma=arma&language=la', 'GET'],
  ['fetchRepoIntertexts', () => api.fetchRepoIntertexts({ page: 2, q: 'x' }), '/api/intertexts?page=2&q=x', 'GET'],
  ['fetchRepoStats', () => api.fetchRepoStats(), '/api/intertexts/stats', 'GET'],
  ['registerIntertext', () => api.registerIntertext({ a: 1 }), '/api/intertexts', 'POST', { a: 1 }],
  ['fetchMyIntertexts', () => api.fetchMyIntertexts(), '/api/intertexts/my', 'GET'],
  ['updateIntertext', () => api.updateIntertext(4, { a: 2 }), '/api/intertexts/4', 'PUT', { a: 2 }],
  ['deleteIntertext', () => api.deleteIntertext(4), '/api/intertexts/4', 'DELETE'],
  ['fetchAuthStatus', () => api.fetchAuthStatus(), '/api/auth/user', 'GET'],
  ['fetchLineSearch', () => api.fetchLineSearch({ query: 'arma', language: 'la' }), '/api/line-search?query=arma&language=la', 'GET'],
  ['searchCorpusForLemmas', () => api.searchCorpusForLemmas(['arma'], 't1', 'la'), '/api/corpus-search', 'POST',
    { lemmas: ['arma'], exclude_text: 't1', language: 'la' }],
  ['fetchSavedSearches', () => api.fetchSavedSearches(), '/api/auth/saved-searches', 'GET'],
  ['saveSearch', () => api.saveSearch('mine', params), '/api/auth/saved-searches', 'POST', { name: 'mine', params }],
  ['deleteSavedSearch', () => api.deleteSavedSearch(9), '/api/auth/saved-searches/9', 'DELETE'],
  ['wildcardSearch', () => api.wildcardSearch({ query: 'ar*' }), '/api/wildcard-search', 'POST', { query: 'ar*' }],
  ['fetchLanguages', () => api.fetchLanguages(), '/api/languages', 'GET'],
  ['fetchTranslationIndex', () => api.fetchTranslationIndex('la'), '/api/passages/translations?language=la', 'GET'],
  ['fetchTextDescriptions', () => api.fetchTextDescriptions('la'), '/api/text-descriptions?language=la', 'GET'],
  ['fetchStats', () => api.fetchStats(), '/api/stats', 'GET'],
  ['fetchTextHierarchy', () => api.fetchTextHierarchy('grc'), '/api/texts/hierarchy?language=grc', 'GET'],
  ['postLineSearch', () => api.postLineSearch({ query: 'arma' }), '/api/line-search', 'POST', { query: 'arma' }],
  ['getJson', () => api.getJson('/api/version'), '/api/version', 'GET'],
  ['postJsonTo', () => api.postJsonTo('/api/feedback', { message: 'hi' }), '/api/feedback', 'POST', { message: 'hi' }],
];

const STREAMS = [
  ['searchTextsStream', () => api.searchTextsStream(params), '/api/search-stream'],
  ['searchFusionStream', () => api.searchFusionStream(params), '/api/search-fusion'],
];

let fetchMock;
beforeEach(() => {
  fetchMock = vi.fn();
  vi.stubGlobal('fetch', fetchMock);
});
afterEach(() => vi.unstubAllGlobals());

const sent = () => {
  const [url, init = {}] = fetchMock.mock.calls[0];
  return { url, method: init.method || 'GET', body: init.body, headers: init.headers || {} };
};

describe('every exported function is covered', () => {
  it('lists each export once', () => {
    const covered = new Set([
      ...SHAPES.map((s) => s[0]), ...STREAMS.map((s) => s[0]),
      'createSearchId', 'requestSearchCancellation',
    ]);
    expect([...covered].sort()).toEqual(Object.keys(api).sort());
  });
});

describe('request shapes', () => {
  it.each(SHAPES)('%s', async (_name, call, url, method, body) => {
    fetchMock.mockResolvedValue(jsonResponse(_name === 'fetchAllResults' ? '{"results":[]}' : okBody));
    await call();
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const request = sent();
    expect(request.url).toBe(url);
    expect(request.method).toBe(method);
    if (body === undefined) {
      expect(request.body).toBeUndefined();
    } else {
      expect(JSON.parse(request.body)).toEqual(body);
      expect(request.headers['Content-Type']).toBe(JSON_HEADERS['Content-Type']);
    }
  });

  it.each(STREAMS)('%s', async (_name, call, url) => {
    fetchMock.mockResolvedValue(sseResponse());
    await call();
    const request = sent();
    expect(request.url).toBe(url);
    expect(request.method).toBe('POST');
    expect(JSON.parse(request.body)).toEqual(params);
    expect(request.headers['Content-Type']).toBe('application/json');
  });

  it('requestSearchCancellation posts the search id', () => {
    fetchMock.mockResolvedValue(jsonResponse());
    api.requestSearchCancellation('s1');
    const request = sent();
    expect(request.url).toBe('/api/search-cancel');
    expect(request.method).toBe('POST');
    expect(JSON.parse(request.body)).toEqual({ search_id: 's1' });
  });

  it('requestSearchCancellation sends nothing without an id', () => {
    api.requestSearchCancellation('');
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('createSearchId returns a fresh id each time', () => {
    expect(api.createSearchId()).not.toBe(api.createSearchId());
  });
});

describe('a server error is reported readably', () => {
  const html = '<!DOCTYPE html><html><body>Internal Server Error</body></html>';

  it.each(SHAPES)('%s: a 500 with an HTML body', async (_name, call) => {
    fetchMock.mockResolvedValue(jsonResponse(html, 500));
    const error = await call().then(() => null, (e) => e);
    expect(error).toBeInstanceOf(Error);
    expect(error.message).not.toMatch(/Unexpected token|JSON\.parse|is not valid JSON/);
    expect(error.message).toContain('500');
  });

  const PAGE_FUNCTIONS = ['postLineSearch', 'getJson', 'postJsonTo'];

  it.each(SHAPES.filter((s) => !PAGE_FUNCTIONS.includes(s[0])))('%s: a 400 carries the server message', async (_name, call) => {
    fetchMock.mockResolvedValue(jsonResponse('{"error":"offset must be a whole number"}', 400));
    const error = await call().then(() => null, (e) => e);
    expect(error).toBeInstanceOf(Error);
    expect(error.message).toContain('offset must be a whole number');
  });

  // Pages that show the server's own `error` field get the body back, as
  // they always did; a body that is not JSON still throws a readable message.
  it.each(SHAPES.filter((s) => PAGE_FUNCTIONS.includes(s[0])))('%s: a 400 comes back as the body', async (_name, call) => {
    fetchMock.mockResolvedValue(jsonResponse('{"error":"Provide query or line_text"}', 400));
    expect(await call()).toEqual({ error: 'Provide query or line_text' });
  });

  it.each(STREAMS)('%s: a 500 names the status', async (_name, call) => {
    fetchMock.mockResolvedValue({ ...jsonResponse(html, 500), body: null });
    const error = await call().then(() => null, (e) => e);
    expect(error.message).toContain('500');
  });

  it('a 405 from the stream still contains 405 (the search hook falls back on it)', async () => {
    fetchMock.mockResolvedValue({ ...jsonResponse(html, 405), body: null });
    const error = await api.searchTextsStream(params).then(() => null, (e) => e);
    expect(error.message).toContain('405');
  });

  it('an empty body is reported', async () => {
    fetchMock.mockResolvedValue(jsonResponse('', 200));
    const error = await api.fetchCorpus('la').then(() => null, (e) => e);
    expect(error.message).toMatch(/Empty response/);
  });
});

describe('valid answers are returned as before', () => {
  it('fetchAuthStatus adds the display name and flag', async () => {
    fetchMock.mockResolvedValue(jsonResponse('{"user":{"first_name":"A","last_name":"B"}}'));
    const data = await api.fetchAuthStatus();
    expect(data.authenticated).toBe(true);
    expect(data.user.name).toBe('A B');
  });

  it('fetchAuthStatus without a user is not authenticated', async () => {
    fetchMock.mockResolvedValue(jsonResponse('{"user":null}'));
    expect((await api.fetchAuthStatus()).authenticated).toBe(false);
  });

  it('fetchAllResults returns the rows', async () => {
    fetchMock.mockResolvedValue(jsonResponse('{"results":[1,2]}'));
    expect(await api.fetchAllResults('r1')).toEqual([1, 2]);
  });
});
