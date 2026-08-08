/**
 * Shared utilities for generating external reference links.
 */

export function getDictionaryUrl(word, language) {
  if (!word) return null;
  if (language === 'en') {
    return `https://en.wiktionary.org/wiki/${encodeURIComponent(word)}`;
  }
  // Coptic: no external lookup wired yet (Logeion has no Coptic; the Coptic
  // Dictionary Online needs the manuscript form, not the matcher's normalized
  // lemma), so omit the link rather than show a broken one.
  if (language === 'cop') {
    return null;
  }
  // Latin and Greek both use Logeion
  return `https://logeion.uchicago.edu/${encodeURIComponent(word)}`;
}
