// The citation printed above each side of a result card and in the corpus
// panel's parallel picker. Moved out of SearchResults.jsx (cleaning job H4,
// 2026-10-13) so the card and the panel share it.
import { formatReference } from '../../utils/formatting';
import { resolveDisplayCitation } from '../../utils/textNames';

// The server now builds the full "<Author>, <Work title> <locus>" citation
// itself (issue #566) and attaches it to each side as `citation`, the same
// way Line Search has always shown it. Use that when a result carries it;
// fall back to the old tag-parsing formatReference() for results from
// before this shipped (cached searches, saved parallels); then, if that
// still reads as the raw internal id (Persian, Urdu, or any other language
// without a static abbreviation table -- result card tidy, 2026-10-08),
// resolve it against the corpus list's own author/title (`corpusMap`, from
// `useCorpusTextMap`). side is 'source' or 'target'.
export const citationFor = (r, side, language, corpusMap) => {
  const s = r[side];
  const raw = r[`${side}_locus`] || s?.ref;
  const existing = (s && s.citation) || (raw ? formatReference(raw, language) : '');
  return resolveDisplayCitation(existing, raw, corpusMap).text;
};
