// One source for what each search does, what it covers, where it is weak and
// how well it has been measured (2026-10-10). The scope box on every search
// page and the Help table "How well does it work?" both read from here, so a
// figure is written once. Every measured row was moved word for word from the
// Help table or taken from the scope spec of 2026-10-10. Where a search has not
// been measured, the row says "Not measured yet".
//
// A measured row carries language, against, result and date. It also carries
// `search`, the label of the Help table's first column. A row that belongs to
// two searches (the Hebrew fusion row also describes Cross-Language) is one
// object, so the Help table lists it once.

const FUSION_LA = { search: "Verbal parallels (Fusion)", language: "Latin", against: "862 parallels from five published commentaries and studies (Lucan, Valerius Flaccus and Statius against Vergil, Ovid and Statius)", result: "About 92 percent found (788 to 798 of 862, depending on the run); on the Valerius Flaccus set, nine of the first ten results are attested in the commentaries", date: "September 2026" };
const FUSION_GRC = { search: "Verbal parallels (Fusion)", language: "Greek", against: "121 Homeric parallels in later epic (Iliad and Odyssey benchmarks)", result: "69 percent found searching whole works, 97 percent searching book by book", date: "early 2026" };
const FUSION_COP = { search: "Verbal parallels (Fusion)", language: "Coptic", against: "Scripture quoted in scripture: the 22 marked citations of Isaiah in Romans (held out from all tuning), and a broad 124-pair reference list", result: "On the held-out citations, 59 percent in the first hundred and eight of the first ten are genuine; on the broad list, 14.5 percent in the first hundred, since Coptic search is tuned for quotation rather than loose allusion", date: "August 2026" };
const FUSION_HE = { search: "Verbal parallels (Fusion)", language: "Hebrew", against: "The 22 marked citations of Isaiah in Romans, searched from the Hebrew through the Septuagint into the Greek New Testament", result: "15 of 22 in the first hundred, 9 in the first ten; the direct word-for-word route found none", date: "August 2026" };
const FUSION_EN = { search: "Verbal parallels (Fusion)", language: "English", against: "No published list of parallels has been run yet", result: "Not measured", date: "" };
const CROSS_GRC_LA = { search: "Cross-Language (Greek to Latin)", language: "Greek and Latin", against: "412 Homeric parallels in the Aeneid from Knauer's index", result: "About 40 percent in the first fifty for a given target line, 94 percent found somewhere in the ranking; only 31 percent of the listed parallels share any vocabulary across the two languages", date: "2026" };
const THEME_LAGRC = { search: "Theme Search", language: "Latin and Greek", against: "Confidence band: 32 test subjects, half present in the corpus and half absent. Recall: the works Curtius cites for eleven topoi (57 works held here)", result: "The band agrees with the test set on 88 to 91 percent of subjects. Of Curtius's 57 works, 23 appear somewhere in the returned lists and 7 among the first ten; a frontier language model asked the same questions from memory names 14 and 13. Precision of the first ten results, sixteen test themes, judged against a scholar's grading rule: about 29 percent by description order, about 43 percent after the reading step (see The reading step under Theme Search)", date: "September 2026" };
const THEME_OTHER = { search: "Theme Search", language: "Coptic, Hebrew, English", against: "Included in the index; no language-specific test yet", result: "Not measured separately", date: "" };
const RARE_ALL = { search: "Rare words, rare pairs, line and string search", language: "All", against: "Exact lookups in the index", result: "They return every occurrence the index holds; there is no recall to measure, only the coverage of the corpus and the accuracy of the dictionary forms (see each language section)", date: "" };

const NOT_YET = 'Not measured yet';

const DOCUMENTS_ROW = { search: 'Inscriptions & Papyri', language: 'Latin and Greek', against: 'No test list yet', result: NOT_YET, date: '' };
const EVENTS_ROW = { search: 'Events', language: 'Latin and Greek', against: '43 passages historians cite for twelve events', result: 'About a third of the first twenty passages listed for an event were among them (precision at 20 of 0.32 to 0.40 by method)', date: 'October 2026' };
const COINS_ROW = { search: 'Coins', language: 'Latin', against: "Ten passages with known coin parallels, the Reader's related imagery", result: '17 of the 50 coin types offered were real parallels (about one in three). The Greek catalogues, included for a test, took 27 of the 50 places with about three real ones, so a Latin passage now uses the Roman catalogues only', date: 'October 2026' };
const OBJECTS_ROW = { search: 'Objects', language: 'English descriptions', against: 'No test list yet', result: NOT_YET, date: '' };

const NO_CONFIDENCE_NOTE = 'A search restricted to one author or work has no confidence band.';

export const SEARCH_SCOPE = {
  parallel: {
    id: 'parallel',
    name: 'Phrase Search',
    does: 'You set only the texts to compare; the search finds the most similar phrases between them, based on a variety of similarity types.',
    scope: 'Two chosen works are compared line by line through eleven channels (shared dictionary forms, exact words, sound, meaning, synonyms, syntax, rare words and quotation), and the channels\' scores are fused into one. A result is a pair of lines, one from each work.',
    covers: 'The literary corpus, by language.',
    limits: 'It compares one pair of works at a time. English has no syntax data and Greek has it for about half its texts. Coptic is tuned for quotation, and Persian and Urdu run nine channels, including a refrain-and-rhyme channel of their own.',
    measured: [FUSION_LA, FUSION_GRC, FUSION_COP, FUSION_HE, FUSION_EN],
    helpSection: 'fusion-search',
  },
  cross: {
    id: 'cross',
    name: 'Cross-Language',
    does: 'Compares a work in one language with a work in another through dictionaries, shared script and meaning.',
    scope: 'A work in one language is compared with a work in another through a dictionary, shared vocabulary and a model of meaning trained on both. A result is a pair of passages, one from each work.',
    covers: 'The literary corpus, by language.',
    limits: 'Seven language pairs are open, and each works through what its two languages have in common. Greek to Latin finds most known parallels somewhere in the ranking but few of them near the top. Persian to Urdu works through the vocabulary the two languages share.',
    measured: [CROSS_GRC_LA, FUSION_HE],
    helpSection: 'cross-lingual',
  },
  theme: {
    id: 'theme',
    name: 'Theme Search',
    does: 'Describe a scene or an idea in English and get the passages about it, across languages, ranked by meaning.',
    scope: 'Your description is compared with a short description written for each passage, and the closest passages come back from every indexed language at once. A result is a passage window.',
    covers: 'The passage index, 603,594 windows at the 2026-08-25 release.',
    limits: `A subject that is absent from the corpus gets a low confidence band and not an empty list. ${NO_CONFIDENCE_NOTE} The ranking rests on a model's description of each passage, so very short or fragmentary passages rank poorly.`,
    measured: [THEME_LAGRC, THEME_OTHER],
    helpSection: 'theme-search',
  },
  line: {
    id: 'line',
    name: 'Line Search',
    does: 'Enter a line to find other lines like it. Choose an existing line to search or write your own.',
    scope: 'Every line in the corpus that carries the words you type, with the lines that quote the whole phrase first.',
    covers: 'The literary corpus, by language.',
    limits: 'It matches dictionary forms, so an inflected form is found but a misspelling is not. Common words are dropped unless the phrase is only common words. It searches one language at a time.',
    measured: [RARE_ALL],
    helpSection: 'search-modes',
  },
  string: {
    id: 'string',
    name: 'Strings',
    does: 'Enter specific terms, optionally with wildcards (am*), phrases, or AND/OR operators.',
    scope: 'Every line in the corpus that contains the exact characters, words, phrases or wildcard patterns you type.',
    covers: 'The literary corpus, by language.',
    limits: 'It matches exact characters only, so it does not join an inflected form to its dictionary form. It searches one language at a time.',
    measured: [RARE_ALL],
    helpSection: 'search-modes',
  },
  bigram: {
    id: 'bigram',
    name: 'Rare Pairs',
    does: 'Finds rare two-word combinations that two chosen texts share. It can catch unusual pairings of otherwise ordinary words.',
    scope: 'Two chosen works are searched for word pairs they share that occur in few other works, ranked by how often the pair occurs in the corpus. A result is a pair of words and the two lines that hold it.',
    covers: 'The literary corpus, by language.',
    limits: 'Rarity is measured against the corpus held here, so a word that was common in lost literature can look rare.',
    measured: [RARE_ALL],
    helpSection: 'search-modes',
  },
  hapax: {
    id: 'hapax',
    name: 'Rare Words',
    does: 'Finds rare individual words that two chosen texts share.',
    scope: 'Two chosen works are searched for words they share that occur in few other works, ranked by how often the word occurs in the corpus. A result is a word and the two lines that hold it.',
    covers: 'The literary corpus, by language.',
    limits: 'Rarity is measured against the corpus held here, so a word that was common in lost literature can look rare.',
    measured: [RARE_ALL],
    helpSection: 'search-modes',
  },
  documents: {
    id: 'documents',
    name: 'Inscriptions & Papyri',
    does: 'Finds the words of a phrase in 257,000 inscriptions and papyri, with the literature or on their own.',
    scope: 'A phrase is looked up in the inscriptions and papyri, alone or together with the literature. A result is a line of a document.',
    covers: 'About 257,000 inscriptions and papyri in Latin and Greek.',
    limits: 'Restored text is marked and can be excluded. Formulas (phrases common on stone) can be hidden. Coverage follows the four source corpora named in Help.',
    measured: [DOCUMENTS_ROW],
    helpSection: 'documents',
  },
  events: {
    id: 'events',
    name: 'Events',
    does: 'Lists historical events with the passages that tell of them, the inscriptions and papyri from nearby and the scholarship.',
    scope: 'The events are the battles, sieges, campaigns and treaties of 800 BCE to 600 CE recorded in Wikidata, with their dates, places and participants. For each event, passages are gathered in two ways, by the names of the people and places involved and by Theme Search on a description of the event, and the two rankings are merged. Inscriptions and papyri come from within the event\'s years and near its place. Scholarship is the articles citing the leading passages. A result is an event with that dossier.',
    covers: 'Events from Wikidata (CC0), with the literature, the inscriptions and papyri and the citation index behind each dossier.',
    limits: 'A famous name pulls in unrelated lines, and the theme route alone cannot tell one battle from another, so an event told without its own names ranks its passages poorly. Each event\'s description comes from Wikipedia where an article exists, otherwise from Wikidata\'s one line.',
    measured: [EVENTS_ROW],
    helpSection: 'events',
  },
  coins: {
    id: 'coins',
    name: 'Coins',
    does: 'Searches the legends and catalogue descriptions of Greek and Roman coin types.',
    scope: 'Coin legends and the catalogues\' descriptions of what each side shows are searched. A result is a coin type.',
    covers: 'Greek and Roman coin types from nine catalogues published through nomisma.org.',
    limits: 'A coin type is a catalogue entry and not one coin, and images are on the catalogues\' own pages. The Reader\'s related imagery matches a description to a passage and is not a coin known to refer to it. For a Latin passage it draws on the Roman catalogues only.',
    measured: [COINS_ROW],
    helpSection: 'coins',
  },
  objects: {
    id: 'objects',
    name: 'Objects',
    does: 'Searches museum catalogue descriptions of Greek, Roman and Etruscan objects.',
    scope: 'The titles, descriptions, labels and inscriptions of museum objects are searched. A result is an object.',
    covers: 'Greek, Roman and Etruscan objects from the Cleveland Museum of Art, the Art Institute of Chicago and the Smithsonian.',
    limits: 'Three museums are held so far. The descriptions are the museums\' own and vary from a paragraph to a catalogue-card line.',
    measured: [OBJECTS_ROW],
    helpSection: 'objects',
  },
};

// The Help table lists each distinct row once, entries in this order.
const HELP_ORDER = ['parallel', 'cross', 'theme', 'line', 'string', 'bigram', 'hapax', 'documents', 'events', 'coins', 'objects'];

export function allMeasuredRows() {
  const seen = new Set();
  const out = [];
  for (const id of HELP_ORDER) {
    for (const row of SEARCH_SCOPE[id].measured) {
      if (!seen.has(row)) {
        seen.add(row);
        out.push(row);
      }
    }
  }
  return out;
}

const n = (v) => Number(v).toLocaleString('en-US');

function worksHeld(counts, names) {
  const t = counts && counts.texts;
  if (!t) return null;
  const parts = Object.entries(t).map(([code, k]) => `${names[code] || code.toUpperCase()} ${n(k)}`);
  return parts.length ? `Works held now: ${parts.join(', ')}.` : null;
}

// The live version of an entry's `covers` line, from /api/scope, or null when
// the route has no figure (the box then shows the dated line above).
export function liveCovers(id, counts, names = {}) {
  if (!counts) return null;
  switch (id) {
    case 'theme':
      return counts.passage_windows ? `The passage index, ${n(counts.passage_windows)} windows now.` : null;
    case 'documents': {
      const d = counts.documents || {};
      const parts = Object.entries(d).map(([code, k]) => `${names[code] || code.toUpperCase()} ${n(k)}`);
      return parts.length ? `Inscriptions and papyri held now: ${parts.join(', ')}.` : null;
    }
    case 'events':
      return counts.events ? `${n(counts.events)} events held now.` : null;
    case 'coins':
      return counts.coins ? `${n(counts.coins)} coin types held now.` : null;
    case 'objects':
      return counts.objects ? `${n(counts.objects)} objects held now.` : null;
    default:
      return worksHeld(counts, names);
  }
}
