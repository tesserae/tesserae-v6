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
  // Latin and Greek both use Logeion
  return `https://logeion.uchicago.edu/${encodeURIComponent(word)}`;
}
