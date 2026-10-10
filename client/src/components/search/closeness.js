/**
 * Closeness of a Line Search hit to a multi-word query (owner's review
 * 2026-10-10: "sit tibi terra levis" put literature lines sharing only
 * "terra" on top; "the default should be (near) quotation").
 *
 * The server marks each literary hit with `quotation` (every content word of
 * the query, within a short window) and `n_matched` (how many of the query's
 * content words it shares); the response carries `query_lemma_count`. Lines
 * that quote the phrase come first, then those sharing more words, then the
 * older text.
 */
export function closenessSort(a, b) {
  if (!!b.quotation !== !!a.quotation) return b.quotation ? 1 : -1;
  const na = a.n_matched || 0;
  const nb = b.n_matched || 0;
  if (nb !== na) return nb - na;
  const aYear = a.year || 9999;
  const bYear = b.year || 9999;
  if (aYear !== bYear) return aYear - bYear;
  return (a.author || '').localeCompare(b.author || '');
}

/** The short tag beside a hit, or null for a one-word query. */
export function closenessLabel(result, queryLemmaCount) {
  if (!queryLemmaCount || queryLemmaCount < 2) return null;
  if (result.quotation) return { text: 'whole phrase', tone: 'strong' };
  const n = Math.min(result.n_matched || 0, queryLemmaCount);
  if (n >= queryLemmaCount) return { text: 'all words, apart', tone: 'mid' };
  return { text: `${n} of ${queryLemmaCount} words`, tone: 'weak' };
}

export const TONE_CLASS = {
  strong: 'bg-green-100 text-green-800',
  mid: 'bg-amber-100 text-amber-800',
  weak: 'bg-gray-100 text-gray-600',
};
