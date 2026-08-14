/**
 * Shared Greek text utilities for display and normalization.
 */

export const displayGreekWithFinalSigma = (text) => {
  if (!text) return text;
  return text.replace(/σ(?=\s|$|[,.;:!?])/g, 'ς');
};

export const normalizeGreek = (text) => {
  if (!text) return '';
  return text
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .replace(/ς/g, 'σ');
};

// Search-syntax example strings for the String Search legend. The Greek
// words are extracted verbatim from Iliad 1.1 in the corpus (never typed),
// so the accents/encoding are exactly what the corpus uses.
export const GREEK_SYNTAX_EXAMPLES = {
  wild: "μῆν*",
  wildFind: "μῆνιν",
  single: "θε?",
  and: "μῆνιν AND θεὰ",
  or: "θεὰ OR ἄειδε",
  prox: "μῆνιν ~ ἄειδε",
  phrase: "\"μῆνιν ἄειδε\"",
};
