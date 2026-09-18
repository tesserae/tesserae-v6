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
