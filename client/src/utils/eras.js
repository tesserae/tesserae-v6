// Era ordering + colors for the timeline bar charts, shared by LineSearch,
// CorpusSearchResults, and WildcardSearch.
//
// Era label strings MUST match the `era` values the backend attaches to results
// (see backend/author_dates.json). Ordering is per-language because some labels
// (Augustan, Medieval, Renaissance, Modern) are reused across languages at very
// different dates -- e.g. Latin's Augustan is ~27 BCE, English's Augustan is the
// early 1700s -- so a single flat order cannot place them correctly for both.

export const ERA_ORDER_BY_LANG = {
  la:  ['Republic', 'Augustan', 'Early Imperial', 'Later Imperial', 'Late Antique', 'Early Medieval', 'Carolingian', 'Medieval', 'Renaissance', 'Modern', 'Unknown'],
  grc: ['Archaic', 'Classical', 'Hellenistic', 'Early Imperial', 'Later Imperial', 'Late Antique', 'Late Imperial', 'Unknown'],
  en:  ['Medieval', 'Renaissance', 'Early Modern', 'Restoration', 'Augustan', 'Neoclassical', 'Romantic', 'Victorian', 'Modern', 'Unknown'],
  cop: ['Early Coptic', 'Classical Coptic', 'Late Antique Coptic', 'Bohairic Medieval', 'Unknown'],
};

export const ERA_COLORS = {
  // Greek (existing)
  'Archaic': 'rgba(155, 35, 53, 0.7)',
  'Classical': 'rgba(224, 123, 0, 0.7)',
  'Hellenistic': 'rgba(197, 179, 88, 0.7)',
  // Latin (existing)
  'Republic': 'rgba(0, 105, 148, 0.7)',
  'Augustan': 'rgba(120, 81, 169, 0.7)',
  'Early Imperial': 'rgba(34, 139, 34, 0.7)',
  'Later Imperial': 'rgba(30, 144, 255, 0.7)',
  'Late Antique': 'rgba(139, 69, 19, 0.7)',
  'Early Medieval': 'rgba(112, 128, 144, 0.7)',
  // added: Latin/Greek tail
  'Late Imperial': 'rgba(30, 144, 255, 0.7)',
  'Carolingian': 'rgba(160, 120, 90, 0.7)',
  // added: shared / English eras
  'Medieval': 'rgba(90, 100, 120, 0.7)',
  'Renaissance': 'rgba(180, 60, 80, 0.7)',
  'Early Modern': 'rgba(200, 130, 40, 0.7)',
  'Restoration': 'rgba(150, 110, 60, 0.7)',
  'Neoclassical': 'rgba(80, 150, 120, 0.7)',
  'Romantic': 'rgba(190, 90, 120, 0.7)',
  'Victorian': 'rgba(70, 90, 110, 0.7)',
  'Modern': 'rgba(100, 100, 100, 0.7)',
  // added: Coptic eras
  'Early Coptic': 'rgba(120, 80, 60, 0.7)',
  'Classical Coptic': 'rgba(170, 110, 70, 0.7)',
  'Late Antique Coptic': 'rgba(139, 69, 19, 0.7)',
  'Bohairic Medieval': 'rgba(110, 90, 130, 0.7)',
  // fallback
  'Unknown': 'rgba(128, 128, 128, 0.7)',
};

// Order the eras present in `eraCounts` for a given language, chronologically,
// NEVER dropping any: known eras first in order, then any leftover eras appended
// (so an unexpected era still shows rather than vanishing from the chart).
export function orderEras(language, eraCounts) {
  const order = ERA_ORDER_BY_LANG[language] || ERA_ORDER_BY_LANG.la;
  const inOrder = order.filter(era => eraCounts[era] > 0);
  const extras = Object.keys(eraCounts).filter(era => eraCounts[era] > 0 && !order.includes(era));
  return [...inOrder, ...extras];
}
