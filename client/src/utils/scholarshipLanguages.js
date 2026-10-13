/**
 * Which languages have installed secondary scholarship (commentaries), so
 * the Reader's Scholarship tab can offer itself only where there is
 * something to show, rather than from a hard-coded list that drifts from
 * what is actually installed.
 *
 * Fetched once from /api/scholarship/sources (its additive `languages`
 * field) and cached on the client for the rest of the visit: every
 * consumer shares the one request instead of asking again per mount.
 */
let cached = null;

export function scholarshipLanguages() {
  if (!cached) {
    cached = fetch('/api/scholarship/sources')
      .then((r) => (r.ok ? r.json() : { languages: [] }))
      .then((d) => new Set(d.languages || []))
      .catch(() => new Set());
  }
  return cached;
}

/** Test-only: the module cache otherwise outlives any one test. */
export function resetScholarshipLanguagesCache() {
  cached = null;
}
