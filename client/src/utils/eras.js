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
  // No 'Nineteenth century' here. One author carried that label, Poe, and a
  // century is not a period in the same series as the rest. He was retagged
  // Romantic in backend/author_dates.json on 2026-09-22, which is where the
  // standard accounts place him (American Romanticism, and Dark Romanticism
  // in particular) and where his neighbours in this corpus already sit:
  // Coleridge 1834 and Wordsworth 1850, both Romantic.
  en:  ['Medieval', 'Renaissance', 'Early Modern', 'Restoration', 'Augustan', 'Neoclassical', 'Romantic', 'Victorian', 'Modern', 'Unknown'],
  cop: ['Early Coptic', 'Classical Coptic', 'Late Antique Coptic', 'Bohairic Medieval', 'Unknown'],
  // Hebrew joined the Corpus Browser on 2026-09-21. Every one of the 39
  // Hebrew Bible books is tagged Biblical, so that plus Unknown is the whole
  // list until something later is added. Without a key here the filter fell
  // back to the Latin eras, which is the same gap Coptic had.
  he:  ['Biblical', 'Unknown'],
  // Persian dynastic era labels. Persian OVERVIEW.md ("19 authors dated as of
  // 2026-08-25 ... with dynastic era labels (Samanid, Ghaznavid, Seljuk,
  // Ilkhanid, Timurid, Safavid, Mughal, Modern). These labels are editorial
  // and want a specialist.") names most of these; the authoritative source is
  // backend/author_dates.json itself, whose fa entries (editorial-2026-08-25,
  // 18 of the corpus's 19 authors dated, the 19th -- fa/iqbal -- added Phase 3
  // by identity with fa/iqbal_lahori, a separately filed diwan work merged
  // into this same id by the 2026-10-07 rename) use a finer set including two
  // labels the OVERVIEW.md summary omitted (Khwarazmian, "Seljuk of Rum").
  // Order below is chronological by each label's earliest attested author
  // year in that file
  // (Samanid 941 -> Ghaznavid 1020 -> Seljuk 1088 -> Khwarazmian 1221 ->
  // "Seljuk of Rum" 1273 -> Ilkhanid 1292 -> Muzaffarid 1390 -> Timurid 1492 ->
  // Safavid 1676 -> Mughal 1720 -> Modern 1938). Still "editorial and wants a
  // specialist" per the source note -- not independently re-verified here.
  fa:  ['Samanid', 'Ghaznavid', 'Seljuk', 'Khwarazmian', 'Seljuk of Rum', 'Ilkhanid',
        'Muzaffarid', 'Timurid', 'Safavid', 'Mughal', 'Modern', 'Unknown'],
  // Arabic: 'Pre-Islamic' and 'Early Islamic' are sourced (research/languages/
  // arabic/OVERVIEW.md + backend/author_dates.json's editorial-2026-08-25
  // imruulqais/tarafa/quran rows). al-Busiri (13th c.) and Ahmad Shawqi
  // (d. 1932), added to author_dates.json Phase 3, have sourced DATES but no
  // sourced era-CATEGORY name for medieval/modern Arabic literary periods, so
  // both carry era 'Unknown' rather than an invented label -- flagged for a
  // specialist, same as Persian's dynastic labels.
  // 2026-09-06: the Arabic Wikisource import (Mutanabbi, Abu Nuwas, the
  // Mu'allaqat, al-Nawawi and others) brought authors from every classical
  // period, so the list now runs Pre-Islamic -> Early Islamic (to 661) ->
  // Umayyad -> Abbasid -> Andalusi -> Mamluk -> Modern, the standard
  // dynastic periodization of Arabic literary history.
  ar:  ['Pre-Islamic', 'Early Islamic', 'Umayyad', 'Abbasid', 'Andalusi', 'Mamluk', 'Modern', 'Unknown'],
  // Urdu: backend/author_dates.json's ur entries (editorial-2026-08-25 for
  // ghalib/iqbal, Phase 3 for mir by identity with ghalib's bucket -- Mir,
  // 1723-1810, lived entirely within it) use exactly two labels: 'Mughal /
  // Colonial' (Mir, Ghalib) and 'Modern' (Iqbal). No finer period scheme (e.g.
  // splitting Mughal from Colonial) is sourced anywhere in the workspaces or
  // research notes, so none is invented here.
  ur:  ['Mughal / Colonial', 'Modern', 'Unknown'],
};

export const ERA_COLORS = {
  // Hebrew
  'Biblical': 'rgba(90, 122, 92, 0.7)',
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
  // added: Persian dynastic eras (see ERA_ORDER_BY_LANG.fa for sourcing)
  'Samanid': 'rgba(180, 140, 60, 0.7)',
  'Ghaznavid': 'rgba(160, 90, 50, 0.7)',
  'Seljuk': 'rgba(140, 60, 90, 0.7)',
  'Khwarazmian': 'rgba(120, 100, 40, 0.7)',
  'Seljuk of Rum': 'rgba(160, 80, 110, 0.7)',
  'Ilkhanid': 'rgba(110, 70, 130, 0.7)',
  'Muzaffarid': 'rgba(90, 130, 60, 0.7)',
  'Timurid': 'rgba(180, 70, 70, 0.7)',
  'Safavid': 'rgba(20, 130, 100, 0.7)',
  'Mughal': 'rgba(150, 110, 30, 0.7)',
  // added: Urdu era (distinct key from Persian's plain 'Mughal' -- Urdu's
  // sourced bucket spans Mughal AND colonial British India, see
  // ERA_ORDER_BY_LANG.ur)
  'Mughal / Colonial': 'rgba(130, 90, 40, 0.7)',
  // added: Arabic eras
  'Pre-Islamic': 'rgba(100, 60, 30, 0.7)',
  'Early Islamic': 'rgba(40, 130, 90, 0.7)',
  'Umayyad': 'rgba(60, 110, 150, 0.7)',
  'Abbasid': 'rgba(120, 70, 40, 0.7)',
  'Andalusi': 'rgba(170, 100, 60, 0.7)',
  'Mamluk': 'rgba(100, 80, 120, 0.7)',
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


// Where an era sorts, for a list ordered chronologically. Same contract as
// orderEras: a label the table does not know is never dropped, it goes last,
// so an unexpected or missing era still sorts somewhere sensible instead of
// disappearing or landing first.
//
// This exists because CorpusBrowser kept its own second copy of the order and
// wrote it in snake_case ('early_imperial') while the backend sends labels
// ('Early Imperial'), so every lookup missed and the era sort had no effect
// at all. For Latin, Greek and English the fallback to year hid it; for
// Hebrew, where no work has a year, and for Coptic, where 140 of 187 have
// none, "chronological" was alphabetical by author.
export function eraRank(language, era) {
  const order = ERA_ORDER_BY_LANG[language] || ERA_ORDER_BY_LANG.la;
  const i = order.indexOf(era);
  return i === -1 ? order.length : i;
}
