/**
 * Shared utilities for generating external reference links.
 */

// The tooltip on the dictionary icon. For Persian, Urdu and Arabic the form
// is usually inflected or a compound, so the link is a search and says so.
export function dictionaryLinkTitle(word, language, dictionaryName) {
  if (['fa', 'ur', 'ar'].includes(language)) {
    return `Search ${dictionaryName} for this form: "${word}". It may be an inflected form or a compound, so the nearest entries are shown.`;
  }
  return `Look up "${word}" in ${dictionaryName}`;
}

export function getDictionaryUrl(word, language) {
  if (!word) return null;
  // English, Persian, Urdu, Arabic and Hebrew: Wiktionary, which has full
  // entries for all of them. Logeion is a Latin and Greek dictionary and
  // answered nothing for an Arabic word (2026-09-07).
  if (language === 'en') {
    return `https://en.wiktionary.org/wiki/${encodeURIComponent(word)}`;
  }
  // The rare words of these corpora are mostly inflected forms and compounds
  // written without the joiner, which Wiktionary lists only under a headword
  // and so answered with blanks (NC, 2026-09-07). Each language's own
  // dictionary site searches by form: Vajehyab (Dehkhoda, Moin, Amid) found
  // آیینه‌ای, Rekhta found ابروباد "cloud and wind", Almaany resolves an
  // inflected Arabic verb to its root.
  if (language === 'fa') {
    return `https://www.vajehyab.com/?q=${encodeURIComponent(word)}`;
  }
  if (language === 'ur') {
    return `https://rekhtadictionary.com/search?keyword=${encodeURIComponent(word)}`;
  }
  if (language === 'ar') {
    return `https://www.almaany.com/ar/dict/ar-ar/${encodeURIComponent(word)}/`;
  }
  if (language === 'he') {
    return `https://en.wiktionary.org/w/index.php?search=${encodeURIComponent(word)}`;
  }
  // Coptic uses the Coptic Dictionary Online (KELLIA). The Rare Words Explorer
  // passes the manuscript-spelled lemma, which matches CDO's Sahidic entries.
  if (language === 'cop') {
    return `https://coptic-dictionary.org/results.cgi?quick_search=${encodeURIComponent(word)}`;
  }
  // Hebrew: Wiktionary carries Biblical Hebrew entries, same as English.
  if (language === 'he') {
    return `https://en.wiktionary.org/wiki/${encodeURIComponent(word)}`;
  }
  // Latin and Greek both use Logeion
  return `https://logeion.uchicago.edu/${encodeURIComponent(word)}`;
}
