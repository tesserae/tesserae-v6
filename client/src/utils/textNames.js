import { useEffect, useState } from 'react';

const ABBREVIATION_MAP = {
  'hom': { author: 'Homer' },
  'homer': { author: 'Homer' },
  'hes': { author: 'Hesiod' },
  'hesiod': { author: 'Hesiod' },
  'aesch': { author: 'Aeschylus' },
  'aeschylus': { author: 'Aeschylus' },
  'soph': { author: 'Sophocles' },
  'sophocles': { author: 'Sophocles' },
  'eur': { author: 'Euripides' },
  'euripides': { author: 'Euripides' },
  'ar': { author: 'Aristophanes' },
  'aristophanes': { author: 'Aristophanes' },
  'pind': { author: 'Pindar' },
  'pindar': { author: 'Pindar' },
  'theoc': { author: 'Theocritus' },
  'theocritus': { author: 'Theocritus' },
  'callim': { author: 'Callimachus' },
  'callimachus': { author: 'Callimachus' },
  'apoll': { author: 'Apollonius' },
  'apollonius': { author: 'Apollonius' },
  'plat': { author: 'Plato' },
  'plato': { author: 'Plato' },
  'arist': { author: 'Aristotle' },
  'aristotle': { author: 'Aristotle' },
  'thuc': { author: 'Thucydides' },
  'thucydides': { author: 'Thucydides' },
  'hdt': { author: 'Herodotus' },
  'herodotus': { author: 'Herodotus' },
  'xen': { author: 'Xenophon' },
  'xenophon': { author: 'Xenophon' },
  'plut': { author: 'Plutarch' },
  'plutarch': { author: 'Plutarch' },
  'verg': { author: 'Vergil', work: 'Aeneid' },
  'aen': { work: 'Aeneid' },
  'ecl': { work: 'Eclogues' },
  'georg': { work: 'Georgics' },
  'g': { work: 'Georgics' },
  'luc': { author: 'Lucan', work: 'Bellum Civile' },
  'ov': { author: 'Ovid' },
  'ovid': { author: 'Ovid' },
  'met': { work: 'Metamorphoses' },
  'am': { work: 'Amores' },
  'ars': { work: 'Ars Amatoria' },
  'fast': { work: 'Fasti' },
  'trist': { work: 'Tristia' },
  'her': { work: 'Heroides' },
  'pont': { work: 'Epistulae ex Ponto' },
  'rem': { work: 'Remedia Amoris' },
  'ib': { work: 'Ibis' },
  'stat': { author: 'Statius' },
  'theb': { work: 'Thebaid' },
  'ach': { work: 'Achilleid' },
  'silv': { work: 'Silvae' },
  'sil': { author: 'Silius Italicus', work: 'Punica' },
  'val': { author: 'Valerius Flaccus' },
  'flac': { work: 'Argonautica' },
  'lucr': { author: 'Lucretius', work: 'De Rerum Natura' },
  'cat': { author: 'Catullus', work: 'Carmina' },
  'catu': { author: 'Catullus', work: 'Carmina' },
  'tib': { author: 'Tibullus', work: 'Elegies' },
  'prop': { author: 'Propertius', work: 'Elegies' },
  'hor': { author: 'Horace' },
  'horat': { author: 'Horace' },
  'carm': { work: 'Carmina' },
  'sat': { work: 'Satires' },
  'epist': { work: 'Epistles' },
  'ars_poet': { work: 'Ars Poetica' },
  'epod': { work: 'Epodes' },
  'pers': { author: 'Persius', work: 'Satires' },
  'juv': { author: 'Juvenal', work: 'Satires' },
  'iuv': { author: 'Juvenal', work: 'Satires' },
  'mart': { author: 'Martial', work: 'Epigrammata' },
  'phaedr': { author: 'Phaedrus', work: 'Fabulae' },
  'manil': { author: 'Manilius', work: 'Astronomica' },
  'sen': { author: 'Seneca' },
  'med': { work: 'Medea' },
  'herc': { work: 'Hercules Furens' },
  'troad': { work: 'Troades' },
  'phoen': { work: 'Phoenissae' },
  'phaed': { work: 'Phaedra' },
  'oed': { work: 'Oedipus' },
  'agam': { work: 'Agamemnon' },
  'thy': { work: 'Thyestes' },
  'oct': { work: 'Octavia' },
  'plaut': { author: 'Plautus' },
  'ter': { author: 'Terence' },
  'enn': { author: 'Ennius', work: 'Annales' },
  'cic': { author: 'Cicero' },
  'caes': { author: 'Caesar' },
  'liv': { author: 'Livy', work: 'Ab Urbe Condita' },
  'sall': { author: 'Sallust' },
  'tac': { author: 'Tacitus' },
  'suet': { author: 'Suetonius' },
  'nep': { author: 'Cornelius Nepos' },
  'quint': { author: 'Quintilian', work: 'Institutio Oratoria' },
  'plin': { author: 'Pliny' },
  'apul': { author: 'Apuleius' },
  'petron': { author: 'Petronius', work: 'Satyricon' },
  'gell': { author: 'Aulus Gellius', work: 'Noctes Atticae' },
  'macr': { author: 'Macrobius', work: 'Saturnalia' },
  'boeth': { author: 'Boethius' },
  'claud': { author: 'Claudian' },
  'prud': { author: 'Prudentius' },
  'auson': { author: 'Ausonius' },
  'drac': { author: 'Dracontius' },
  'sidon': { author: 'Sidonius Apollinaris' },
  'ven': { author: 'Venantius Fortunatus' },
  'fort': { author: 'Venantius Fortunatus' },
  'corip': { author: 'Corippus' },
  'sedul': { author: 'Sedulius' },
  'juven': { author: 'Juvencus' },
  'alcim': { author: 'Alcimus Avitus' },
  'ambr': { author: 'Ambrose' },
  'hier': { author: 'Jerome' },
  'aug': { author: 'Augustine' },
  'hrab': { author: 'Hrabanus Maurus' },
  'hildeb': { author: 'Hildebert of Lavardin' },
  'alan': { author: 'Alan of Lille' },
  'bern': { author: 'Bernard Silvestris' },
  'walt': { author: 'Walter of Châtillon' },
};

const WORK_NAMES = {
  'il': 'Iliad',
  'iliad': 'Iliad',
  'od': 'Odyssey',
  'odyssey': 'Odyssey',
  'theog': 'Theogony',
  'theogony': 'Theogony',
  'wd': 'Works and Days',
  'works': 'Works and Days',
  'ag': 'Agamemnon',
  'agamemnon': 'Agamemnon',
  'cho': 'Choephoroe',
  'lib': 'Libation Bearers',
  'eum': 'Eumenides',
  'pers': 'Persae',
  'prom': 'Prometheus Bound',
  'sept': 'Seven Against Thebes',
  'supp': 'Suppliants',
  'aj': 'Ajax',
  'ant': 'Antigone',
  'el': 'Electra',
  'ot': 'Oedipus Tyrannus',
  'oc': 'Oedipus at Colonus',
  'phil': 'Philoctetes',
  'trach': 'Trachiniae',
  'alc': 'Alcestis',
  'andr': 'Andromache',
  'ba': 'Bacchae',
  'cycl': 'Cyclops',
  'hec': 'Hecuba',
  'hel': 'Helen',
  'heracl': 'Heraclidae',
  'hf': 'Heracles',
  'hipp': 'Hippolytus',
  'ion': 'Ion',
  'ia': 'Iphigenia in Aulis',
  'it': 'Iphigenia in Tauris',
  'med': 'Medea',
  'or': 'Orestes',
  'phoen': 'Phoenissae',
  'rhes': 'Rhesus',
  'tro': 'Troades',
  'aeneid': 'Aeneid',
  'aen': 'Aeneid',
  'eclogues': 'Eclogues',
  'ecl': 'Eclogues',
  'georgics': 'Georgics',
  'georg': 'Georgics',
  'bellum_civile': 'Bellum Civile',
  'pharsalia': 'Bellum Civile',
  'metamorphoses': 'Metamorphoses',
  'met': 'Metamorphoses',
  'amores': 'Amores',
  'ars_amatoria': 'Ars Amatoria',
  'fasti': 'Fasti',
  'tristia': 'Tristia',
  'heroides': 'Heroides',
  'thebaid': 'Thebaid',
  'theb': 'Thebaid',
  'achilleid': 'Achilleid',
  'silvae': 'Silvae',
  'punica': 'Punica',
  'argonautica': 'Argonautica',
  'de_rerum_natura': 'De Rerum Natura',
  'carmina': 'Carmina',
  'satires': 'Satires',
  'epistles': 'Epistles',
  'epigrammata': 'Epigrammata',
  'fabulae': 'Fabulae',
  'astronomica': 'Astronomica',
  'annales': 'Annales',
  'de_bello_gallico': 'De Bello Gallico',
  'de_bello_civili': 'De Bello Civili',
  'ab_urbe_condita': 'Ab Urbe Condita',
  'satyricon': 'Satyricon',
  'noctes_atticae': 'Noctes Atticae',
  'saturnalia': 'Saturnalia',
  'institutio_oratoria': 'Institutio Oratoria',
  'confessiones': 'Confessiones',
  'de_civitate_dei': 'De Civitate Dei',
  'consolatio': 'Consolation of Philosophy',
};

// Author-specific work overrides for ambiguous abbreviations.
// Maps (author_abbrev, work_part(s)) → work title.
const AUTHOR_WORK_OVERRIDES = {
  'sen': {
    'her.o': 'Hercules Oetaeus',
    'her.f': 'Hercules Furens',
    'herc.o': 'Hercules Oetaeus',
    'herc.f': 'Hercules Furens',
  },
  'seneca': {
    'her.o': 'Hercules Oetaeus',
    'her.f': 'Hercules Furens',
    'herc.o': 'Hercules Oetaeus',
    'herc.f': 'Hercules Furens',
  },
  'alcuin': {
    'carm': 'Carmina',
  },
  'hildeb': {
    'carm': 'Carmina',
  },
};

// Full names for the abbreviated English work tags (keyed on the space-joined,
// lower-cased name tokens), so a ref like "Milton P.L. 1.519" reads as
// "Paradise Lost", not "P L". Single-word works (Lycidas, Hyperion) need no entry.
const ENGLISH_WORK_NAMES = {
  'p l': 'Paradise Lost',
  'p r': 'Paradise Regained',
  'f q': 'Faerie Queene',
  'r a m': 'Rime of the Ancient Mariner',
  's innoc': 'Songs of Innocence',
  's exper': 'Songs of Experience',
  'p p': "Pilgrim's Progress",
  'l alleg': "L'Allegro",
  'il pens': 'Il Penseroso',
  'grecian urn': 'Ode on a Grecian Urn',
  'eve st agnes': 'The Eve of St Agnes',
  'robin hood': 'Robin Hood',
};

export function expandLocus(locus) {
  if (!locus) return { work: '', reference: locus || '' };

  const parts = locus.toLowerCase().split(/[\s.]+/);
  let author = null;
  let authorKey = null;
  let work = null;
  let reference = '';

  for (let i = 0; i < parts.length; i++) {
    const part = parts[i].replace(/[.,]/g, '');

    if (ABBREVIATION_MAP[part]) {
      const mapped = ABBREVIATION_MAP[part];
      if (mapped.author && !author) {
        author = mapped.author;
        authorKey = part;
      }
      if (mapped.work && !work) {
        // Before applying a global work mapping, check author-specific overrides
        const overrides = authorKey ? AUTHOR_WORK_OVERRIDES[authorKey] : null;
        if (overrides) {
          // Try two-part key (e.g., "her.o")
          const nextPart = parts[i + 1]?.replace(/[.,]/g, '');
          const twoPartKey = nextPart ? `${part}.${nextPart}` : null;
          if (twoPartKey && overrides[twoPartKey]) {
            work = overrides[twoPartKey];
            i++; // skip the next part since we consumed it
            continue;
          }
          // Try single-part override
          if (overrides[part]) {
            work = overrides[part];
            continue;
          }
        }
        work = mapped.work;
      }
    } else if (WORK_NAMES[part] && !work) {
      // Check author override before global lookup
      const overrides = authorKey ? AUTHOR_WORK_OVERRIDES[authorKey] : null;
      if (overrides) {
        const nextPart = parts[i + 1]?.replace(/[.,]/g, '');
        const twoPartKey = nextPart ? `${part}.${nextPart}` : null;
        if (twoPartKey && overrides[twoPartKey]) {
          work = overrides[twoPartKey];
          i++;
          continue;
        }
        if (overrides[part]) {
          work = overrides[part];
          continue;
        }
      }
      work = WORK_NAMES[part];
    } else if (/^\d/.test(part)) {
      reference = parts.slice(i).join('.');
      break;
    } else if (!work && authorKey) {
      // Check if this unknown part + next form a known override
      const overrides = AUTHOR_WORK_OVERRIDES[authorKey];
      if (overrides) {
        const nextPart = parts[i + 1]?.replace(/[.,]/g, '');
        const twoPartKey = nextPart ? `${part}.${nextPart}` : null;
        if (twoPartKey && overrides[twoPartKey]) {
          work = overrides[twoPartKey];
          i++;
          continue;
        }
        if (overrides[part]) {
          work = overrides[part];
          continue;
        }
      }
    }
  }

  // Fallback for refs whose leading token is not a known abbreviation (all of
  // English, plus any Greek/Coptic author absent from ABBREVIATION_MAP): treat
  // the leading non-numeric tokens as author/work instead of returning "Unknown".
  if (!author) {
    const orig = (locus || '').split(/[\s.]+/).filter(Boolean);
    const numAt = orig.findIndex(p => /^\d/.test(p));
    const nameParts = numAt === -1 ? orig : orig.slice(0, numAt);
    const refParts = numAt === -1 ? [] : orig.slice(numAt);
    if (nameParts.length) author = nameParts[0];
    if (!work && nameParts.length > 1) {
      const rawWork = nameParts.slice(1).join(' ');
      work = ENGLISH_WORK_NAMES[rawWork.toLowerCase()] || rawWork;
    }
    if (!reference && refParts.length) reference = refParts.join('.');
  }

  return { author, work, reference };
}

export function formatFullCitation(author, locus) {
  const expanded = expandLocus(locus);
  const displayAuthor = author || expanded.author || 'Unknown';
  const displayWork = expanded.work || '';
  const displayRef = expanded.reference || locus;
  
  if (displayWork) {
    return { author: displayAuthor, work: displayWork, reference: displayRef };
  }
  
  return { author: displayAuthor, work: '', reference: displayRef };
}

export function formatTesseraeIdentifier(id) {
  if (!id) return '';
  const cleanId = id.replace(/\.tess$/, '');
  const parts = cleanId.split('.');
  
  let author = '';
  let work = '';
  let extra = '';
  
  if (parts.length > 0) {
    const authorPart = parts[0];
    const mappedAuthor = ABBREVIATION_MAP[authorPart.toLowerCase()]?.author;
    author = mappedAuthor || authorPart.charAt(0).toUpperCase() + authorPart.slice(1);
  }
  
  if (parts.length > 1) {
    const workPart = parts[1];
    const mappedWork = WORK_NAMES[workPart.toLowerCase()] || ABBREVIATION_MAP[workPart.toLowerCase()]?.work;
    work = mappedWork || workPart.charAt(0).toUpperCase() + workPart.slice(1).replace(/_/g, ' ');
  }
  
  if (parts.length > 2) {
    extra = ' ' + parts.slice(2).map(p => {
      if (p.toLowerCase() === 'part') return 'Part';
      return p.charAt(0).toUpperCase() + p.slice(1);
    }).join(' ');
  }
  
  if (author && work) {
    return `${author}, ${work}${extra}`;
  } else if (author) {
    return `${author}${extra}`;
  }
  return cleanId;
}


// ---------------------------------------------------------------------------
// Corpus-wide display names (result card tidy, 2026-10-08).
//
// The card's citations and the file-naming abbreviation tables above
// (ABBREVIATION_MAP / WORK_NAMES) were built for Latin and Greek, which the
// site has carried the longest. Persian and Urdu (and anything else outside
// those tables) fell through to the raw filename-shaped id -- "hafez.diwan.5097"
// where Latin shows "Vergil, Aeneid 1.1" -- because nothing in this file knew
// their authors or titles. The corpus list the site already serves at
// `/api/texts?language=<lang>` carries exactly that (an `author` and a
// `title`/`work` per text id), the same record the corpus browser and the
// Reader's own titles read from. This section fetches that list once per
// language, caches it, and resolves a raw ref against it.

const _corpusTextCache = new Map(); // language -> Map(textId -> metadata)
const _corpusTextPromises = new Map(); // language -> Promise
const _corpusTextSubscribers = new Set();

function _notifyCorpusTextSubscribers() {
  _corpusTextSubscribers.forEach((fn) => {
    try { fn(); } catch { /* a subscriber's own error is not this cache's problem */ }
  });
}

/** Test-only: clears the cached `/api/texts` maps so a test can mock a
 *  fresh fetch for the same language without seeing a previous test's
 *  cached (or empty) result. The running app never needs this -- the
 *  corpus list does not change under a page that is already open. */
export function __resetCorpusTextMapCacheForTests() {
  _corpusTextCache.clear();
  _corpusTextPromises.clear();
}

/** Fetch and cache `/api/texts?language=<language>` as a Map keyed by the
 *  text id without its `.tess` suffix, lower-cased. Resolves to an empty Map
 *  on any failure (missing language, network error, non-array body) so a
 *  caller never has to special-case the failure shape. */
export function loadCorpusTextMap(language) {
  if (!language) return Promise.resolve(new Map());
  if (_corpusTextCache.has(language)) return Promise.resolve(_corpusTextCache.get(language));
  if (_corpusTextPromises.has(language)) return _corpusTextPromises.get(language);

  const promise = fetch(`/api/texts?language=${encodeURIComponent(language)}`)
    .then((r) => (r && r.ok ? r.json() : []))
    .then((list) => {
      const map = new Map();
      (Array.isArray(list) ? list : []).forEach((t) => {
        const id = String(t?.id || '').replace(/\.tess$/, '').toLowerCase();
        if (id) map.set(id, t);
      });
      _corpusTextCache.set(language, map);
      _corpusTextPromises.delete(language);
      _notifyCorpusTextSubscribers();
      return map;
    })
    .catch(() => {
      const map = new Map();
      _corpusTextCache.set(language, map);
      _corpusTextPromises.delete(language);
      return map;
    });
  _corpusTextPromises.set(language, promise);
  return promise;
}

/** The cached Map for a language, or null when nothing has been fetched
 *  (and is not yet in flight) for it. Synchronous; never fetches. */
export function getCorpusTextMapSync(language) {
  return _corpusTextCache.get(language) || null;
}

/** React hook: the corpus text map for `language`, re-rendering once the
 *  first fetch resolves. Kicks off the fetch itself if nothing has asked
 *  for this language yet; returns null until it is loaded, so a caller
 *  should keep its own fallback for that window. */
export function useCorpusTextMap(language) {
  const [map, setMap] = useState(() => getCorpusTextMapSync(language));

  useEffect(() => {
    if (!language) return undefined;
    const current = getCorpusTextMapSync(language);
    if (current) {
      setMap(current);
      return undefined;
    }
    const onUpdate = () => setMap(getCorpusTextMapSync(language));
    _corpusTextSubscribers.add(onUpdate);
    loadCorpusTextMap(language);
    return () => _corpusTextSubscribers.delete(onUpdate);
  }, [language]);

  return map;
}

/** A ref/tag with any `<...>` markup stripped and whitespace trimmed -- the
 *  raw site id a citation is built from and the value worth keeping visible
 *  (the Cite output, a popover's last line) once the display form is a name. */
export function siteIdFromRef(ref) {
  return String(ref || '').replace(/<\/?.*?>/g, '').trim();
}

/** True for a ref still shaped like the internal id ("hafez.diwan.5097":
 *  lower-case, dot-separated, no comma) rather than a resolved display
 *  citation ("Hafez, Diwan 5097"), which always carries a comma once there
 *  is a work, or at least a capitalized author when there is not. */
export function looksLikeRawSiteId(text) {
  const s = String(text || '').trim();
  if (!s) return true;
  if (s.includes(',')) return false;
  return /^[a-z][a-z0-9_]*(\.[a-z0-9_]+)+$/.test(s);
}

/** Resolve a raw ref against a loaded corpus text map by trying it as
 *  `<known text id>.<reference>`, longest id first (so "iqbal.zabur_e_ajam.26.1"
 *  matches the id "iqbal.zabur_e_ajam", not a shorter false prefix). Returns
 *  null when no segment-prefix of `ref` is a text id the map holds. */
export function citationFromCorpusMap(ref, corpusMap) {
  const clean = siteIdFromRef(ref);
  if (!clean || !corpusMap || !corpusMap.size) return null;
  const segs = clean.split('.');
  for (let cut = segs.length - 1; cut >= 1; cut--) {
    const candidate = segs.slice(0, cut).join('.').toLowerCase();
    const meta = corpusMap.get(candidate);
    if (meta) {
      return {
        author: meta.author || '',
        work: meta.title || meta.work || '',
        reference: segs.slice(cut).join('.'),
        siteId: clean,
        idCut: cut,
      };
    }
  }
  return null;
}

const _joinCitation = ({ author, work, reference }) => {
  const head = work ? `${author}, ${work}` : author;
  return reference ? `${head} ${reference}`.trim() : head;
};

/**
 * The display text for one side of a result card: the server's own
 * citation, or the frontend's static Latin/Greek/English tables, when
 * either already reads as a name ("Vergil, Aeneid 1.1"); the corpus text
 * map's author/title for anything that still reads as a raw id (Persian,
 * Urdu, or any language without a static table entry); the raw id itself,
 * once more, only if nothing above resolved it (the map has not loaded yet).
 *
 * @param {string} existingText what the caller already has (the server
 *   citation, or the static-table `formatReference` result) -- may be '',
 *   missing, or still raw.
 * @param {string} rawRef the unformatted ref/tag this citation is for.
 * @param {Map|null} [corpusMap] a map from `useCorpusTextMap`/`loadCorpusTextMap`.
 * @returns {{text: string, siteId: string}}
 */
export function resolveDisplayCitation(existingText, rawRef, corpusMap) {
  const siteId = siteIdFromRef(rawRef);
  if (existingText && !looksLikeRawSiteId(existingText)) {
    return { text: existingText, siteId };
  }
  const hit = citationFromCorpusMap(siteId, corpusMap);
  if (hit) {
    return { text: _joinCitation(hit), siteId };
  }
  if (existingText) {
    return { text: existingText, siteId };
  }
  if (siteId) {
    const expanded = expandLocus(siteId);
    return { text: _joinCitation(expanded), siteId };
  }
  return { text: '', siteId };
}

/**
 * The Reader header and selection toolbar's own range display: a readable
 * citation for `refStart` (the corpus text map or the static tables,
 * exactly as `resolveDisplayCitation` resolves a result card's), with
 * `refEnd` shortened to only what differs from it -- "Iqbal, Asrar-e
 * Khudi 1.1-5", not "...1.1-iqbal.asrar_e_khudi.1.5". Before this, both
 * spots printed the raw site id and its end ref verbatim whenever no
 * `existingText` citation had been fetched yet for the open text (owner
 * review of Asrar-e Khudi, 2026-10-08) -- which is always true for a
 * passage the reader just selected, since the selection carries only
 * refs, never a citation string.
 *
 * Falls back to the two raw refs, dashed together, only when neither the
 * corpus map nor the static tables resolve anything -- a reader still
 * sees the position rather than nothing.
 *
 * @param {string} refStart
 * @param {string} [refEnd] defaults to `refStart` (a single-ref selection).
 * @param {Map|null} [corpusMap] from `useCorpusTextMap`/`loadCorpusTextMap`.
 * @returns {string}
 */
export function formatSelectionRange(refStart, refEnd, corpusMap) {
  const startId = siteIdFromRef(refStart);
  const endId = siteIdFromRef(refEnd || refStart);
  if (!startId) return endId;
  const start = resolveDisplayCitation('', startId, corpusMap).text || startId;
  if (endId === startId) return start;
  const end = resolveDisplayCitation('', endId, corpusMap).text || endId;
  // Shorten `end` to what differs from `start`: walk both display strings
  // to the first differing character, then back up to the last '.' or ' '
  // boundary before it, so "Iqbal, Asrar-e Khudi 1.1" / "...1.5" yields
  // "5", not a mid-number cut.
  let i = 0;
  while (i < start.length && i < end.length && start[i] === end[i]) i += 1;
  const cut = Math.max(end.lastIndexOf('.', i - 1), end.lastIndexOf(' ', i - 1)) + 1;
  const tail = end.slice(cut) || end;
  return `${start}–${tail}`;
}

/** Collapse a sorted set of line numbers into "a to b" runs, but only once a
 *  run is 3 or more lines long -- "1 to 7" is shorter than spelling out
 *  seven numbers, but "5097 to 5098" is longer than "5097, 5098" for a run
 *  of two, so a short run is listed out instead: [1,2,3,5,7,8] ->
 *  ["1 to 3", "5", "7", "8"]. */
export function collapseLineRuns(nums) {
  const uniq = [...new Set(nums)].sort((a, b) => a - b);
  if (!uniq.length) return [];
  const runs = [];
  let runStart = uniq[0];
  let prev = uniq[0];
  const flush = () => {
    if (prev - runStart + 1 >= 3) {
      runs.push(`${runStart} to ${prev}`);
    } else {
      for (let n = runStart; n <= prev; n++) runs.push(`${n}`);
    }
  };
  for (let i = 1; i <= uniq.length; i++) {
    const n = uniq[i];
    if (n === prev + 1) { prev = n; continue; }
    flush();
    runStart = n;
    prev = n;
  }
  return runs;
}

/**
 * One work's share of a refrain-lines group: the work named once, then its
 * lines collapsed into ranges where they run consecutively. Shared by the
 * refrain-lines popover (one call per side).
 *
 * @param {string[]} refs raw refs, e.g. ["hafez.diwan.5097", "hafez.diwan.5098", ...].
 * @param {Map|null} [corpusMap]
 * @returns {{label: string, text: string}|null}
 */
export function formatLineGroup(refs, corpusMap) {
  const clean = (refs || []).map(siteIdFromRef).filter(Boolean);
  if (!clean.length) return null;

  const first = clean[0];
  const hit = citationFromCorpusMap(first, corpusMap);
  let workLabel;
  let cut;
  if (hit) {
    workLabel = hit.work ? `${hit.author}, ${hit.work}` : hit.author;
    cut = hit.idCut;
  } else {
    const expanded = expandLocus(first);
    workLabel = expanded.work ? `${expanded.author}, ${expanded.work}` : expanded.author;
    const refLen = expanded.reference ? expanded.reference.split('.').length : 1;
    cut = Math.max(1, first.split('.').length - refLen);
  }

  const loci = clean.map((r) => r.split('.').slice(cut).join('.') || r);

  const prefixes = new Set();
  const lineNums = [];
  let allNumeric = loci.length > 0;
  loci.forEach((l) => {
    const segs = l.split('.');
    const last = segs[segs.length - 1];
    if (!/^\d+$/.test(last)) { allNumeric = false; return; }
    lineNums.push(Number(last));
    prefixes.add(segs.slice(0, -1).join('.'));
  });

  let label = workLabel;
  let text;
  if (allNumeric && prefixes.size === 1) {
    const prefix = [...prefixes][0];
    if (prefix) label = `${workLabel} ${prefix}`;
    text = `lines ${collapseLineRuns(lineNums).join(', ')}`;
  } else {
    text = `lines ${loci.join(', ')}`;
  }
  return { label, text };
}

/**
 * The refrain-lines popover's extra content (result card tidy, second pass,
 * 2026-10-08): the two works, each named once with their lines (collapsed
 * into ranges) -- the information the "N + M refrain lines" badge stands
 * for, shown compactly after the badge's one-sentence explanation.
 */
export function formatRefrainPopover(poetics, corpusMap) {
  const sourceLines = poetics?.source_lines || [];
  const targetLines = poetics?.target_lines || [];
  const lines = [formatLineGroup(sourceLines, corpusMap), formatLineGroup(targetLines, corpusMap)]
    .filter(Boolean)
    .map((g) => `${g.label}: ${g.text}`);
  return { lines };
}
