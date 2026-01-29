"""
Unified distance filtering for all Tesserae search types.

This module provides a single source of truth for:
- Prose/poetry detection
- Maximum distance thresholds
- Distance-based result filtering

All search endpoints (line search, pairwise, corpus) should use these functions
to ensure consistent filtering behavior across the entire application.
"""

import re
import unicodedata

PROSE_AUTHORS = [
    # Latin prose authors
    'cicero', 'caesar', 'livy', 'sallust', 'tacitus', 'suetonius',
    'nepos', 'quintilian', 'pliny', 'apuleius', 'petronius',
    'augustine', 'jerome', 'ambrose', 'seneca_prose', 'ammianus',
    'curtius', 'valerius_maximus', 'gellius', 'macrobius', 'boethius',
    'cassiodorus', 'isidore', 'bede', 'hegesippus', 'hilary',
    'cassian', 'lactantius', 'tertullian', 'cyprian', 'minucius',
    'arnobius', 'firmicus', 'sulpicius', 'orosius', 'salvian',
    'florus', 'eutropius', 'dante', 'justinus', 'frontinus', 'eugippius',
    'sedulius', 'salutati', 'petrarch', 'boccaccio', 'poggio',
    'bruni', 'valla', 'ficino', 'poliziano', 'erasmus',
    'cic.', 'caes.', 'liv.', 'sall.', 'tac.', 'suet.', 'nep.',
    'quint.', 'plin.', 'apul.', 'petron.', 'aug.', 'hier.', 'ambr.',
    'amm.', 'curt.', 'val.max.', 'gell.', 'macr.', 'boeth.', 'cass.',
    'isid.', 'bed.', 'lact.', 'tert.', 'cypr.', 'oros.', 'flor.', 'eutr.',
    # Greek prose authors
    'epictetus', 'plato', 'aristotle', 'xenophon', 'thucydides', 'herodotus',
    'plutarch', 'lucian', 'demosthenes', 'isocrates', 'lysias', 'polybius',
    'diodorus', 'strabo', 'pausanias', 'dio', 'appian', 'arrian',
    'diogenes_laertius', 'athenaeus', 'aelian', 'philostratus', 'plotinus',
    'porphyry', 'iamblichus', 'proclus', 'longinus', 'galen', 'hippocrates',
    'josephus', 'philo', 'clement', 'origen', 'eusebius', 'basil', 'gregory',
    'chrysostom', 'theodoret', 'procopius', 'agathias', 'menander',
    'discourses', 'enchiridion', 'republic', 'symposium', 'phaedo', 'laws',
    'anabasis', 'hellenica', 'memorabilia', 'histories', 'peloponnesian'
]

PROSE_MARKERS = [
    'epistulae', 'letters', 'de_officiis', 'de_oratore', 
    'de_finibus', 'de_natura', 'tusculan', 'bellum_gallicum',
    'bellum_civile', 'historiae', 'annales', 'agricola', 'germania', 
    'dialogus', 'satyricon', 'confessions', 'de_civitate',
    'res_gestae', 'rerum_gestarum', 'orationes', 'in_catilinam',
    'pro_', 'contra_', 'adversus_',
    'confucius', 'sinarum', 'philosophus',
    'divina_commedia', 'divine_comedy', 'commedia', 'divina_comedia',
    'couplet', 'proem', 'decl',
    'excidio', 'hierosolymitano', 'tractatus', 'super_psalmos',
    'conlationes', 'institutionum', 'divinarum', 'apologeticum',
    'adversus_marcionem', 'de_spectaculis',
    'opus_paschale', 'paschale', 'de_laboribus', 'herculis'
]

POETRY_MAX_DISTANCE = 10
PROSE_MAX_DISTANCE = 4  # No more than 3 intervening words (positions 0 to 4)


def is_prose_text(text_id: str, language: str = 'la') -> bool:
    """
    Determine if a text is prose based on its ID/filename.
    
    Args:
        text_id: The text filename or identifier
        language: Language code (la, grc, en)
    
    Returns:
        True if the text is prose, False if poetry
    """
    if not text_id:
        return False
    
    text_lower = text_id.lower()
    
    for marker in PROSE_AUTHORS + PROSE_MARKERS:
        if marker in text_lower:
            return True
    
    return False


def get_max_distance(text_id: str, language: str = 'la') -> int:
    """
    Get the maximum allowed distance between matched words for a text.
    
    Args:
        text_id: The text filename or identifier
        language: Language code
    
    Returns:
        Maximum word distance threshold
    """
    if is_prose_text(text_id, language):
        return PROSE_MAX_DISTANCE
    return POETRY_MAX_DISTANCE


def normalize_latin(s: str) -> str:
    """Normalize Latin text for comparison (v->u, j->i)"""
    return s.replace('v', 'u').replace('j', 'i')

def normalize_greek(s: str) -> str:
    """Normalize Greek text by removing diacritics and combining characters."""
    # NFD decomposition separates base chars from combining marks
    decomposed = unicodedata.normalize('NFD', s)
    # Keep only letters and numbers (category starts with 'L' or 'N')
    base_chars = ''.join(c for c in decomposed if unicodedata.category(c)[0] in ('L', 'N'))
    return base_chars.lower()

def calculate_match_distance(text: str, matched_words: list, language: str = 'la') -> int:
    """
    Calculate the word distance between matched terms in a text.
    
    Args:
        text: The full text of the line/unit
        matched_words: List of matched words found in the text
        language: Language code for normalization
    
    Returns:
        Distance (span) between first and last matched word positions,
        or 0 if fewer than 2 matches found
    """
    if not text or not matched_words or len(matched_words) < 2:
        return 0
    
    # For Greek, use proper Unicode normalization
    if language == 'grc':
        words_list = text.split()
        words_list = [normalize_greek(w) for w in words_list]
        matched_words_normalized = [normalize_greek(w) for w in matched_words]
    else:
        words_list = re.sub(r'[^\w\s]', '', text.lower()).split()
        matched_words_normalized = [w.lower() for w in matched_words]
        
        if language == 'la':
            words_list = [normalize_latin(w) for w in words_list]
            matched_words_normalized = [normalize_latin(w) for w in matched_words_normalized]
    
    match_positions = []
    for i, word in enumerate(words_list):
        if word in matched_words_normalized:
            match_positions.append(i)
    
    if len(match_positions) < 2:
        return 0
    
    return match_positions[-1] - match_positions[0]


def passes_distance_filter(text: str, matched_words: list, text_id: str, language: str = 'la') -> bool:
    """
    Check if a result passes the distance filter.
    
    This is the main function that all search endpoints should use.
    
    Args:
        text: The full text of the line/unit
        matched_words: List of matched words found in the text
        text_id: The text filename or identifier (for prose detection)
        language: Language code
    
    Returns:
        True if the result passes the filter (words are close enough),
        False if it should be rejected (words too far apart)
    """
    if not matched_words or len(matched_words) < 2:
        return True
    
    distance = calculate_match_distance(text, matched_words, language)
    
    if distance == 0:
        return True
    
    max_dist = get_max_distance(text_id, language)
    
    return distance <= max_dist
