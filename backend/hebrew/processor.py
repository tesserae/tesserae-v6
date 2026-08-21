"""
Hebrew text processing for Tesserae V6.

Provides tokenization, normalization, and lemmatization for Hebrew text.
Uses a two-tier lemmatization system:
1. Primary: BHSA lookup table (data/lemma_tables/hebrew_lemmas.json)
2. Fallback: Stanza Hebrew pipeline (Modern Hebrew model, less accurate on Biblical)

Key Hebrew-specific processing:
- Nikkud (vowel points) stripping for consistent matching
- Cantillation marks (te'amim) stripping
- Sin/shin dot handling
- Unicode NFC normalization
"""

import json
import os
import re
import unicodedata
from backend.logging_config import get_logger

logger = get_logger('hebrew.processor')

# Stanza pipeline - lazy loaded
_stanza_nlp = None

# BHSA lemma lookup table - lazy loaded
_hebrew_lemma_table = None


def _get_lemma_table():
    """Lazy-load the BHSA Hebrew lemma lookup table."""
    global _hebrew_lemma_table
    if _hebrew_lemma_table is None:
        table_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            'data', 'lemma_tables', 'hebrew_lemmas.json'
        )
        if os.path.exists(table_path):
            with open(table_path, 'r', encoding='utf-8') as f:
                _hebrew_lemma_table = json.load(f)
            logger.info(f'Hebrew lemma table loaded: {len(_hebrew_lemma_table)} entries')
        else:
            _hebrew_lemma_table = {}
            logger.warning(f'Hebrew lemma table not found at {table_path}')
    return _hebrew_lemma_table


def _get_stanza():
    """Lazy-load the Stanza Hebrew pipeline."""
    global _stanza_nlp
    if _stanza_nlp is None:
        import stanza
        try:
            _stanza_nlp = stanza.Pipeline(
                'he',
                processors='tokenize,mwt,lemma,pos',
                verbose=False,
                use_gpu=False,
            )
            logger.info('Stanza Hebrew pipeline loaded')
        except Exception as e:
            logger.warning(f'Stanza Hebrew pipeline failed to load: {e}')
            _stanza_nlp = False  # sentinel to avoid repeated attempts
    return _stanza_nlp if _stanza_nlp is not False else None


def normalize_hebrew(text):
    """Normalize Hebrew text for consistent matching.

    - Strip nikkud (vowel points) and cantillation marks (te'amim)
    - Strip maqaf (Hebrew hyphen)
    - Unicode NFC normalization
    """
    # NFC first so composed forms are handled consistently
    text = unicodedata.normalize('NFC', text)
    # Strip nikkud (U+0591-U+05BD, U+05BF-U+05C7) - vowel points and cantillation
    text = re.sub(r'[\u0591-\u05BD\u05BF-\u05C7]', '', text)
    # Strip maqaf (Hebrew hyphen U+05BE) - treat hyphenated words as separate
    text = text.replace('\u05BE', ' ')
    # Strip sof pasuq (U+05C3) and other punctuation marks
    text = text.replace('\u05C3', '')
    return text


def tokenize_hebrew(text, preserve_case=False):
    """Tokenize Hebrew text into words.

    Returns (original_tokens, normalized_tokens) matching the pattern
    used by other language handlers.
    """
    # Remove .tess reference tags if present
    text = re.sub(r'<[^>]+>', '', text)
    # Remove Masoretic paragraph markers {פ}/{ס} (petuchah/setumah) that some
    # digitizations (e.g. Sefaria) include inline; otherwise they tokenize as
    # spurious single-letter words.
    text = re.sub(r'\{[^}]*\}', ' ', text)
    # Split on maqaf (U+05BE, the Hebrew hyphen). It lives inside the Hebrew Unicode
    # block, so without this the token regex fuses maqaf-joined words (e.g. \u05D0\u05EA\u05BE\u05DB\u05DC,
    # \u05D1\u05E0\u05D9\u05BE\u05D9\u05E9\u05E8\u05D0\u05DC) into one token \u2014 ~7% of biblical tokens \u2014 breaking lexical matching.
    text = text.replace('\u05BE', ' ').strip()
    if not text:
        return [], []

    # Hebrew Unicode block: U+0590-U+05FF (Hebrew), U+FB1D-U+FB4F (Hebrew presentation forms)
    tokens = re.findall(r'[\u0590-\u05FF\uFB1D-\uFB4F]+', text)

    original_tokens = list(tokens)
    normalized = [normalize_hebrew(t) for t in tokens]
    # Filter out empty tokens (can happen after stripping all diacritics from a pure-nikkud token)
    pairs = [(o, n) for o, n in zip(original_tokens, normalized) if n.strip()]
    if pairs:
        original_tokens, normalized = zip(*pairs)
        return list(original_tokens), list(normalized)
    return [], []


# Hebrew proclitic letters (conjunction waw, article he, and the inseparable
# prepositions be/ke/le/me, plus relative she) that BHSA stores as SEPARATE
# morphemes. Biblical surface tokens fuse them (e.g. ויאמר = ו + יאמר,
# בארץ = ב + ארץ), so on a direct table miss we strip 1-3 leading clitic letters
# and retry the lookup against the BHSA table before falling back to Stanza.
_HE_PREFIX = set('והבכלמש')


def _lookup_lemma(form, table):
    """Table lookup with Hebrew clitic-prefix stripping on a miss."""
    if form in table:
        return table[form]
    for k in (1, 2, 3):
        if len(form) > k + 1 and all(c in _HE_PREFIX for c in form[:k]):
            rest = form[k:]
            if rest in table:
                return table[rest]
    return None


def lemmatize_hebrew(tokens):
    """Lemmatize Hebrew tokens using BHSA table with Stanza fallback.

    Returns list of lemmas (one per token). Lemmas are normalized
    (nikkud stripped) for consistent matching.
    """
    if not tokens:
        return []

    table = _get_lemma_table()
    lemmas = []

    # Tokens that need Stanza fallback
    stanza_needed = []
    stanza_indices = []

    for i, token in enumerate(tokens):
        normalized = normalize_hebrew(token)
        lemma = _lookup_lemma(normalized, table)
        if lemma is not None:
            lemmas.append(lemma)
        else:
            lemmas.append(None)  # placeholder
            stanza_needed.append(normalized)
            stanza_indices.append(i)

    # Stanza fallback for tokens not in BHSA table
    if stanza_needed:
        nlp = _get_stanza()
        if nlp:
            try:
                text = ' '.join(stanza_needed)
                doc = nlp(text)
                stanza_lemmas = []
                for sent in doc.sentences:
                    for word in sent.words:
                        stanza_lemmas.append(
                            normalize_hebrew(word.lemma) if word.lemma else normalize_hebrew(word.text)
                        )

                # Align Stanza output back to our indices
                for j, idx in enumerate(stanza_indices):
                    if j < len(stanza_lemmas):
                        lemmas[idx] = stanza_lemmas[j]
                    else:
                        lemmas[idx] = normalize_hebrew(tokens[idx])
            except Exception as e:
                logger.warning(f'Stanza fallback failed: {e}')
                for idx in stanza_indices:
                    lemmas[idx] = normalize_hebrew(tokens[idx])
        else:
            # No Stanza available - use normalized form
            for idx in stanza_indices:
                lemmas[idx] = normalize_hebrew(tokens[idx])

    # Ensure no None values remain
    return [l if l is not None else normalize_hebrew(tokens[i]) for i, l in enumerate(lemmas)]


def get_pos_tags(tokens, language='he'):
    """Get POS tags for Hebrew tokens using Stanza."""
    if not tokens:
        return []

    nlp = _get_stanza()
    if not nlp:
        return ['UNK'] * len(tokens)

    try:
        text = ' '.join(tokens)
        doc = nlp(text)

        tags = []
        for sent in doc.sentences:
            for word in sent.words:
                tags.append(word.upos or 'UNK')

        if len(tags) == len(tokens):
            return tags
        elif len(tags) > len(tokens):
            return tags[:len(tokens)]
        else:
            return tags + ['UNK'] * (len(tokens) - len(tags))

    except Exception:
        return ['UNK'] * len(tokens)


class HebrewLanguageHandler:
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
        original_tokens, tokens = tokenize_hebrew(text)
        lemmas = lemmatize_hebrew(tokens)
        pos_tags = get_pos_tags(tokens)
        return original_tokens, tokens, lemmas, pos_tags

    def tokenize(self, text, preserve_case=False):
        return tokenize_hebrew(text, preserve_case)

    def lemmatize(self, tokens):
        return lemmatize_hebrew(tokens)

    def get_pos_tags(self, tokens):
        return get_pos_tags(tokens)

    def lemmatize_word(self, word):
        """Lemmatize a single word. Used by process_line/lemmatize_single_word."""
        lemmas = lemmatize_hebrew([word])
        return lemmas[0] if lemmas else normalize_hebrew(word)

    def split_into_phrases(self, text):
        """Split Hebrew text into phrases on sentence-ending punctuation.

        Biblical Hebrew uses sof pasuq (U+05C3) as verse/sentence end,
        plus standard punctuation.
        """
        # Sof pasuq is stripped in normalization, so split on standard punct
        # and also treat the original sof pasuq as a boundary
        phrases = re.split(r'[\u05C3.?!:]', text)
        return [p.strip() for p in phrases if p.strip() and len(p.strip().split()) >= 2]

    def ends_sentence(self, text):
        """Check if text ends with sentence-ending punctuation."""
        text = text.rstrip()
        if not text:
            return False
        return text[-1] in '.\u05C3?!:'
