// Shared constants for the documents-collection search (inscriptions and
// papyri), used by both LineSearch.jsx's "Documents"/"Both" option and the
// Inscriptions & Papyri page (client/src/components/documents/InscriptionsPapyriPage.jsx).
// Moved out of LineSearch.jsx verbatim so the two never drift apart.

// The "Hide stock formulas" checkbox's own fixed threshold -- matches
// backend/app.py's DOCUMENTS_FORMULA_DEFAULT_N, measured against the real
// documents indexes (dis manibus/bene merenti/votum solvit libens merito/hic
// situs est, thousands of sharing documents each, vs. arma virumque/arma
// virumque cano, fewer than 20).
export const DOCUMENTS_FORMULA_DEFAULT_N = 100;

// Document hits are paged SERVER-SIDE at this fixed size (no client-side
// re-paging of a 500-row ceiling -- see docs/DECISIONS.md, "document results
// are ranked, a 500-row cap is gone").
export const DOC_PAGE_SIZE = 50;

// One-click example searches, each checked against the live documents
// indexes. Well-known, pungent texts rather than the commonest formulas on
// stone. Shown only when the documents control is itself available (the
// trial flag plus the server switch).
export const DOCUMENT_EXAMPLE_SEARCHES = {
  la: [
    { label: '"balnea vina Venus"', hint: 'an epitaph: baths, wine and love ruin our bodies, and make life',
      query: 'balnea vina Venus', collection: 'documents', searchType: 'lemma' },
    { label: '"admiror paries te non cecidisse"', hint: 'a Pompeian graffito wondering that the wall has not fallen under so much scribbling',
      query: 'admiror paries te non cecidisse', collection: 'documents', searchType: 'lemma' },
    { label: '"suspirium puellarum"', hint: 'a gladiator’s graffito: the girls’ heart-throb',
      query: 'suspirium puellarum', collection: 'documents', searchType: 'lemma' },
    { label: '"tene me ne fugiam"', hint: 'slave collars: hold me so I do not run away',
      query: 'tene me ne fugiam', collection: 'documents', searchType: 'lemma' },
    { label: '"venimus huc cupidi"', hint: 'a Pompeian graffito: we came here eager, and leave more eager still',
      query: 'venimus huc cupidi', collection: 'documents', searchType: 'lemma' },
    { label: '"arma virumque cano"', hint: 'Vergil’s first line, scratched on Pompeian walls; searched in Both so the literature shows beside the stones',
      query: 'arma virumque cano', collection: 'both', searchType: 'lemma' },
  ],
  grc: [
    { label: 'ἐὰν ἦν θήλεα ἔκβαλε', hint: 'a letter home from Alexandria: if it is a girl, expose it',
      query: 'ἐὰν ἦν θήλεα ἔκβαλε', collection: 'documents', searchType: 'lemma' },
    { label: 'Ἀπίων Ἐπιμάχῳ τῷ πατρί', hint: 'a recruit’s letter to his father from the fleet at Misenum',
      query: 'Ἀπίων Ἐπιμάχῳ τῷ πατρί', collection: 'documents', searchType: 'lemma' },
    { label: 'θάρσει οὐδεὶς ἀθάνατος', hint: 'an epitaph’s consolation: take heart, no one is immortal',
      query: 'θάρσει οὐδεὶς ἀθάνατος', collection: 'documents', searchType: 'lemma' },
  ],
};
