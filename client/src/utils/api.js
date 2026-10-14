const API_BASE = '/api';

export const createSearchId = () => crypto.randomUUID();

export const requestSearchCancellation = (searchId) => {
  if (!searchId) return;
  // Keep this independent of the aborted request so it can still be sent when
  // the page is navigating away or the original fetch has been cancelled.
  void fetch(`${API_BASE}/search-cancel`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'same-origin',
    keepalive: true,
    body: JSON.stringify({ search_id: searchId }),
  }).catch(() => {});
};

const previewOf = (text) => (text.length > 120 ? text.substring(0, 120) + '...' : text);

// The server's own message when the body is JSON with an `error` field.
const serverMessage = (text) => {
  try {
    const body = JSON.parse(text);
    if (body && typeof body.error === 'string') return body.error;
  } catch {
    // not JSON
  }
  return '';
};

// The server's message, else the fallback, else the status and a short preview.
const errorMessage = (url, status, text, fallback) => (
  serverMessage(text) || fallback
  || (text ? `${status} from ${url}: ${previewOf(text)}` : `${status} from ${url}`)
);

// The one careful request: checks response.ok, reads the text first, and
// reports a bad payload with a preview. `init` goes to fetch unchanged.
// `fallback` replaces the status line when the server sent no message.
// `errorBody: true` is for pages that show the server's own `error` field
// themselves: an error status whose body is JSON with an `error` field comes
// back as that body, as it always did, instead of being thrown.
const jsonRequest = async (url, init, { fallback, errorBody = false } = {}) => {
  // No second argument when there is no init, exactly as a bare fetch(url).
  const response = await (init === undefined ? fetch(url) : fetch(url, init));
  const text = await response.text();
  if (!response.ok) {
    if (errorBody && serverMessage(text)) return JSON.parse(text);
    throw new Error(errorMessage(url, response.status, text, fallback ? fallback(response.status) : undefined));
  }
  if (!text) {
    throw new Error(`Empty response from ${url}`);
  }
  try {
    return JSON.parse(text);
  } catch {
    throw new Error(`Bad JSON (${text.length}b) from ${url}: ${previewOf(text)}`);
  }
};

const jsonFetch = (url) => jsonRequest(url, {
  headers: { 'Accept': 'application/json' },
  credentials: 'same-origin'
});

const postJson = (path, body, signal, options) => jsonRequest(`${API_BASE}${path}`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(body),
  signal
}, options);

// A failed stream request: keep "<label>: <status>" (the search hook looks for
// the 405) and add the server's message when it sent one.
const streamError = async (response, label) => {
  const message = serverMessage(await response.text().catch(() => ''));
  return new Error(message ? `${label}: ${response.status}: ${message}` : `${label}: ${response.status}`);
};

export const fetchCorpus = async (language) => {
  return jsonFetch(`${API_BASE}/texts?language=${language}`);
};

export const fetchAuthors = async (language) => {
  return jsonFetch(`${API_BASE}/authors?language=${language}`);
};

// Default per-channel fusion weights for a language (Advanced UI pre-fill).
export const fetchFusionDefaultWeights = async (language) => {
  return jsonFetch(`${API_BASE}/fusion-default-weights?language=${language}`);
};

export const fetchTexts = async (author) => {
  return jsonFetch(`${API_BASE}/texts?author=${author}`);
};

export const fetchTextContent = async (textId) => {
  return jsonRequest(`${API_BASE}/text/${textId}`);
};

export const fetchProvenanceInfo = async (textId) => {
  return jsonRequest(`${API_BASE}/text/${textId}/provenance`);
};

export const searchTexts = async (params, signal) => {
  return postJson('/search', params, signal);
};

export const searchTextsStream = async (params, onProgress, signal, onQueued) => {
  const response = await fetch(`${API_BASE}/search-stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params),
    signal
  });

  if (!response.ok) {
    throw await streamError(response, 'Search failed');
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  let finalResult = null;

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop() || '';

    for (const line of lines) {
      if (line.startsWith('data: ')) {
        try {
          const data = JSON.parse(line.slice(6));
          if (data.type === 'progress') {
            if (onProgress) {
              onProgress(data.step, data.detail, data.elapsed, data);
            }
          } else if (data.type === 'queued') {
            if (onQueued) {
              onQueued(data.detail, data.wait_time);
            }
          } else if (data.type === 'complete') {
            finalResult = data;
          } else if (data.type === 'cancelled') {
            throw new Error(data.message || 'Search terminated by administrator');
          } else if (data.type === 'error') {
            throw new Error(data.message);
          }
        } catch (e) {
          if (e.message && !e.message.includes('JSON')) {
            throw e;
          }
        }
      }
    }
  }

  if (!finalResult) {
    throw new Error(
      'Connection to server was lost during search. ' +
      'The search may still be running in the background — please try again in a few minutes.'
    );
  }

  return finalResult;
};

export const searchFusionStream = async (params, onProgress, signal, onIntermediate, onQueued) => {
  const response = await fetch(`${API_BASE}/search-fusion`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params),
    signal
  });

  if (!response.ok) {
    throw await streamError(response, 'Fusion search failed');
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  let finalResult = null;

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop() || '';

    for (const line of lines) {
      if (line.startsWith('data: ')) {
        try {
          const data = JSON.parse(line.slice(6));
          if (data.type === 'progress') {
            if (onProgress) {
              onProgress(data.step, data.detail, data.elapsed, data);
            }
          } else if (data.type === 'queued') {
            if (onQueued) {
              onQueued(data.detail, data.wait_time);
            }
          } else if (data.type === 'intermediate') {
            if (onIntermediate) {
              onIntermediate(data);
            }
          } else if (data.type === 'complete') {
            finalResult = data;
          } else if (data.type === 'cancelled') {
            throw new Error(data.message || 'Search terminated by administrator');
          } else if (data.type === 'error') {
            throw new Error(data.message);
          }
        } catch (e) {
          if (e.message && !e.message.includes('JSON')) {
            throw e;
          }
        }
      }
    }
  }

  if (!finalResult) {
    throw new Error(
      'Connection to server was lost during search. ' +
      'The search may still be running in the background — please try again in a few minutes.'
    );
  }

  return finalResult;
};

// Pages of a finished, server-held search (see backend/result_pages.py).
// `query` carries offset/limit/sort and the optional chart filter.
export const fetchResultPage = async (resultId, query, signal) => {
  return jsonRequest(
    `${API_BASE}/search-results/${encodeURIComponent(resultId)}?${new URLSearchParams(query)}`,
    { signal, credentials: 'same-origin' },
    { fallback: (status) => `Could not load results (${status})` });
};

// Every stored row in score order, fetched only when an export is requested.
export const fetchAllResults = async (resultId) => {
  const data = await jsonRequest(
    `${API_BASE}/search-results/${encodeURIComponent(resultId)}/export`,
    { credentials: 'same-origin' },
    { fallback: (status) => `Could not load results (${status})` });
  return data.results || [];
};

export const searchSemanticCross = async (params, signal) => {
  return postJson('/search', { ...params, match_type: 'semantic_cross' }, signal);
};

export const searchHapax = async (params, signal) => {
  return postJson('/hapax-search', params, signal);
};

export const searchBigrams = async (params, signal) => {
  return postJson('/rare-bigram-search', params, signal);
};

export const fetchCorpusRareWords = async (language, maxOccurrences) => {
  return jsonRequest(`${API_BASE}/rare-lemmata?language=${language}&max_occurrences=${maxOccurrences}`);
};

export const fetchCorpusRareBigrams = async (language, maxOccurrences = 10) => {
  return jsonRequest(`${API_BASE}/rare-bigrams?language=${language}&max_occurrences=${maxOccurrences}`);
};

export const fetchWordOccurrences = async (lemma, language) => {
  return jsonRequest(`${API_BASE}/rare-word-locations/${encodeURIComponent(lemma)}?language=${language}`);
};

export const fetchWordDefinition = async (lemma, language) => {
  return jsonRequest(`${API_BASE}/rare-lemmata?lemma=${encodeURIComponent(lemma)}&language=${language}`);
};

export const fetchRepoIntertexts = async (params) => {
  const query = new URLSearchParams(params).toString();
  return jsonRequest(`${API_BASE}/intertexts?${query}`);
};

export const fetchRepoStats = async () => {
  return jsonRequest(`${API_BASE}/intertexts/stats`);
};

export const registerIntertext = async (data) => {
  return postJson('/intertexts', data);
};

export const fetchMyIntertexts = async () => {
  return jsonRequest(`${API_BASE}/intertexts/my`);
};

export const updateIntertext = async (id, data) => {
  return jsonRequest(`${API_BASE}/intertexts/${id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data)
  });
};

export const deleteIntertext = async (id) => {
  return jsonRequest(`${API_BASE}/intertexts/${id}`, { method: 'DELETE' });
};

export const fetchAuthStatus = async () => {
  const data = await jsonRequest(`${API_BASE}/auth/user`);
  if (data.user) {
    const firstName = data.user.first_name || '';
    const lastName = data.user.last_name || '';
    data.user.name = data.user.orcid_name || `${firstName} ${lastName}`.trim() || 'Account';
    data.authenticated = true;
  } else {
    data.authenticated = false;
  }
  return data;
};

export const fetchLineSearch = async (params) => {
  const query = new URLSearchParams(params).toString();
  return jsonRequest(`${API_BASE}/line-search?${query}`);
};

export const searchCorpusForLemmas = async (lemmas, excludeText, language) => {
  return postJson('/corpus-search', { lemmas, exclude_text: excludeText, language });
};

export const fetchSavedSearches = async () => {
  return jsonRequest(`${API_BASE}/auth/saved-searches`);
};

export const saveSearch = async (name, params) => {
  return postJson('/auth/saved-searches', { name, params });
};

export const deleteSavedSearch = async (id) => {
  return jsonRequest(`${API_BASE}/auth/saved-searches/${id}`, { method: 'DELETE' });
};

export const wildcardSearch = async (params, signal) => {
  return postJson('/wildcard-search', params, signal);
};

// Languages the server holds, with the feature switches the pages read.
export const fetchLanguages = async () => {
  return jsonRequest(`${API_BASE}/languages`);
};

// The passage-translation index for a language (works with aligned English).
export const fetchTranslationIndex = async (language) => {
  return jsonRequest(`${API_BASE}/passages/translations?language=${language}`);
};

export const fetchTextDescriptions = async (language) => {
  return jsonRequest(`${API_BASE}/text-descriptions?language=${language}`);
};

export const fetchStats = async () => {
  return jsonRequest(`${API_BASE}/stats`);
};

export const fetchTextHierarchy = async (language) => {
  return jsonRequest(`${API_BASE}/texts/hierarchy?language=${language}`);
};

// Line Search and the Reader's word search. The pages show the server's own
// `error` field (for example "Provide query or line_text"), so an error
// status with that field comes back as the body.
export const postLineSearch = async (params, signal) => {
  return postJson('/line-search', params, signal, { errorBody: true });
};

// Generic reads and writes for pages whose URL is built in the page. `url`
// is the full path (starting /api/...). These pages show the server's own
// `error` field themselves, so an error status with that field comes back as
// the body (see jsonRequest); anything else that is not JSON throws a
// readable message.
export const getJson = async (url, { signal, credentials } = {}) => {
  const init = {};
  if (signal) init.signal = signal;
  if (credentials) init.credentials = credentials;
  return jsonRequest(url, Object.keys(init).length ? init : undefined, { errorBody: true });
};

export const postJsonTo = async (url, body, { signal } = {}) => {
  return jsonRequest(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    signal
  }, { errorBody: true });
};

// ---------------------------------------------------------------------------
// Admin pages and the assistant dock.
//
// These pages branch on the response status themselves (a failed save shows the
// server's message, a failed side load is skipped), so `adminRequest` does not
// throw on an error status. It returns { ok, status, data } where `data` is the
// parsed JSON body, `{}` for an empty successful body, and `{ error: <readable
// message> }` when an error status came with something that is not JSON (an
// Apache or proxy error page). A successful status with a body that is not JSON
// throws the same readable "Bad JSON" message as the helpers above. Each
// function below sends exactly the URL, method, headers and body the page sent
// before it was moved here.
// ---------------------------------------------------------------------------
const adminRequest = async (url, init) => {
  const response = await (init === undefined ? fetch(url) : fetch(url, init));
  const text = await response.text();
  let data;
  try {
    data = text ? JSON.parse(text) : {};
  } catch {
    if (response.ok) {
      throw new Error(`Bad JSON (${text.length}b) from ${url}: ${previewOf(text)}`);
    }
    data = { error: errorMessage(url, response.status, text) };
    return { ok: false, status: response.status, data };
  }
  if (!response.ok && !text) {
    data = { error: errorMessage(url, response.status, text) };
  }
  return { ok: response.ok, status: response.status, data };
};

const JSON_TYPE = { 'Content-Type': 'application/json' };

// Sign-in and session
export const fetchAdminSession = () => adminRequest('/api/admin/me', { credentials: 'include' });

export const adminLogin = (password, email) => adminRequest('/api/admin/login', {
  method: 'POST',
  headers: { ...JSON_TYPE },
  body: JSON.stringify({ password, email }),
  credentials: 'include'
});

export const adminResetPassword = (body) => adminRequest('/api/admin/reset-password', {
  method: 'POST',
  headers: { ...JSON_TYPE },
  credentials: 'include',
  body: JSON.stringify(body)
});

export const adminLogout = () => adminRequest('/api/admin/logout', {
  method: 'POST',
  credentials: 'include'
});

// The admin overview loads these eight together.
export const fetchAdminFeedback = () => adminRequest('/api/admin/feedback', { credentials: 'include' });
export const fetchCorpusStatus = () => adminRequest('/api/corpus-status');
export const fetchAdminAnalytics = () => adminRequest('/api/admin/analytics', { credentials: 'include' });
export const fetchLemmaCacheStats = () => adminRequest('/api/admin/lemma-cache/stats', { credentials: 'include' });
export const fetchSearchCacheStats = () => adminRequest('/api/admin/search-cache/stats', { credentials: 'include' });
export const fetchFrequencyCacheStats = () => adminRequest('/api/admin/frequency-cache/stats', { credentials: 'include' });
export const fetchBigramCacheStats = () => adminRequest('/api/admin/bigram-cache/stats', { credentials: 'include' });
export const fetchAdminUsage = () => adminRequest('/api/admin/usage', { credentials: 'include' });

// Analytics tab (no credentials option, an Accept header)
export const fetchAdminAnalyticsJson = () => adminRequest('/api/admin/analytics', {
  headers: { 'Accept': 'application/json' }
});
export const fetchAdminPaths = (days = 30) => adminRequest(`/api/admin/paths?days=${days}`, {
  headers: { 'Accept': 'application/json' }
});

// Users tab
export const fetchAdminUsers = (authHeaders) => adminRequest('/api/admin/users', {
  headers: authHeaders, credentials: 'include'
});
export const fetchAdminRoles = (authHeaders) => adminRequest('/api/admin/roles', {
  headers: authHeaders, credentials: 'include'
});
export const createAdminUser = (authHeaders, user) => adminRequest('/api/admin/users', {
  method: 'POST',
  headers: { ...JSON_TYPE, ...authHeaders },
  credentials: 'include',
  body: JSON.stringify(user)
});
export const changeAdminUserRole = (authHeaders, userId, role, action) => adminRequest(`/api/admin/users/${userId}/roles`, {
  method: 'POST',
  headers: { ...JSON_TYPE, ...authHeaders },
  credentials: 'include',
  body: JSON.stringify({ role, action })
});
export const deleteAdminUser = (authHeaders, userId) => adminRequest(`/api/admin/users/${userId}`, {
  method: 'DELETE',
  headers: { ...authHeaders },
  credentials: 'include'
});

// Text requests tab
export const fetchAdminRequests = (params, signal) => adminRequest(`/api/admin/requests?${params}`, {
  credentials: 'include', signal
});
export const fetchAdminRequest = (id, signal) => adminRequest(`/api/admin/requests/${id}`, {
  credentials: 'include', signal
});
export const approveAdminRequestQuick = (authHeaders, id) => adminRequest(`/api/admin/requests/${id}/approve`, {
  method: 'POST',
  headers: authHeaders
});
export const updateAdminRequest = (authHeaders, id, body) => adminRequest(`/api/admin/requests/${id}`, {
  method: 'PUT',
  headers: { ...JSON_TYPE, ...authHeaders },
  body: JSON.stringify(body)
});
export const deleteAdminRequest = (authHeaders, id) => adminRequest(`/api/admin/requests/${id}`, {
  method: 'DELETE',
  headers: authHeaders
});
export const approveAdminRequest = (authHeaders, id, body) => adminRequest(`/api/admin/requests/${id}/approve`, {
  method: 'POST',
  headers: { ...JSON_TYPE, ...authHeaders },
  body: JSON.stringify(body)
});

// Sources tab
export const fetchAdminSources = (authHeaders) => adminRequest('/api/admin/sources', { headers: authHeaders });
export const updateAdminSource = (authHeaders, id, updates) => adminRequest(`/api/admin/sources/${id}`, {
  method: 'PUT',
  headers: { ...JSON_TYPE, ...authHeaders },
  body: JSON.stringify(updates)
});
export const deleteAdminSource = (authHeaders, id) => adminRequest(`/api/admin/sources/${id}`, {
  method: 'DELETE',
  headers: authHeaders
});
export const addAdminSource = (authHeaders, source) => adminRequest('/api/admin/sources', {
  method: 'POST',
  headers: { ...JSON_TYPE, ...authHeaders },
  body: JSON.stringify(source)
});

// Settings and audit tabs
export const fetchAdminSettings = (authHeaders) => adminRequest('/api/admin/settings', { headers: authHeaders });
export const saveAdminSettings = (authHeaders, settings) => adminRequest('/api/admin/settings', {
  method: 'POST',
  headers: { ...JSON_TYPE, ...authHeaders },
  body: JSON.stringify(settings)
});
export const fetchAdminAuditLog = (authHeaders) => adminRequest('/api/admin/audit-log?limit=100', { headers: authHeaders });

// Cache tab
export const clearAdminCache = (endpoint, authHeaders) => adminRequest(endpoint, {
  method: 'POST',
  headers: { ...JSON_TYPE, ...authHeaders },
  body: JSON.stringify({})
});
export const recalculateFrequencies = (authHeaders) => adminRequest('/api/frequencies/recalculate', {
  method: 'POST',
  headers: authHeaders
});
export const buildBigramCache = (authHeaders, language) => adminRequest('/api/admin/bigram-cache/build', {
  method: 'POST',
  headers: { ...JSON_TYPE, ...authHeaders },
  body: JSON.stringify({ language })
});
export const fetchBigramCacheStatsWithHeaders = (authHeaders) => adminRequest('/api/admin/bigram-cache/stats', {
  headers: authHeaders
});

// Dictionary review tab
export const fetchDictionaryReview = (status, limit, offset) => adminRequest(
  `/api/admin/dictionary-review?status=${status}&limit=${limit}&offset=${offset}`,
  { credentials: 'include' }
);
export const updateDictionaryReviewEntry = (id, status) => adminRequest(`/api/admin/dictionary-review/${id}`, {
  method: 'PUT',
  credentials: 'include',
  headers: { ...JSON_TYPE },
  body: JSON.stringify({ status })
});
export const reloadDictionaryReview = () => adminRequest('/api/admin/dictionary-review/reload', {
  method: 'POST',
  credentials: 'include'
});
// The accepted entries as a CSV file: returned as a Blob.
export const fetchDictionaryReviewExport = async () => {
  const url = '/api/admin/dictionary-review/export';
  const response = await fetch(url, { credentials: 'include' });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(errorMessage(url, response.status, text));
  }
  return response.blob();
};

// Genre classification tab
export const fetchTextGenres = () => adminRequest('/api/admin/text-genres', { credentials: 'include' });
export const saveTextGenres = (updates) => adminRequest('/api/admin/text-genres', {
  method: 'POST',
  credentials: 'include',
  headers: { ...JSON_TYPE },
  body: JSON.stringify({ updates })
});

// Performance tab
export const fetchConcurrency = () => adminRequest('/api/admin/concurrency', { credentials: 'include' });
export const fetchActiveSearches = () => adminRequest('/api/admin/concurrency/active', { credentials: 'include' });
export const killActiveSearch = (slotId) => adminRequest(`/api/admin/concurrency/active/${slotId}`, {
  method: 'DELETE',
  credentials: 'include'
});
export const updateConcurrency = (settings) => adminRequest('/api/admin/concurrency', {
  method: 'PUT',
  headers: { ...JSON_TYPE },
  credentials: 'include',
  body: JSON.stringify(settings)
});
export const resetConcurrency = () => adminRequest('/api/admin/concurrency/reset', {
  method: 'POST',
  headers: { ...JSON_TYPE },
  credentials: 'include',
  body: JSON.stringify({})
});
export const setStressTest = (enabled) => adminRequest('/api/admin/concurrency/stress-test', {
  method: 'POST',
  headers: { ...JSON_TYPE },
  credentials: 'include',
  body: JSON.stringify({ enabled })
});
export const killAllActiveSearches = () => adminRequest('/api/admin/concurrency/active/all', {
  method: 'DELETE',
  credentials: 'include'
});

// Feedback and metadata tabs
export const updateAdminFeedback = (feedbackId, status) => adminRequest(`/api/admin/feedback/${feedbackId}`, {
  method: 'PUT',
  credentials: 'include',
  headers: { ...JSON_TYPE },
  body: JSON.stringify({ status })
});
export const fetchAdminCorpusTexts = (authHeaders, language) => adminRequest(
  `/api/admin/corpus-texts${language ? `?language=${language}` : ''}`,
  { headers: authHeaders }
);
export const saveTextMetadata = (authHeaders, textId, fields) => adminRequest(`/api/admin/text-metadata/${textId}`, {
  method: 'PUT',
  headers: { ...JSON_TYPE, ...authHeaders },
  body: JSON.stringify(fields)
});

// The assistant dock asks once whether the assistant is available.
export const fetchAssistantStatus = () => jsonRequest('/api/assistant/status');
