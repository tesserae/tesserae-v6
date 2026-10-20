// The full titles of the epigraphic and papyrological publications that lead the
// record of a document ("CIL 11, 01923", "Not. Sc., 1888, p. 562", "P.Oxy. 63 4394").
// The project lead, 2026-10-20: "I'm not an epigrapher but I don't know what this
// means: Not. Sc. We have the room to spell things out." Each abbreviation is shown
// as its title with the abbreviation in parentheses, so a specialist still sees the
// form they know. Only abbreviations whose expansion is certain are listed; an
// unlisted one is left as written.
export const EDITION_NAMES = {
  'AE': "L'Année épigraphique",
  'CIL': 'Corpus Inscriptionum Latinarum',
  'CIG': 'Corpus Inscriptionum Graecarum',
  'CIS': 'Corpus Inscriptionum Semiticarum',
  'IG': 'Inscriptiones Graecae',
  'IGUR': 'Inscriptiones Graecae Urbis Romae',
  'IGRR': 'Inscriptiones Graecae ad Res Romanas Pertinentes',
  'IGASM': 'Iscrizioni greche arcaiche di Sicilia e Magna Grecia',
  'IGDS': 'Inscriptions grecques dialectales de Sicile',
  'ILS': 'Inscriptiones Latinae Selectae',
  'ILLRP': 'Inscriptiones Latinae Liberae Rei Publicae',
  'ILJug': 'Inscriptiones Latinae quae in Iugoslavia repertae sunt',
  'ILBulg': 'Inscriptiones Latinae in Bulgaria repertae',
  'ILAlg': "Inscriptions latines de l'Algérie",
  'ILTun': 'Inscriptions latines de la Tunisie',
  'ICUR': 'Inscriptiones Christianae Urbis Romae',
  'InscrIt': 'Inscriptiones Italiae',
  'IDR': 'Inscriptiones Daciae Romanae',
  'IMS': 'Inscriptions de la Mésie Supérieure',
  'IScM': 'Inscriptiones Scythiae Minoris',
  'IRT': 'The Inscriptions of Roman Tripolitania',
  'RIB': 'The Roman Inscriptions of Britain',
  'RIU': 'Die römischen Inschriften Ungarns',
  'OGIS': 'Orientis Graeci Inscriptiones Selectae',
  'SEG': 'Supplementum Epigraphicum Graecum',
  'Syll.': 'Sylloge Inscriptionum Graecarum',
  'EphEp': 'Ephemeris Epigraphica',
  'Not. Sc.': 'Notizie degli Scavi di Antichità',
  'NSA': 'Notizie degli Scavi di Antichità',
  'SB': 'Sammelbuch griechischer Urkunden aus Ägypten',
  'BGU': 'Berliner Griechische Urkunden',
  'SPP': 'Studien zur Palaeographie und Papyruskunde',
  'PSI': 'Papiri greci e latini (Società Italiana)',
  'BASP': 'Bulletin of the American Society of Papyrologists',
  'P.Oxy.': 'The Oxyrhynchus Papyri',
  'P.Tebt.': 'The Tebtunis Papyri',
  'P.Lond.': 'Greek Papyri in the British Museum',
  'P.Mich.': 'Michigan Papyri',
  'P.Col.': 'Columbia Papyri',
  'P.Petr.': 'The Flinders Petrie Papyri',
  'P.Gurob': 'Greek Papyri from Gurob',
  'P.Brux.': 'Papyri Bruxellenses',
  'P.Cair. Zen.': 'Zenon Papyri in the Cairo Museum',
  'O.Mich.': 'Ostraca in the University of Michigan Collection',
  'O.Masada': 'Ostraca from Masada',
};

const escape = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
const KEYS = Object.keys(EDITION_NAMES).sort((a, b) => b.length - a.length);
// An abbreviation counts only as a whole token: at the start or after a space,
// semicolon, dash or parenthesis, and followed by a space, digit, comma, period
// or the end. So "IG" never matches inside "IGDS", and "AE" never inside a word.
const PATTERN = new RegExp(
  `(^|[\\s;(–-])(${KEYS.map(escape).join('|')})(?=[\\s\\d,.)]|$)`, 'g');

/** The edition line with each known abbreviation written out. */
export function expandEditions(text) {
  if (!text) return text;
  return String(text).replace(PATTERN, (m, before, abbr) => `${before}${EDITION_NAMES[abbr]} (${abbr})`);
}
