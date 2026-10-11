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

// One-click example searches, verified against the live documents indexes.
// Shown only when the documents control is itself available (the trial flag
// plus the server switch).
export const DOCUMENT_EXAMPLE_SEARCHES = {
  // Epigraphy first (owner 2026-10-10: a historian trying the page should
  // meet meaningful inscriptions, with the literary quotations at the end).
  la: [
    { label: '"tribunicia potestate"', hint: 'the emperors’ dating formula: the year of tribunician power',
      query: 'tribunicia potestate', collection: 'documents', searchType: 'lemma' },
    { label: '"decreto decurionum"', hint: 'by decree of the town council: civic honours and burials',
      query: 'decreto decurionum', collection: 'documents', searchType: 'lemma' },
    { label: '"sevir augustalis"', hint: 'the freedmen’s priesthood of the imperial cult',
      query: 'sevir augustalis', collection: 'documents', searchType: 'lemma' },
    { label: '"sit tibi terra levis"', hint: 'an epitaph wish, with its own literary echoes',
      query: 'sit tibi terra levis', collection: 'both', searchType: 'lemma' },
    { label: '"conticuere omnes"', hint: 'Aeneid 2.1, scratched into Pompeian walls',
      query: 'conticuere omnes', collection: 'both', searchType: 'exact' },
    { label: '"arma virumque cano"', hint: 'Vergil’s opening, plus a Pompeii fuller’s parody of it',
      query: 'arma virumque cano', collection: 'both', searchType: 'lemma' },
  ],
  grc: [
    { label: 'ἡ βουλὴ καὶ ὁ δῆμος', hint: '"the council and the people", the opening of a civic decree',
      query: 'βουλὴ καὶ ὁ δῆμος', collection: 'documents', searchType: 'lemma' },
    { label: 'ἀγαθῇ τύχῃ', hint: '"with good fortune", the heading of decrees and dedications',
      query: 'ἀγαθῇ τύχῃ', collection: 'documents', searchType: 'lemma' },
    { label: 'οὐδεὶς ἀθάνατος', hint: '"no one is immortal", a Greek epitaph phrase',
      query: 'οὐδεὶς ἀθάνατος', collection: 'documents', searchType: 'lemma' },
  ],
};
