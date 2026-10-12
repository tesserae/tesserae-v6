// The live services' recent articles (backend/scholarship_recent.py), shared by
// Search One Text and Theme Search's Scholarship list.
// The server answers available false, reason 'off', for a service it has no key for.
export const RECENT_SERVICES = ['openalex', 'crossref', 'core', 'books', 's2'];
export const RECENT_LABELS = { openalex: 'OpenAlex', crossref: 'Crossref', core: 'CORE', books: 'Google Books', s2: 'Semantic Scholar' };

export function joinNames(names) {
  if (names.length < 2) return names.join('');
  return `${names.slice(0, -1).join(', ')} and ${names[names.length - 1]}`;
}

/** Items from several services as one list: deduped by DOI, then by the first
 *  80 characters of the title, in the order the server uses (title names the
 *  work, title words matched, question words matched, full-text naming, newest). */
export function mergeRecent(have, incoming) {
  const out = [...have];
  const keys = (it) => [String(it.doi || '').toLowerCase(), String(it.title || '').toLowerCase().slice(0, 80)].filter(Boolean);
  const seen = new Set(out.flatMap(keys));
  for (const it of incoming || []) {
    if (!it || !it.title || keys(it).some((k) => seen.has(k))) continue;
    keys(it).forEach((k) => seen.add(k));
    out.push(it);
  }
  return out.sort((a, b) => (
    (b.title_names_work ? 1 : 0) - (a.title_names_work ? 1 : 0)
    || (b.title_hits || 0) - (a.title_hits || 0)
    || (b.score || 0) - (a.score || 0)
    || (b.full_names_work ? 1 : 0) - (a.full_names_work ? 1 : 0)
    || (Number(b.year) || 0) - (Number(a.year) || 0)
  ));
}

export function recentUrl(it) {
  return it.oa_url || (it.doi ? `https://doi.org/${it.doi}` : null) || it.url || null;
}

/** One request per service, all at once. onAnswer(service, result) is called as each lands
 *  (result is {} when the request failed). Returns a function that stops the callbacks. */
export function fetchRecent(question, work, onAnswer) {
  let dead = false;
  const w = work ? `&work=${encodeURIComponent(work)}` : '';
  const asks = RECENT_SERVICES.map((svc) => fetch(
    `/api/passages/recent-scholarship?question=${encodeURIComponent(question)}${w}&service=${svc}`,
  ).then((res) => res.json()).catch(() => ({})).then((r) => { if (!dead) onAnswer(svc, r || {}); }));
  return { stop: () => { dead = true; }, done: Promise.allSettled(asks) };
}
