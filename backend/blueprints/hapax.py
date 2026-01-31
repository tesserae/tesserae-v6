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
from flask import Blueprint, jsonify, request
import os
import json

from backend.logging_config import get_logger
from backend.frequency_cache import load_frequency_cache, get_corpus_frequencies
from backend.inverted_index import get_connection, is_index_available
from backend.text_processor import get_latin_lemma_table, get_greek_lemma_table

logger = get_logger('hapax')


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


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

hapax_bp = Blueprint('hapax', __name__, url_prefix='/api')

_texts_dir = None
_text_processor = None
_author_dates = None

_latin_lemma_table = {}
_greek_lemma_table = {}
_latin_valid_lemmas = set()
_greek_valid_lemmas = set()
_greek_display_forms = {}
_greek_text_forms = {}


def load_greek_display_forms():
    """Load mapping from normalized Greek to proper dictionary forms with diacritics"""
    global _greek_display_forms, _greek_text_forms
    
    if _greek_display_forms:
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
    """Convert Latin lookalike characters to Greek equivalents"""
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
        with urllib.request.urlopen(req, timeout=3) as response:
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
        with urllib.request.urlopen(req, timeout=3) as response:
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
        with urllib.request.urlopen(req, timeout=5) as response:
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
        with urllib.request.urlopen(req, timeout=3) as response:
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
        with urllib.request.urlopen(req, timeout=3) as response:
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
        text_path = os.path.join(_texts_dir, language, text_id)
        if not os.path.exists(text_path):
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
    """Remove trailing/leading punctuation from a word"""
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
    """Convert medial sigma at word end to final sigma for Greek"""
    if word and word[-1] == 'σ':
        return word[:-1] + 'ς'
    return word


def fix_greek_combining(word):
    """Fix malformed Greek where combining marks come before base letters"""
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


def get_display_form(lemma, language, locations):
    """Get a display form with diacritics by sampling from locations"""
    import unicodedata
    
    display = None
    if locations:
        for loc in locations[:3]:
            positions = loc.get('positions', [])
            if positions:
                word = get_original_word_form(loc['text_id'], loc['ref'], positions[0], language)
                if word:
                    word = strip_punctuation(word)
                    if language == 'grc':
                        # Fix malformed combining character order, then normalize to NFC
                        word = fix_greek_combining(word)
                        display = unicodedata.normalize('NFC', word)
                    else:
                        # For Latin, lowercase and handle u/v normalization
                        display = word.lower()
                    break
    
    # Fallback to Morpheus lookup if Greek and no location found
    if not display and language == 'grc':
        display = get_greek_display_form(lemma)
    
    # If still no display, use the lemma itself
    if not display:
        display = lemma
    
    # Convert trailing medial sigma to final sigma for Greek
    if language == 'grc' and display and display.endswith('σ'):
        display = display[:-1] + 'ς'
    
    return display


def init_hapax_blueprint(texts_dir, text_processor, author_dates):
    """Initialize blueprint with required dependencies"""
    global _texts_dir, _text_processor, _author_dates
    _texts_dir = texts_dir
    _text_processor = text_processor
    _author_dates = author_dates


_line_text_cache = {}

def get_line_text_from_file(text_id, language, ref):
    """
    Look up the actual line text from a .tess file given text_id and ref.
    Uses caching to avoid re-reading files for multiple lookups.
    """
    global _line_text_cache
    
    cache_key = f"{language}/{text_id}"
    
    if cache_key not in _line_text_cache:
        text_path = os.path.join(_texts_dir, language, text_id)
        if not os.path.exists(text_path):
            return None
        
        try:
            lines_by_ref = {}
            with open(text_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                    if '>' in line:
                        parts = line.split('>', 1)
                        if len(parts) == 2:
                            line_ref = parts[0].strip().lstrip('<')
                            line_text = parts[1].strip()
                            lines_by_ref[line_ref] = line_text
            _line_text_cache[cache_key] = lines_by_ref
        except Exception as e:
            logger.error(f"Error reading text file {text_path}: {e}")
            _line_text_cache[cache_key] = {}
    
    lines = _line_text_cache.get(cache_key, {})
    
    if ref in lines:
        return lines[ref]
    
    for cached_ref, text in lines.items():
        if ref in cached_ref or cached_ref in ref:
            return text
    
    return None


def get_rare_words_from_cache(language, max_occurrences=10):
    """Get lemmas with corpus frequency between 1 and max_occurrences"""
    cached = load_frequency_cache(language)
    if not cached or 'frequencies' not in cached:
        return {}
    
    rare_words = {}
    for lemma, count in cached['frequencies'].items():
        if 1 <= count <= max_occurrences:
            rare_words[lemma] = count
    
    return rare_words


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
    '''
    
    locations = []
    try:
        cursor.execute(query, list(expanded_lemmas))
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
    text_path = os.path.join(_texts_dir, language, text_id)
    if not os.path.exists(text_path):
        return set()
    
    try:
        units = _text_processor.process_file(text_path, language)
        all_lemmas = set()
        for unit in units:
            all_lemmas.update(unit.get('lemmas', []))
        return all_lemmas
    except Exception as e:
        logger.error(f"Error processing text {text_id}: {e}")
        return set()


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
        
        filtered = {k: v for k, v in rare_words.items() if v >= min_occ}
        
        sorted_words = sorted(filtered.items(), key=lambda x: (x[1], x[0]))[:limit]
        
        results = []
        for lemma, count in sorted_words:
            entry = {
                'lemma': lemma,
                'count': count,
                'language': language
            }
            if include_locations:
                entry['locations'] = lookup_lemma_locations(lemma, language)
            results.append(entry)
        
        return jsonify({
            'language': language,
            'total_rare_words': len(filtered),
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


def regenerate_rare_words_cache(language):
    """
    Regenerate rare words cache from current frequency data.
    Call this after adding new texts to update the Rare Words Explorer.
    """
    import re
    import unicodedata
    from backend.frequency_cache import load_frequency_cache
    
    logger.info(f"Regenerating rare words cache for {language}")
    
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
    
    seen = {}
    for w in rare_words:
        key = w['lemma']
        if key not in seen or w['count'] < seen[key]['count']:
            seen[key] = w
    
    # Look up first location for each rare word to get author/work info
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
    
    unique_rare = sorted(seen.values(), key=lambda x: x.get('display', x.get('lemma', '')).lower().lstrip('*'))
    
    cache_dir = os.path.join('cache', 'rare_words')
    os.makedirs(cache_dir, exist_ok=True)
    cache_path = os.path.join(cache_dir, f'{language}.json')
    
    with open(cache_path, 'w', encoding='utf-8') as f:
        json.dump({'words': unique_rare, 'total': len(unique_rare)}, f, ensure_ascii=False)
    
    clear_rare_words_memory_cache(language)
    
    logger.info(f"Regenerated rare words cache for {language}: {len(unique_rare)} words")
    return True


@hapax_bp.route('/rare-lemmata-full', methods=['GET'])
def get_rare_lemmata_full():
    """
    Get rare words with display forms from pre-cached data.
    Instant loading - no computation on request.
    
    Query params:
        language: 'la', 'grc', or 'en' (default: 'la')
        max_occurrences: max corpus frequency (default: 10)
        limit: max number to return (default: 50000)
    """
    try:
        language = request.args.get('language', 'la')
        max_occ = int(request.args.get('max_occurrences', 10))
        limit = int(request.args.get('limit', 50000))
        
        # Load from pre-cached file for instant response
        cached = load_rare_words_cache(language)
        if not cached:
            return jsonify({
                'language': language,
                'total': 0,
                'max_occurrences': max_occ,
                'words': [],
                'error': 'Cache not available'
            })
        
        # Filter by max_occurrences
        all_words = cached.get('words', [])
        matching = [w for w in all_words if w['count'] <= max_occ]
        filtered = matching[:limit]
        
        # Format response using pre-computed display forms
        results = []
        for w in filtered:
            display = w.get('display', w.get('lemma', ''))
            # Strip leading asterisks (denote reconstructed forms in linguistics)
            if display.startswith('*'):
                display = display[1:]
            results.append({
                'lemma': display,
                'count': w['count'],
                'first_author': w.get('first_author', ''),
                'first_work': w.get('first_work', ''),
                'first_locus': w.get('first_locus', ''),
                'text_id': w.get('text_id', '')
            })
        
        response = jsonify({
            'language': language,
            'total': len(matching),  # Total matching, not limited
            'max_occurrences': max_occ,
            'words': results
        })
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        return response
        
    except Exception as e:
        logger.error(f"Error in rare-lemmata-full: {e}")
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


@hapax_bp.route('/hapax-search', methods=['POST'])
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
    """
    try:
        data = request.get_json() or {}
        source_id = data.get('source')
        target_id = data.get('target')
        language = data.get('language', 'la')
        source_language = data.get('source_language', language)
        target_language = data.get('target_language', language)
        max_occ = int(data.get('max_occurrences', 50))
        
        if not source_id or not target_id:
            return jsonify({'error': 'Please select both source and target texts'}), 400
        
        source_lemmas = get_text_lemmas(source_id, source_language)
        target_lemmas = get_text_lemmas(target_id, target_language)
        
        if not source_lemmas:
            return jsonify({'error': f'Could not process source text: {source_id}'}), 400
        if not target_lemmas:
            return jsonify({'error': f'Could not process target text: {target_id}'}), 400
        
        shared_lemmas = source_lemmas & target_lemmas
        
        source_rare = get_rare_words_from_cache(source_language, max_occ)
        target_rare = get_rare_words_from_cache(target_language, max_occ)
        
        all_rare = set(source_rare.keys()) | set(target_rare.keys())
        
        shared_rare = shared_lemmas & all_rare
        
        results = []
        for lemma in shared_rare:
            corpus_count = source_rare.get(lemma, target_rare.get(lemma, 0))
            
            source_locations = []
            target_locations = []
            
            import re
            source_base = re.sub(r'\.part\.\d+\.tess$', '.tess', source_id)
            target_base = re.sub(r'\.part\.\d+\.tess$', '.tess', target_id)
            source_is_full = '.part.' not in source_id
            target_is_full = '.part.' not in target_id
            
            def matches_source(loc_id):
                if loc_id == source_id:
                    return True
                if '.part.' in source_id and loc_id == source_base:
                    return True
                if source_is_full:
                    loc_base = re.sub(r'\.part\.\d+\.tess$', '.tess', loc_id)
                    if loc_base == source_id:
                        return True
                return False
            
            def matches_target(loc_id):
                if loc_id == target_id:
                    return True
                if '.part.' in target_id and loc_id == target_base:
                    return True
                if target_is_full:
                    loc_base = re.sub(r'\.part\.\d+\.tess$', '.tess', loc_id)
                    if loc_base == target_id:
                        return True
                return False
            
            all_locations = lookup_lemma_locations(lemma, source_language)
            for loc in all_locations:
                loc_text_id = loc['text_id']
                if matches_source(loc_text_id):
                    source_locations.append(loc)
                elif matches_target(loc_text_id):
                    target_locations.append(loc)
            
            if source_language != target_language:
                target_all_locations = lookup_lemma_locations(lemma, target_language)
                for loc in target_all_locations:
                    loc_text_id = loc['text_id']
                    if matches_target(loc_text_id):
                        target_locations.append(loc)
            
            display_form = get_display_form(lemma, source_language, source_locations + target_locations)
            
            if len(source_locations) > 0 and len(target_locations) > 0:
                results.append({
                    'lemma': lemma,
                    'display_form': display_form,
                    'corpus_count': corpus_count,
                    'source_occurrences': len(source_locations),
                    'target_occurrences': len(target_locations),
                    'source_locations': source_locations,
                    'target_locations': target_locations,
                    'all_corpus_locations': all_locations
                })
        
        results.sort(key=lambda x: (x['corpus_count'], x['lemma']))
        
        return jsonify({
            'source': source_id,
            'target': target_id,
            'source_language': source_language,
            'target_language': target_language,
            'max_occurrences': max_occ,
            'source_total_lemmas': len(source_lemmas),
            'target_total_lemmas': len(target_lemmas),
            'shared_lemmas': len(shared_lemmas),
            'shared_rare_count': len(results),
            'results': results
        })
        
    except Exception as e:
        logger.error(f"Error in hapax-search: {e}")
        return jsonify({'error': str(e)}), 500


@hapax_bp.route('/rare-bigram-search', methods=['POST'])
def rare_bigram_search():
    """
    Find shared rare word-pairs (bigrams) between source and target texts.
    Identifies unusual collocations even when individual words are common.
    
    POST body:
        source: source text filename
        target: target text filename  
        language: 'la', 'grc', or 'en'
        min_rarity: minimum rarity score (0-1, default 0.9)
        limit: max results to return (default 100)
    """
    try:
        from backend.bigram_frequency import (
            is_bigram_cache_available, load_bigram_cache,
            extract_bigrams, get_bigram_rarity_score, make_bigram_key
        )
        
        data = request.get_json() or {}
        source_id = data.get('source')
        target_id = data.get('target')
        language = data.get('language', 'la')
        min_rarity = float(data.get('min_rarity', 0.9))
        limit = int(data.get('limit', 100))
        
        if not source_id or not target_id:
            return jsonify({'error': 'Please select both source and target texts'}), 400
        
        if not is_bigram_cache_available(language):
            return jsonify({
                'error': f'Bigram index not built for {language}. Please build it in Admin → Cache Management.'
            }), 400
        
        load_bigram_cache(language)
        
        lang_dir = os.path.join(_texts_dir, language)
        source_path = os.path.join(lang_dir, source_id)
        target_path = os.path.join(lang_dir, target_id)
        
        if not os.path.exists(source_path):
            return jsonify({'error': f'Source text not found: {source_id}'}), 404
        if not os.path.exists(target_path):
            return jsonify({'error': f'Target text not found: {target_id}'}), 404
        
        source_units = _text_processor.process_file(source_path, language, unit_type='line')
        target_units = _text_processor.process_file(target_path, language, unit_type='line')
        
        source_bigram_locations = {}
        for unit in source_units:
            lemmas = unit.get('lemmas', [])
            for i in range(len(lemmas) - 1):
                if lemmas[i] and lemmas[i+1]:
                    bg_key = make_bigram_key(lemmas[i], lemmas[i+1])
                    if bg_key not in source_bigram_locations:
                        source_bigram_locations[bg_key] = []
                    source_bigram_locations[bg_key].append({
                        'ref': unit.get('ref', ''),
                        'text': normalize_line_text(unit.get('text', ''), language),
                        'words': [lemmas[i], lemmas[i+1]]
                    })
        
        target_bigram_locations = {}
        for unit in target_units:
            lemmas = unit.get('lemmas', [])
            for i in range(len(lemmas) - 1):
                if lemmas[i] and lemmas[i+1]:
                    bg_key = make_bigram_key(lemmas[i], lemmas[i+1])
                    if bg_key not in target_bigram_locations:
                        target_bigram_locations[bg_key] = []
                    target_bigram_locations[bg_key].append({
                        'ref': unit.get('ref', ''),
                        'text': normalize_line_text(unit.get('text', ''), language),
                        'words': [lemmas[i], lemmas[i+1]]
                    })
        
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
            rarity = get_bigram_rarity_score(bg_key, language)
            if rarity >= min_rarity:
                words = bg_key.split('|')
                lemma1 = words[0] if len(words) > 0 else ''
                lemma2 = words[1] if len(words) > 1 else ''
                
                # Get proper dictionary forms for display
                dict_form1 = get_dictionary_form(lemma1, language)
                dict_form2 = get_dictionary_form(lemma2, language)
                
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
                    'source_locations': source_bigram_locations[bg_key][:5],
                    'target_locations': target_bigram_locations[bg_key][:5]
                })
        
        results.sort(key=lambda x: -x['rarity'])
        results = results[:limit]
        
        return jsonify({
            'source': source_id,
            'target': target_id,
            'language': language,
            'min_rarity': min_rarity,
            'source_unique_bigrams': len(source_bigram_locations),
            'target_unique_bigrams': len(target_bigram_locations),
            'shared_bigrams': len(shared_bigrams),
            'shared_rare_count': len(results),
            'results': results
        })
        
    except Exception as e:
        logger.error(f"Error in rare-bigram-search: {e}")
        return jsonify({'error': str(e)}), 500


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
