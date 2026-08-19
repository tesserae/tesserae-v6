"""
Arabic text processing for Tesserae V6.

Provides tokenization, normalization, and lemmatization for Arabic text.
Uses Stanza for morphological analysis (tokenization, MWT expansion, lemmatization, POS).

Key Arabic-specific processing:
- Diacritics (tashkeel) stripping for consistent matching
- Alif variant normalization (أ إ آ ٱ → ا)
- Taa marbuta normalization (ة → ه at end of word, kept for now)
- Stanza handles clitic segmentation via MWT (multi-word token) expansion
"""

import re
import unicodedata
from backend.logging_config import get_logger

logger = get_logger('arabic.processor')

def _plugin_use_gpu():
    """Use the GPU for Stanza when available (index-build pod); CPU on Marvin.
    Override with TESSERAE_STANZA_GPU=0/1."""
    import os
    v = os.environ.get('TESSERAE_STANZA_GPU')
    if v is not None:
        return v == '1'
    try:
        import torch
        return torch.cuda.is_available()
    except Exception:
        return False


# Stanza pipeline - lazy loaded
_stanza_nlp = None


def _get_stanza():
    """Lazy-load the Stanza Arabic pipeline."""
    global _stanza_nlp
    if _stanza_nlp is None:
        import stanza
        _stanza_nlp = stanza.Pipeline(
            'ar',
            processors='tokenize,mwt,lemma,pos',
            verbose=False,
            use_gpu=_plugin_use_gpu(),
        )
        logger.info('Stanza Arabic pipeline loaded')
    return _stanza_nlp


def normalize_arabic(text):
    """Normalize Arabic text for consistent matching.

    - Strip tashkeel (diacritics / vowel marks)
    - Normalize alif variants to bare alif
    - Normalize alif maqsura to ya
    - Strip tatweel (kashida)
    """
    # Strip tashkeel (Arabic diacritics: fathatan through sukun)
    text = re.sub(r'[\u0617-\u061A\u064B-\u0652\u0670]', '', text)
    # Normalize alif variants: أ إ آ ٱ → ا
    text = re.sub(r'[أإآٱ]', 'ا', text)
    # Normalize alif maqsura → ya  (ى → ي)
    text = text.replace('ى', 'ي')
    # Strip tatweel/kashida (ـ)
    text = text.replace('\u0640', '')
    return text


def tokenize_arabic(text, preserve_case=False):
    """Tokenize Arabic text into words.

    Returns (original_tokens, normalized_tokens) matching the pattern
    used by tokenize_latin/tokenize_greek in text_processor.py.
    """
    # Remove .tess reference tags if present
    text = re.sub(r'<[^>]+>', '', text).strip()
    if not text:
        return [], []

    # Split on whitespace and punctuation, keeping Arabic script
    # Arabic Unicode blocks: \u0600-\u06FF, \u0750-\u077F, \u08A0-\u08FF
    tokens = re.findall(r'[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF]+', text)

    original_tokens = list(tokens)
    normalized = [normalize_arabic(t) for t in tokens]

    return original_tokens, normalized


def lemmatize_arabic(tokens):
    """Lemmatize Arabic tokens using Stanza.

    Returns list of lemmas (one per token). Lemmas are normalized
    (diacritics stripped) for consistent matching.
    """
    if not tokens:
        return []

    try:
        nlp = _get_stanza()
        # Join tokens into text for Stanza processing
        text = ' '.join(tokens)
        doc = nlp(text)

        # Map Stanza words back to our input tokens.
        # Stanza may split tokens differently (MWT expansion),
        # so we collect all lemmas and try to align.
        stanza_words = []
        for sent in doc.sentences:
            for word in sent.words:
                stanza_words.append(word)

        # Simple alignment: if Stanza produces same count, 1:1 map.
        # Otherwise, map by position in text.
        if len(stanza_words) == len(tokens):
            lemmas = [normalize_arabic(w.lemma) if w.lemma else normalize_arabic(tokens[i])
                      for i, w in enumerate(stanza_words)]
        else:
            # Stanza split differently (MWT expansion etc.)
            # Build a mapping from character offset to lemma
            lemma_map = {}
            for w in stanza_words:
                if w.start_char is not None:
                    lemma_map[w.start_char] = normalize_arabic(w.lemma) if w.lemma else ''

            # Map each of our tokens to the nearest Stanza word
            lemmas = []
            pos = 0
            for token in tokens:
                # Find this token in the joined text
                idx = text.find(token, pos)
                if idx >= 0 and idx in lemma_map:
                    lemmas.append(lemma_map[idx])
                    pos = idx + len(token)
                elif stanza_words:
                    # Fallback: use normalized form
                    lemmas.append(normalize_arabic(token))
                else:
                    lemmas.append(normalize_arabic(token))

        return lemmas

    except Exception as e:
        logger.warning(f'Stanza lemmatization failed, using normalized forms: {e}')
        return [normalize_arabic(t) for t in tokens]


def get_pos_tags(tokens, language='ar'):
    """Get POS tags for Arabic tokens using Stanza."""
    if not tokens:
        return []

    try:
        nlp = _get_stanza()
        text = ' '.join(tokens)
        doc = nlp(text)

        tags = []
        for sent in doc.sentences:
            for word in sent.words:
                tags.append(word.upos or 'UNK')

        # Align to input token count
        if len(tags) == len(tokens):
            return tags
        elif len(tags) > len(tokens):
            return tags[:len(tokens)]
        else:
            return tags + ['UNK'] * (len(tokens) - len(tags))

    except Exception:
        return ['UNK'] * len(tokens)


class ArabicLanguageHandler:
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
        original_tokens, tokens = tokenize_arabic(text)
        lemmas = lemmatize_arabic(tokens)
        pos_tags = get_pos_tags(tokens)
        return original_tokens, tokens, lemmas, pos_tags

    def tokenize(self, text, preserve_case=False):
        return tokenize_arabic(text, preserve_case)

    def lemmatize(self, tokens):
        return lemmatize_arabic(tokens)

    def get_pos_tags(self, tokens):
        return get_pos_tags(tokens)

    def lemmatize_word(self, word):
        """Lemmatize a single word. Used by process_line/lemmatize_single_word."""
        lemmas = lemmatize_arabic([word])
        return lemmas[0] if lemmas else normalize_arabic(word)

    def split_into_phrases(self, text):
        """Split Arabic text into phrases on sentence-ending punctuation."""
        # Arabic uses period, question mark, exclamation; also ؟ (Arabic question mark)
        phrases = re.split(r'[.؟?!]', text)
        return [p.strip() for p in phrases if p.strip() and len(p.strip().split()) >= 2]

    def ends_sentence(self, text):
        """Check if text ends with Arabic sentence-ending punctuation."""
        text = text.rstrip()
        if not text:
            return False
        return text[-1] in '.؟?!'
