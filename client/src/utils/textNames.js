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

export function expandLocus(locus) {
  if (!locus) return { work: '', reference: locus || '' };
  
  const parts = locus.toLowerCase().split(/[\s.]+/);
  let author = null;
  let work = null;
  let reference = '';
  
  for (let i = 0; i < parts.length; i++) {
    const part = parts[i].replace(/[.,]/g, '');
    
    if (ABBREVIATION_MAP[part]) {
      const mapped = ABBREVIATION_MAP[part];
      if (mapped.author && !author) author = mapped.author;
      if (mapped.work && !work) work = mapped.work;
    } else if (WORK_NAMES[part] && !work) {
      work = WORK_NAMES[part];
    } else if (/^\d/.test(part)) {
      reference = parts.slice(i).join('.');
      break;
    }
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
