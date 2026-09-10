/**
 * Plain names for the fusion channels, shared by the search settings panel and
 * the findings block above the results assistant, so the two never disagree.
 * The backend keeps the same table in backend/assistant/findings.py for the
 * prose.
 */
export const CHANNEL_LABELS = [
  ['lemma', 'Shared words'],
  ['lemma_min1', 'Single word'],
  ['exact', 'Exact'],
  ['sound', 'Sound'],
  ['edit_distance', 'Spelling'],
  ['semantic', 'Meaning'],
  ['dictionary', 'Synonyms'],
  ['syntax', 'Syntax'],
  ['syntax_structural', 'Structure'],
  ['rare_word', 'Rare words'],
  ['quotation', 'Verbatim run'],
  ['context', 'Content'],
  ['form', 'Form'],
];

const LABEL_OF = Object.fromEntries(CHANNEL_LABELS);

export function channelLabel(name) {
  return LABEL_OF[name] || String(name).replace(/_/g, ' ');
}
