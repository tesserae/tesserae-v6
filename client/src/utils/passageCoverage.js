/**
 * Which works Theme Search (and Similar Passages) covers, shared by Browse
 * Corpus (the "N of M" count line, the covered-only filter and its
 * heading) and the Theme Search page (the "Searches N of M works" line).
 * One definition, so the two counts can't drift apart from each other:
 * verified equal against production (2026-09-19), 765 of 782 for Latin,
 * computed both ways.
 */

/** homer.iliad.part.2.tess and homer.iliad.tess are one translated work; both
 *  collapse to the same base id, homer.iliad. */
export const baseWorkId = (id) =>
  String(id || '').replace(/\.tess$/, '').split('.part.')[0];

/** Distinct works (parts collapsed) among `texts` (an /api/texts array), and
 *  how many of those base ids appear in `coveredIds` (an array or Set, as
 *  /api/passages/works's `works` field returns). */
export const coverageCounts = (texts, coveredIds) => {
  const baseIds = new Set((texts || []).map((t) => baseWorkId(t.id)));
  const covered = coveredIds instanceof Set ? coveredIds : new Set(coveredIds || []);
  let n = 0;
  baseIds.forEach((id) => { if (covered.has(id)) n += 1; });
  return { covered: n, total: baseIds.size };
};

/**
 * Fetch /api/passages/works?language=<language>, retrying if the request
 * fails or comes back with an empty works list.
 *
 * Right after a deploy reload (`touch tesseraev6_flask.wsgi`), each Apache
 * worker loads the ~2GB passage index on its first request, which can take
 * about 90 seconds; a request to this route during that window used to come
 * back slow or empty, and the caller's silent fallback then read as "this
 * language simply has no Theme Search coverage" rather than "still
 * loading". Retries once at +3s and once more at +10s before giving up.
 *
 * `corpusHasWorks` gates the retries, not the first attempt: a language
 * with nothing in Browse Corpus at all has nothing to check coverage
 * against, so there is no point waiting 13 seconds to learn that. Always
 * resolves (never rejects) to an array, which may still be empty after
 * every attempt -- the caller can't tell that apart from "coverage is
 * genuinely zero", so treat a persistent empty result as "still loading"
 * rather than assert a count of zero.
 */
export const fetchCoveredWorks = async (language, corpusHasWorks, delays = [3000, 10000]) => {
  const attempt = async () => {
    try {
      const res = await fetch(`/api/passages/works?language=${language}`);
      const data = await res.json();
      return Array.isArray(data?.works) ? data.works : [];
    } catch {
      return [];
    }
  };
  let works = await attempt();
  if (!corpusHasWorks) return works;
  for (const delay of delays) {
    if (works.length > 0) break;
    await new Promise((resolve) => setTimeout(resolve, delay));
    works = await attempt();
  }
  return works;
};
