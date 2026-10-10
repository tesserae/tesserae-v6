/**
 * Closeness of a Line Search hit to a multi-word query (owner's review
 * 2026-10-10: "sit tibi terra levis" put literature lines sharing only
 * "terra" on top; "the default should be (near) quotation").
 *
 * The server marks each literary hit with `quotation` (every content word of
 * the query within a short window, and the query's own words, common ones
 * included, present in surface form), `n_surface` (how many of the query's
 * words as typed the line carries), `n_matched` (how many of the query's
 * content words it shares) and `span` (the width of the window holding the
 * matched words). The response carries `query_lemma_count` (content words)
 * and `query_word_count` (words as typed). Lines that quote the phrase come
 * first, then those carrying more of its words, then the closer ones, then
 * the older text.
 */
export function closenessSort(a, b) {
  if (!!b.quotation !== !!a.quotation) return b.quotation ? 1 : -1;
  const sa = a.n_surface || 0;
  const sb = b.n_surface || 0;
  if (sb !== sa) return sb - sa;
  const na = a.n_matched || 0;
  const nb = b.n_matched || 0;
  if (nb !== na) return nb - na;
  const wa = a.span == null ? 1e9 : a.span;
  const wb = b.span == null ? 1e9 : b.span;
  if (wa !== wb) return wa - wb;
  const aYear = a.year || 9999;
  const bYear = b.year || 9999;
  if (aYear !== bYear) return aYear - bYear;
  return (a.author || '').localeCompare(b.author || '');
}

/**
 * The short tag beside a hit, or null for a one-word query. When the query
 * had common words that the search dropped (`queryWordCount` above
 * `queryLemmaCount`), the tags say "key words" so "2 of 2" is not read as
 * the whole four-word phrase.
 */
export function closenessLabel(result, queryLemmaCount, queryWordCount) {
  if (!queryLemmaCount || queryLemmaCount < 2) return null;
  const dropped = (queryWordCount || 0) > queryLemmaCount;
  if (result.quotation) return { text: 'whole phrase', tone: 'strong' };
  const n = Math.min(result.n_matched || 0, queryLemmaCount);
  if (n >= queryLemmaCount) {
    const together = result.span != null && result.span <= queryLemmaCount + 1;
    if (dropped) return { text: together ? 'key words together' : 'key words apart', tone: 'mid' };
    return { text: together ? 'all words, together' : 'all words, apart', tone: 'mid' };
  }
  return { text: `${n} of ${queryLemmaCount} ${dropped ? 'key words' : 'words'}`, tone: 'weak' };
}

export const TONE_CLASS = {
  strong: 'bg-green-100 text-green-800',
  mid: 'bg-amber-100 text-amber-800',
  weak: 'bg-gray-100 text-gray-600',
};
