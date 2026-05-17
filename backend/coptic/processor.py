"""
Coptic text processing for Tesserae V6.

Provides tokenization, normalization, and lemmatization for Coptic text.
Uses pre-annotated data from Coptic SCRIPTORIUM (CoNLL-U with lemmas)
as the primary lemmatization source. No Stanza model exists for Coptic.

Key Coptic-specific processing:
- Supralinear stroke stripping (combining overline U+0305)
- Dual Unicode block normalization (legacy U+03E2-03EF -> primary U+2C80-2CFF)
- Case folding (Unicode has upper/lowercase Coptic, manuscripts are unicameral)
- NFC normalization
- Per-tess-file sub-word lemma cache (Coptic SCRIPTORIUM CoNLL-U), keyed by
  ref (e.g. ``sahidica.mark.13.9``). Bound groups are split into morphemes
  here, so search operates on sub-word units rather than whole bound groups
  (which would produce artifactually rare matches).
"""

import json
import os
import re
import unicodedata
from collections import OrderedDict

from backend.logging_config import get_logger

logger = get_logger('coptic.processor')

# Pre-annotated lemma cache - lazy loaded
_coptic_lemma_table = None

# Per-tess-file lemma cache (LRU). Maps tess basename (no .tess suffix) to
# {ref: {"tokens": [...], "lemmas": [...]}} loaded from
# cache/lemmas/cop/<basename>.json. None means we already tried and the file
# was missing -- avoids retrying every line.
_TESS_LEMMA_CACHE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    'cache', 'lemmas', 'cop'
)
_TESS_LEMMA_CACHE_MAX = 30
_tess_lemma_cache = OrderedDict()  # basename -> dict | None


def _load_tess_lemma_cache(basename):
    """Load the Coptic SCRIPTORIUM sub-word lemma cache for one .tess file.

    Returns a dict keyed by ref (each value has ``tokens`` and ``lemmas`` lists)
    or ``None`` if the cache file is absent. Results are memoised in a small
    LRU; ``None`` is cached too so we don't keep stat'ing the disk for files
    that never had a cache (e.g. user-supplied .tess inputs).
    """
    if basename in _tess_lemma_cache:
        # Refresh LRU position
        _tess_lemma_cache.move_to_end(basename)
        return _tess_lemma_cache[basename]

    cache_path = os.path.join(_TESS_LEMMA_CACHE_DIR, f"{basename}.json")
    data = None
    if os.path.exists(cache_path):
        try:
            with open(cache_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except (json.JSONDecodeError, IOError) as exc:
            logger.warning(f"Coptic sub-word cache unreadable: {cache_path} ({exc})")
            data = None
    else:
        logger.debug(f"Coptic sub-word cache not found: {cache_path}")

    _tess_lemma_cache[basename] = data
    if len(_tess_lemma_cache) > _TESS_LEMMA_CACHE_MAX:
        _tess_lemma_cache.popitem(last=False)
    return data


def get_subword_units_for_ref(tess_basename, ref):
    """Return ``(tokens, lemmas)`` for ``ref`` from the SCRIPTORIUM cache.

    ``tess_basename`` is the .tess filename minus its ``.tess`` extension
    (e.g. ``sahidica.mark`` for ``sahidica.mark.tess``). Returns ``None`` if
    the cache file does not exist or does not contain ``ref`` -- callers
    should fall back to runtime bound-group tokenization in that case.
    """
    cache = _load_tess_lemma_cache(tess_basename)
    if not cache:
        return None
    entry = cache.get(ref)
    if not entry:
        return None
    tokens = entry.get('tokens')
    lemmas = entry.get('lemmas')
    if not tokens or not lemmas or len(tokens) != len(lemmas):
        return None
    return list(tokens), list(lemmas)

# Mapping from legacy "Greek and Coptic" block (U+03E2-03EF) to primary Coptic block (U+2C80-2CFF)
_LEGACY_TO_COPTIC = {
    '\u03E2': '\u2CB2',  # Shei
    '\u03E3': '\u2CB3',
    '\u03E4': '\u2CB4',  # Fei
    '\u03E5': '\u2CB5',
    '\u03E6': '\u2CB6',  # Khei
    '\u03E7': '\u2CB7',
    '\u03E8': '\u2CB8',  # Hori
    '\u03E9': '\u2CB9',
    '\u03EA': '\u2CBA',  # Gangia
    '\u03EB': '\u2CBB',
    '\u03EC': '\u2CBC',  # Shima
    '\u03ED': '\u2CBD',
    '\u03EE': '\u2CBE',  # Dei
    '\u03EF': '\u2CBF',
}


def _get_lemma_table():
    """Lazy-load the Coptic lemma lookup table (built from SCRIPTORIUM annotations)."""
    global _coptic_lemma_table
    if _coptic_lemma_table is None:
        table_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            'data', 'lemma_tables', 'coptic_lemmas.json'
        )
        if os.path.exists(table_path):
            with open(table_path, 'r', encoding='utf-8') as f:
                _coptic_lemma_table = json.load(f)
            logger.info(f'Coptic lemma table loaded: {len(_coptic_lemma_table)} entries')
        else:
            _coptic_lemma_table = {}
            logger.warning(f'Coptic lemma table not found at {table_path}')
    return _coptic_lemma_table


def normalize_coptic(text):
    """Normalize Coptic text for consistent matching.

    - NFC normalization
    - Map legacy Unicode block characters to primary Coptic block
    - Strip supralinear stroke (combining overline U+0305 and others)
    - Strip other combining marks (U+0300-U+036F range, except those meaningful for Coptic)
    - Lowercase
    """
    # NFC first
    text = unicodedata.normalize('NFC', text)
    # Map legacy block characters
    for legacy, primary in _LEGACY_TO_COPTIC.items():
        text = text.replace(legacy, primary)
    # Strip combining overline (supralinear stroke) and other combining marks
    # U+0305 = combining overline, U+035E = combining double macron
    # Also strip general combining diacriticals that appear in some digitizations
    text = re.sub(r'[\u0300-\u036F]', '', text)
    # Lowercase (Coptic Unicode has case distinction even though manuscripts don't)
    text = text.lower()
    return text


def tokenize_coptic(text, preserve_case=False):
    """Tokenize Coptic text into words.

    Returns (original_tokens, normalized_tokens) matching the pattern
    used by other language handlers.
    """
    # Remove .tess reference tags if present
    text = re.sub(r'<[^>]+>', '', text).strip()
    if not text:
        return [], []

    # Coptic Unicode blocks:
    # U+2C80-U+2CFF (primary Coptic block)
    # U+03E2-U+03EF (legacy, in Greek and Coptic block)
    # U+0300-U+036F (combining marks, for supralinear strokes)
    # Also catch Coptic fraction/number characters
    tokens = re.findall(
        r'[\u2C80-\u2CFF\u03E2-\u03EF\u0300-\u036F]+',
        text
    )

    original_tokens = list(tokens)
    normalized = [normalize_coptic(t) for t in tokens]
    # Filter out empty tokens
    pairs = [(o, n) for o, n in zip(original_tokens, normalized) if n.strip()]
    if pairs:
        original_tokens, normalized = zip(*pairs)
        return list(original_tokens), list(normalized)
    return [], []


def lemmatize_coptic(tokens):
    """Lemmatize Coptic tokens using the pre-built lookup table.

    The table is built from Coptic SCRIPTORIUM CoNLL-U annotations.
    No Stanza model exists for Coptic, so tokens not in the table
    fall back to their normalized form.
    """
    if not tokens:
        return []

    table = _get_lemma_table()
    lemmas = []
    for token in tokens:
        normalized = normalize_coptic(token)
        if normalized in table:
            lemmas.append(table[normalized])
        else:
            lemmas.append(normalized)
    return lemmas


def get_pos_tags(tokens, language='cop'):
    """Get POS tags for Coptic tokens.

    Without Stanza or a runtime NLP pipeline, returns 'UNK' for all tokens.
    POS data is available in the SCRIPTORIUM annotations but would need
    to be pre-loaded similarly to the lemma table.
    """
    return ['UNK'] * len(tokens)


class CopticLanguageHandler:
    """Language handler registered with text_processor's language registry.

    Provides the interface expected by the registry:
    - tokenize_and_lemmatize(text) -> (original_tokens, tokens, lemmas, pos_tags)
    - tokenize(text) -> (original_tokens, normalized_tokens)
    - lemmatize(tokens) -> lemmas
    - get_pos_tags(tokens) -> pos_tags
    - split_into_phrases(text) -> list of phrases
    - ends_sentence(text) -> bool
    """

    def tokenize_and_lemmatize(self, text):
        """Full pipeline: tokenize, lemmatize, POS tag."""
        original_tokens, tokens = tokenize_coptic(text)
        lemmas = lemmatize_coptic(tokens)
        pos_tags = get_pos_tags(tokens)
        return original_tokens, tokens, lemmas, pos_tags

    def tokenize(self, text, preserve_case=False):
        return tokenize_coptic(text, preserve_case)

    def lemmatize(self, tokens):
        return lemmatize_coptic(tokens)

    def get_pos_tags(self, tokens):
        return get_pos_tags(tokens)

    def lemmatize_word(self, word):
        """Lemmatize a single word."""
        lemmas = lemmatize_coptic([word])
        return lemmas[0] if lemmas else normalize_coptic(word)

    def split_into_phrases(self, text):
        """Split Coptic text into phrases on sentence-ending punctuation.

        Coptic manuscripts use various punctuation marks including
        middle dot, dicolon, and standard period.
        """
        phrases = re.split(r'[.·:;]', text)
        return [p.strip() for p in phrases if p.strip() and len(p.strip().split()) >= 2]

    def ends_sentence(self, text):
        """Check if text ends with sentence-ending punctuation."""
        text = text.rstrip()
        if not text:
            return False
        return text[-1] in '.·:;'
