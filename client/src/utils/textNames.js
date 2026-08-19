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

export function formatLocus(locus, authorOverride = null) {
  const expanded = expandLocus(locus);
  
  const parts = [];
  if (expanded.work) {
    parts.push(expanded.work);
  }
  if (expanded.reference) {
    parts.push(expanded.reference);
  }
  
  return parts.join(' ') || locus;
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

