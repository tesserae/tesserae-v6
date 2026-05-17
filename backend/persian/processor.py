"""
Persian text processing for Tesserae V6.

Uses Stanza for morphological analysis. Persian uses Arabic script plus
4 extra letters (pe, che, zhe, gaf). Morphology is concatenative (Indo-European),
simpler than Arabic's root-and-pattern system.

Key Persian-specific processing:
- Diacritics (tashkeel) stripping (same as Arabic)
- Persian ya/kaf normalization (U+06CC -> U+064A, U+06A9 -> U+0643)
- Half-space (ZWNJ, U+200C) removal for matching
- Alif variant normalization
"""

import re
import unicodedata
from backend.logging_config import get_logger

logger = get_logger('persian.processor')

_stanza_nlp = None


def _get_stanza():
    """Lazy-load the Stanza Persian pipeline."""
    global _stanza_nlp
    if _stanza_nlp is None:
        import stanza
        _stanza_nlp = stanza.Pipeline(
            'fa',
            processors='tokenize,lemma,pos',
            verbose=False,
            use_gpu=False,
        )
        logger.info('Stanza Persian pipeline loaded')
    return _stanza_nlp


def normalize_persian(text):
    """Normalize Persian text for consistent matching.

    - Strip tashkeel (diacritics / vowel marks)
    - Normalize alif variants to bare alif
    - Normalize Persian ya (U+06CC) to Arabic ya (U+064A) for cross-script matching
    - Normalize Persian kaf (U+06A9) to Arabic kaf (U+0643)
    - Remove half-space (ZWNJ, U+200C)
    - Strip tatweel/kashida
    """
    # Strip tashkeel
    text = re.sub(r'[\u0617-\u061A\u064B-\u0652\u0670]', '', text)
    # Normalize alif variants
    text = re.sub(r'[أإآٱ]', 'ا', text)
    # Normalize Persian ya -> Arabic ya
    text = text.replace('\u06CC', '\u064A')
    # Normalize alif maqsura -> ya
    text = text.replace('ى', 'ي')
    # Normalize Persian kaf -> Arabic kaf
    text = text.replace('\u06A9', '\u0643')
    # Remove half-space (ZWNJ)
    text = text.replace('\u200C', '')
    # Strip tatweel
    text = text.replace('\u0640', '')
    return text


def tokenize_persian(text, preserve_case=False):
    """Tokenize Persian text into words."""
    text = re.sub(r'<[^>]+>', '', text).strip()
    if not text:
        return [], []

    # Persian uses Arabic script block + extra letters (pe, che, zhe, gaf)
    # All within U+0600-U+06FF. Also catch U+200C (half-space) within words.
    tokens = re.findall(r'[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\u200C]+', text)

    original_tokens = list(tokens)
    normalized = [normalize_persian(t) for t in tokens]

    return original_tokens, normalized


def lemmatize_persian(tokens):
    """Lemmatize Persian tokens using Stanza."""
    if not tokens:
        return []

    try:
        nlp = _get_stanza()
        text = ' '.join(tokens)
        doc = nlp(text)

        stanza_words = []
        for sent in doc.sentences:
            for word in sent.words:
                stanza_words.append(word)

        if len(stanza_words) == len(tokens):
            lemmas = [normalize_persian(w.lemma) if w.lemma else normalize_persian(tokens[i])
                      for i, w in enumerate(stanza_words)]
        else:
            lemma_map = {}
            for w in stanza_words:
                if w.start_char is not None:
                    lemma_map[w.start_char] = normalize_persian(w.lemma) if w.lemma else ''

            lemmas = []
            pos = 0
            for token in tokens:
                idx = text.find(token, pos)
                if idx >= 0 and idx in lemma_map:
                    lemmas.append(lemma_map[idx])
                    pos = idx + len(token)
                else:
                    lemmas.append(normalize_persian(token))

        return lemmas

    except Exception as e:
        logger.warning(f'Stanza lemmatization failed, using normalized forms: {e}')
        return [normalize_persian(t) for t in tokens]


def get_pos_tags(tokens, language='fa'):
    """Get POS tags for Persian tokens using Stanza."""
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

        if len(tags) == len(tokens):
            return tags
        elif len(tags) > len(tokens):
            return tags[:len(tokens)]
        else:
            return tags + ['UNK'] * (len(tokens) - len(tags))

    except Exception:
        return ['UNK'] * len(tokens)


class PersianLanguageHandler:
    """Language handler registered with text_processor's language registry."""

    def tokenize_and_lemmatize(self, text):
        original_tokens, tokens = tokenize_persian(text)
        lemmas = lemmatize_persian(tokens)
        pos_tags = get_pos_tags(tokens)
        return original_tokens, tokens, lemmas, pos_tags

    def tokenize(self, text, preserve_case=False):
        return tokenize_persian(text, preserve_case)

    def lemmatize(self, tokens):
        return lemmatize_persian(tokens)

    def get_pos_tags(self, tokens):
        return get_pos_tags(tokens)

    def lemmatize_word(self, word):
        lemmas = lemmatize_persian([word])
        return lemmas[0] if lemmas else normalize_persian(word)

    def split_into_phrases(self, text):
        phrases = re.split(r'[.؟?!]', text)
        return [p.strip() for p in phrases if p.strip() and len(p.strip().split()) >= 2]

    def ends_sentence(self, text):
        text = text.rstrip()
        if not text:
            return False
        return text[-1] in '.؟?!'
