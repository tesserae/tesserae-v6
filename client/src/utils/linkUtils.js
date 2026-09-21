/**
 * Shared utilities for generating external reference links.
 */

export function getDictionaryUrl(word, language) {
  if (!word) return null;
  if (language === 'en') {
    return `https://en.wiktionary.org/wiki/${encodeURIComponent(word)}`;
  }
  // Coptic uses the Coptic Dictionary Online (KELLIA). The Rare Words Explorer
  // passes the manuscript-spelled lemma, which matches CDO's Sahidic entries.
  if (language === 'cop') {
    return `https://coptic-dictionary.org/results.cgi?quick_search=${encodeURIComponent(word)}`;
  }
  // Hebrew: Wiktionary carries Biblical Hebrew entries, same as English.
  // (Rare Words Explorer has no Hebrew entries to link from yet -- see
  // regenerate_rare_words_cache in backend/blueprints/hapax.py, which has
  // no Hebrew branch -- but this fixes the link for whenever it does, and
  // for any other caller that passes a Hebrew word.)
  if (language === 'he') {
    return `https://en.wiktionary.org/wiki/${encodeURIComponent(word)}`;
  }
  // Latin and Greek both use Logeion
  return `https://logeion.uchicago.edu/${encodeURIComponent(word)}`;
}
