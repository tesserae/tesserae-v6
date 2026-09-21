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

from backend.utils import detect_text_type

POETRY_MAX_DISTANCE = 10
PROSE_MAX_DISTANCE = 4  # No more than 3 intervening words (positions 0 to 4)


def is_prose_text(text_id: str, language: str = 'la') -> bool:
    """
    Determine if a text is prose based on its ID/filename.
    Delegates to the unified detect_text_type() in utils.py.

    Args:
        text_id: The text filename or identifier
        language: Language code (la, grc, en)

    Returns:
        True if the text is prose, False if poetry
    """
    if not text_id:
        return False
    return detect_text_type(text_id, language=language) == 'prose'


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


# One shared rule, backend/latin_orthography.py. This used to keep case, so a
# capitalised word at the start of a line did not match its lowercase self
# when the distance filter compared matched words.
from backend.latin_orthography import fold_latin as normalize_latin  # noqa: E402

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
    
    positions_by_word = {}
    for i, word in enumerate(words_list):
        if word in matched_words_normalized:
            if word not in positions_by_word:
                positions_by_word[word] = []
            positions_by_word[word].append(i)
    
    if len(positions_by_word) < 2:
        return 0
    
    all_position_lists = list(positions_by_word.values())
    min_dist = float('inf')
    for a_idx in range(len(all_position_lists)):
        for b_idx in range(a_idx + 1, len(all_position_lists)):
            for pa in all_position_lists[a_idx]:
                for pb in all_position_lists[b_idx]:
                    d = abs(pa - pb)
                    if d < min_dist:
                        min_dist = d
    
    return min_dist if min_dist != float('inf') else 0


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
