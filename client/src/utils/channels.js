/**
 * Names and one-line descriptions of the fusion channels, shared by the
 * search settings panel, the result cards and the findings block above the
 * results assistant, so they never disagree. The names are the technical
 * terms (owner, 2026-10-16: "Don't dumb this down. You can use the norm
 * technical terms and just put in tooltips"); the descriptions are the
 * tooltips. The backend keeps its own plain-prose table in
 * backend/assistant/findings.py.
 */
export const CHANNEL_LABELS = [
  ['lemma', 'Lemma'],
  ['lemma_min1', 'Lemma (single)'],
  ['exact', 'Exact form'],
  ['sound', 'Sound (trigrams)'],
  ['edit_distance', 'Edit distance'],
  ['semantic', 'Semantic (embeddings)'],
  ['dictionary', 'Dictionary synonyms'],
  ['syntax', 'Syntax'],
  ['syntax_structural', 'Syntax (structural)'],
  ['rare_word', 'Rare word'],
  ['quotation', 'Quotation'],
  ['context', 'Content (passage embeddings)'],
  ['form', 'Form (meter and rhyme)'],
];

export const CHANNEL_DESCRIPTIONS = {
  lemma: 'Two or more shared lemmata (dictionary headwords) within the window. The classic Tesserae match.',
  lemma_min1: 'A single shared lemma. The widest net and the noisiest.',
  exact: 'Two or more identical surface forms, inflection and all.',
  sound: 'Similarity of character trigrams (Jaccard), catching sound play and near-forms the lemmatizer misses.',
  edit_distance: 'Small Levenshtein distance between word forms, as in Filum, catching spelling variants and corrupt forms.',
  semantic: 'Cosine similarity of SPhilBERTa sentence embeddings, a match of meaning without shared words.',
  dictionary: 'Synonym pairs from the Tesserae V3 synonymy tables, with cross-language pairs for Greek and Latin.',
  syntax: 'The same dependency relations (Universal Dependencies parses) at the positions of the shared lemmata.',
  syntax_structural: 'The same dependency head pattern with no shared lemma, confirmed by a synonym or an embedding match.',
  rare_word: 'Shared lemmata of low corpus frequency, weighted by rarity.',
  quotation: 'A verbatim run of three or more consecutive forms.',
  context: 'Similarity of the passage embeddings used by Theme Search, a match of content at passage scale.',
  form: 'Shared poetic form, meter and rhyme, for Persian and Urdu verse.',
};

// The short form for the badge on a result card ("lemma + sound"), where the
// parenthetical of the full name would not fit.
export const CHANNEL_SHORT = {
  lemma: 'lemma',
  lemma_min1: 'single lemma',
  exact: 'exact',
  sound: 'sound',
  edit_distance: 'edit distance',
  semantic: 'semantic',
  dictionary: 'synonyms',
  syntax: 'syntax',
  syntax_structural: 'structural',
  rare_word: 'rare word',
  quotation: 'quotation',
  context: 'content',
  form: 'form',
};

const LABEL_OF = Object.fromEntries(CHANNEL_LABELS);

export function channelBadge(name) {
  return CHANNEL_SHORT[name] || String(name).replace(/_/g, ' ').toLowerCase();
}

export function channelLabel(name) {
  return LABEL_OF[name] || String(name).replace(/_/g, ' ');
}

export function channelDescription(name) {
  return CHANNEL_DESCRIPTIONS[name] || '';
}
