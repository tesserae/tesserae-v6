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

const englishWorkMetadata = {
  'hamlet': { author: 'Shakespeare', title: 'Hamlet' },
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
};

const formatLocation = (loc) => {
  if (!loc) return '';
  return loc.trim().replace(/\s+/g, '.');
};

export const formatReference = (ref, language = null) => {
  if (!ref) return '';
  
  const cleanRef = ref.replace(/<\/?.*?>/g, '').trim();
  
  if (language === 'en' || (!language && /^[a-z_]+\s+[IVX\d]/i.test(cleanRef))) {
    const parts = cleanRef.split(/\s+/);
    if (parts.length >= 2) {
      const workKey = parts[0].toLowerCase();
      const location = formatLocation(parts.slice(1).join('.'));
      
      const meta = englishWorkMetadata[workKey];
      if (meta) {
        return `${meta.author}, ${meta.title} ${location}`;
      }
      const titleCase = workKey.charAt(0).toUpperCase() + workKey.slice(1);
      return `${titleCase} ${location}`;
    }
  }
  
  if (language === 'la' || language === 'grc' || /^[a-z]+[\.\s]/i.test(cleanRef)) {
    const parts = cleanRef.split(/[\.\s]+/);
    
    if (parts.length >= 2) {
      const firstKey = parts[0].toLowerCase().trim();
      const firstMeta = greekLatinWorkMetadata[firstKey];
      
      if (firstMeta) {
        const secondPart = parts[1]?.toLowerCase().trim();
        const workTitle = workTitles[secondPart];
        
        if (workTitle) {
          const location = formatLocation(parts.slice(2).join('.'));
          return `${firstMeta.author}, ${workTitle} ${location}`;
        }
        
        if (firstMeta.work) {
          const location = formatLocation(parts.slice(1).join('.'));
          return `${firstMeta.author}, ${firstMeta.work} ${location}`;
        }
        
        const location = formatLocation(parts.slice(1).join('.'));
        return `${firstMeta.author} ${location}`;
      }
      
      const secondPart = parts[1]?.toLowerCase().trim();
      const workTitle = workTitles[secondPart];
      if (workTitle) {
        const authorCase = firstKey.charAt(0).toUpperCase() + firstKey.slice(1);
        const location = formatLocation(parts.slice(2).join('.'));
        return `${authorCase}, ${workTitle} ${location}`;
      }
    }
  }
  
  return formatLocation(cleanRef.replace(/\s+/g, '.'));
};
