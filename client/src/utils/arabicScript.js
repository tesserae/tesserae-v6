// Comparison form for Persian, Urdu and Arabic words on the page (2026-09-06).
//
// The engine reports matched words in a normalized form: Arabic kaf and yeh,
// no vowel marks, no zero-width joiners. The texts on screen keep their own
// spelling: Persian kaf and yeh, Urdu's heh and yeh variants, vowelled
// Arabic. So a word the engine matched was not being found in the line it
// came from, and Rare Pairs showed no highlight for these languages. Folding
// both sides through this function makes them comparable.

export const foldArabicScript = (s) => String(s || '')
  // vowel marks, tatweel, zero-width and direction marks
  .replace(/[ً-ٰٟۖ-ۭـ‌‍‎‏]/g, '')
  // yeh variants (Arabic, Persian, alef maksura, Urdu barree) -> Persian yeh
  .replace(/[يیىےۓ]/g, 'ی')
  // kaf variants -> Persian kaf
  .replace(/[كک]/g, 'ک')
  // alef with hamza or madda -> bare alef
  .replace(/[آأإٱ]/g, 'ا')
  // heh variants, Urdu heh goal and doachashmee, ta marbuta -> heh
  .replace(/[ہھۃة]/g, 'ه')
  // noon ghunna -> noon
  .replace(/ں/g, 'ن');

// Punctuation at either end of a token, Latin and Arabic-script alike.
const EDGE = /^[\s.,;:!?'"()\[\]—–،؛؟۔«»-]+|[\s.,;:!?'"()\[\]—–،؛؟۔«»-]+$/g;

export const stripEdgePunctuation = (s) => String(s || '').replace(EDGE, '');

export const isArabicScriptLanguage = (language) => language === 'fa' || language === 'ur' || language === 'ar';

// True when a folded token is the folded target, or carries it with an
// attached article, preposition or ending (Arabic al-, bi-, wa-, case
// endings; Persian ezafe and plural endings). Targets shorter than three
// letters must match exactly, or ordinary particles light up everywhere.
export const arabicTokenMatches = (foldedToken, foldedTarget) => {
  if (!foldedToken || !foldedTarget) return false;
  if (foldedToken === foldedTarget) return true;
  if (foldedTarget.length < 3) return false;
  return foldedToken.includes(foldedTarget);
};
