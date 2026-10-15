// The "Download everything (CSV)" file of the Rare Words page: one row per
// place the word occurs in the corpus, with the source and target locations
// the ordinary export has beside it. The occurrences come from a request made
// with include_corpus_locations: true; the default response leaves them out.

export const EVERYTHING_HEADERS = [
  'Word', 'Lemma', 'Work', 'Citation', 'Line Text', 'Source Locations', 'Target Locations',
];

const quote = (cell) => `"${String(cell ?? '').replace(/"/g, '""')}"`;

export const corpusOccurrenceRows = (results) => {
  const rows = [];
  (results || []).forEach((r) => {
    const srcLocs = (r.source_locations || []).map((loc) => loc.ref).join('; ');
    const tgtLocs = (r.target_locations || []).map((loc) => loc.ref).join('; ');
    const word = r.display_form || r.lemma || '';
    const occurrences = r.all_corpus_locations || [];
    if (occurrences.length === 0) {
      rows.push([word, r.lemma || '', '', '', '', srcLocs, tgtLocs]);
      return;
    }
    occurrences.forEach((loc) => {
      const work = [loc.author, loc.work].filter(Boolean).join(', ');
      rows.push([
        word,
        r.lemma || '',
        work,
        loc.citation || loc.ref || '',
        loc.text || '',
        srcLocs,
        tgtLocs,
      ]);
    });
  });
  return rows;
};

export const corpusOccurrencesCsv = (results) => {
  const rows = corpusOccurrenceRows(results);
  return [EVERYTHING_HEADERS, ...rows].map((row) => row.map(quote).join(',')).join('\n');
};
