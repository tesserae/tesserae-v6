const API_BASE = '/api';

export const fetchCorpus = async (language) => {
  const response = await fetch(`${API_BASE}/texts?language=${language}`);
  return response.json();
};

export const fetchAuthors = async (language) => {
  const response = await fetch(`${API_BASE}/authors?language=${language}`);
  return response.json();
};

export const fetchTexts = async (author) => {
  const response = await fetch(`${API_BASE}/texts?author=${author}`);
  return response.json();
};

export const fetchTextContent = async (textId) => {
  const response = await fetch(`${API_BASE}/text/${textId}`);
  return response.json();
};

export const fetchProvenanceInfo = async (textId) => {
  const response = await fetch(`${API_BASE}/text/${textId}/provenance`);
  return response.json();
};

export const searchTexts = async (params, signal) => {
  const response = await fetch(`${API_BASE}/search`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params),
    signal
  });
  return response.json();
};

export const searchTextsStream = async (params, onProgress, signal) => {
  const response = await fetch(`${API_BASE}/search-stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params),
    signal
  });
  
  if (!response.ok) {
    throw new Error(`Search failed: ${response.status}`);
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
              onProgress(data.step, data.detail, data.elapsed);
            }
          } else if (data.type === 'complete') {
            finalResult = data;
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
  
  return finalResult || { results: [], total_matches: 0 };
};

export const searchSemanticCross = async (params, signal) => {
  const response = await fetch(`${API_BASE}/search`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ...params, match_type: 'semantic_cross' }),
    signal
  });
  return response.json();
};

export const searchHapax = async (params, signal) => {
  const response = await fetch(`${API_BASE}/hapax-search`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params),
    signal
  });
  return response.json();
};

export const searchBigrams = async (params, signal) => {
  const response = await fetch(`${API_BASE}/rare-bigram-search`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params),
    signal
  });
  return response.json();
};

export const fetchCorpusRareWords = async (language, maxOccurrences) => {
  const response = await fetch(`${API_BASE}/rare-lemmata?language=${language}&max_occurrences=${maxOccurrences}`);
  return response.json();
};

export const fetchCorpusRareBigrams = async (language, maxOccurrences = 10) => {
  const response = await fetch(`${API_BASE}/rare-bigrams?language=${language}&max_occurrences=${maxOccurrences}`);
  return response.json();
};

export const fetchWordOccurrences = async (lemma, language) => {
  const response = await fetch(`${API_BASE}/rare-word-locations/${encodeURIComponent(lemma)}?language=${language}`);
  return response.json();
};

export const fetchWordDefinition = async (lemma, language) => {
  const response = await fetch(`${API_BASE}/rare-lemmata?lemma=${encodeURIComponent(lemma)}&language=${language}`);
  return response.json();
};

export const fetchRepoIntertexts = async (params) => {
  const query = new URLSearchParams(params).toString();
  const response = await fetch(`${API_BASE}/intertexts?${query}`);
  return response.json();
};

export const fetchRepoStats = async () => {
  const response = await fetch(`${API_BASE}/intertexts/stats`);
  return response.json();
};

export const registerIntertext = async (data) => {
  const response = await fetch(`${API_BASE}/intertexts`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data)
  });
  return response.json();
};

export const fetchMyIntertexts = async () => {
  const response = await fetch(`${API_BASE}/intertexts/my`);
  return response.json();
};

export const updateIntertext = async (id, data) => {
  const response = await fetch(`${API_BASE}/intertexts/${id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data)
  });
  return response.json();
};

export const deleteIntertext = async (id) => {
  const response = await fetch(`${API_BASE}/intertexts/${id}`, {
    method: 'DELETE'
  });
  return response.json();
};

export const fetchAuthStatus = async () => {
  const response = await fetch(`${API_BASE}/auth/user`);
  const data = await response.json();
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
  const response = await fetch(`${API_BASE}/line-search?${query}`);
  return response.json();
};

export const searchCorpusForLemmas = async (lemmas, excludeText, language) => {
  const response = await fetch(`${API_BASE}/corpus-search`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ lemmas, exclude_text: excludeText, language })
  });
  return response.json();
};

export const fetchSavedSearches = async () => {
  const response = await fetch(`${API_BASE}/auth/saved-searches`);
  return response.json();
};

export const saveSearch = async (name, params) => {
  const response = await fetch(`${API_BASE}/auth/saved-searches`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, params })
  });
  return response.json();
};

export const deleteSavedSearch = async (id) => {
  const response = await fetch(`${API_BASE}/auth/saved-searches/${id}`, {
    method: 'DELETE'
  });
  return response.json();
};

export const wildcardSearch = async (params, signal) => {
  const response = await fetch(`${API_BASE}/wildcard-search`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params),
    signal
  });
  return response.json();
};
