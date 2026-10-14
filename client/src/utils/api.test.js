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
  blob: async () => 'blob',
});

// The admin pages and the assistant dock: the request each function sends is the
// request the page sent before the call moved here (URL, method, body).
const AH = { 'X-Admin-Key': 'k' };
const ADMIN_SHAPES = [
  ['fetchAdminSession', () => api.fetchAdminSession(), '/api/admin/me', 'GET'],
  ['adminLogin', () => api.adminLogin('pw', 'a@b.edu'), '/api/admin/login', 'POST', { password: 'pw', email: 'a@b.edu' }],
  ['adminResetPassword', () => api.adminResetPassword({ current_password: 'a', new_password: 'b', confirm_password: 'b' }),
    '/api/admin/reset-password', 'POST', { current_password: 'a', new_password: 'b', confirm_password: 'b' }],
  ['adminLogout', () => api.adminLogout(), '/api/admin/logout', 'POST'],
  ['fetchAdminFeedback', () => api.fetchAdminFeedback(), '/api/admin/feedback', 'GET'],
  ['fetchCorpusStatus', () => api.fetchCorpusStatus(), '/api/corpus-status', 'GET'],
  ['fetchAdminAnalytics', () => api.fetchAdminAnalytics(), '/api/admin/analytics', 'GET'],
  ['fetchLemmaCacheStats', () => api.fetchLemmaCacheStats(), '/api/admin/lemma-cache/stats', 'GET'],
  ['fetchSearchCacheStats', () => api.fetchSearchCacheStats(), '/api/admin/search-cache/stats', 'GET'],
  ['fetchFrequencyCacheStats', () => api.fetchFrequencyCacheStats(), '/api/admin/frequency-cache/stats', 'GET'],
  ['fetchBigramCacheStats', () => api.fetchBigramCacheStats(), '/api/admin/bigram-cache/stats', 'GET'],
  ['fetchAdminUsage', () => api.fetchAdminUsage(), '/api/admin/usage', 'GET'],
  ['fetchAdminAnalyticsJson', () => api.fetchAdminAnalyticsJson(), '/api/admin/analytics', 'GET'],
  ['fetchAdminPaths', () => api.fetchAdminPaths(30), '/api/admin/paths?days=30', 'GET'],
  ['fetchAdminUsers', () => api.fetchAdminUsers(AH), '/api/admin/users', 'GET'],
  ['fetchAdminRoles', () => api.fetchAdminRoles(AH), '/api/admin/roles', 'GET'],
  ['createAdminUser', () => api.createAdminUser(AH, { email: 'e' }), '/api/admin/users', 'POST', { email: 'e' }],
  ['changeAdminUserRole', () => api.changeAdminUserRole(AH, 7, 'ADMIN', 'add'), '/api/admin/users/7/roles', 'POST', { role: 'ADMIN', action: 'add' }],
  ['deleteAdminUser', () => api.deleteAdminUser(AH, 7), '/api/admin/users/7', 'DELETE'],
  ['fetchAdminRequests', () => api.fetchAdminRequests('page=1'), '/api/admin/requests?page=1', 'GET'],
  ['fetchAdminRequest', () => api.fetchAdminRequest(3), '/api/admin/requests/3', 'GET'],
  ['approveAdminRequestQuick', () => api.approveAdminRequestQuick(AH, 3), '/api/admin/requests/3/approve', 'POST'],
  ['updateAdminRequest', () => api.updateAdminRequest(AH, 3, { status: 'approved' }), '/api/admin/requests/3', 'PUT', { status: 'approved' }],
  ['deleteAdminRequest', () => api.deleteAdminRequest(AH, 3), '/api/admin/requests/3', 'DELETE'],
  ['approveAdminRequest', () => api.approveAdminRequest(AH, 3, { content: 'c', overwrite: true }), '/api/admin/requests/3/approve', 'POST',
    { content: 'c', overwrite: true }],
  ['fetchAdminSources', () => api.fetchAdminSources(AH), '/api/admin/sources', 'GET'],
  ['updateAdminSource', () => api.updateAdminSource(AH, 5, { work: 'w' }), '/api/admin/sources/5', 'PUT', { work: 'w' }],
  ['deleteAdminSource', () => api.deleteAdminSource(AH, 5), '/api/admin/sources/5', 'DELETE'],
  ['addAdminSource', () => api.addAdminSource(AH, { work: 'w' }), '/api/admin/sources', 'POST', { work: 'w' }],
  ['fetchAdminSettings', () => api.fetchAdminSettings(AH), '/api/admin/settings', 'GET'],
  ['saveAdminSettings', () => api.saveAdminSettings(AH, { notification_emails: 'a@b' }), '/api/admin/settings', 'POST', { notification_emails: 'a@b' }],
  ['fetchAdminAuditLog', () => api.fetchAdminAuditLog(AH), '/api/admin/audit-log?limit=100', 'GET'],
  ['clearAdminCache', () => api.clearAdminCache('/api/admin/lemma-cache/clear', AH), '/api/admin/lemma-cache/clear', 'POST', {}],
  ['recalculateFrequencies', () => api.recalculateFrequencies(AH), '/api/frequencies/recalculate', 'POST'],
  ['buildBigramCache', () => api.buildBigramCache(AH, 'la'), '/api/admin/bigram-cache/build', 'POST', { language: 'la' }],
  ['fetchBigramCacheStatsWithHeaders', () => api.fetchBigramCacheStatsWithHeaders(AH), '/api/admin/bigram-cache/stats', 'GET'],
  ['fetchDictionaryReview', () => api.fetchDictionaryReview('pending', 25, 50), '/api/admin/dictionary-review?status=pending&limit=25&offset=50', 'GET'],
  ['updateDictionaryReviewEntry', () => api.updateDictionaryReviewEntry(8, 'accepted'), '/api/admin/dictionary-review/8', 'PUT', { status: 'accepted' }],
  ['reloadDictionaryReview', () => api.reloadDictionaryReview(), '/api/admin/dictionary-review/reload', 'POST'],
  ['fetchDictionaryReviewExport', () => api.fetchDictionaryReviewExport(), '/api/admin/dictionary-review/export', 'GET'],
  ['fetchTextGenres', () => api.fetchTextGenres(), '/api/admin/text-genres', 'GET'],
  ['saveTextGenres', () => api.saveTextGenres([{ filename: 'f' }]), '/api/admin/text-genres', 'POST', { updates: [{ filename: 'f' }] }],
  ['fetchConcurrency', () => api.fetchConcurrency(), '/api/admin/concurrency', 'GET'],
  ['fetchActiveSearches', () => api.fetchActiveSearches(), '/api/admin/concurrency/active', 'GET'],
  ['killActiveSearch', () => api.killActiveSearch('s1'), '/api/admin/concurrency/active/s1', 'DELETE'],
  ['updateConcurrency', () => api.updateConcurrency({ max_searches: 4 }), '/api/admin/concurrency', 'PUT', { max_searches: 4 }],
  ['resetConcurrency', () => api.resetConcurrency(), '/api/admin/concurrency/reset', 'POST', {}],
  ['setStressTest', () => api.setStressTest(true), '/api/admin/concurrency/stress-test', 'POST', { enabled: true }],
  ['killAllActiveSearches', () => api.killAllActiveSearches(), '/api/admin/concurrency/active/all', 'DELETE'],
  ['updateAdminFeedback', () => api.updateAdminFeedback(2, 'responded'), '/api/admin/feedback/2', 'PUT', { status: 'responded' }],
  ['fetchAdminCorpusTexts', () => api.fetchAdminCorpusTexts(AH, 'la'), '/api/admin/corpus-texts?language=la', 'GET'],
  ['saveTextMetadata', () => api.saveTextMetadata(AH, 't1', { era: 'x' }), '/api/admin/text-metadata/t1', 'PUT', { era: 'x' }],
  ['fetchAssistantStatus', () => api.fetchAssistantStatus(), '/api/assistant/status', 'GET'],
];

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
      ...SHAPES.map((s) => s[0]), ...ADMIN_SHAPES.map((s) => s[0]), ...STREAMS.map((s) => s[0]),
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

  it.each(ADMIN_SHAPES)('%s', async (_name, call, url, method, body) => {
    fetchMock.mockResolvedValue(jsonResponse());
    await call();
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const request = sent();
    expect(request.url).toBe(url);
    expect(request.method).toBe(method);
    if (body === undefined) {
      expect(request.body).toBeUndefined();
    } else {
      expect(JSON.parse(request.body)).toEqual(body);
      expect(request.headers['Content-Type']).toBe('application/json');
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

describe('admin requests', () => {
  const okOutcome = async (call) => {
    fetchMock.mockResolvedValue(jsonResponse());
    await call();
    return fetchMock.mock.calls.at(-1)[1] || {};
  };

  it('keeps the credentials option and merges the admin headers after the JSON type', async () => {
    const init = await okOutcome(() => api.createAdminUser(AH, { email: 'e' }));
    expect(init.credentials).toBe('include');
    expect(init.headers).toEqual({ 'Content-Type': 'application/json', 'X-Admin-Key': 'k' });
    const read = await okOutcome(() => api.fetchAdminSources(AH));
    expect(read.headers).toBe(AH);
    expect(read.credentials).toBeUndefined();
  });

  it('keeps the Accept header and no credentials on the analytics reads', async () => {
    const init = await okOutcome(() => api.fetchAdminAnalyticsJson());
    expect(init).toEqual({ headers: { Accept: 'application/json' } });
  });

  it('sends a bare fetch(url) for the corpus status', async () => {
    fetchMock.mockResolvedValue(jsonResponse());
    await api.fetchCorpusStatus();
    expect(fetchMock.mock.calls[0]).toEqual(['/api/corpus-status']);
  });

  it('returns ok, status and the parsed body', async () => {
    fetchMock.mockResolvedValue(jsonResponse('{"users":[1]}'));
    expect(await api.fetchAdminUsers(AH)).toEqual({ ok: true, status: 200, data: { users: [1] } });
  });

  it('keeps a JSON error body so the page can show the server message', async () => {
    fetchMock.mockResolvedValue(jsonResponse('{"error":"Role is required"}', 400));
    expect(await api.changeAdminUserRole(AH, 1, '', 'add')).toEqual({
      ok: false, status: 400, data: { error: 'Role is required' },
    });
  });

  it('turns an error page into a readable message instead of a JSON parse error', async () => {
    fetchMock.mockResolvedValue(jsonResponse('<html><body>502 Bad Gateway</body></html>', 502));
    const outcome = await api.saveAdminSettings(AH, {});
    expect(outcome.ok).toBe(false);
    expect(outcome.status).toBe(502);
    expect(outcome.data.error).toMatch(/^502 from \/api\/admin\/settings: <html>/);
  });

  it('names the status when an error comes with an empty body', async () => {
    fetchMock.mockResolvedValue(jsonResponse('', 500));
    expect((await api.fetchAdminAuditLog(AH)).data.error).toBe('500 from /api/admin/audit-log?limit=100');
  });

  it('throws a readable message when a successful answer is not JSON', async () => {
    fetchMock.mockResolvedValue(jsonResponse('<html>login</html>'));
    await expect(api.fetchAdminSession()).rejects.toThrow(/^Bad JSON \(\d+b\) from \/api\/admin\/me: <html>login/);
  });

  it('treats an empty successful body as an empty object', async () => {
    fetchMock.mockResolvedValue(jsonResponse(''));
    expect((await api.adminLogout()).data).toEqual({});
  });

  it('reads the dictionary export as a blob, and names the failure', async () => {
    fetchMock.mockResolvedValue(jsonResponse());
    expect(await api.fetchDictionaryReviewExport()).toBe('blob');
    fetchMock.mockResolvedValue(jsonResponse('<html>oops</html>', 500));
    await expect(api.fetchDictionaryReviewExport()).rejects.toThrow(/^500 from \/api\/admin\/dictionary-review\/export/);
  });
});
