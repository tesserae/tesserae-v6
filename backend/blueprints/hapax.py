"""
Tesserae V6 - Hapax Blueprint

Routes for rare word (hapax legomenon) and rare pair searches.
Helps scholars find unusual vocabulary shared between texts.

Key Features:
    - Hapax search: Find words that appear rarely in the corpus
    - Rare pairs: Find bigrams (word pairs) shared between texts
    - Corpus rarity exploration: Browse rare vocabulary by author/text
    - Dictionary lookups: Show definitions for rare Latin/Greek words

Rarity Scoring:
    - Based on corpus-wide frequency (how many texts contain the word)
    - 100% rare = appears in only the source and target texts
    - Configurable minimum rarity threshold

Uses:
    - Inverted index for fast lemma lookups
    - Pre-computed frequency caches for rarity scoring
    - Lewis & Short (Latin) and LSJ (Greek) dictionaries
"""

# =============================================================================
# IMPORTS
# =============================================================================
from flask import Blueprint, Response, jsonify, request
from flask_login import current_user
import csv
import io
import os
import json
import unicodedata

from backend.logging_config import get_logger
from backend.frequency_cache import load_frequency_cache
from backend.inverted_index import get_connection
from backend.text_processor import get_latin_lemma_table, get_greek_lemma_table
from backend.utils import resolve_text_path
from backend.lemma_cache import load_units_cached
from backend.services import log_search, get_user_location
from backend.blueprints.async_poll import SearchInputError

logger = get_logger('hapax')

# Coptic lemmatization normalizes the seven Coptic-only letters into the
# "dialect-P" Coptic block (ϣ→ⲳ, ϩ→ⲹ, ϫ→ⲻ, …). For display we reverse that so
# results show the manuscript letterforms scholars recognize. Built from the
# forward map, so there is no hand-typed Coptic here.
try:
    from backend.coptic.processor import _LEGACY_TO_COPTIC as _COPTIC_LEGACY_MAP
    _COPTIC_TO_MANUSCRIPT = {v: k for k, v in _COPTIC_LEGACY_MAP.items()}
except Exception:  # pragma: no cover - coptic package optional
    _COPTIC_TO_MANUSCRIPT = {}


def _coptic_manuscript_form(text):
    """Restore manuscript Coptic letterforms from the normalized lemma alphabet."""
    if not text or not _COPTIC_TO_MANUSCRIPT:
        return text
    return ''.join(_COPTIC_TO_MANUSCRIPT.get(ch, ch) for ch in text)

# Greek display forms: normalized lemma -> accented form for display
_greek_display_forms = None
def get_greek_display_forms():
    """Load cached Greek display forms (normalized → accented) from JSON.
    Returns dict mapping stripped lemma keys to proper dictionary forms."""
    global _greek_display_forms
    if _greek_display_forms is None:
        display_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                                     'data', 'lemma_tables', 'greek_display_forms.json')
        if os.path.exists(display_path):
            with open(display_path, 'r', encoding='utf-8') as f:
                _greek_display_forms = json.load(f)
            logger.info(f"Loaded {len(_greek_display_forms)} Greek display forms")
        else:
            _greek_display_forms = {}
    return _greek_display_forms


# =============================================================================
# STOPLIST DEFINITIONS
# =============================================================================
LATIN_STOPWORDS = {
    'et', 'in', 'est', 'non', 'ut', 'cum', 'ad', 'sed', 'si', 'quod', 'qui', 'quae', 'que',
    'de', 'ex', 'per', 'ab', 'ac', 'atque', 'aut', 'nec', 'neque', 'enim', 'nam', 'iam',
    'tamen', 'autem', 'quidem', 'hic', 'haec', 'hoc', 'ille', 'illa', 'illud', 'is', 'ea',
    'id', 'se', 'suus', 'ego', 'tu', 'nos', 'vos', 'sum', 'esse', 'sui'
}

GREEK_STOPWORDS = {
    'καί', 'δέ', 'τε', 'ὁ', 'ἡ', 'τό', 'ἐν', 'εἰς', 'ἐκ', 'ἀπό', 'πρός', 'ὑπό', 'μέν',
    'γάρ', 'ἀλλά', 'οὐ', 'μή', 'ὡς', 'αὐτός', 'οὗτος', 'ἐγώ', 'σύ', 'εἰμί'
}


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


def _coerce_bool(value):
    """Coerce a value that may be a string or bool into a Python bool.
    Handles JSON booleans, string 'true'/'1'/'yes', and passthrough bools."""
    if isinstance(value, str):
        return value.lower() in ('true', '1', 'yes')
    return bool(value)


def _parse_search_params(data):
    """Extract and validate common search parameters from request JSON.
    Returns (source_id, target_id, language) or raises ValueError on missing texts."""
    source_id = data.get('source')
    target_id = data.get('target')
    language = data.get('language', 'la')
    if not source_id or not target_id:
        raise ValueError('Please select both source and target texts')
    return source_id, target_id, language


def _resolve_text_path(text_id, language):
    """Build the filesystem path for a text and verify it exists.
    Returns the full path string, or raises FileNotFoundError."""
    text_path = resolve_text_path(_texts_dir, language, text_id)
    if not text_path:
        raise FileNotFoundError(f'Text not found: {text_id}')
    return text_path


def _extract_bigram_locations(units, make_bigram_key_fn, language):
    """Build a dict mapping bigram keys to their occurrence locations from processed text units.
    Each location entry contains ref, normalized line text, and the two lemma words."""
    bigram_locations = {}
    for unit in units:
        lemmas = unit.get('lemmas', [])
        for i in range(len(lemmas) - 1):
            if lemmas[i] and lemmas[i+1]:
                bg_key = make_bigram_key_fn(lemmas[i], lemmas[i+1])
                if bg_key not in bigram_locations:
                    bigram_locations[bg_key] = []
                bigram_locations[bg_key].append({
                    'ref': unit.get('ref', ''),
                    'text': normalize_line_text(unit.get('text', ''), language),
                    'words': [lemmas[i], lemmas[i+1]]
                })
    return bigram_locations


def _dedup_locations_by_ref(locations):
    """Collapse repeated refs in a locations list, preserving order. A bigram that
    occurs twice in one verse yields two entries with the same ref, which reads as
    a duplicate in the displayed locations. Keep the first entry per ref."""
    seen = set()
    out = []
    for loc in locations:
        ref = loc.get('ref', '')
        if ref in seen:
            continue
        seen.add(ref)
        out.append(loc)
    return out


def extract_reference_numbers(ref_str):
    """
    Extract numeric parts from CTS reference (e.g., "verg. aen. 1.5" -> (1, 5)).
    Returns tuple of integers for sorting by occurrence order.
    """
    import re
    if not ref_str:
        return (float('inf'), float('inf'))
    
    numbers = re.findall(r'\d+', ref_str)
    if not numbers:
        return (float('inf'), float('inf'))
    
    try:
        nums = tuple(int(n) for n in numbers)
        # Pad with 0s to ensure consistent tuple lengths
        return nums + (0,) * (2 - len(nums)) if len(nums) < 2 else nums[:2]
    except (ValueError, TypeError):
        return (float('inf'), float('inf'))


def is_word_in_stoplist(word, language):
    """Check if a word is in the stoplist for the given language.

    Greek inputs from the lemma pipeline are accent-stripped (NFKD +
    combining-character removal) and have final sigma normalized to medial
    sigma. GREEK_STOPWORDS is written with full diacritics ('καί', 'γάρ')
    for source-readability, so the lookup side must apply the same
    normalization the lemma pipeline uses before comparing. Without this,
    high-frequency Greek function words leak past the stoplist into
    rare-bigram results because the literal string comparison never
    matches.
    """
    if not word:
        return False

    if language == 'la':
        return word.lower().strip() in LATIN_STOPWORDS
    elif language == 'grc':
        normalized = unicodedata.normalize('NFKD', word.lower().strip())
        normalized = ''.join(c for c in normalized if unicodedata.category(c) != 'Mn')
        normalized = normalized.replace('ς', 'σ')
        for entry in GREEK_STOPWORDS:
            entry_norm = unicodedata.normalize('NFKD', entry.lower().strip())
            entry_norm = ''.join(c for c in entry_norm if unicodedata.category(c) != 'Mn')
            entry_norm = entry_norm.replace('ς', 'σ')
            if entry_norm == normalized:
                return True
        return False
    elif language == 'cop':
        # Coptic rare-pair lemmas and COPTIC_STOP_WORDS are both in the
        # normalized (normalize_coptic) alphabet, so they compare directly.
        # Without this, Coptic function words (articles like ⲡ, particles like
        # ϫⲉ) were never filtered, so rare pairs came out as content-word +
        # function-word — only one meaningful, highlightable word — rather than
        # genuine two-word collocations.
        try:
            from backend.coptic.stopwords import COPTIC_STOP_WORDS
            from backend.coptic.processor import normalize_coptic
            return normalize_coptic(word.lower().strip()) in COPTIC_STOP_WORDS
        except Exception:
            return False

    return False


def get_dictionary_form(lemma_key, language):
    """
    Convert a lemma key (stem) to its proper dictionary form (citation form).
    Uses the lemma tables loaded from UD treebanks.
    """
    if not lemma_key:
        return lemma_key
    
    # The lemma tables map surface forms to dictionary forms
    # We need to find the dictionary form that this lemma key represents
    if language == 'la':
        # For Latin, the lemma_key is often already a dictionary form or close to it
        # Check if it's a known lemma in the table values
        lemma_table = get_latin_lemma_table()
        
        # First check if this lemma_key is itself a dictionary form (appears as a value)
        # If so, return it as-is
        lemma_lower = lemma_key.lower()
        
        # Common Latin dictionary form patterns - expand truncated stems
        latin_stems_to_dict = {
            'uasta': 'vastus',
            'uoragi': 'vorago',
            'numi': 'numen',
            'turbi': 'turbo',
            'culmi': 'culmen',
            'terra': 'terra',
            'pro': 'pro',
            'de': 'de',
        }
        
        # Check our manual mapping first
        if lemma_lower in latin_stems_to_dict:
            return latin_stems_to_dict[lemma_lower]
        
        # Check if it exists as a value in the lemma table (it's already a dictionary form)
        dict_forms = set(lemma_table.values())
        if lemma_lower in dict_forms:
            return lemma_lower
        
        # Check u/v variants
        v_variant = lemma_lower.replace('u', 'v')
        if v_variant in dict_forms:
            return v_variant
        
        u_variant = lemma_lower.replace('v', 'u')
        if u_variant in dict_forms:
            return u_variant
        
        # Fallback: return the original
        return lemma_key
    
    elif language == 'grc':
        # For Greek, use the Greek display form lookup
        return get_greek_display_form(lemma_key) or lemma_key
    
    return lemma_key

hapax_bp = Blueprint('hapax', __name__)

_texts_dir = None
_text_processor = None
_author_dates = None

_latin_lemma_table = {}
_greek_lemma_table = {}
_latin_valid_lemmas = set()
_greek_valid_lemmas = set()
_greek_text_forms = {}


def load_greek_display_forms():
    """Build Greek display form lookup from corpus data files.
    Loads normalized → accented form mapping from greek_display_forms.json
    and text form fallback from greek_text_forms.json."""
    global _greek_display_forms, _greek_text_forms

    if _greek_display_forms is not None:
        return
    
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    display_path = os.path.join(base_dir, 'data', 'lemma_tables', 'greek_display_forms.json')
    
    if os.path.exists(display_path):
        try:
            with open(display_path, 'r', encoding='utf-8') as f:
                _greek_display_forms = json.load(f)
            logger.info(f"Loaded {len(_greek_display_forms)} Greek display forms")
        except Exception as e:
            logger.error(f"Failed to load Greek display forms: {e}")
    
    text_forms_path = os.path.join(base_dir, 'data', 'lemma_tables', 'greek_text_forms.json')
    if os.path.exists(text_forms_path):
        try:
            with open(text_forms_path, 'r', encoding='utf-8') as f:
                _greek_text_forms = json.load(f)
            logger.info(f"Loaded {len(_greek_text_forms)} Greek text forms as fallback")
        except Exception as e:
            logger.error(f"Failed to load Greek text forms: {e}")


def normalize_to_greek(text):
    """Normalize string for Greek display form lookup.
    Converts Latin lookalike characters (a→α, b→β, etc.) to Greek equivalents."""
    latin_to_greek = {
        'a': 'α', 'b': 'β', 'e': 'ε', 'h': 'η', 'i': 'ι', 'k': 'κ',
        'm': 'μ', 'n': 'ν', 'o': 'ο', 'p': 'ρ', 't': 'τ', 'u': 'υ',
        'x': 'χ', 'y': 'υ', 'z': 'ζ', 'A': 'Α', 'B': 'Β', 'E': 'Ε',
        'H': 'Η', 'I': 'Ι', 'K': 'Κ', 'M': 'Μ', 'N': 'Ν', 'O': 'Ο',
        'P': 'Ρ', 'T': 'Τ', 'X': 'Χ', 'Y': 'Υ', 'Z': 'Ζ'
    }
    return ''.join(latin_to_greek.get(c, c) for c in text)


def get_greek_display_form(normalized_lemma):
    """Get the proper Greek dictionary form with diacritics and final sigma"""
    if not _greek_display_forms:
        load_greek_display_forms()
    
    # First normalize any Latin lookalikes to Greek
    greek_lemma = normalize_to_greek(normalized_lemma)
    
    # Direct lookup in display forms (dictionary forms)
    if greek_lemma in _greek_display_forms:
        return _greek_display_forms[greek_lemma]
    
    # Try original too (may have other encoding)
    if normalized_lemma in _greek_display_forms:
        return _greek_display_forms[normalized_lemma]
    
    # Try without parenthetical variants like ουτω(σ) -> ουτωσ
    import re
    cleaned = re.sub(r'[() ]', '', greek_lemma)
    if cleaned != normalized_lemma and cleaned in _greek_display_forms:
        return _greek_display_forms[cleaned]
    
    # Try base form without σ ending (ουτωσ -> ουτω)
    if cleaned.endswith('σ') and cleaned[:-1] in _greek_display_forms:
        return _greek_display_forms[cleaned[:-1]]
    
    # Try with σ ending (ουτω -> ουτωσ)
    if not cleaned.endswith('σ') and (cleaned + 'σ') in _greek_display_forms:
        return _greek_display_forms[cleaned + 'σ']
    
    # For contract verbs: ζω -> ζαω
    if len(cleaned) >= 2 and cleaned.endswith('ω'):
        expanded = cleaned[:-1] + 'αω'
        if expanded in _greek_display_forms:
            return _greek_display_forms[expanded]
    
    # Fallback: Try text forms from corpus (has diacritics from actual texts)
    if _greek_text_forms:
        # Try normalized Greek form
        if greek_lemma in _greek_text_forms:
            text_form = _greek_text_forms[greek_lemma]
            if text_form and text_form[-1] == 'σ':
                text_form = text_form[:-1] + 'ς'
            return text_form
        # Try cleaned form
        if cleaned in _greek_text_forms:
            text_form = _greek_text_forms[cleaned]
            if text_form and text_form[-1] == 'σ':
                text_form = text_form[:-1] + 'ς'
            return text_form
        # Try original with mixed characters
        if normalized_lemma in _greek_text_forms:
            text_form = _greek_text_forms[normalized_lemma]
            if text_form and text_form[-1] == 'σ':
                text_form = text_form[:-1] + 'ς'
            return text_form
    
    # Not found - at least fix final sigma and normalize to Greek
    result = greek_lemma
    if result and result[-1] == 'σ':
        result = result[:-1] + 'ς'
    return result


def load_dictionary_tables():
    """Load lemma lookup tables for dictionary validation"""
    global _latin_lemma_table, _greek_lemma_table, _latin_valid_lemmas, _greek_valid_lemmas
    
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    
    latin_path = os.path.join(base_dir, 'data', 'lemma_tables', 'latin_lemmas.json')
    if os.path.exists(latin_path):
        try:
            with open(latin_path, 'r', encoding='utf-8') as f:
                _latin_lemma_table = json.load(f)
            _latin_valid_lemmas = set(_latin_lemma_table.values())
            _latin_valid_lemmas.update(_latin_lemma_table.keys())
            _latin_valid_lemmas.discard(':')
            _latin_valid_lemmas.discard(',')
            _latin_valid_lemmas.discard(';')
            _latin_valid_lemmas.discard('.')
            logger.info(f"Loaded {len(_latin_lemma_table)} Latin dictionary entries")
        except Exception as e:
            logger.error(f"Failed to load Latin lemma table: {e}")
    
    greek_path = os.path.join(base_dir, 'data', 'lemma_tables', 'greek_lemmas.json')
    if os.path.exists(greek_path):
        try:
            with open(greek_path, 'r', encoding='utf-8') as f:
                _greek_lemma_table = json.load(f)
            _greek_valid_lemmas = set(_greek_lemma_table.values())
            _greek_valid_lemmas.update(_greek_lemma_table.keys())
            logger.info(f"Loaded {len(_greek_lemma_table)} Greek dictionary entries")
        except Exception as e:
            logger.error(f"Failed to load Greek lemma table: {e}")


def is_valid_dictionary_word(word, language):
    """Check if a word exists in the dictionary for the given language"""
    if not word or len(word) < 2:
        return False
    
    word_lower = word.lower().strip()
    
    if not word_lower or len(word_lower) < 2:
        return False
    
    if any(c.isdigit() for c in word_lower):
        return False
    
    if word_lower[0] in '*#@[]<>{}':
        return False
    
    if language == 'la':
        if not _latin_valid_lemmas:
            load_dictionary_tables()
        return word_lower in _latin_valid_lemmas
    elif language == 'grc':
        if not _greek_valid_lemmas:
            load_dictionary_tables()
        return word_lower in _greek_valid_lemmas
    
    return True


def get_dictionary_lemma(word, language):
    """Get the dictionary headword (lemma) for a word form"""
    word_lower = word.lower().strip()
    
    if language == 'la':
        if not _latin_lemma_table:
            load_dictionary_tables()
        return _latin_lemma_table.get(word_lower, word_lower)
    elif language == 'grc':
        if not _greek_lemma_table:
            load_dictionary_tables()
        return _greek_lemma_table.get(word_lower, word_lower)
    
    return word_lower


def fetch_latin_definition(lemma):
    """Fetch Latin definition from Wiktionary API, with Perseus fallback"""
    import urllib.request
    import urllib.parse
    import re
    
    try:
        url = f"https://en.wiktionary.org/api/rest_v1/page/definition/{urllib.parse.quote(lemma)}"
        req = urllib.request.Request(url, headers={'User-Agent': 'Tesserae/6.0'})
        with urllib.request.urlopen(req, timeout=3) as response:  # nosec B310
            data = json.loads(response.read().decode('utf-8'))
            
            if 'la' in data:
                for entry in data['la']:
                    definitions = entry.get('definitions', [])
                    if definitions:
                        defn = definitions[0].get('definition', '')
                        defn = re.sub(r'<[^>]+>', '', defn)
                        if defn:
                            return defn[:300]
    except Exception as e:
        logger.debug(f"Wiktionary Latin lookup failed for {lemma}: {e}")
    
    try:
        url = f"https://www.perseus.tufts.edu/hopper/morph?l={urllib.parse.quote(lemma)}&la=la"
        req = urllib.request.Request(url, headers={'User-Agent': 'Tesserae/6.0'})
        with urllib.request.urlopen(req, timeout=3) as response:  # nosec B310
            html = response.read().decode('utf-8', errors='ignore')
            
            match = re.search(r'<td class="la_morph_word"[^>]*>.*?</td>\s*<td class="la_morph_gloss"[^>]*>(.*?)</td>', html, re.DOTALL)
            if match:
                gloss = match.group(1)
                gloss = re.sub(r'<[^>]+>', '', gloss)
                gloss = ' '.join(gloss.split())[:300]
                if gloss:
                    return gloss
    except Exception as e:
        logger.debug(f"Perseus Latin lookup failed for {lemma}: {e}")
    
    return None


def fetch_english_definition(word):
    """Fetch English definition from free dictionary API"""
    import urllib.request
    
    try:
        url = f"https://api.dictionaryapi.dev/api/v2/entries/en/{word}"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=5) as response:  # nosec B310
            data = json.loads(response.read().decode('utf-8'))
            if data and len(data) > 0:
                meanings = data[0].get('meanings', [])
                if meanings:
                    definitions = meanings[0].get('definitions', [])
                    if definitions:
                        return definitions[0].get('definition', '')[:300]
    except Exception as e:
        logger.debug(f"Could not fetch English definition for {word}: {e}")
    
    return None


def fetch_greek_definition(lemma):
    """Fetch Greek definition from Wiktionary API, with Perseus LSJ fallback"""
    import urllib.request
    import urllib.parse
    import re
    
    try:
        url = f"https://en.wiktionary.org/api/rest_v1/page/definition/{urllib.parse.quote(lemma)}"
        req = urllib.request.Request(url, headers={'User-Agent': 'Tesserae/6.0'})
        with urllib.request.urlopen(req, timeout=3) as response:  # nosec B310
            data = json.loads(response.read().decode('utf-8'))
            
            for lang_code in ['grc', 'el', 'other']:
                if lang_code in data:
                    entries = data[lang_code] if isinstance(data[lang_code], list) else [data[lang_code]]
                    for entry in entries:
                        definitions = entry.get('definitions', [])
                        if definitions:
                            defn = definitions[0].get('definition', '')
                            defn = re.sub(r'<[^>]+>', '', defn)
                            if defn:
                                return defn[:300]
    except Exception as e:
        logger.debug(f"Wiktionary Greek lookup failed for {lemma}: {e}")
    
    try:
        url = f"https://www.perseus.tufts.edu/hopper/morph?l={urllib.parse.quote(lemma)}&la=greek"
        req = urllib.request.Request(url, headers={'User-Agent': 'Tesserae/6.0'})
        with urllib.request.urlopen(req, timeout=3) as response:  # nosec B310
            html = response.read().decode('utf-8', errors='ignore')
            
            match = re.search(r'<td class="greek_morph_word"[^>]*>.*?</td>\s*<td class="greek_morph_gloss"[^>]*>(.*?)</td>', html, re.DOTALL)
            if match:
                gloss = match.group(1)
                gloss = re.sub(r'<[^>]+>', '', gloss)
                gloss = ' '.join(gloss.split())[:300]
                if gloss:
                    return gloss
    except Exception as e:
        logger.debug(f"Perseus Greek lookup failed for {lemma}: {e}")
    
    return None


def get_definition(lemma, language):
    """Get definition for a word in any language"""
    if language == 'la':
        return fetch_latin_definition(lemma)
    elif language == 'grc':
        return fetch_greek_definition(lemma)
    elif language == 'en':
        return fetch_english_definition(lemma)
    return None


def normalize_line_text(text, language='la'):
    """
    Normalize line text: lowercase the first word unless it's a proper noun.
    In Latin texts, only proper nouns (names, places) should be capitalized.
    """
    if not text or not text.strip():
        return text
    
    words = text.split()
    if not words:
        return text
    
    first_word = words[0]
    
    # Common Latin proper noun patterns (names, places, etc.)
    # We keep these capitalized
    latin_proper_nouns = {
        'roma', 'romanus', 'romam', 'romae', 'romanorum', 'romani',
        'troia', 'troiae', 'troianus', 'troiam',
        'italia', 'italiae', 'italiam',
        'graecia', 'graecus', 'graeci',
        'iuppiter', 'iovis', 'iovi', 'iovem',
        'mars', 'martis', 'marti', 'martem',
        'venus', 'veneris', 'veneri', 'venerem',
        'iuno', 'iunonis', 'iunoni', 'iunonem',
        'apollo', 'apollinis', 'apollini', 'apollinem',
        'minerva', 'minervae', 'minervam',
        'aeneas', 'aeneae', 'aeneam',
        'turnus', 'turni', 'turno', 'turnum',
        'achilles', 'achillis', 'achilli', 'achillem',
        'hector', 'hectoris', 'hectori', 'hectorem',
        'priamus', 'priami', 'priamo', 'priamum',
        'caesar', 'caesaris', 'caesari', 'caesarem',
        'augustus', 'augusti', 'augusto', 'augustum',
        'hercules', 'herculis', 'herculi', 'herculem',
    }
    
    first_lower = first_word.lower().replace('v', 'u')
    
    # If it's a proper noun, keep capitalized
    if first_lower in latin_proper_nouns or first_lower.rstrip(',.;:!?') in latin_proper_nouns:
        return text
    
    # Otherwise lowercase the first word
    words[0] = first_word.lower()
    return ' '.join(words)


def deduplicate_locations(locations):
    """
    Remove locations from segmented versions when full version exists.
    Pattern: author.work.tess (full) vs author.work.part.N.tess (segment)
    """
    full_versions = set()
    for loc in locations:
        text_id = loc.get('text_id', '')
        if '.part.' not in text_id:
            base = text_id.replace('.tess', '')
            full_versions.add(base)
    
    deduplicated = []
    for loc in locations:
        text_id = loc.get('text_id', '')
        if '.part.' in text_id:
            parts = text_id.split('.part.')
            base = parts[0]
            if base in full_versions:
                continue
        deduplicated.append(loc)
    
    return deduplicated


_line_cache = {}

def get_original_word_form(text_id, ref, position, language):
    """Get the original word form with diacritics from the .tess file"""
    global _line_cache
    
    cache_key = (text_id, ref, language)
    if cache_key in _line_cache:
        tokens = _line_cache[cache_key]
    else:
        text_path = resolve_text_path(_texts_dir, language, text_id)
        if not text_path:
            return None
        
        try:
            with open(text_path, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.startswith('<') and '>' in line:
                        tag_end = line.index('>')
                        line_ref = line[1:tag_end].strip()
                        if line_ref == ref:
                            text_content = line[tag_end+1:].strip()
                            tokens = text_content.split()
                            _line_cache[cache_key] = tokens
                            break
                else:
                    return None
        except Exception as e:
            logger.error(f"Error reading {text_path}: {e}")
            return None
    
    if 0 <= position < len(tokens):
        return tokens[position]
    return None


def strip_punctuation(word):
    """Remove leading/trailing punctuation from a token, preserving Greek diacritics.
    Also strips stray combining marks at word boundaries."""
    import re
    import unicodedata
    # Strip common punctuation and combining marks at word boundaries
    word = re.sub(r'^[,;:.·!?\'\"\[\]\(\)«»]+|[,;:.·!?\'\"\[\]\(\)«»]+$', '', word)
    # Also strip any trailing combining marks (accents that don't belong at word end)
    while word and unicodedata.combining(word[-1]):
        word = word[:-1]
    while word and unicodedata.combining(word[0]):
        word = word[1:]
    return word


def fix_final_sigma(word):
    """Convert medial sigma (σ) at word end to final sigma (ς) for Greek display."""
    if word and word[-1] == 'σ':
        return word[:-1] + 'ς'
    return word


def fix_greek_combining(word):
    """Fix malformed Greek where combining marks appear before base letters.
    Reorders so combining diacritics follow their base character (NFC-like)."""
    import unicodedata
    if not word:
        return word
    
    result = []
    pending_combining = []
    
    for char in word:
        if unicodedata.combining(char):
            # It's a combining character - save it
            pending_combining.append(char)
        else:
            # It's a base character - add it, then add pending combining marks
            result.append(char)
            result.extend(pending_combining)
            pending_combining = []
    
    # Any remaining combining marks
    result.extend(pending_combining)
    
    return ''.join(result)


def strip_latin_enclitics(word):
    """Strip common Latin enclitics (-que, -ne, -ve/-ue) from a word.
    Conservative: only strips -que (most common and unambiguous).
    -ne and -ve are too often part of the stem (e.g., omne, nave)."""
    if not word or len(word) < 6:
        return word
    lower = word.lower().replace('v', 'u')
    # Words where -que is part of the stem, not an enclitic
    _que_whole_words = {
        'usque', 'quoque', 'ubique', 'undique', 'utrique', 'utroque',
        'neque', 'atque', 'absque', 'itaque', 'namque', 'quisque',
        'quinque', 'denique', 'plerumque', 'plerique', 'cumque',
        'quandoque', 'quacumque', 'quocumque', 'quoscumque'
    }
    if lower.endswith('que'):
        if lower not in _que_whole_words:
            return word[:-3]
    return word


def clean_lemma_key(lemma):
    """Clean up lemma notation for display and matching.
    Removes prefix separators (de_-suesco -> desuesco, ad-pello -> adpello)
    and trailing homograph numbers (eo1 -> eo, edo1 -> edo)."""
    import re
    if not lemma:
        return lemma
    # Remove prefix separators: _- or single -
    cleaned = lemma.replace('_-', '')
    # Only remove hyphens that separate prefix from stem (not in Greek or if hyphen is the whole thing)
    if '-' in cleaned and len(cleaned) > 2:
        cleaned = cleaned.replace('-', '')
    # Remove trailing homograph disambiguation numbers
    cleaned = re.sub(r'\d+$', '', cleaned)
    return cleaned or lemma


def word_matches_lemma(word, lemma, language):
    """Check if a surface word plausibly matches a lemma (for position validation).
    Handles Latin u/v and i/j normalization, enclitics, prefix notation,
    Greek diacritics, and stem matching."""
    import unicodedata as _ucd
    if not word or not lemma:
        return False
    w = word.lower()
    # Clean lemma: remove prefix separators and trailing numbers
    l = clean_lemma_key(lemma).lower()
    if language == 'la':
        w = w.replace('v', 'u').replace('j', 'i')
        l = l.replace('v', 'u').replace('j', 'i')
        if w == l:
            return True
        # Try after stripping enclitics
        w_stripped = strip_latin_enclitics(word).lower().replace('v', 'u').replace('j', 'i')
        if w_stripped != w and w_stripped == l:
            return True
        # Stem match: shared prefix of at least 4 chars (Latin inflection)
        min_stem = min(4, len(l))
        if len(l) >= 3:
            if len(w) >= min_stem and w[:min_stem] == l[:min_stem]:
                return True
            if len(w_stripped) >= min_stem and w_stripped[:min_stem] == l[:min_stem]:
                return True
    elif language == 'grc':
        # Strip diacritics and normalize sigma for comparison
        w_base = ''.join(c for c in _ucd.normalize('NFD', w) if not _ucd.combining(c))
        l_base = ''.join(c for c in _ucd.normalize('NFD', l) if not _ucd.combining(c))
        w_base = w_base.replace('ς', 'σ')
        l_base = l_base.replace('ς', 'σ')
        if w_base == l_base:
            return True
        min_stem = min(4, len(l_base))
        if len(l_base) >= 3 and len(w_base) >= min_stem and w_base[:min_stem] == l_base[:min_stem]:
            return True
    else:
        # English
        if w == l:
            return True
        min_stem = min(4, len(l))
        if len(l) >= 3 and len(w) >= min_stem and w[:min_stem] == l[:min_stem]:
            return True
    return False


def _find_lemma_token_in_text(text, lemma, language):
    """Search line text for a token matching the lemma. Returns (token, index) or (None, -1).
    Strips enclitics from the returned token for clean display.
    This is a fallback when index positions are misaligned."""
    if not text:
        return None, -1
    tokens = text.split()
    for idx, token in enumerate(tokens):
        clean = strip_punctuation(token)
        if clean and word_matches_lemma(clean, lemma, language):
            # Strip enclitics for clean display
            if language == 'la':
                clean = strip_latin_enclitics(clean)
            return clean, idx
    return None, -1


def get_display_form(lemma, language, locations):
    """Get a display form with diacritics by sampling from locations.
    Validates that the word at the indexed position actually matches the lemma;
    falls back to searching the line text if positions are misaligned."""
    import unicodedata

    display = None
    if locations:
        for loc in locations[:5]:
            positions = loc.get('positions', [])
            # Try position-based lookup first (fast path)
            if positions:
                word = get_original_word_form(loc['text_id'], loc['ref'], positions[0], language)
                if word:
                    word = strip_punctuation(word)
                    if word and word_matches_lemma(word, lemma, language):
                        if language == 'la':
                            word = strip_latin_enclitics(word)
                        if language == 'grc':
                            word = fix_greek_combining(word)
                            display = unicodedata.normalize('NFC', word)
                        else:
                            display = word
                        break
            # Fallback: search through line text for a matching token
            if not display:
                token, _ = _find_lemma_token_in_text(loc.get('text', ''), lemma, language)
                if token:
                    if language == 'grc':
                        token = fix_greek_combining(token)
                        display = unicodedata.normalize('NFC', token)
                    else:
                        display = token
                    break

    # Fallback to Morpheus lookup if Greek and no location found
    if not display and language == 'grc':
        display = get_greek_display_form(lemma)

    # If still no display, use the lemma itself (cleaned up)
    if not display:
        display = clean_lemma_key(lemma)

    # Convert trailing medial sigma to final sigma for Greek
    if language == 'grc' and display and display.endswith('σ'):
        display = display[:-1] + 'ς'

    return display


def is_proper_noun(lemma, language, locations):
    """
    Determine if a word is a proper noun by checking capitalization patterns
    across multiple corpus occurrences.

    Instead of trusting index positions (which may be misaligned), searches
    the actual line text for tokens matching the lemma and checks their case.

    Uses ratio-based detection: if >= 50% of non-line-initial occurrences
    are capitalized, the word is a proper noun. This tolerates prose authors
    who sometimes lowercase proper adjectives (e.g., Pliny) while catching
    borderline cases like Caspia (57%) and Hesperidum (50%).

    Works for Latin, Greek, and English.
    """
    if not locations:
        return False

    uppercase_non_initial = 0
    lowercase_non_initial = 0
    uppercase_initial = 0
    lowercase_initial = 0

    for loc in locations[:20]:
        text = loc.get('text', '')
        if not text:
            continue
        tokens = text.split()
        for idx, token in enumerate(tokens):
            clean = strip_punctuation(token)
            if not clean:
                continue
            if not word_matches_lemma(clean, lemma, language):
                continue

            is_upper = clean[0].isupper()
            is_line_initial = (idx == 0)

            if is_line_initial:
                if is_upper:
                    uppercase_initial += 1
                else:
                    lowercase_initial += 1
            else:
                if is_upper:
                    uppercase_non_initial += 1
                else:
                    lowercase_non_initial += 1
            break  # Only count first match per line to avoid double-counting

    # Use ratio-based detection for non-initial positions
    total_non_initial = uppercase_non_initial + lowercase_non_initial
    if total_non_initial > 0:
        uppercase_ratio = uppercase_non_initial / total_non_initial
        # >= 50% uppercase in non-initial positions -> proper noun
        # Catches borderline cases (Caspia 57%, Hesperidum 50%)
        if uppercase_ratio >= 0.5:
            return True
        return False

    # Only line-initial evidence available — use as tie-breaker
    # If always uppercase at line start and never lowercase, likely proper noun
    # But this is weak evidence, so require multiple occurrences
    if uppercase_initial >= 2 and lowercase_initial == 0:
        return True

    return False


def init_hapax_blueprint(texts_dir, text_processor, author_dates):
    """Initialize hapax blueprint with shared dependencies (texts dir, processor, dates).
    Called once at app startup to inject references needed by route handlers."""
    global _texts_dir, _text_processor, _author_dates
    _texts_dir = texts_dir
    _text_processor = text_processor
    _author_dates = author_dates


_line_text_cache = {}
_LINE_TEXT_CACHE_MAX_SIZE = 20

def get_line_text_from_file(text_id, language, ref):
    """
    Look up the actual line text from a .tess file given text_id and ref.
    Uses bounded LRU-style caching to avoid memory issues.
    """
    global _line_text_cache
    
    cache_key = f"{language}/{text_id}"
    
    if cache_key not in _line_text_cache:
        if len(_line_text_cache) >= _LINE_TEXT_CACHE_MAX_SIZE:
            oldest_key = next(iter(_line_text_cache))
            del _line_text_cache[oldest_key]
        
        text_path = resolve_text_path(_texts_dir, language, text_id)
        if not text_path:
            return None

        try:
            lines_by_ref = {}
            with open(text_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                    if line.startswith('<') and '>' in line:
                        tag_end = line.index('>')
                        line_ref = line[1:tag_end].strip()
                        line_text = line[tag_end + 1:].strip()
                        if line_ref:
                            lines_by_ref[line_ref] = line_text
            _line_text_cache[cache_key] = lines_by_ref
        except Exception as e:
            logger.error(f"Error reading text file {text_path}: {e}")
            _line_text_cache[cache_key] = {}
    
    lines = _line_text_cache.get(cache_key, {})
    return lines.get(ref, '')


def get_rare_words_from_cache(language, max_occurrences=10):
    """Get lemmas with corpus frequency between 1 and max_occurrences.
    NOTE: This uses token frequency. For hapax search, prefer
    get_document_frequency() which counts how many TEXTS contain a lemma."""
    cached = load_frequency_cache(language)
    if not cached or 'frequencies' not in cached:
        return {}

    rare_words = {}
    for lemma, count in cached['frequencies'].items():
        if 1 <= count <= max_occurrences:
            rare_words[lemma] = count

    return rare_words


def _base_filename_expr(alias='t'):
    """Return a SQL expression that collapses partition filenames to their base work.

    The inverted index treats each .tess file as a separate text_id. A long
    work like Homer's Iliad is indexed as both the full file
    (homer.iliad.tess) AND each of its 24 part files (homer.iliad.part.N.tess).
    Counting distinct text_ids therefore inflates document frequency for any
    word in such a work, pushing genuine hapaxes out of the rare-word range.

    This expression rewrites 'homer.iliad.part.1.tess' to 'homer.iliad.tess'
    so COUNT(DISTINCT ...) counts each work once regardless of how it was
    partitioned for indexing.
    """
    fn = f"{alias}.filename"
    return (
        f"CASE WHEN instr({fn}, '.part.') > 0 "
        f"THEN substr({fn}, 1, instr({fn}, '.part.') - 1) || '.tess' "
        f"ELSE {fn} END"
    )


def get_document_frequency(lemma, language):
    """Get the number of distinct texts that contain this lemma (document frequency).
    Uses the inverted index for accurate corpus-wide rarity measurement.

    Partition files (homer.iliad.part.N.tess) are collapsed to their base
    work (homer.iliad.tess) so a word indexed across both the full file and
    its parts contributes a document frequency of 1, not 1 + part_count.
    """
    conn = get_connection(language)
    if not conn:
        return 0

    try:
        cursor = conn.cursor()
        # Expand to u/v and i/j variants for Latin
        expanded = {lemma}
        if language == 'la':
            expanded.add(lemma.replace('u', 'v'))
            expanded.add(lemma.replace('v', 'u'))
            expanded.add(lemma.replace('i', 'j'))
            expanded.add(lemma.replace('j', 'i'))

        placeholders = ','.join(['?' for _ in expanded])
        base_expr = _base_filename_expr('t')
        cursor.execute(
            f'SELECT COUNT(DISTINCT {base_expr}) '  # nosec B608
            f'FROM postings p JOIN texts t ON p.text_id = t.text_id '
            f'WHERE p.lemma IN ({placeholders})',
            list(expanded)
        )
        return cursor.fetchone()[0]
    except Exception as e:
        logger.error(f"Document frequency lookup error for '{lemma}': {e}")
        return 0


_lemma_doc_freq_available = {}  # language -> bool (does the index have the precomputed table?)


def _has_lemma_doc_freq(conn, language):
    """Return True when the index DB has the precomputed lemma_doc_freq table.

    Memoized per language. The table maps each stored lemma form to the number
    of distinct base works containing it (parts collapsed to their whole work,
    matching _base_filename_expr). When present it replaces the per-lemma
    COUNT(DISTINCT ...) scan over the full postings table — an indexed seek
    instead of a 17M-row aggregation.
    """
    if language in _lemma_doc_freq_available:
        return _lemma_doc_freq_available[language]
    try:
        row = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='lemma_doc_freq'"
        ).fetchone()
        available = row is not None
    except Exception:
        available = False
    _lemma_doc_freq_available[language] = available
    return available


def get_document_frequencies_batch(lemmas, language):
    """Get document frequencies for a batch of lemmas efficiently.
    Returns dict mapping lemma -> number of texts containing it."""
    conn = get_connection(language)
    if not conn:
        return {}

    try:
        cursor = conn.cursor()
        result = {}

        # Fast path: read from the precomputed per-lemma document-frequency
        # table when the index has it. Falls back to the live COUNT(DISTINCT)
        # aggregation for indexes built before the table existed (grc/en/cop
        # until rebuilt), so results are identical either way.
        use_precomputed = _has_lemma_doc_freq(conn, language)
        base_expr = _base_filename_expr('t')

        # Process in batches to avoid huge SQL queries
        lemma_list = list(lemmas)
        batch_size = 500
        for i in range(0, len(lemma_list), batch_size):
            batch = lemma_list[i:i + batch_size]

            # Build expanded set with u/v variants
            expanded_map = {}  # expanded_form -> original_lemma
            for lemma in batch:
                variants = {lemma}
                if language == 'la':
                    variants.add(lemma.replace('u', 'v'))
                    variants.add(lemma.replace('v', 'u'))
                for v in variants:
                    expanded_map[v] = lemma

            all_variants = list(expanded_map.keys())
            placeholders = ','.join(['?' for _ in all_variants])
            if use_precomputed:
                cursor.execute(
                    f'SELECT lemma, df FROM lemma_doc_freq '  # nosec B608
                    f'WHERE lemma IN ({placeholders})',
                    all_variants
                )
            else:
                cursor.execute(
                    f'SELECT p.lemma, COUNT(DISTINCT {base_expr}) '  # nosec B608
                    f'FROM postings p JOIN texts t ON p.text_id = t.text_id '
                    f'WHERE p.lemma IN ({placeholders}) GROUP BY p.lemma',
                    all_variants
                )

            # Aggregate counts back to original lemma (sums u/v variant forms,
            # matching the pre-existing behavior for both paths)
            for row_lemma, count in cursor.fetchall():
                original = expanded_map.get(row_lemma, row_lemma)
                result[original] = result.get(original, 0) + count

        return result
    except Exception as e:
        logger.error(f"Batch document frequency error: {e}")
        return {}


def lookup_lemma_locations(lemma, language):
    """Look up all occurrences of a lemma using the inverted index"""
    conn = get_connection(language)
    if not conn:
        return []
    
    cursor = conn.cursor()
    
    expanded_lemmas = {lemma}
    if language == 'la':
        expanded_lemmas.add(lemma.replace('u', 'v'))
        expanded_lemmas.add(lemma.replace('v', 'u'))
        expanded_lemmas.add(lemma.replace('i', 'j'))
        expanded_lemmas.add(lemma.replace('j', 'i'))
        # Also search for enclitic forms (words with -que, -ne, -ue attached)
        # This handles old index entries that weren't stripped
        for enc in ['que', 'ne', 'ue']:
            expanded_lemmas.add(lemma + enc)
            expanded_lemmas.add(lemma.replace('u', 'v') + enc)
            expanded_lemmas.add(lemma.replace('v', 'u') + enc)
    
    placeholders = ','.join(['?' for _ in expanded_lemmas])
    query = f'''
        SELECT t.filename, p.ref, p.positions
        FROM postings p
        JOIN texts t ON p.text_id = t.text_id
        WHERE p.lemma IN ({placeholders})
        ORDER BY t.filename, p.ref
    '''  # nosec B608
    
    locations = []
    try:
        cursor.execute(query, list(expanded_lemmas))  # nosec B608
        for row in cursor.fetchall():
            filename, ref, positions_json = row
            parts = filename.replace('.tess', '').split('.') if filename else ['unknown']
            author = parts[0] if parts else 'unknown'
            work_title = '.'.join(parts[1:]) if len(parts) > 1 else parts[0]
            line_text = get_line_text_from_file(filename, language, ref)
            locations.append({
                'text_id': filename,
                'author': author.replace('_', ' ').title(),
                'work': work_title.replace('_', ' ').title(),
                'ref': ref,
                'text': line_text or '',
                'positions': json.loads(positions_json) if positions_json else []
            })
    except Exception as e:
        logger.error(f"Lemma lookup error: {e}")
    
    return deduplicate_locations(locations)


def get_text_lemmas(text_id, language):
    """Get all lemmas from a specific text"""
    text_path = resolve_text_path(_texts_dir, language, text_id)
    if not text_path:
        return set()
    
    try:
        units = load_units_cached(text_path, language, _text_processor)
        all_lemmas = set()
        for unit in units:
            all_lemmas.update(unit.get('lemmas', []))
        return all_lemmas
    except Exception as e:
        logger.error(f"Error processing text {text_id}: {e}")
        return set()


def find_rare_word_matches_direct(source_units, target_units, language='la',
                                   max_occurrences=50):
    """Find matches based on shared rare lemmas between source and target units.

    Uses an inverted-index approach (like the dictionary channel): collects all
    lemmas, batch-queries document frequencies, filters to rare words, then
    builds a target index for fast pair lookup.

    Called by the fusion engine (backend/fusion.py) for the rare_word channel.

    Args:
        source_units: List of dicts with 'lemmas' field
        target_units: List of dicts with 'lemmas' field
        language: Language code ('la', 'grc', 'en')
        max_occurrences: Maximum corpus doc frequency to count as "rare"

    Returns:
        List of match dicts: [{'source_idx', 'target_idx', 'matched_lemmas'}, ...]
    """
    from collections import defaultdict

    # Per-language manual stoplist for filtering function-class morphemes.
    # Critical for Coptic post sub-word tokenisation (2026-05-01) — the
    # rare_word channel otherwise generates millions of candidate matches
    # on common bound morphemes whose corpus-doc-frequency happens to
    # land within max_occurrences in some texts.
    manual_stoplist = set()
    if language == 'cop':
        try:
            from backend.coptic.stopwords import COPTIC_STOP_WORDS
            manual_stoplist = COPTIC_STOP_WORDS
        except Exception:
            pass

    def _accept(l):
        return len(l) > 2 and l not in manual_stoplist

    # Collect unique lemmas per unit
    source_lemma_sets = []
    all_source_lemmas = set()
    for unit in source_units:
        lemmas = set(l.lower() for l in unit.get('lemmas', []) if _accept(l))
        source_lemma_sets.append(lemmas)
        all_source_lemmas.update(lemmas)

    target_lemma_sets = []
    all_target_lemmas = set()
    for unit in target_units:
        lemmas = set(l.lower() for l in unit.get('lemmas', []) if _accept(l))
        target_lemma_sets.append(lemmas)
        all_target_lemmas.update(lemmas)

    # Only query doc freqs for lemmas that appear in both source and target
    shared_lemmas = all_source_lemmas & all_target_lemmas
    if not shared_lemmas:
        logger.info("[RARE_WORD] No shared lemmas between source and target")
        return []

    # Batch document-frequency lookup
    doc_freqs = get_document_frequencies_batch(shared_lemmas, language)

    # Filter to rare: 1 <= doc_freq <= max_occurrences
    rare_lemmas = set()
    for lemma in shared_lemmas:
        df = doc_freqs.get(lemma, 0)
        if 1 <= df <= max_occurrences:
            rare_lemmas.add(lemma)

    if not rare_lemmas:
        logger.info(f"[RARE_WORD] No rare lemmas (max_occ={max_occurrences}) "
                     f"among {len(shared_lemmas)} shared lemmas")
        return []

    logger.info(f"[RARE_WORD] {len(rare_lemmas)} rare lemmas "
                f"(from {len(shared_lemmas)} shared, max_occ={max_occurrences})")

    # Build target index: rare_lemma -> set of target line indices
    target_index = defaultdict(set)
    for tgt_idx, lemma_set in enumerate(target_lemma_sets):
        for lemma in lemma_set:
            if lemma in rare_lemmas:
                target_index[lemma].add(tgt_idx)

    # For each source unit, find target units sharing rare lemmas via index
    matches = []
    for src_idx, src_lemmas in enumerate(source_lemma_sets):
        # tgt_idx -> set of shared rare lemmas
        pair_shared = defaultdict(set)
        for lemma in src_lemmas:
            if lemma in target_index:
                for tgt_idx in target_index[lemma]:
                    pair_shared[tgt_idx].add(lemma)

        for tgt_idx, shared_rare in pair_shared.items():
            if len(shared_rare) >= 1:
                matches.append({
                    'source_idx': src_idx,
                    'target_idx': tgt_idx,
                    'matched_lemmas': list(shared_rare),
                })

    logger.info(f"[RARE_WORD] Found {len(matches)} matches "
                f"(source={len(source_units)}, target={len(target_units)})")
    return matches


@hapax_bp.route('/rare-lemmata', methods=['GET'])
def get_rare_lemmata():
    """
    Get rare words (hapax legomena) from the corpus.
    
    Query params:
        language: 'la', 'grc', or 'en' (default: 'la')
        max_occurrences: max corpus frequency (default: 10)
        min_occurrences: min corpus frequency (default: 1)
        limit: max number to return (default: 500)
        include_locations: whether to include text locations (default: false)
    """
    try:
        language = request.args.get('language', 'la')
        max_occ = int(request.args.get('max_occurrences', 10))
        min_occ = int(request.args.get('min_occurrences', 1))
        limit = int(request.args.get('limit', 500))
        include_locations = request.args.get('include_locations', 'false').lower() == 'true'
        
        rare_words = get_rare_words_from_cache(language, max_occ)

        # Strip leading/trailing whitespace from lemma keys
        cleaned = {}
        for k, v in rare_words.items():
            clean_k = k.strip()
            if clean_k and v >= min_occ:
                cleaned[clean_k] = cleaned.get(clean_k, 0) + v

        sorted_words = sorted(cleaned.items(), key=lambda x: (x[1], x[0]))[:limit]

        # Load Greek display forms for accented display
        display_forms = get_greek_display_forms() if language == 'grc' else {}

        results = []
        for lemma, count in sorted_words:
            display = display_forms.get(lemma, lemma) if display_forms else lemma
            entry = {
                'lemma': lemma,
                'display': display,
                'count': count,
                'language': language
            }
            if include_locations:
                entry['locations'] = lookup_lemma_locations(lemma, language)
            results.append(entry)
        
        return jsonify({
            'language': language,
            'total_rare_words': len(cleaned),
            'returned': len(results),
            'max_occurrences': max_occ,
            'min_occurrences': min_occ,
            'words': results
        })
        
    except Exception as e:
        logger.error(f"Error in rare-lemmata: {e}")
        return jsonify({'error': str(e)}), 500


_rare_words_cache = {}

def load_rare_words_cache(language):
    """Load pre-cached rare words for instant access"""
    global _rare_words_cache
    if language in _rare_words_cache:
        return _rare_words_cache[language]
    
    cache_path = os.path.join('cache', 'rare_words', f'{language}.json')
    if os.path.exists(cache_path):
        try:
            with open(cache_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                _rare_words_cache[language] = data
                return data
        except Exception as e:
            logger.error(f"Error loading rare words cache for {language}: {e}")
    return None


def clear_rare_words_memory_cache(language=None):
    """Clear in-memory rare words cache so next request reloads from disk"""
    global _rare_words_cache
    if language:
        _rare_words_cache.pop(language, None)
    else:
        _rare_words_cache = {}
    logger.info(f"Cleared rare words memory cache for {language or 'all languages'}")


def _is_coptic_aggregate(base):
    """True for combined/duplicate lemma-cache files that would double-count the
    same words: whole-corpus supersets (``<dialect>.bible`` / ``.ot`` / ``.nt``),
    the all-Shenoute file, and hash-suffixed cache variants. Individual books and
    works (sahidic.genesis, shenoute.abraham, mercurius, …) are kept."""
    import re
    if re.search(r'-[0-9a-f]{8,}$', base):        # hash-suffixed cache variant
        return True
    if base == 'shenoute.all':
        return True
    return bool(re.search(r'\.(bible|ot|nt)$', base))


def _coptic_manuscript_form(lemma):
    """Convert a normalized Coptic lemma back to manuscript spelling for display.

    normalize_coptic() maps the legacy 'Greek and Coptic' block letters (ϣ ϥ ϩ
    ϫ ϭ …) into the Coptic block for matching. Reverse that 1:1 map so the Rare
    Words Explorer shows the letterforms used in the source texts. (The
    supralinear stroke, stripped during normalization, is conventionally omitted
    in lemma citation.)
    """
    from backend.coptic.processor import _LEGACY_TO_COPTIC
    inv = {v: k for k, v in _LEGACY_TO_COPTIC.items()}
    return ''.join(inv.get(c, c) for c in lemma)


def _clean_coptic_lemma(lem):
    """Trim leading/trailing non-Coptic-block characters (whitespace, editorial
    brackets/parentheses, verse-number digits, dots) so tokenization and
    transcription artifacts don't split one word into spurious rare variants.
    Returns '' if nothing usable remains."""
    import re
    if not lem:
        return ''
    return re.sub(r'^[^Ⲁ-⳿]+|[^Ⲁ-⳿]+$', '', lem)


def _coptic_rare_frequencies():
    """Per-lemma (count, first_filename, first_ref) for Coptic, from the
    SCRIPTORIUM sub-word lemma cache (cache/lemmas/cop), excluding aggregate
    whole-corpus files.

    Uses the lemmatizer's segmented sub-word lemmas — not the search index's
    bound-group forms — so counts reflect actual words (every occurrence of
    'man' counts as ⲣⲱⲙⲉ regardless of the attached article or preposition).
    First occurrence is captured here (files walked in sorted order) so the
    Explorer's provenance columns don't depend on a separate index lookup.
    """
    import glob
    from collections import Counter
    counts = Counter()
    first = {}  # lemma -> (filename, ref)
    cache_dir = os.path.join('cache', 'lemmas', 'cop')
    for path in sorted(glob.glob(os.path.join(cache_dir, '*.json'))):
        base = os.path.basename(path)[:-5]  # strip .json
        if _is_coptic_aggregate(base):
            continue
        filename = base + '.tess'
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception:
            continue
        if not isinstance(data, dict):
            continue
        for ref, entry in data.items():
            if not isinstance(entry, dict):
                continue
            for lem in (entry.get('lemmas') or []):
                lem = _clean_coptic_lemma(lem)
                if not lem:
                    continue
                counts[lem] += 1
                if lem not in first:
                    first[lem] = (filename, ref)
    return {lem: (n, *first[lem]) for lem, n in counts.items()}


def regenerate_rare_words_cache(language):
    """
    Regenerate rare words cache from current frequency data.
    Call this after adding new texts to update the Rare Words Explorer.
    """
    import re
    import unicodedata
    from backend.frequency_cache import load_frequency_cache

    logger.info(f"Regenerating rare words cache for {language}")

    if language == 'cop':
        # Coptic counts sub-word lemmas from the SCRIPTORIUM lemma cache directly;
        # the shared frequency cache holds bound-group forms (from the search
        # index) that are wrong for rare-word counting.
        frequencies = _coptic_rare_frequencies()
        if not frequencies:
            logger.error("No Coptic lemma cache found for rare-words regeneration")
            return False
    else:
        freq_data = load_frequency_cache(language)
        if not freq_data:
            logger.error(f"No frequency data for {language}")
            return False
        frequencies = freq_data.get('frequencies', {})

    rare_words = []
    
    if language == 'la':
        load_dictionary_tables()
        for lemma, count in frequencies.items():
            if 1 <= count <= 10:
                clean = re.sub(r'[^a-zA-Z]', '', lemma).lower()
                if len(clean) < 3:
                    continue
                if not any(c in clean for c in 'aeiou'):
                    continue
                if clean not in _latin_valid_lemmas:
                    continue
                display = _latin_lemma_table.get(clean, clean)
                rare_words.append({'lemma': clean, 'display': display, 'count': count})
    
    elif language == 'grc':
        load_dictionary_tables()
        load_greek_display_forms()
        for lemma, count in frequencies.items():
            if 1 <= count <= 10:
                normalized = unicodedata.normalize('NFKD', lemma)
                normalized = ''.join(c for c in normalized if not unicodedata.combining(c))
                normalized = normalized.replace('ς', 'σ').lower()
                if len(normalized) < 2:
                    continue
                if normalized not in _greek_valid_lemmas:
                    continue
                display = get_greek_display_form(normalized)
                # Ensure proper NFC normalization (combining marks after base chars)
                display = unicodedata.normalize('NFC', display)
                rare_words.append({'lemma': normalized, 'display': display, 'count': count})
    
    elif language == 'en':
        concat_endings = ['had', 'was', 'did', 'and', 'the', 'but', 'for', 'his', 'her', 'not', 'are', 'all', 'can', 'one', 'our', 'out', 'you', 'she', 'say']
        for lemma, count in frequencies.items():
            if 1 <= count <= 10:
                clean = re.sub(r'[—–\-]+', ' ', lemma)
                clean = re.sub(r'[^a-zA-Z\s]', '', clean).strip().lower()
                if ' ' in clean or len(clean) < 3 or len(clean) > 18:
                    continue
                if not any(c in clean for c in 'aeiou'):
                    continue
                is_concat = False
                if len(clean) > 10:
                    for ending in concat_endings:
                        if clean.endswith(ending) and len(clean) > len(ending) + 4:
                            is_concat = True
                            break
                if is_concat:
                    continue
                rare_words.append({'lemma': clean, 'display': clean, 'count': count})

    elif language == 'cop':
        from backend.coptic.stopwords import COPTIC_STOP_WORDS
        for lemma, (count, first_file, first_ref) in frequencies.items():
            if 1 <= count <= 10:
                if len(lemma) < 2:
                    continue
                if lemma in COPTIC_STOP_WORDS:
                    continue
                # Must be entirely Coptic-block letters — reject transcription
                # artifacts (lacuna brackets [...], parentheses, verse digits,
                # internal dots) that the lemma cache carries from critical editions.
                if not re.fullmatch(r'[Ⲁ-⳿]+', lemma):
                    continue
                parts = first_file.replace('.tess', '').split('.')
                rare_words.append({
                    'lemma': lemma,                             # normalized form, for index lookup
                    'display': _coptic_manuscript_form(lemma),  # manuscript spelling for display
                    'count': count,
                    'first_author': parts[0] if parts else first_file,
                    'first_work': '.'.join(parts[1:]) if len(parts) > 1 else '',
                    'first_locus': first_ref,
                    'text_id': first_file,
                })

    seen = {}
    for w in rare_words:
        key = w['lemma']
        if key not in seen or w['count'] < seen[key]['count']:
            seen[key] = w
    
    # Look up first location for each rare word to get author/work info.
    # Coptic already carries provenance from _coptic_rare_frequencies (and the
    # index lookup doesn't resolve its sub-word lemmas), so skip it here.
    if language != 'cop':
        logger.info(f"Looking up first locations for {len(seen)} rare words...")
        for lemma, word_data in seen.items():
            try:
                locations = lookup_lemma_locations(lemma, language)
                # Deduplicate to avoid part files when full version exists
                locations = deduplicate_locations(locations)
                if locations:
                    first_loc = locations[0]
                    word_data['first_author'] = first_loc.get('author', '')
                    word_data['first_work'] = first_loc.get('work', '')
                    word_data['first_locus'] = first_loc.get('ref', '')
                    word_data['text_id'] = first_loc.get('text_id', '')
            except Exception as e:
                logger.debug(f"Could not look up location for {lemma}: {e}")
    
    def greek_sort_key(x):
        """Sort by base letter form so accented and unaccented entries interleave"""
        display = x.get('display', x.get('lemma', '')).lower().lstrip('*')
        # Normalize to base characters for sorting (Ἀ sorts with α, not after ω)
        normalized = unicodedata.normalize('NFD', display)
        base = ''.join(c for c in normalized if not unicodedata.combining(c))
        return base

    unique_rare = sorted(seen.values(), key=greek_sort_key)
    
    cache_dir = os.path.join('cache', 'rare_words')
    os.makedirs(cache_dir, exist_ok=True)
    cache_path = os.path.join(cache_dir, f'{language}.json')
    
    with open(cache_path, 'w', encoding='utf-8') as f:
        json.dump({'words': unique_rare, 'total': len(unique_rare)}, f, ensure_ascii=False)
    
    clear_rare_words_memory_cache(language)
    
    logger.info(f"Regenerated rare words cache for {language}: {len(unique_rare)} words")
    return True


RARE_LEMMATA_PAGE_SIZES = {25, 50, 100, 500}
RARE_LEMMATA_SORT_FIELDS = {'frequency', 'lemma', 'author'}
RARE_LEMMATA_SORT_ORDERS = {'asc', 'desc'}


def _get_rare_lemmata_matching(language, max_occ):
    """Load and filter the cached rare-word records for an Explorer request."""
    cached = load_rare_words_cache(language)
    # Regenerate when the cache is missing OR empty. An empty cache can be left
    # behind by an earlier run that lacked support for a language (e.g. Coptic
    # before it was added); without the empty-check it would never self-heal.
    if not cached or not cached.get('words'):
        logger.info(f"Rare-words cache missing/empty for {language}, regenerating lazily")
        try:
            if regenerate_rare_words_cache(language):
                cached = load_rare_words_cache(language)
        except Exception as e:
            logger.error(f"Lazy cache regeneration failed for {language}: {e}")

    if not cached:
        return None

    return [word for word in cached.get('words', []) if word['count'] <= max_occ]


def _rare_lemmata_sort_key(word, sort_by, language='la'):
    if language == 'cop':
        # Collate Coptic by the normalized lemma: the Coptic Unicode block orders
        # the Greek-derived letters first and the Demotic-derived letters
        # (ϣ ϥ ϩ ϫ ϭ …) last — traditional Coptic alphabetical order. The
        # manuscript display puts those letters in the legacy block, which would
        # (wrongly) sort them first.
        lemma = word.get('lemma', word.get('display', '')).lstrip('*')
    else:
        lemma = word.get('display', word.get('lemma', '')).lstrip('*').casefold()
    if sort_by == 'frequency':
        return (word.get('count', 0), lemma)
    if sort_by == 'author':
        return (word.get('first_author', '').casefold(), lemma)
    return (lemma,)


def _format_rare_lemma(word):
    """Return the public Explorer representation of a cached rare word."""
    display = word.get('display', word.get('lemma', ''))
    if display.startswith('*'):
        display = display[1:]
    return {
        'lemma': unicodedata.normalize('NFC', display),
        'count': word['count'],
        'first_author': word.get('first_author', ''),
        'first_work': word.get('first_work', ''),
        'first_locus': word.get('first_locus', ''),
        'text_id': word.get('text_id', '')
    }


def _parse_rare_lemmata_params(require_paging=True):
    """Parse and validate the shared Rare Words Explorer query parameters."""
    language = request.args.get('language', 'la')
    try:
        max_occ = int(request.args.get('max_occurrences', 10))
    except (TypeError, ValueError):
        return None, jsonify({'error': 'max_occurrences must be an integer'}), 400

    sort_by = request.args.get('sort_by', 'frequency')
    sort_order = request.args.get('sort_order', 'asc')
    if sort_by not in RARE_LEMMATA_SORT_FIELDS:
        return None, jsonify({'error': 'sort_by must be frequency, lemma, or author'}), 400
    if sort_order not in RARE_LEMMATA_SORT_ORDERS:
        return None, jsonify({'error': 'sort_order must be asc or desc'}), 400

    params = {
        'language': language,
        'max_occ': max_occ,
        'sort_by': sort_by,
        'sort_order': sort_order,
    }
    if require_paging:
        try:
            offset = int(request.args.get('offset', 0))
            limit = int(request.args.get('limit', 50))
        except (TypeError, ValueError):
            return None, jsonify({'error': 'offset and limit must be integers'}), 400
        if offset < 0:
            return None, jsonify({'error': 'offset must be zero or greater'}), 400
        if limit not in RARE_LEMMATA_PAGE_SIZES:
            return None, jsonify({'error': 'limit must be one of 25, 50, 100, or 500'}), 400
        params.update({'offset': offset, 'limit': limit})

    return params, None, None


@hapax_bp.route('/rare-lemmata-full', methods=['GET'])
def get_rare_lemmata_full():
    """
    Get rare words with display forms from pre-cached data.
    Instant loading - no computation on request.
    
    Query params:
        language: 'la', 'grc', or 'en' (default: 'la')
        max_occurrences: max corpus frequency (default: 10)
        offset: zero-based result offset (default: 0)
        limit: page size: 25, 50, 100, or 500 (default: 50)
        sort_by: frequency, lemma, or author (default: frequency)
        sort_order: asc or desc (default: asc)
    """
    params, error_response, error_status = _parse_rare_lemmata_params()
    if error_response:
        return error_response, error_status

    try:
        matching = _get_rare_lemmata_matching(params['language'], params['max_occ'])
        if matching is None:
            return jsonify({
                'language': params['language'],
                'total': 0,
                'max_occurrences': params['max_occ'],
                'offset': params['offset'],
                'limit': params['limit'],
                'words': [],
                'error': 'Cache not available and could not be regenerated. '
                         'Check that frequency data exists for this language.'
            })

        matching.sort(
            key=lambda word: _rare_lemmata_sort_key(word, params['sort_by'], params['language']),
            reverse=params['sort_order'] == 'desc'
        )
        page = matching[params['offset']:params['offset'] + params['limit']]
        results = [_format_rare_lemma(word) for word in page]
        
        response = jsonify({
            'language': params['language'],
            'total': len(matching),
            'max_occurrences': params['max_occ'],
            'offset': params['offset'],
            'limit': params['limit'],
            'words': results
        })
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        return response
        
    except Exception as e:
        logger.error(f"Error in rare-lemmata-full: {e}")
        return jsonify({'error': str(e)}), 500


@hapax_bp.route('/rare-lemmata-full/export', methods=['GET'])
def export_rare_lemmata_full():
    """Download every matching Rare Words Explorer entry as a CSV file."""
    params, error_response, error_status = _parse_rare_lemmata_params(require_paging=False)
    if error_response:
        return error_response, error_status

    try:
        matching = _get_rare_lemmata_matching(params['language'], params['max_occ'])
        if matching is None:
            return jsonify({'error': 'Rare words cache is not available'}), 503

        matching.sort(
            key=lambda word: _rare_lemmata_sort_key(word, params['sort_by'], params['language']),
            reverse=params['sort_order'] == 'desc'
        )
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['Lemma', 'Frequency', 'First Author', 'First Work', 'First Locus'])
        for word in matching:
            formatted = _format_rare_lemma(word)
            writer.writerow([
                formatted['lemma'], formatted['count'], formatted['first_author'],
                formatted['first_work'], formatted['first_locus']
            ])

        # Prepend UTF-8 BOM so Excel reads non-Latin scripts (Coptic, Greek) as Unicode, not Windows-1252.
        response = Response('﻿' + output.getvalue(), mimetype='text/csv; charset=utf-8')
        response.headers['Content-Disposition'] = (
            f"attachment; filename=rare_words_{params['language']}.csv"
        )
        return response
    except Exception as e:
        logger.error(f"Error exporting rare-lemmata-full: {e}")
        return jsonify({'error': str(e)}), 500


@hapax_bp.route('/rare-word-locations/<lemma>', methods=['GET'])
def get_rare_word_locations(lemma):
    """
    Get all locations where a specific rare word appears, with definition.
    
    Query params:
        language: 'la', 'grc', or 'en' (default: 'la')
    """
    try:
        language = request.args.get('language', 'la')
        
        locations = lookup_lemma_locations(lemma, language)
        
        actual_count = len(locations)
        
        definition = get_definition(lemma, language)
        
        return jsonify({
            'lemma': lemma,
            'language': language,
            'corpus_count': actual_count,
            'definition': definition,
            'locations': locations
        })
        
    except Exception as e:
        logger.error(f"Error in rare-word-locations: {e}")
        return jsonify({'error': str(e)}), 500


@hapax_bp.route('/lemma-forms/<lemma>', methods=['GET'])
def get_lemma_forms(lemma):
    """
    Get all known surface forms for a given lemma using the lemma tables.
    
    Query params:
        language: 'la', 'grc', or 'en' (default: 'la')
    
    Returns:
        forms: list of all surface forms that map to this lemma
    """
    try:
        from backend.text_processor import get_latin_lemma_table, get_greek_lemma_table
        
        language = request.args.get('language', 'la')
        lemma_lower = lemma.lower()
        
        if language == 'la':
            lemma_table = get_latin_lemma_table()
        elif language == 'grc':
            lemma_table = get_greek_lemma_table()
        else:
            return jsonify({'lemma': lemma, 'forms': [lemma]})
        
        forms = set()
        forms.add(lemma_lower)
        
        lemma_variants = {lemma_lower}
        if language == 'la':
            lemma_variants.add(lemma_lower.replace('u', 'v'))
            lemma_variants.add(lemma_lower.replace('v', 'u'))
        
        for surface_form, mapped_lemma in lemma_table.items():
            mapped_lower = mapped_lemma.lower()
            if mapped_lower in lemma_variants:
                forms.add(surface_form.lower())
        
        return jsonify({
            'lemma': lemma,
            'language': language,
            'forms': sorted(list(forms))
        })
        
    except Exception as e:
        logger.error(f"Error in lemma-forms: {e}")
        return jsonify({'error': str(e)}), 500


def _scan_text_lemma_locations(text_id, language, lemmas_of_interest):
    """Find where each lemma occurs within ONE text by scanning its own units
    with the current lemmatizer, independent of the inverted index.

    Used for Coptic, whose inverted index was built with an older bound-group
    lemmatization (so its lemma forms no longer match the current sub-word
    lemmatizer) and whose aggregate corpus files (sahidic.bible, ...) aren't
    indexed at all. Returns dict: lemma -> [location dict], matching the shape
    that lookup_lemma_locations produces (text_id, author, work, ref, text,
    positions).
    """
    from collections import defaultdict
    path = resolve_text_path(_texts_dir, language, text_id)
    if not path:
        return {}
    try:
        units = load_units_cached(path, language, _text_processor)
    except Exception as e:
        logger.error(f"Error scanning {text_id} for lemma locations: {e}")
        return {}
    parts = text_id.replace('.tess', '').split('.')
    author = (parts[0] if parts else text_id).replace('_', ' ').title()
    work = ('.'.join(parts[1:]) if len(parts) > 1 else '').replace('_', ' ').title()
    wanted = set(lemmas_of_interest)
    out = defaultdict(list)
    for u in units:
        lems = u.get('lemmas', [])
        present = wanted.intersection(lems)
        for lem in present:
            positions = [i for i, l in enumerate(lems) if l == lem]
            out[lem].append({
                'text_id': text_id,
                'author': author,
                'work': work,
                'ref': u.get('ref', ''),
                'text': u.get('text', ''),
                'positions': positions,
            })
    return out


def _compute_rare_words(source_id, target_id, language, source_language, target_language, max_occ, exclude_proper, limit=None):
    """Compute shared rare words between source and target texts.

    Pure compute core extracted from the ``hapax_search`` view: no Flask
    request, current_user, or log_search references. Raises SearchInputError
    on bad input. Returns the result dict.
    """
    source_lemmas = get_text_lemmas(source_id, source_language)
    target_lemmas = get_text_lemmas(target_id, target_language)

    if not source_lemmas:
        raise SearchInputError(f'Could not process source text: {source_id}')
    if not target_lemmas:
        raise SearchInputError(f'Could not process target text: {target_id}')

    shared_lemmas = source_lemmas & target_lemmas

    # Use document frequency (how many texts contain the lemma) for rarity,
    # not token frequency. A word in 3 texts is rare; a word in 500 is not.
    doc_freqs = get_document_frequencies_batch(shared_lemmas, source_language)

    shared_rare = {l for l in shared_lemmas
                   if 1 <= doc_freqs.get(l, 0) <= max_occ}

    import re
    source_base = re.sub(r'\.part\.\d+.*\.tess$', '.tess', source_id)
    target_base = re.sub(r'\.part\.\d+.*\.tess$', '.tess', target_id)
    source_is_full = '.part.' not in source_id
    target_is_full = '.part.' not in target_id

    def matches_source(loc_id):
        if loc_id == source_id:
            return True
        if '.part.' in source_id and loc_id == source_base:
            return True
        if source_is_full and re.sub(r'\.part\.\d+.*\.tess$', '.tess', loc_id) == source_id:
            return True
        return False

    def matches_target(loc_id):
        if loc_id == target_id:
            return True
        if '.part.' in target_id and loc_id == target_base:
            return True
        if target_is_full and re.sub(r'\.part\.\d+.*\.tess$', '.tess', loc_id) == target_id:
            return True
        return False

    # Decide, per side, whether to locate the lemma by scanning the text directly
    # or via the inverted index:
    #  - Coptic: its index uses an older bound-group lemmatization and omits
    #    aggregate files, so it can't locate current sub-word lemmas.
    #  - A .part.N text: parts are NOT in the index (only whole works are), and the
    #    index filter matches the whole work, so it would return the word's
    #    locations across the ENTIRE work (other books/poems) rather than the
    #    selected part. Scanning the part file gives only that part's lines.
    src_scan_needed = (source_language == 'cop') or ('.part.' in source_id)
    tgt_scan_needed = (target_language == 'cop') or ('.part.' in target_id)
    src_scan = _scan_text_lemma_locations(source_id, source_language, shared_rare) if src_scan_needed else None
    tgt_scan = _scan_text_lemma_locations(target_id, target_language, shared_rare) if tgt_scan_needed else None

    results = []
    for lemma in shared_rare:
        corpus_count = doc_freqs.get(lemma, 0)
        all_locations = lookup_lemma_locations(lemma, source_language)

        if src_scan_needed:
            source_locations = src_scan.get(lemma, [])
        else:
            source_locations = [loc for loc in all_locations if matches_source(loc['text_id'])]

        if tgt_scan_needed:
            target_locations = tgt_scan.get(lemma, [])
        else:
            target_locations = [loc for loc in all_locations if matches_target(loc['text_id'])]
            if source_language != target_language:
                for loc in lookup_lemma_locations(lemma, target_language):
                    if matches_target(loc['text_id']):
                        target_locations.append(loc)

        display_form = get_display_form(lemma, source_language, source_locations + target_locations)

        if len(source_locations) > 0 and len(target_locations) > 0:
            # Check if this word is a proper noun — corpus-wide OR local context
            # Local context catches names like Achates that are always capitalized
            # in the source/target but have lowercase homographs elsewhere in corpus
            word_is_pn = (is_proper_noun(lemma, source_language, all_locations) or
                          is_proper_noun(lemma, source_language, source_locations + target_locations))

            # Lowercase display_form for non-proper-nouns that got capitalized
            # from line-initial sampling (e.g., "Fatalem" at start of a line)
            if not word_is_pn and display_form and display_form[0].isupper():
                display_form = display_form[0].lower() + display_form[1:]

            results.append({
                'lemma': lemma,
                'display_form': display_form,
                'corpus_count': corpus_count,
                'is_proper_noun': word_is_pn,
                'source_occurrences': len(source_locations),
                'target_occurrences': len(target_locations),
                'source_locations': source_locations,
                'target_locations': target_locations,
                'all_corpus_locations': all_locations
            })

    # Apply proper noun filter if requested
    proper_nouns_excluded = 0
    if exclude_proper:
        filtered = []
        for r in results:
            if r['is_proper_noun']:
                proper_nouns_excluded += 1
            else:
                filtered.append(r)
        results = filtered

    results.sort(key=lambda x: (x['corpus_count'], x['lemma']))

    total = len(results)
    if limit is not None and limit > 0:
        results = results[:limit]

    return {
        'source': source_id,
        'target': target_id,
        'source_language': source_language,
        'target_language': target_language,
        'max_occurrences': max_occ,
        'exclude_proper_nouns': exclude_proper,
        'proper_nouns_excluded': proper_nouns_excluded,
        'source_total_lemmas': len(source_lemmas),
        'target_total_lemmas': len(target_lemmas),
        'shared_lemmas': len(shared_lemmas),
        'shared_rare_count': total,
        'showing': len(results),
        'results': results
    }


@hapax_bp.route('/hapax-search', methods=['GET', 'POST'])
def hapax_search():
    """
    Find shared rare words between source and target texts.

    POST body:
        source: source text filename (e.g., 'homer.iliad.part.1.tess')
        target: target text filename
        language: 'la', 'grc', or 'en' (default based on text)
        source_language: source text language (for cross-lingual)
        target_language: target text language (for cross-lingual)
        max_occurrences: max corpus frequency to consider rare (default: 10)
        exclude_proper_nouns: filter out proper nouns like names/places (default: false)
    """
    try:
        # Accept both POST JSON bodies and GET query-string params.
        data = request.get_json(silent=True) or request.args
        try:
            source_id, target_id, language = _parse_search_params(data)
        except ValueError as e:
            return jsonify({'error': str(e)}), 400
        source_language = data.get('source_language', language)
        target_language = data.get('target_language', language)
        max_occ = int(data.get('max_occurrences', 50))
        exclude_proper = _coerce_bool(data.get('exclude_proper_nouns', False))
        try:
            limit = data.get('limit', data.get('top_n'))
            limit = int(limit) if limit not in (None, '') else None
        except (TypeError, ValueError):
            limit = None

        try:
            result = _compute_rare_words(source_id, target_id, language,
                                         source_language, target_language,
                                         max_occ, exclude_proper, limit)
        except SearchInputError as e:
            return jsonify({'error': str(e)}), e.status

        req_user_id = current_user.id if current_user and current_user.is_authenticated else None
        req_city, req_country, _ip = get_user_location()
        log_search('Rare Words', language, source_id, target_id, None,
                   'rare_words', result['shared_rare_count'], False, req_user_id, req_city, req_country, _ip)

        return jsonify(result)

    except Exception as e:
        logger.error(f"Error in hapax-search: {e}")
        return jsonify({'error': str(e)}), 500


def _compute_rare_bigrams(source_id, target_id, language, min_rarity, limit, stoplist_basis, stoplist_size, use_stoplist):
    """Compute shared rare bigrams between source and target texts.

    Pure compute core extracted from the ``rare_bigram_search`` view: no Flask
    request, current_user, or log_search references. Raises SearchInputError
    on bad input. Returns the result dict.
    """
    from backend.bigram_frequency import (
        is_bigram_cache_available, load_bigram_cache,
        extract_bigrams, get_bigram_rarity_score, make_bigram_key
    )

    if not is_bigram_cache_available(language):
        raise SearchInputError(
            f'Bigram index not built for {language}. Please build it in Admin → Cache Management.'
        )

    load_bigram_cache(language)

    # Adapt min_rarity for small corpora: with N docs, a shared bigram
    # (doc_freq >= 2) has max rarity = 1 - 2/N. The default 0.9 threshold
    # is calibrated for Latin/Greek (~2100 texts) and is impossible for
    # small corpora like English (14 texts, max rarity = 0.857).
    from backend.bigram_frequency import _bigram_cache
    cached = _bigram_cache.get(language, {})
    total_docs = cached.get('total_docs', 1)
    max_possible_rarity = 1.0 - (2.0 / max(total_docs, 2))
    if min_rarity > max_possible_rarity:
        min_rarity = max(0.5, max_possible_rarity - 0.05)
        logger.info(f"Adapted min_rarity to {min_rarity:.3f} for {language} corpus ({total_docs} docs, max possible {max_possible_rarity:.3f})")

    try:
        source_path = _resolve_text_path(source_id, language)
    except FileNotFoundError:
        raise SearchInputError(f'Source text not found: {source_id}', 404)
    try:
        target_path = _resolve_text_path(target_id, language)
    except FileNotFoundError:
        raise SearchInputError(f'Target text not found: {target_id}', 404)

    source_units = load_units_cached(source_path, language, _text_processor, unit_type='line')
    target_units = load_units_cached(target_path, language, _text_processor, unit_type='line')

    source_bigram_locations = _extract_bigram_locations(source_units, make_bigram_key, language)
    target_bigram_locations = _extract_bigram_locations(target_units, make_bigram_key, language)

    dynamic_stopwords = set()
    if use_stoplist and stoplist_size > 0:
        source_lemma_freq = {}
        target_lemma_freq = {}
        for unit in source_units:
            for lemma in unit.get('lemmas', []):
                if lemma:
                    source_lemma_freq[lemma.lower()] = source_lemma_freq.get(lemma.lower(), 0) + 1
        for unit in target_units:
            for lemma in unit.get('lemmas', []):
                if lemma:
                    target_lemma_freq[lemma.lower()] = target_lemma_freq.get(lemma.lower(), 0) + 1

        if stoplist_basis == 'source':
            freq = source_lemma_freq
        elif stoplist_basis == 'target':
            freq = target_lemma_freq
        elif stoplist_basis == 'source_target':
            freq = {}
            for k, v in source_lemma_freq.items():
                freq[k] = freq.get(k, 0) + v
            for k, v in target_lemma_freq.items():
                freq[k] = freq.get(k, 0) + v
        else:
            freq = source_lemma_freq

        sorted_words = sorted(freq.items(), key=lambda x: -x[1])
        dynamic_stopwords = set(w for w, _ in sorted_words[:stoplist_size])

    shared_bigrams = set(source_bigram_locations.keys()) & set(target_bigram_locations.keys())

    def get_surface_forms_from_text(text, lemma1, lemma2, lang):
        """Extract actual surface forms from text that match the lemmas using the lemma table"""
        if not text:
            return [], []

        # Clean and tokenize
        import re
        tokens = re.findall(r"[\w']+", text)

        # Get the lemma table for reverse lookup
        if lang == 'la':
            lemma_table = _latin_lemma_table or get_latin_lemma_table()
        elif lang == 'grc':
            lemma_table = _greek_lemma_table or get_greek_lemma_table()
        else:
            lemma_table = {}

        # Normalize for comparison
        def normalize(w):
            if lang == 'la':
                return w.lower().replace('v', 'u').replace('j', 'i')
            else:
                import unicodedata
                return unicodedata.normalize('NFD', w.lower())

        lemma1_norm = normalize(lemma1)
        lemma2_norm = normalize(lemma2)

        forms1, forms2 = [], []
        for token in tokens:
            token_lower = token.lower()
            token_norm = normalize(token)

            # Check if this token's lemma matches our target lemmas
            # First check the lemma table
            mapped_lemma = lemma_table.get(token_lower, token_lower)
            mapped_norm = normalize(mapped_lemma)

            # Match if: token maps to the lemma, or token starts with lemma stem
            if mapped_norm == lemma1_norm or token_norm == lemma1_norm or \
               (len(lemma1_norm) >= 3 and token_norm.startswith(lemma1_norm[:min(4, len(lemma1_norm))])):
                if token_lower not in [f.lower() for f in forms1]:
                    forms1.append(token_lower)

            if mapped_norm == lemma2_norm or token_norm == lemma2_norm or \
               (len(lemma2_norm) >= 3 and token_norm.startswith(lemma2_norm[:min(4, len(lemma2_norm))])):
                if token_lower not in [f.lower() for f in forms2]:
                    forms2.append(token_lower)

        return forms1, forms2

    results = []
    for bg_key in shared_bigrams:
        words = bg_key.split('|')
        lemma1 = words[0] if len(words) > 0 else ''
        lemma2 = words[1] if len(words) > 1 else ''

        if use_stoplist:
            if stoplist_size > 0 and dynamic_stopwords:
                if lemma1.lower() in dynamic_stopwords or lemma2.lower() in dynamic_stopwords:
                    continue
            else:
                if is_word_in_stoplist(lemma1, language) or is_word_in_stoplist(lemma2, language):
                    continue

        rarity = get_bigram_rarity_score(bg_key, language)
        if rarity >= min_rarity:
            # Get proper dictionary forms for display
            dict_form1 = get_dictionary_form(lemma1, language)
            dict_form2 = get_dictionary_form(lemma2, language)
            if language == 'cop':
                # Show manuscript letterforms (ϣ, ϩ, ϫ …) rather than the
                # normalized dialect-P block used internally for matching.
                dict_form1 = _coptic_manuscript_form(dict_form1)
                dict_form2 = _coptic_manuscript_form(dict_form2)

            # Get actual matched words from all locations for highlighting
            src_locs = source_bigram_locations[bg_key]
            tgt_locs = target_bigram_locations[bg_key]
            matched_words = set()

            # Gather surface forms from both source and target locations
            for loc in (src_locs[:3] + tgt_locs[:3]):
                text = loc.get('text', '')
                forms1, forms2 = get_surface_forms_from_text(text, lemma1, lemma2, language)
                matched_words.update(forms1)
                matched_words.update(forms2)

            matched_words = list(matched_words)

            # Extract first source reference for occurrence-based sorting
            first_source_ref = ''
            if source_bigram_locations[bg_key]:
                first_source_ref = source_bigram_locations[bg_key][0].get('ref', '')

            results.append({
                'bigram': f'{dict_form1} + {dict_form2}',
                'word1': lemma1,
                'word2': lemma2,
                'display1': dict_form1,
                'display2': dict_form2,
                'matched_words': matched_words,
                'rarity': round(rarity, 4),
                'rarity_percent': round(rarity * 100, 1),
                'source_occurrences': len(source_bigram_locations[bg_key]),
                'target_occurrences': len(target_bigram_locations[bg_key]),
                'source_locations': _dedup_locations_by_ref(source_bigram_locations[bg_key])[:5],
                'target_locations': _dedup_locations_by_ref(target_bigram_locations[bg_key])[:5],
                '_first_source_ref': first_source_ref
            })

    results.sort(key=lambda x: -x['rarity'])
    results = results[:limit]

    out = {
        'source': source_id,
        'target': target_id,
        'language': language,
        'min_rarity': min_rarity,
        'source_unique_bigrams': len(source_bigram_locations),
        'target_unique_bigrams': len(target_bigram_locations),
        'shared_bigrams': len(shared_bigrams),
        'shared_rare_count': len(results),
        'results': results
    }

    # Coptic: an empty result across two different dialects is expected, not a
    # miss. Sahidic and Bohairic are separate written dialects that share almost
    # no surface vocabulary, so name that when it happens instead of leaving the
    # user to read the zero as an error.
    if language == 'cop' and not results:
        from backend.utils import infer_coptic_dialect
        src_dialect = infer_coptic_dialect(source_id)
        tgt_dialect = infer_coptic_dialect(target_id)
        if src_dialect and tgt_dialect and src_dialect != tgt_dialect:
            out['dialect_note'] = (
                f'No shared rare pairs is expected here: the source is '
                f'{src_dialect.capitalize()} Coptic and the target is '
                f'{tgt_dialect.capitalize()} Coptic. The two dialects share almost '
                f'no surface vocabulary, so a cross-dialect comparison returns few '
                f'or no lexical matches.'
            )
            out['source_dialect'] = src_dialect
            out['target_dialect'] = tgt_dialect

    return out


@hapax_bp.route('/rare-bigram-search', methods=['GET', 'POST'])
def rare_bigram_search():
    """
    Find shared rare word-pairs (bigrams) between source and target texts.
    Identifies unusual collocations even when individual words are common.

    POST body:
        source: source text filename
        target: target text filename
        language: 'la', 'grc', or 'en' (default: 'la')
        min_rarity: minimum rarity score (0-1, default 0.9)
        limit: max results to return (default 100)
        stoplist_basis: 'none', 'source_target', 'source', 'target', or 'corpus' (default: 'source_target')
        stoplist_size: number of top-frequency words to exclude (default: 0 = curated list)
        stoplist: legacy boolean for backward compatibility
    """
    try:
        # Accept both POST JSON bodies and GET query-string params.
        data = request.get_json(silent=True) or request.args
        try:
            source_id, target_id, language = _parse_search_params(data)
        except ValueError as e:
            return jsonify({'error': str(e)}), 400
        min_rarity = float(data.get('min_rarity', 0.9))
        limit = int(data.get('limit', 100))

        stoplist_basis = data.get('stoplist_basis', 'source_target')
        stoplist_size = int(data.get('stoplist_size', 0))
        use_stoplist = _coerce_bool(data.get('stoplist', False))
        if stoplist_basis == 'none':
            use_stoplist = False
        elif stoplist_basis in ('source_target', 'source', 'target', 'corpus'):
            use_stoplist = True

        try:
            result = _compute_rare_bigrams(source_id, target_id, language, min_rarity,
                                           limit, stoplist_basis, stoplist_size, use_stoplist)
        except SearchInputError as e:
            return jsonify({'error': str(e)}), e.status

        req_user_id = current_user.id if current_user and current_user.is_authenticated else None
        req_city, req_country, _ip = get_user_location()
        log_search('Rare Pairs', language, source_id, target_id, None,
                   'rare_pairs', len(result['results']), False, req_user_id, req_city, req_country, _ip)

        return jsonify(result)

    except Exception as e:
        logger.error(f"Error in rare-bigram-search: {e}")
        return jsonify({'error': str(e)}), 500


@hapax_bp.route('/hapax-search-poll', methods=['GET'])
def hapax_search_poll():
    from backend.blueprints.async_poll import poll, make_job_key
    data = request.args
    try:
        source_id, target_id, language = _parse_search_params(data)
    except ValueError as e:
        return jsonify({'status': 'error', 'error': str(e)}), 200
    source_language = data.get('source_language', language)
    target_language = data.get('target_language', language)
    try:
        max_occ = int(data.get('max_occurrences', 50))
    except (TypeError, ValueError):
        max_occ = 50
    exclude_proper = _coerce_bool(data.get('exclude_proper_nouns', False))
    try:
        limit = int(data.get('limit', 60))
    except (TypeError, ValueError):
        limit = 60
    key = make_job_key('hapax', source_id, target_id, source_language, target_language, max_occ, exclude_proper, limit)

    def compute():
        return _compute_rare_words(source_id, target_id, language, source_language, target_language, max_occ, exclude_proper, limit)

    def transform(d):
        slim = []
        for r in d.get('results', []):
            slim.append({
                'lemma': r.get('lemma'), 'display_form': r.get('display_form'),
                'corpus_count': r.get('corpus_count'), 'is_proper_noun': r.get('is_proper_noun'),
                'source_locations': (r.get('source_locations') or [])[:5],
                'target_locations': (r.get('target_locations') or [])[:5],
            })
        resp = {'source': d.get('source'), 'target': d.get('target'),
                'shared_rare_count': d.get('shared_rare_count'), 'showing': len(slim),
                'results': slim}
        # Carry the cross-dialect Coptic explanation through the slim MCP shape,
        # so an empty Sahidic-vs-Bohairic result says why instead of a bare zero.
        for k in ('dialect_note', 'source_dialect', 'target_dialect'):
            if k in d:
                resp[k] = d[k]
        return resp
    return poll('hapax', key, compute, transform)


@hapax_bp.route('/rare-bigram-search-poll', methods=['GET'])
def rare_bigram_search_poll():
    from backend.blueprints.async_poll import poll, make_job_key
    data = request.args
    try:
        source_id, target_id, language = _parse_search_params(data)
    except ValueError as e:
        return jsonify({'status': 'error', 'error': str(e)}), 200
    try:
        min_rarity = float(data.get('min_rarity', 0.9))
    except (TypeError, ValueError):
        min_rarity = 0.9
    try:
        limit = int(data.get('limit', 60))
    except (TypeError, ValueError):
        limit = 60
    stoplist_basis = data.get('stoplist_basis', 'source_target')
    try:
        stoplist_size = int(data.get('stoplist_size', 0))
    except (TypeError, ValueError):
        stoplist_size = 0
    use_stoplist = _coerce_bool(data.get('stoplist', False))
    if stoplist_basis == 'none':
        use_stoplist = False
    elif stoplist_basis in ('source_target', 'source', 'target', 'corpus'):
        use_stoplist = True
    key = make_job_key('rarebigram', source_id, target_id, language, min_rarity, limit, stoplist_basis, stoplist_size, use_stoplist)

    def compute():
        return _compute_rare_bigrams(source_id, target_id, language, min_rarity, limit, stoplist_basis, stoplist_size, use_stoplist)

    def transform(d):
        slim = []
        for r in d.get('results', []):
            slim.append({
                'bigram': r.get('bigram'), 'display1': r.get('display1'), 'display2': r.get('display2'),
                'word1': r.get('word1'), 'word2': r.get('word2'),
                'rarity_percent': r.get('rarity_percent'), 'matched_words': r.get('matched_words'),
                'source_locations': (r.get('source_locations') or [])[:5],
                'target_locations': (r.get('target_locations') or [])[:5],
            })
        resp = {'source': d.get('source'), 'target': d.get('target'),
                'shared_rare_count': d.get('shared_rare_count'), 'showing': len(slim),
                'results': slim}
        # Cross-dialect Coptic explanation. Derived HERE at serve time rather
        # than passed through from the compute: the poll path serves from
        # _compute_rare_bigrams (which never attached the note; only the direct
        # HTTP view did), and cached results computed before the note existed
        # would lack it anyway. Serve-time derivation covers both.
        for k in ('dialect_note', 'source_dialect', 'target_dialect'):
            if k in d:
                resp[k] = d[k]
        if language == 'cop' and not slim and 'dialect_note' not in resp:
            from backend.utils import infer_coptic_dialect
            src_dialect = infer_coptic_dialect(source_id)
            tgt_dialect = infer_coptic_dialect(target_id)
            if src_dialect and tgt_dialect and src_dialect != tgt_dialect:
                resp['dialect_note'] = (
                    f'No shared rare pairs is expected here: the source is '
                    f'{src_dialect.capitalize()} Coptic and the target is '
                    f'{tgt_dialect.capitalize()} Coptic. The two dialects share almost '
                    f'no surface vocabulary, so a cross-dialect comparison returns few '
                    f'or no lexical matches.'
                )
                resp['source_dialect'] = src_dialect
                resp['target_dialect'] = tgt_dialect
        return resp
    return poll('rarebigram', key, compute, transform)


@hapax_bp.route('/rare-word-cloud', methods=['GET'])
def get_rare_word_cloud():
    """
    Get data for rare words visualization (word cloud).
    Returns dictionary-validated words with inverted sizing (rarer = larger weight).
    
    Query params:
        language: 'la', 'grc', or 'en' (default: 'la')
        max_occurrences: max corpus frequency (default: 5)
        limit: max words to return (default: 200)
    """
    try:
        language = request.args.get('language', 'la')
        max_occ = int(request.args.get('max_occurrences', 5))
        limit = int(request.args.get('limit', 200))
        
        rare_words = get_rare_words_from_cache(language, max_occ)
        
        lemma_counts = {}
        for word, count in rare_words.items():
            if not is_valid_dictionary_word(word, language):
                continue
            
            dict_lemma = get_dictionary_lemma(word, language)
            
            if dict_lemma in lemma_counts:
                lemma_counts[dict_lemma] = min(lemma_counts[dict_lemma], count)
            else:
                lemma_counts[dict_lemma] = count
        
        import random
        word_list = list(lemma_counts.items())
        random.shuffle(word_list)
        selected_words = word_list[:limit]
        
        max_freq = max_occ
        words = []
        for lemma, count in selected_words:
            weight = (max_freq - count + 1) / max_freq
            
            display_text = lemma
            if language == 'grc':
                locations = lookup_lemma_locations(lemma, language)
                if locations:
                    fetched_form = get_display_form(lemma, language, locations)
                    if fetched_form != lemma:
                        display_text = fetched_form
                display_text = fix_final_sigma(display_text)
            
            words.append({
                'text': display_text,
                'lemma': lemma,
                'count': count,
                'weight': weight,
                'language': language
            })
        
        return jsonify({
            'language': language,
            'max_occurrences': max_occ,
            'total_available': len(lemma_counts),
            'returned': len(words),
            'words': words
        })
        
    except Exception as e:
        logger.error(f"Error in rare-word-cloud: {e}")
        return jsonify({'error': str(e)}), 500


@hapax_bp.route('/rare-bigrams', methods=['GET'])
def get_rare_bigrams():
    """Get list of rare word pairs from corpus bigram index"""
    try:
        from backend.bigram_frequency import get_bigram_cache, is_bigram_cache_available
        
        language = request.args.get('language', 'la')
        min_rarity = float(request.args.get('min_rarity', 0.9))
        limit = int(request.args.get('limit', 200))
        
        if not is_bigram_cache_available(language):
            return jsonify({
                'bigrams': [],
                'message': f'Bigram index not built for {language}. Build it in Admin > Cache Management.'
            })
        
        cache = get_bigram_cache(language)
        if not cache:
            return jsonify({'bigrams': [], 'message': 'Cache not loaded'})
        
        doc_counts = cache.get('doc_frequencies', {})
        total_docs = cache.get('total_docs', 1)
        
        # Calculate threshold doc count (to avoid iterating everything)
        # rarity >= min_rarity means doc_count <= total_docs * (1 - min_rarity)
        max_doc_count = int(total_docs * (1 - min_rarity))
        
        rare_bigrams = []
        for bigram_key, doc_count in doc_counts.items():
            if doc_count > max_doc_count:
                continue
            rarity = 1 - (doc_count / total_docs)
            words = bigram_key.split('|')
            if len(words) == 2:
                rare_bigrams.append({
                    'word1': words[0],
                    'word2': words[1],
                    'doc_count': doc_count,
                    'rarity': round(rarity, 4),
                    'rarity_percent': round(rarity * 100, 1)
                })
            # Stop if we have way more than needed
            if len(rare_bigrams) > limit * 20:
                break
        
        rare_bigrams.sort(key=lambda x: (-x['rarity'], x['word1']))
        rare_bigrams = rare_bigrams[:limit]
        
        return jsonify({
            'language': language,
            'min_rarity': min_rarity,
            'total_corpus_bigrams': len(doc_counts),
            'total_docs': total_docs,
            'returned': len(rare_bigrams),
            'bigrams': rare_bigrams
        })
        
    except Exception as e:
        logger.error(f"Error in rare-bigrams: {e}")
        return jsonify({'error': str(e)}), 500
