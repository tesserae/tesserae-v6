/**
 * Format elapsed time in seconds to a human-readable string.
 * @param {number} seconds - Elapsed time in seconds
 * @returns {string} Formatted time (e.g., "3.2s" or "2m 15s")
 */
export const formatElapsedTime = (seconds) => {
  if (seconds == null || seconds <= 0) return '';
  if (seconds < 60) return `${Number(seconds).toFixed(1)}s`;
  const mins = Math.floor(seconds / 60);
  const secs = Math.round(seconds % 60);
  return `${mins}m ${secs}s`;
};

export const formatDate = (dateString) => {
  if (!dateString) return '';
  const date = new Date(dateString);
  return date.toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric'
  });
};

export const formatScore = (score) => {
  if (typeof score !== 'number') return '-';
  return score.toFixed(2);
};

export const formatLocus = (locus) => {
  if (!locus) return '';
  return locus.replace(/<\/?.*?>/g, '');
};

export const highlightMatches = (text, matches) => {
  if (!matches || matches.length === 0) return text;
  let result = text;
  matches.forEach(match => {
    const regex = new RegExp(`\\b(${match})\\b`, 'gi');
    result = result.replace(regex, '<mark class="bg-yellow-200 px-0.5 rounded">$1</mark>');
  });
  return result;
};

export const getLanguageName = (code) => {
  const names = {
    'la': 'Latin',
    'grc': 'Greek',
    'en': 'English'
  };
  return names[code] || code;
};

export const getEraName = (era) => {
  const eras = {
    'archaic': 'Archaic',
    'classical': 'Classical',
    'hellenistic': 'Hellenistic',
    'republic': 'Republic',
    'augustan': 'Augustan',
    'early_imperial': 'Early Imperial',
    'later_imperial': 'Later Imperial',
    'late_antique': 'Late Antique',
    'early_medieval': 'Early Medieval'
  };
  return eras[era] || era;
};

export const sortByScore = (results) => {
  return [...results].sort((a, b) => (b.score || 0) - (a.score || 0));
};

export const sortByLocus = (results) => {
  return [...results].sort((a, b) => {
    const locusA = a.source_locus || '';
    const locusB = b.source_locus || '';
    return locusA.localeCompare(locusB, undefined, { numeric: true });
  });
};

// The author token of an English reference tag, as written in texts/en, to the
// name shown. Keys are lower-cased with trailing periods removed ("carr." to
// "carr"). Every author in the English corpus as of 2026-09-10.
const ENGLISH_AUTHORS = {
  milton: 'Milton', keats: 'Keats', spenser: 'Spenser', blake: 'Blake',
  bunyan: 'Bunyan', coleridge: 'Coleridge', cowper: 'Cowper',
  ebrowning: 'Elizabeth Barrett Browning', shelley: 'Shelley',
  wordsworth: 'Wordsworth', carr: 'Carroll', swift: 'Swift',
  shake: 'Shakespeare', web: 'World English Bible',
};

// The work token(s) of those tags, keyed the same way (a multi-token work is
// joined with single spaces), to the title shown. A work not listed here is
// shown as written with its trailing periods removed, which is right for
// "Hyperion", "Lycidas", "Comus" and every Bible book.
const ENGLISH_WORKS = {
  'p.l': 'Paradise Lost', 'p.r': 'Paradise Regained',
  'il.pens': 'Il Penseroso', 'l.alleg': "L'Allegro",
  'f.q': 'The Faerie Queene', 'p.p': "The Pilgrim's Progress",
  'r.a.m': 'The Rime of the Ancient Mariner',
  's.exper': 'Songs of Experience', 's.innoc': 'Songs of Innocence',
  'alice': "Alice's Adventures in Wonderland", 'gull': "Gulliver's Travels",
  'prelude': 'The Prelude', 'task': 'The Task', 'son': 'Sonnets',
  'eve.st.agnes': 'The Eve of St. Agnes', 'grecian.urn': 'Ode on a Grecian Urn',
  'ode.bards': 'Ode (Bards of Passion and of Mirth)',
  'mermaid': 'Lines on the Mermaid Tavern', 'robin.hood': 'Robin Hood',
  'autumn': 'To Autumn', 'melancholy': 'Ode on Melancholy',
  'nightingale': 'Ode to a Nightingale', 'psyche': 'Ode to Psyche',
};

const englishWorkMetadata = {
  'hamlet': { author: 'Shakespeare', title: 'Hamlet' },
  'richard iii': { author: 'Shakespeare', title: 'Richard III' },
  'othello': { author: 'Shakespeare', title: 'Othello' },
  'macbeth': { author: 'Shakespeare', title: 'Macbeth' },
  'lear': { author: 'Shakespeare', title: 'King Lear' },
  'tempest': { author: 'Shakespeare', title: 'The Tempest' },
  'midsummer': { author: 'Shakespeare', title: "A Midsummer Night's Dream" },
  'romeo': { author: 'Shakespeare', title: 'Romeo and Juliet' },
  'julius': { author: 'Shakespeare', title: 'Julius Caesar' },
  'merchant': { author: 'Shakespeare', title: 'The Merchant of Venice' },
  'twelfth': { author: 'Shakespeare', title: 'Twelfth Night' },
  'task': { author: 'Cowper', title: 'The Task' },
  'paradise_lost': { author: 'Milton', title: 'Paradise Lost' },
  'paradise_regained': { author: 'Milton', title: 'Paradise Regained' },
  'samson': { author: 'Milton', title: 'Samson Agonistes' },
  'faerie': { author: 'Spenser', title: 'The Faerie Queene' },
  'canterbury': { author: 'Chaucer', title: 'The Canterbury Tales' },
  'beowulf': { author: 'Anonymous', title: 'Beowulf' },
  'pentateuch': { author: 'World English Bible', title: 'Pentateuch' },
  'prophets': { author: 'World English Bible', title: 'Prophets' },
  'revelation': { author: 'World English Bible', title: 'Revelation' },
  'writings': { author: 'World English Bible', title: 'Writings' },
  'iliad': { author: 'Homer (trans.)', title: 'Iliad' },
  'odyssey': { author: 'Homer (trans.)', title: 'Odyssey' },
  'aeneid': { author: 'Vergil (trans.)', title: 'Aeneid' },
};

const greekLatinWorkMetadata = {
  'a': { author: 'Apollonius Rhodius', work: 'Argonautica' },
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
  'apoll': { author: 'Apollonius Rhodius' },
  'apollonius': { author: 'Apollonius Rhodius' },
  'apollonius_rhodius': { author: 'Apollonius Rhodius' },
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
  'verg': { author: 'Vergil' },
  'vergil': { author: 'Vergil' },
  'ov': { author: 'Ovid' },
  'ovid': { author: 'Ovid' },
  'hor': { author: 'Horace' },
  'horace': { author: 'Horace' },
  'luc': { author: 'Lucan', work: 'Bellum Civile' },
  'lucan': { author: 'Lucan', work: 'Bellum Civile' },
  'stat': { author: 'Statius' },
  'statius': { author: 'Statius' },
  'juv': { author: 'Juvenal', work: 'Satires' },
  'iuv': { author: 'Juvenal', work: 'Satires' },
  'juvenal': { author: 'Juvenal', work: 'Satires' },
  'mart': { author: 'Martial', work: 'Epigrammata' },
  'martial': { author: 'Martial', work: 'Epigrammata' },
  'cat': { author: 'Catullus', work: 'Carmina' },
  'catu': { author: 'Catullus', work: 'Carmina' },
  'catullus': { author: 'Catullus', work: 'Carmina' },
  'prop': { author: 'Propertius', work: 'Elegies' },
  'propertius': { author: 'Propertius', work: 'Elegies' },
  'tib': { author: 'Tibullus', work: 'Elegies' },
  'tibullus': { author: 'Tibullus', work: 'Elegies' },
  'lucr': { author: 'Lucretius', work: 'De Rerum Natura' },
  'lucretius': { author: 'Lucretius', work: 'De Rerum Natura' },
  'sil': { author: 'Silius Italicus', work: 'Punica' },
  'sen': { author: 'Seneca' },
  'seneca': { author: 'Seneca' },
  'plaut': { author: 'Plautus' },
  'plautus': { author: 'Plautus' },
  'ter': { author: 'Terence' },
  'terence': { author: 'Terence' },
  'liv': { author: 'Livy' },
  'livy': { author: 'Livy' },
  'tac': { author: 'Tacitus' },
  'tacitus': { author: 'Tacitus' },
  'sall': { author: 'Sallust' },
  'sallust': { author: 'Sallust' },
  'caes': { author: 'Caesar' },
  'caesar': { author: 'Caesar' },
  'cic': { author: 'Cicero' },
  'cicero': { author: 'Cicero' },
  'val': { author: 'Valerius Flaccus' },
  'valerius': { author: 'Valerius Flaccus' },
  'silius': { author: 'Silius Italicus', work: 'Punica' },
  'claud': { author: 'Claudian' },
  'claudian': { author: 'Claudian' },
  'apul': { author: 'Apuleius' },
  'apuleius': { author: 'Apuleius' },
  'aug': { author: 'Augustine' },
  'augustine': { author: 'Augustine' },
  'amm': { author: 'Ammianus' },
  'ammianus': { author: 'Ammianus' },
  'alcuin': { author: 'Alcuin' },
  'hildeb': { author: 'Hildebert of Lavardin' },
  'hildebert': { author: 'Hildebert of Lavardin' },
  'hildebert_of_lavardin': { author: 'Hildebert of Lavardin' },
  'hildeg': { author: 'Hildegard of Bingen' },
  'hildegard': { author: 'Hildegard of Bingen' },
  'hildegard_of_bingen': { author: 'Hildegard of Bingen' },
  'vulgate': { author: 'Vulgate' },
  'petronius': { author: 'Petronius' },
  'petr': { author: 'Petronius' },
  'aus': { author: 'Ausonius' },
  'ausonius': { author: 'Ausonius' },
  'prud': { author: 'Prudentius' },
  'prudentius': { author: 'Prudentius' },
  'gel': { author: 'Aulus Gellius' },
  'gellius': { author: 'Aulus Gellius' },
  'ambrose': { author: 'Ambrose' },
  'tertullian': { author: 'Tertullian' },
  'jerome': { author: 'Jerome' },
};

const workTitles = {
  'il': 'Iliad',
  'iliad': 'Iliad',
  'od': 'Odyssey',
  'odyssey': 'Odyssey',
  'aen': 'Aeneid',
  'aeneid': 'Aeneid',
  'ecl': 'Eclogues',
  'eclogues': 'Eclogues',
  'g': 'Georgics',
  'georg': 'Georgics',
  'georgics': 'Georgics',
  'met': 'Metamorphoses',
  'metamorphoses': 'Metamorphoses',
  'am': 'Amores',
  'amores': 'Amores',
  'ars': 'Ars Amatoria',
  'fast': 'Fasti',
  'fasti': 'Fasti',
  'her': 'Heroides',
  'heroides': 'Heroides',
  'tr': 'Tristia',
  'tristia': 'Tristia',
  'pont': 'Epistulae ex Ponto',
  'carm': 'Odes',
  'odes': 'Odes',
  'sat': 'Satires',
  'satires': 'Satires',
  'ep': 'Epistles',
  'epist': 'Epistles',
  'epistles': 'Epistles',
  'phars': 'Pharsalia',
  'pharsalia': 'Pharsalia',
  'bc': 'Bellum Civile',
  'theb': 'Thebaid',
  'thebaid': 'Thebaid',
  'ach': 'Achilleid',
  'achilleid': 'Achilleid',
  'silv': 'Silvae',
  'silvae': 'Silvae',
  'ag': 'Agamemnon',
  'agamemnon': 'Agamemnon',
  'cho': 'Choephoroe',
  'choephoroe': 'Choephoroe',
  'eum': 'Eumenides',
  'eumenides': 'Eumenides',
  'pers': 'Persae',
  'persae': 'Persae',
  'prom': 'Prometheus Bound',
  'prometheus': 'Prometheus Bound',
  'sept': 'Seven Against Thebes',
  'supp': 'Suppliants',
  'suppliants': 'Suppliants',
  'aj': 'Ajax',
  'ajax': 'Ajax',
  'ant': 'Antigone',
  'antigone': 'Antigone',
  'el': 'Electra',
  'electra': 'Electra',
  'ot': 'Oedipus Tyrannus',
  'oedipus': 'Oedipus Tyrannus',
  'oc': 'Oedipus at Colonus',
  'phil': 'Philoctetes',
  'philoctetes': 'Philoctetes',
  'trach': 'Trachiniae',
  'trachiniae': 'Trachiniae',
  'alc': 'Alcestis',
  'alcestis': 'Alcestis',
  'andr': 'Andromache',
  'andromache': 'Andromache',
  'ba': 'Bacchae',
  'bacchae': 'Bacchae',
  'cycl': 'Cyclops',
  'cyclops': 'Cyclops',
  'hec': 'Hecuba',
  'hecuba': 'Hecuba',
  'hel': 'Helen',
  'helen': 'Helen',
  'heracl': 'Heraclidae',
  'heraclidae': 'Heraclidae',
  'hf': 'Heracles',
  'heracles': 'Heracles',
  'hipp': 'Hippolytus',
  'hippolytus': 'Hippolytus',
  'ia': 'Iphigenia at Aulis',
  'it': 'Iphigenia in Tauris',
  'ion': 'Ion',
  'med': 'Medea',
  'medea': 'Medea',
  'or': 'Orestes',
  'orestes': 'Orestes',
  'phoen': 'Phoenissae',
  'phoenissae': 'Phoenissae',
  'rh': 'Rhesus',
  'rhesus': 'Rhesus',
  'tro': 'Troades',
  'troades': 'Troades',
  'theog': 'Theogony',
  'theogony': 'Theogony',
  'wad': 'Works and Days',
  'shield': 'Shield of Heracles',
  'arg': 'Argonautica',
  'argonautica': 'Argonautica',
  'id': 'Idylls',
  'idylls': 'Idylls',
  'hymn': 'Hymns',
  'hymns': 'Hymns',
  'aet': 'Aetia',
  'aitia': 'Aetia',
  'drn': 'De Rerum Natura',
  'rnr': 'De Rerum Natura',
  'nat': 'De Rerum Natura',
  'genesis': 'Genesis',
  'exodus': 'Exodus',
  'leviticus': 'Leviticus',
  'numbers': 'Numbers',
  'deuteronomy': 'Deuteronomy',
};

// Author-specific work abbreviation overrides.
// These take precedence over the global workTitles map when the author is known.
// Handles multi-part abbreviations (e.g., "her.o" = Hercules Oetaeus for Seneca).
// Canonical override objects to avoid duplication across aliases
const senecaOverrides = {
  'her.o': 'Hercules Oetaeus',
  'her.f': 'Hercules Furens',
  'herc.f': 'Hercules Furens',
  'herc.o': 'Hercules Oetaeus',
  'med': 'Medea',
  'phoen': 'Phoenissae',
  'ag': 'Agamemnon',
  'oed': 'Oedipus',
  'phaedr': 'Phaedra',
  'thy': 'Thyestes',
  'tro': 'Troades',
};

const hildebertOverrides = {
  'carm_lib_reg': 'Carmen in libros regum',
  'carm': 'Carmina',
  'carmina': 'Carmina',
  'de_ordine_mundi': 'De ordine mundi',
  'de_operibus_sex_dierum': 'De operibus sex dierum',
  'de_mysterio_missae': 'De mysterio missae',
  'de_machabaeis': 'De Machabaeis',
  'vita_mariae_aegyptiacae': 'Vita Mariae Aegyptiacae',
};

const hildegardOverrides = {
  'scivias': 'Scivias',
  'physica': 'Physica',
  'cause_et_cure': 'Causae et Curae',
  'symphonia': 'Symphonia',
};

const ciceroOverrides = {
  'att': 'Epistulae ad Atticum',
  'fam': 'Epistulae ad Familiares',
  'ver': 'In Verrem',
  'phil': 'Philippicae',
  'tusc': 'Tusculanae Disputationes',
  'fin': 'De Finibus',
  'nat': 'De Natura Deorum',
  'off': 'De Officiis',
  'catil': 'In Catilinam',
  'arch': 'Pro Archia',
  'brut': 'Brutus',
  'amicit': 'De Amicitia',
  'senect': 'De Senectute',
  'div': 'De Divinatione',
  'rep': 'De Republica',
  'inv': 'De Inventione',
  'orat': 'De Oratore',
  'orator': 'Orator',
  'clu': 'Pro Cluentio',
  'mil': 'Pro Milone',
  'mur': 'Pro Murena',
  'sest': 'Pro Sestio',
  'caec': 'Pro Caecina',
  'planc': 'Pro Plancio',
  'quinct': 'Pro Quinctio',
  'ros': 'Pro Roscio Amerino',
};

const plautusOverrides = {
  'amph': 'Amphitruo',
  'am': 'Amphitruo',
  'asin': 'Asinaria',
  'as': 'Asinaria',
  'aul': 'Aulularia',
  'bacch': 'Bacchides',
  'capt': 'Captivi',
  'cas': 'Casina',
  'cist': 'Cistellaria',
  'curc': 'Curculio',
  'epid': 'Epidicus',
  'ep': 'Epidicus',
  'men': 'Menaechmi',
  'merc': 'Mercator',
  'mil': 'Miles Gloriosus',
  'most': 'Mostellaria',
  'pers': 'Persa',
  'poen': 'Poenulus',
  'pseud': 'Pseudolus',
  'ps': 'Pseudolus',
  'rud': 'Rudens',
  'stich': 'Stichus',
  'trin': 'Trinummus',
  'truc': 'Truculentus',
};

const ausoniusOverrides = {
  'mos': 'Mosella',
  'biss': 'Bissula',
  'caes': 'Caesares',
  'cent': 'Cento Nuptialis',
  'cup': 'Cupido Cruciatus',
  'ecl': 'Eclogae',
  'ep': 'Epistulae',
  'ephem': 'Ephemeris',
  'epigr': 'Epigrammata',
  'epit': 'Epitaphia',
  'fast': 'Fasti',
  'grat': 'Gratiarum Actio',
  'griph': 'Griphus Ternarii Numeri',
  'idyll': 'Idyllia',
  'orat': 'Oratio',
  'par': 'Parentalia',
  'praef': 'Praefationes',
  'prof': 'Professores',
  'sap': 'Ludus Septem Sapientum',
  'tech': 'Technopaegnion',
  'urb': 'Ordo Urbium Nobilium',
};

const prudentiusOverrides = {
  'apo': 'Apotheosis',
  'ditto': 'Dittochaeon',
  'epil': 'Epilogus',
  'ham': 'Hamartigenia',
  'peristeph': 'Peristephanon',
  'psych': 'Psychomachia',
  'sym': 'Contra Symmachum',
};

const claudianOverrides = {
  'cm': 'Carmina Minora',
  'cons': 'Panegyricus de Consulatu',
  'eutr': 'In Eutropium',
  'gild': 'De Bello Gildonico',
  'goth': 'De Bello Gothico',
  'mall': 'Panegyricus de Consulatu Mallii',
  'nupt': 'Epithalamium de Nuptiis Honori et Mariae',
  'rapt': 'De Raptu Proserpinae',
  'ruf': 'In Rufinum',
};

const ammianusOverrides = {
  'gest': 'Rerum Gestarum',
};

const sallustOverrides = {
  'cat': 'Bellum Catilinae',
  'catil': 'Bellum Catilinae',
  'jug': 'Bellum Iugurthinum',
  'iug': 'Bellum Iugurthinum',
};

const alcuinOverrides = {
  'carm': 'Carmina',
  'carmina': 'Carmina',
};

const horaceOverrides = {
  'carm': 'Odes',
};

const jeromeOverrides = {
  'in_hier': 'In Hieremiam Prophetam',
  'ep': 'Epistulae',
};

const authorWorkOverrides = {
  'sen': senecaOverrides,
  'seneca': senecaOverrides,
  'alcuin': alcuinOverrides,
  'hor': horaceOverrides,
  'horace': horaceOverrides,
  'hildeb': hildebertOverrides,
  'hildebert': hildebertOverrides,
  'hildebert_of_lavardin': hildebertOverrides,
  'hildeg': hildegardOverrides,
  'hildegard': hildegardOverrides,
  'hildegard_of_bingen': hildegardOverrides,
  'cic': ciceroOverrides,
  'cicero': ciceroOverrides,
  'plaut': plautusOverrides,
  'plautus': plautusOverrides,
  'amm': ammianusOverrides,
  'ammianus': ammianusOverrides,
  'sall': sallustOverrides,
  'sallust': sallustOverrides,
  'aus': ausoniusOverrides,
  'ausonius': ausoniusOverrides,
  'prud': prudentiusOverrides,
  'prudentius': prudentiusOverrides,
  'claud': claudianOverrides,
  'claudian': claudianOverrides,
  'jerome': jeromeOverrides
};

const formatLocation = (loc) => {
  if (!loc) return '';
  return loc.trim().replace(/\s+/g, '.');
};

const appendLocation = (base, location) => (location ? `${base} ${location}` : base);

const formatUnderscoreTitle = (tag) => {
  if (!tag) return '';
  return tag
    .split('_')
    .filter(Boolean)
    .map(word => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ');
};

export const formatReference = (ref, language = null) => {
  if (!ref) return '';

  const cleanRef = ref.replace(/<\/?.*?>/g, '').trim();

  // Handle range refs from window results (e.g., "verg. aen. 1.469-verg. aen. 1.470")
  if (cleanRef.includes('-')) {
    const dashIdx = cleanRef.indexOf('-');
    const left = cleanRef.slice(0, dashIdx).trim();
    const right = cleanRef.slice(dashIdx + 1).trim();
    // Only treat as range if right side looks like a ref (has letters), not just a number
    if (right && /[a-z]/i.test(right)) {
      const formattedLeft = formatReference(left, language);
      const formattedRight = formatReference(right, language);
      // If same author+work, abbreviate: "Vergil, Aeneid 1.469–470"
      // Find where the two formatted strings diverge
      const leftParts = formattedLeft.split(/\s+/);
      const rightParts = formattedRight.split(/\s+/);
      // Find the last numeric part of the right side (the line number)
      const rightLoc = rightParts[rightParts.length - 1];
      const rightLineMatch = rightLoc?.match(/(\d+)$/);
      // Check if everything except the final number matches
      const leftPrefix = leftParts.slice(0, -1).join(' ');
      const rightPrefix = rightParts.slice(0, -1).join(' ');
      if (leftPrefix === rightPrefix && rightLineMatch) {
        return `${formattedLeft}\u2013${rightLineMatch[1]}`;
      }
      return `${formattedLeft}\u2013${formattedRight}`;
    }
  }
  
  if (language === 'en' || (!language && /^[a-z_]+\s+[IVX\d]/i.test(cleanRef))) {
    const parts = cleanRef.split(/\s+/);
    if (parts.length >= 2) {
      // Most English tags name the author and then the work, often as an
      // abbreviation with periods: "Milton P.L. 1.225", "Spenser F.Q. 1.1.1",
      // "carr. alice. 1.12", "WEB 1 Kings 2.3". The branch below was written
      // for the other shape, "hamlet 3.1", where the first token is the work,
      // so on a Milton tag it took "Milton" as the work, found nothing, and
      // joined the rest with periods: "Milton P.L..1.225", "Keats
      // Hyperion.1.296" (NC, 2026-09-10, preparing a talk). The locus is the
      // last token; everything before it is author and work.
      const location = formatLocation(parts[parts.length - 1]);
      const prefix = parts.slice(0, -1);
      const key = (s) => s.toLowerCase().replace(/\.+$/, '');
      const authorKey = key(prefix[0]);
      const author = ENGLISH_AUTHORS[authorKey];
      if (author && prefix.length >= 2) {
        const workTokens = prefix.slice(1);
        const workKey = workTokens.map(key).join(' ');
        const title = ENGLISH_WORKS[workKey]
          || (author === 'World English Bible'
            ? workTokens.join(' ')
            : workTokens.map((w) => w.replace(/\.+$/, '')).join(' '));
        return appendLocation(`${author}, ${title}`, location);
      }
      const workKey = prefix.map(key).join(' ');
      const meta = englishWorkMetadata[workKey] || englishWorkMetadata[key(parts[0])];
      if (meta) {
        return appendLocation(`${meta.author}, ${meta.title}`, location);
      }
      const titleCase = workKey.charAt(0).toUpperCase() + workKey.slice(1);
      return appendLocation(titleCase, location);
    }
  }
  
  if (language === 'la' || language === 'grc' || /^[a-z][a-z_0-9]*[\.\s]/i.test(cleanRef)) {
    const parts = cleanRef.split(/[\.\s]+/);
    
    if (parts.length >= 2) {
      const firstKey = parts[0].toLowerCase().trim();
      const firstMeta = greekLatinWorkMetadata[firstKey];
      
      if (firstMeta) {
        const secondPart = parts[1]?.toLowerCase().trim();
        const thirdPart = parts[2]?.toLowerCase().trim();

        // Check author-specific overrides first (handles multi-part abbreviations)
        const overrides = authorWorkOverrides[firstKey];
        if (overrides) {
          // Try two-part abbreviation first (e.g., "her.o" for Seneca)
          const twoPartKey = secondPart && thirdPart ? `${secondPart}.${thirdPart}` : null;
          if (twoPartKey && overrides[twoPartKey]) {
            const location = formatLocation(parts.slice(3).join('.'));
            return appendLocation(`${firstMeta.author}, ${overrides[twoPartKey]}`, location);
          }
          // Try single-part abbreviation (e.g., "med" for Seneca)
          if (secondPart && overrides[secondPart]) {
            const location = formatLocation(parts.slice(2).join('.'));
            return appendLocation(`${firstMeta.author}, ${overrides[secondPart]}`, location);
          }
        }

        // Fall back to global work titles
        const workTitle = workTitles[secondPart];

        if (workTitle) {
          const location = formatLocation(parts.slice(2).join('.'));
          return appendLocation(`${firstMeta.author}, ${workTitle}`, location);
        }

        // Smart fallback: If second part has underscores (e.g., "de_civitate_dei"),
        // automatically format it as a title ("De Civitate Dei").
        if (secondPart && secondPart.includes('_')) {
          const formattedTitle = formatUnderscoreTitle(secondPart);
          if (formattedTitle) {
            const location = formatLocation(parts.slice(2).join('.'));
            return appendLocation(`${firstMeta.author}, ${formattedTitle}`, location);
          }
        }

        if (firstMeta.work) {
          const location = formatLocation(parts.slice(1).join('.'));
          return appendLocation(`${firstMeta.author}, ${firstMeta.work}`, location);
        }

        const location = formatLocation(parts.slice(1).join('.'));
        return appendLocation(firstMeta.author, location);
      }
      
      const secondPart = parts[1]?.toLowerCase().trim();
      const workTitle = workTitles[secondPart];
      if (workTitle) {
        const authorCase = firstKey.charAt(0).toUpperCase() + firstKey.slice(1);
        const location = formatLocation(parts.slice(2).join('.'));
        return appendLocation(`${authorCase}, ${workTitle}`, location);
      }

      // Smart fallback for anonymous/unknown work tags with underscores (e.g., "carm_biblioth")
      if (firstKey.includes('_')) {
        const formattedTitle = formatUnderscoreTitle(firstKey);
        if (formattedTitle) {
          const location = formatLocation(parts.slice(1).join('.'));
          return appendLocation(formattedTitle, location);
        }
      }
    }
  }
  
  return formatLocation(cleanRef.replace(/\s+/g, '.'));
};
