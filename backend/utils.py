"""
Tesserae V6 - Utility Functions
"""
import os
import re
import json
import logging
import unicodedata

logger = logging.getLogger(__name__)

OVERRIDES_PATH = os.path.join(os.path.dirname(__file__), 'text_metadata_overrides.json')
PROVENANCE_PATH = os.path.join(os.path.dirname(__file__), 'text_provenance.json')

_overrides_cache = None
_overrides_mtime = 0
_provenance_cache = None
_provenance_mtime = 0

def load_provenance(force_reload=False):
    """Load text provenance data from JSON with caching."""
    global _provenance_cache, _provenance_mtime
    try:
        if not os.path.exists(PROVENANCE_PATH):
            return {"sources": {}, "texts": {}}
            
        mtime = os.path.getmtime(PROVENANCE_PATH)
        if not force_reload and _provenance_cache is not None and mtime == _provenance_mtime:
            return _provenance_cache
            
        with open(PROVENANCE_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        # Ensure the structure is correct
        # If it's a flat dict with text keys, or if it has 'sources' but not 'texts'
        if "texts" not in data:
            # We want to keep all top-level keys EXCEPT 'sources' and metadata keys
            texts_dict = {k: v for k, v in data.items() if k not in ("sources", "_description", "_format")}
            data = {"sources": data.get("sources", {}), "texts": texts_dict}

        # Pre-build a normalized (NFC) index for O(1) fallback lookups
        norm_index = {}
        for k, v in data["texts"].items():
            norm_index.setdefault(unicodedata.normalize('NFC', k), v)
        data["_norm_index"] = norm_index

        _provenance_cache = data
        _provenance_mtime = mtime
        return _provenance_cache
    except Exception as e:
        logger.warning(f"Could not load text provenance: {e}")
        return {"sources": {}, "texts": {}}

def resolve_text_path(texts_dir, language, text_id):
    """Resolve a text file path, handling Unicode normalization mismatches.

    Guards against directory traversal by ensuring the resolved path stays
    within texts_dir/language. Returns the real path string or None.
    """
    base_dir = os.path.realpath(texts_dir)
    lang_dir = os.path.realpath(os.path.join(base_dir, language))

    # Reject traversal outside texts_dir
    try:
        if os.path.commonpath([base_dir, lang_dir]) != base_dir:
            return None
    except ValueError:
        return None

    if not os.path.isdir(lang_dir):
        return None

    # 1. Try direct match, validating resolved path stays inside lang_dir
    direct_path = os.path.realpath(os.path.join(lang_dir, text_id))
    try:
        if os.path.commonpath([lang_dir, direct_path]) != lang_dir:
            return None
    except ValueError:
        return None
    if os.path.exists(direct_path):
        return direct_path

    # 2. Try normalized match (NFC)
    # Browsers often send NFC, but the filesystem may store filenames in NFD
    target_norm = unicodedata.normalize('NFC', text_id)
    try:
        for filename in os.listdir(lang_dir):
            if unicodedata.normalize('NFC', filename) == target_norm:
                return os.path.join(lang_dir, filename)
    except OSError:
        pass

    return None

def load_metadata_overrides(force_reload=False):
    global _overrides_cache, _overrides_mtime
    try:
        mtime = os.path.getmtime(OVERRIDES_PATH)
        if not force_reload and _overrides_cache is not None and mtime == _overrides_mtime:
            return _overrides_cache
        with open(OVERRIDES_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
        _overrides_cache = {k: v for k, v in data.items() if not k.startswith('_')}
        _overrides_mtime = mtime
        return _overrides_cache
    except Exception as e:
        logger.warning(f"Could not load metadata overrides: {e}")
        return {}

def save_metadata_overrides(overrides):
    global _overrides_cache, _overrides_mtime
    try:
        with open(OVERRIDES_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception:
        data = {}
    meta_keys = {k: v for k, v in data.items() if k.startswith('_')}
    meta_keys['_last_updated'] = __import__('datetime').date.today().isoformat()
    merged = {**meta_keys, **overrides}
    with open(OVERRIDES_PATH, 'w', encoding='utf-8') as f:
        json.dump(merged, f, indent=2, ensure_ascii=False)
    _overrides_cache = overrides
    _overrides_mtime = os.path.getmtime(OVERRIDES_PATH)

def get_override(text_id):
    overrides = load_metadata_overrides()
    return overrides.get(text_id, {})

def set_override(text_id, fields):
    overrides = load_metadata_overrides()
    if not fields or all(v == '' or v is None for v in fields.values()):
        overrides.pop(text_id, None)
    else:
        clean = {k: v for k, v in fields.items() if v is not None and v != ''}
        if clean:
            overrides[text_id] = clean
        else:
            overrides.pop(text_id, None)
    save_metadata_overrides(overrides)

def load_corpus(directory):
    """Load all .tess files from a directory"""
    texts = []
    if not os.path.exists(directory):
        return texts
    
    for filename in os.listdir(directory):
        if filename.endswith('.tess'):
            filepath = os.path.join(directory, filename)
            metadata = get_text_metadata(filepath)
            texts.append(metadata)
    
    return texts

def clean_cts_reference(ref):
    """Clean CTS URN references to extract readable locus
    e.g., 'urn:cts:latinLit:stoa0040.stoa001.opp-lat1.1.1' -> '1.1'
    """
    if not ref:
        return ref
    
    if 'urn:cts:' in ref:
        parts = ref.split('.')
        numeric_parts = []
        for p in reversed(parts):
            if p and (p.isdigit() or re.match(r'^\d+[a-z]?$', p)):
                numeric_parts.insert(0, p)
            else:
                break
        if numeric_parts:
            return '.'.join(numeric_parts)
    
    return ref

# --- Unified text type classification (5-tier cascade) ---
#
# Tier 1: Manual overrides (text_metadata_overrides.json)
# Tier 2: POETRY_WORKS — explicit known-poetry edge cases that the content
#          heuristic would misclassify (e.g., long .tess lines = multi-verse entries)
# Tier 3: PROSE_WORKS — consolidated list from all detection systems
# Tier 4: Content heuristic — median line length >100 chars = prose
# Tier 5: Default to "poetry" (backward compatible)

POETRY_WORKS = [
    # Dante's Divina Comedia — Latin hexameter verse, but .tess lines are long
    # (~120+ chars) because each entry = one terzina (multiple verses)
    'dante', 'divina_comedia', 'divina_commedia', 'divine_comedy', 'commedia',
    # Sedulius's Carmen Paschale — verse, distinct from his prose Opus Paschale
    'carmen_paschale',
    # Augustine's Psalmus contra partem Donati — rare verse work by a prose author
    'psalmus_contra_partem_donati',
]

PROSE_AUTHORS = [
    # Latin prose authors
    # NOTE: Authors who wrote BOTH prose and verse (cyprian, hilary, lactantius,
    # petronius, florus) are intentionally omitted — the content heuristic (Tier 4)
    # correctly handles them. Only unambiguous prose authors belong here.
    'cicero', 'caesar.', 'livy', 'sallust', 'tacitus', 'suetonius',
    'nepos', 'quintilian', 'pliny', 'apuleius',
    'augustine', 'jerome', 'ambrose', 'seneca_prose', 'ammianus',
    'curtius', 'valerius_maximus', 'gellius', 'macrobius', 'boethius',
    'cassiodorus', 'isidore', 'bede', 'hegesippus',
    'cassian', 'tertullian.', 'minucius',
    'arnobius', 'firmicus', 'sulpicius', 'orosius', 'salvian',
    'eutropius', 'justinus', 'frontinus', 'eugippius',
    'salutati', 'petrarch', 'boccaccio', 'poggio',
    'bruni', 'valla', 'ficino', 'poliziano', 'erasmus',
    'vitruvius', 'celsus', 'columella', 'adamnan',
    'scriptores_historiae_augustae',
    # Latin abbreviations (only for unambiguous prose authors)
    'cic.', 'caes.', 'liv.', 'sall.', 'tac.', 'suet.', 'nep.',
    'quint.', 'plin.', 'apul.', 'aug.', 'hier.', 'ambr.',
    'amm.', 'curt.', 'val.max.', 'gell.', 'macr.', 'boeth.', 'cass.',
    'isid.', 'bed.', 'oros.', 'eutr.',
    # Greek prose authors
    # NOTE: 'dio' removed (3-char substring matches inside Latin words like
    # 'herediolo', 'exordio'). 'strabo' removed (matches walafrid_strabo, a poet).
    # Both are correctly handled by the content heuristic.
    'epictetus', 'plato', 'aristotle', 'xenophon', 'thucydides', 'herodotus',
    'plutarch', 'lucian', 'demosthenes', 'isocrates', 'lysias', 'polybius',
    'diodorus', 'pausanias', 'appian', 'arrian',
    'diogenes_laertius', 'athenaeus', 'aelian', 'philostratus', 'plotinus',
    'porphyry', 'iamblichus', 'proclus', 'longinus', 'galen', 'hippocrates',
    'josephus', 'philo_judaeus', 'clement', 'origen', 'eusebius', 'basil', 'gregory',
    'chrysostom', 'theodoret', 'procopius', 'agathias',
    'achilles_tatius', 'dio_chrysostom', 'marcus_aurelius',
    'theophrastus', 'sextus_empiricus', 'archimedes',
    'aelius_aristides', 'aeschines',
    # Greek abbreviations
    'plat.', 'arist.', 'thuc.', 'hdt.', 'xen.', 'dem.',
    'lys.', 'isoc.', 'plut.', 'diod.', 'polyb.', 'strab.',
    # English prose authors
    'defoe', 'richardson', 'fielding', 'austen', 'dickens',
    'bacon', 'locke', 'hume', 'mill',
    'addison', 'steele', 'johnson',
    'gibbon', 'macaulay', 'carlyle', 'burke', 'paine', 'wollstonecraft',
]

PROSE_MARKERS = [
    # Work titles that unambiguously indicate prose
    # NOTE: Generic markers like 'annales', 'historiae', 'panegyricus', 'contra_',
    # 'fabulae', 'de_spectaculis', 'apologeticum' were removed — they match verse
    # works (Ennius Annales, Claudian panegyrics, Prudentius Contra Symmachum,
    # Phaedrus Fabulae, Martial De Spectaculis, Commodian Carmen Apologeticum).
    # The content heuristic correctly handles all prose works with these titles.
    'epistulae', 'letters', 'de_officiis', 'de_oratore',
    'de_finibus', 'de_natura', 'tusculan', 'bellum_gallicum',
    'agricola', 'germania',
    'dialogus', 'satyricon', 'confessiones', 'de_civitate',
    'res_gestae', 'rerum_gestarum', 'orationes', 'in_catilinam',
    'adversus_',
    # Cicero speeches and other specific Latin prose markers
    'epistulae_ad_familiares', 'epistulae_ad_atticum', 'epistulae_morales',
    'letters_to_atticus', 'letters_to_brutus', 'letters_to_quintus', 'letters_to_friends',
    'de_natura_deorum', 'de_republica', 'de_legibus', 'de_amicitia', 'de_senectute',
    'academica', 'pro_milone', 'pro_caelio', 'pro_murena', 'pro_archia', 'pro_sestio',
    'in_verrem', 'philippicae',
    'bellum_civile_caesar', 'bellum_africum', 'bellum_hispaniense',
    'annales_tacitus', 'historiae_tacitus',
    'ab_urbe_condita', 'periochae',
    'naturalis_historia',
    'institutio_oratoria', 'controversiae', 'suasoriae',
    'de_civitate_dei',
    # Greek prose work markers
    'apology', 'symposium', 'phaedo', 'republic', 'laws', 'timaeus',
    'ethics', 'politics', 'rhetoric', 'metaphysics', 'poetics_aristotle',
    'histories_herodotus', 'peloponnesian', 'anabasis', 'hellenica', 'memorabilia',
    'discourses', 'enchiridion',
    'lives', 'moralia', 'leucippe', 'varia_historia', 'epitome',
    'against_ctesiphon', 'against_timarchus', 'on_the_embassy',
    'meditations', 'progymnasmata', 'ars_rhetorica',
    # Bible / religious prose
    'bible', 'vulgate', 'gospel',
    # Apuleius prose (distinct from Ovid's Metamorphoses via author check)
    'asinus_aureus', 'golden_ass', 'florida', 'apologia',
    # Late antique / medieval prose markers
    'excidio', 'hierosolymitano', 'tractatus', 'super_psalmos',
    'conlationes', 'institutionum', 'divinarum',
    'adversus_marcionem',
    'opus_paschale', 'de_laboribus',
    'confucius', 'sinarum', 'philosophus',
    # English prose markers
    'robinson', 'crusoe', 'pamela', 'clarissa', 'tom_jones', 'joseph_andrews',
    'pride', 'prejudice', 'sensibility', 'emma', 'mansfield',
    'oliver', 'twist', 'expectations', 'copperfield', 'tale_two',
    'essays', 'liberty', 'spectator', 'rambler',
    'decline', 'fall',
]

# Combined list for backward compatibility
PROSE_WORKS = PROSE_AUTHORS + PROSE_MARKERS


def _resolve_text_filepath(filename, language=None):
    """Find the .tess file path for a text ID by checking text directories."""
    texts_root = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'texts')
    if language:
        langs = [language]
    else:
        langs = ['la', 'grc', 'en']
    for lang in langs:
        lang_dir = os.path.join(texts_root, lang)
        if not os.path.isdir(lang_dir):
            continue
        candidate = os.path.join(lang_dir, filename)
        if os.path.isfile(candidate):
            return candidate
        # Try with .tess extension
        if not filename.endswith('.tess'):
            candidate = os.path.join(lang_dir, filename + '.tess')
            if os.path.isfile(candidate):
                return candidate
    return None


def _estimate_text_type_from_content(filepath):
    """Classify by median line length. >100 chars = prose, ≤100 = poetry.

    Classical poetry lines are 30-55 chars (hexameter, lyric, drama).
    Prose lines are 150-250+ chars. The 100-char threshold cleanly separates
    the two with near-zero overlap.

    Reads up to 200 lines, strips <reference> tags, computes median text length.
    """
    import statistics as _stats

    lengths = []
    try:
        with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
            for i, line in enumerate(f):
                if i >= 200:
                    break
                line = line.strip()
                if not line:
                    continue
                # Strip <reference> tag at start of line
                text = re.sub(r'^<[^>]+>\s*', '', line).strip()
                if text:
                    lengths.append(len(text))
    except Exception:
        return None

    if not lengths:
        return None

    median = _stats.median(lengths)
    return 'prose' if median > 100 else 'poetry'


def detect_text_type(filename, content=None, filepath=None, language=None):
    """Detect if text is poetry or prose using a 5-tier cascade.

    Tier 1: Manual overrides (text_metadata_overrides.json) — highest priority
    Tier 2: POETRY_WORKS — explicit known-poetry edge cases
    Tier 3: PROSE_WORKS — consolidated prose author/marker list
    Tier 4: Content heuristic — median line length (if filepath available)
    Tier 5: Default to "poetry" — backward compatible
    """
    # Tier 1: Manual overrides
    override = get_override(filename)
    if 'text_type' in override:
        return override['text_type']

    name_lower = filename.lower().replace('.tess', '')

    # Tier 2: POETRY_WORKS — known-poetry edge cases (checked before prose)
    for marker in POETRY_WORKS:
        if marker in name_lower:
            return 'poetry'

    # Tier 3: PROSE_WORKS — consolidated prose authors + markers
    for marker in PROSE_AUTHORS + PROSE_MARKERS:
        if marker in name_lower:
            return 'prose'

    # Tier 4: Content heuristic — median line length
    resolved = filepath
    if not resolved:
        resolved = _resolve_text_filepath(filename, language)
    if resolved and os.path.isfile(resolved):
        result = _estimate_text_type_from_content(resolved)
        if result:
            return result

    # Tier 5: Default to poetry (backward compatible)
    return 'poetry'

DISPLAY_NAMES = {
    'vergil': 'Vergil',
    'vergil_pseudo': 'Pseudo-Vergil',
    'cicero': 'Cicero',
    'ovid': 'Ovid',
    'horace': 'Horace',
    'lucan': 'Lucan',
    'statius': 'Statius',
    'juvenal': 'Juvenal',
    'martial': 'Martial',
    'catullus': 'Catullus',
    'propertius': 'Propertius',
    'tibullus': 'Tibullus',
    'lucretius': 'Lucretius',
    'seneca': 'Seneca',
    'seneca_younger': 'Seneca the Younger',
    'plautus': 'Plautus',
    'terence': 'Terence',
    'livy': 'Livy',
    'tacitus': 'Tacitus',
    'sallust': 'Sallust',
    'caesar': 'Caesar',
    'valerius_flaccus': 'Valerius Flaccus',
    'silius_italicus': 'Silius Italicus',
    'claudian': 'Claudian',
    'apuleius': 'Apuleius',
    'augustine': 'Augustine',
    'ammianus': 'Ammianus Marcellinus',
    'homer': 'Homer',
    'hesiod': 'Hesiod',
    'aeschylus': 'Aeschylus',
    'sophocles': 'Sophocles',
    'euripides': 'Euripides',
    'aristophanes': 'Aristophanes',
    'plato': 'Plato',
    'aristotle': 'Aristotle',
    'thucydides': 'Thucydides',
    'herodotus': 'Herodotus',
    'plutarch': 'Plutarch',
    'aeneid': 'Aeneid',
    'eclogues': 'Eclogues',
    'georgics': 'Georgics',
    'metamorphoses': 'Metamorphoses',
    'iliad': 'Iliad',
    'odyssey': 'Odyssey',
    'bellum_civile': 'Bellum Civile (Pharsalia)',
    'thebaid': 'Thebaid',
    'achilleid': 'Achilleid',
    'argonautica': 'Argonautica',
    'punica': 'Punica',
    'de_rerum_natura': 'De Rerum Natura',
    'ars_amatoria': 'Ars Amatoria',
    'amores': 'Amores',
    'fasti': 'Fasti',
    'tristia': 'Tristia',
    'heroides': 'Heroides',
    'odes': 'Carmina',
    'carmina': 'Carmina',
    'satires': 'Satires',
    'epistles': 'Epistles',
    'ars_poetica': 'Ars Poetica',
    'rerum_gestarum': 'Res Gestae',
    'confessiones': 'Confessions',
    'de_civitate_dei': 'City of God',
    'cowper': 'Cowper',
    'task': 'The Task',
    'shakespeare': 'Shakespeare',
    'hamlet': 'Hamlet',
    'milton': 'Milton',
    'paradise_lost': 'Paradise Lost',
    'world_english_bible': 'World English Bible',
    'pentateuch': 'Pentateuch',
    'prophets': 'Prophets',
    'revelation': 'Revelation',
    'writings': 'Writings',
}

def format_display_name(raw_name):
    """Convert raw filename part to proper display name"""
    key = raw_name.lower().replace(' ', '_')
    if key in DISPLAY_NAMES:
        return DISPLAY_NAMES[key]
    return raw_name.replace('_', ' ').title()

# Works where parts are individual poems, not books
PART_LABEL_OVERRIDES = {
    'alcuin.carmina': 'Poem',
    'theodulf_of_orleans.carmina': 'Poem',
    'paulinus_of_aquileia.carmina': 'Poem',
}

def parse_part_number(part_str, label='Book'):
    """Parse part number and return display label"""
    part_str = part_str.lower()
    if part_str == 'fragments':
        return 'Fragments'
    try:
        num = int(part_str)
        return f'{label} {num}'
    except ValueError:
        # Handle alphanumeric identifiers like "2a", "2b" with the label
        import re as _re
        if _re.match(r'^\d+[a-z]$', part_str):
            return f'{label} {part_str}'
        return part_str.replace('_', ' ').title()

def fix_surrogate_escapes(s):
    """Fix Python surrogate escapes from non-UTF-8 locale filesystems.
    When Apache/WSGI runs with a non-UTF-8 locale, Python's os.listdir()
    uses surrogateescape for non-ASCII bytes, producing invalid surrogates
    in strings. This re-encodes and properly decodes them as UTF-8."""
    try:
        return s.encode('utf-8', 'surrogateescape').decode('utf-8')
    except (UnicodeDecodeError, UnicodeEncodeError):
        return s

def safe_listdir(directory):
    """List directory contents with proper UTF-8 filename handling.
    Fixes surrogate escapes from non-UTF-8 locale environments (e.g. Apache/WSGI)."""
    try:
        entries = os.listdir(directory)
    except OSError:
        return []
    return [fix_surrogate_escapes(e) for e in entries]

def get_text_metadata(filepath):
    """Extract metadata from a .tess filename with hierarchical structure"""
    filename = fix_surrogate_escapes(os.path.basename(filepath))
    name = filename.replace('.tess', '')
    
    parts = name.split('.')
    author_raw = parts[0] if len(parts) >= 1 else 'unknown'
    author = format_display_name(author_raw)
    
    work_raw = None
    work = None
    part_num = None
    part_display = None
    is_part = False
    
    if len(parts) >= 2:
        if 'part' in parts:
            part_idx = parts.index('part')
            work_raw = '.'.join(parts[1:part_idx])
            if part_idx + 1 < len(parts):
                part_num = parts[part_idx + 1]
                work_part_key = f"{author_raw}.{'.'.join(parts[1:part_idx])}"
                part_label = PART_LABEL_OVERRIDES.get(work_part_key, 'Book')
                part_display = parse_part_number(part_num, label=part_label)
                is_part = True
        else:
            work_raw = '.'.join(parts[1:])
        
        work = format_display_name(work_raw) if work_raw else 'Unknown'
    else:
        work = format_display_name(name)
    
    if is_part and part_display:
        title = f"{work}, {part_display}"
    else:
        title = work
    
    text_type = detect_text_type(filename, filepath=filepath)
    
    # Get provenance info using the pre-built NFC index for O(1) lookup
    provenance_data = load_provenance()
    texts_prov = provenance_data.get('texts', {})
    norm_index = provenance_data.get('_norm_index', {})
    filename_norm = unicodedata.normalize('NFC', filename)
    provenance = texts_prov.get(filename) or norm_index.get(filename_norm, {})
    
    if provenance:
        if 'author' in provenance:
            author = provenance['author']
        if 'title' in provenance:
            title = provenance['title'] or title
            work = title # For display consistency
    
    override = get_override(filename)
    if 'display_author' in override:
        author = override['display_author']
    if 'display_work' in override:
        work = override['display_work']
        if is_part and part_display:
            title = f"{work}, {part_display}"
        else:
            title = work
    
    result = {
        'id': filename,
        'author': author,
        'author_key': author_raw,
        'work': work,
        'work_key': work_raw or name,
        'part': part_display,
        'part_num': part_num,
        'is_part': is_part,
        'title': title,
        'display_name': f"{author}, {title}",
        'filepath': filepath,
        'text_type': text_type
    }
    
    if 'year' in override:
        result['year'] = override['year']
    if 'era' in override:
        result['era'] = override['era']
    if override:
        result['has_override'] = True
    
    return result

def build_text_hierarchy(texts):
    """Build hierarchical structure: Author -> Work -> Parts"""
    hierarchy = {}
    
    for text in texts:
        author_key = text.get('author_key', text['author'].lower())
        work_key = text.get('work_key', text.get('work', '').lower())
        
        if author_key not in hierarchy:
            hierarchy[author_key] = {
                'author': text['author'],
                'works': {}
            }
        
        if work_key not in hierarchy[author_key]['works']:
            hierarchy[author_key]['works'][work_key] = {
                'work': text.get('work', text['title']),
                'whole_text': None,
                'parts': []
            }
        
        if text.get('is_part'):
            hierarchy[author_key]['works'][work_key]['parts'].append({
                'id': text['id'],
                'part': text.get('part'),
                'part_num': text.get('part_num'),
                'display': text.get('part', 'Part')
            })
        else:
            hierarchy[author_key]['works'][work_key]['whole_text'] = text['id']
    
    for author_key in hierarchy:
        for work_key in hierarchy[author_key]['works']:
            work = hierarchy[author_key]['works'][work_key]
            work['parts'].sort(key=lambda x: (
                int(x['part_num']) if x['part_num'] and x['part_num'].isdigit() else 999,
                x['part_num'] or ''
            ))
    
    return hierarchy

def load_text(filepath):
    """Load text content from a file"""
    with open(filepath, 'r', encoding='utf-8') as f:
        return f.read()

def save_results(results, filepath):
    """Save results to a file"""
    import json
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2)
