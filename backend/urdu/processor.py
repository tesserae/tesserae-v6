"""
Urdu text processing for Tesserae V6.

Uses Stanza for morphological analysis. Urdu uses Arabic script (Nastaliq style)
with additional letters for retroflex consonants and other Indo-Aryan sounds.
Shares normalization patterns with Persian (both use Arabic script with extensions).

Key Urdu-specific processing:
- Diacritics (tashkeel/zabar/zer/pesh) stripping
- Alif variant normalization (same as Arabic/Persian)
- Persian ya/kaf normalization (same as Persian)
- Half-space (ZWNJ) removal
- Urdu-specific letters: ٹ ڈ ڑ ں ے ھ (all in U+0600-U+06FF range)
"""

import re
import unicodedata
from backend.logging_config import get_logger

logger = get_logger('urdu.processor')

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


_stanza_nlp = None


def _get_stanza():
    """Lazy-load the Stanza Urdu pipeline."""
    global _stanza_nlp
    if _stanza_nlp is None:
        import stanza
        try:
            _stanza_nlp = stanza.Pipeline(
                'ur',
                processors='tokenize,lemma,pos',
                verbose=False,
                use_gpu=_plugin_use_gpu(),
            )
            logger.info('Stanza Urdu pipeline loaded')
        except Exception as e:
            logger.warning(f'Stanza Urdu pipeline failed to load: {e}')
            _stanza_nlp = False
    return _stanza_nlp if _stanza_nlp is not False else None


def normalize_urdu(text):
    """Normalize Urdu text for consistent matching.

    - Strip tashkeel (diacritics / vowel marks)
    - Normalize alif variants to bare alif
    - Normalize Persian/Urdu ya (U+06CC) to Arabic ya (U+064A)
    - Normalize Persian/Urdu kaf (U+06A9) to Arabic kaf (U+0643)
    - Remove half-space (ZWNJ, U+200C)
    - Strip tatweel/kashida
    """
    # Strip tashkeel
    text = re.sub(r'[\u0617-\u061A\u064B-\u0652\u0670]', '', text)
    # Normalize alif variants
    text = re.sub(r'[أإآٱ]', 'ا', text)
    # Normalize ya variants
    text = text.replace('\u06CC', '\u064A')  # Persian/Urdu ya -> Arabic ya
    text = text.replace('ى', 'ي')             # Alif maqsura -> ya
    # Normalize kaf
    text = text.replace('\u06A9', '\u0643')   # Persian/Urdu kaf -> Arabic kaf
    # Remove half-space (ZWNJ)
    text = text.replace('\u200C', '')
    # Strip tatweel
    text = text.replace('\u0640', '')
    return text


def tokenize_urdu(text, preserve_case=False):
    """Tokenize Urdu text into words."""
    text = re.sub(r'<[^>]+>', '', text).strip()
    if not text:
        return [], []

    # Urdu uses Arabic script plus extra letters (retroflex ٹ ڈ ڑ, nasal ں, ye ے, he ھ)
    # All within U+0600-U+06FF. Also include U+200C (half-space) within words.
    tokens = re.findall(r'[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\u200C]+', text)

    original_tokens = list(tokens)
    normalized = [normalize_urdu(t) for t in tokens]

    return original_tokens, normalized


def lemmatize_urdu(tokens):
    """Lemmatize Urdu tokens using Stanza."""
    if not tokens:
        return []

    nlp = _get_stanza()
    if not nlp:
        return [normalize_urdu(t) for t in tokens]

    try:
        text = ' '.join(tokens)
        doc = nlp(text)

        stanza_words = []
        for sent in doc.sentences:
            for word in sent.words:
                stanza_words.append(word)

        if len(stanza_words) == len(tokens):
            lemmas = [normalize_urdu(w.lemma) if w.lemma else normalize_urdu(tokens[i])
                      for i, w in enumerate(stanza_words)]
        else:
            lemma_map = {}
            for w in stanza_words:
                if w.start_char is not None:
                    lemma_map[w.start_char] = normalize_urdu(w.lemma) if w.lemma else ''

            lemmas = []
            pos = 0
            for token in tokens:
                idx = text.find(token, pos)
                if idx >= 0 and idx in lemma_map:
                    lemmas.append(lemma_map[idx])
                    pos = idx + len(token)
                else:
                    lemmas.append(normalize_urdu(token))

        return lemmas

    except Exception as e:
        logger.warning(f'Stanza lemmatization failed, using normalized forms: {e}')
        return [normalize_urdu(t) for t in tokens]


def get_pos_tags(tokens, language='ur'):
    """Get POS tags for Urdu tokens using Stanza."""
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


class UrduLanguageHandler:
    """Language handler registered with text_processor's language registry."""

    def tokenize_and_lemmatize(self, text):
        original_tokens, tokens = tokenize_urdu(text)
        lemmas = lemmatize_urdu(tokens)
        pos_tags = get_pos_tags(tokens)
        return original_tokens, tokens, lemmas, pos_tags

    def tokenize(self, text, preserve_case=False):
        return tokenize_urdu(text, preserve_case)

    def lemmatize(self, tokens):
        return lemmatize_urdu(tokens)

    def get_pos_tags(self, tokens):
        return get_pos_tags(tokens)

    def lemmatize_word(self, word):
        lemmas = lemmatize_urdu([word])
        return lemmas[0] if lemmas else normalize_urdu(word)

    def split_into_phrases(self, text):
        # Urdu uses period, question mark (standard and Arabic ؟), exclamation
        phrases = re.split(r'[.؟?!۔]', text)
        return [p.strip() for p in phrases if p.strip() and len(p.strip().split()) >= 2]

    def ends_sentence(self, text):
        text = text.rstrip()
        if not text:
            return False
        return text[-1] in '.؟?!۔'
