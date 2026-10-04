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
- Urdu-specific letters: retroflex/nasal/ye/he (all in U+0600-U+06FF range)
- Hemistich ('|') boundary preservation -- see tokenize_urdu docstring (gap A6).
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
    text = re.sub(r'[ؗ-ًؚ-ْٰ]', '', text)
    # Normalize alif variants
    text = re.sub(r'[أإآٱ]', 'ا', text)
    # Normalize ya variants
    text = text.replace('ی', 'ي')  # Persian/Urdu ya -> Arabic ya
    text = text.replace('ى', 'ي')  # Alif maqsura -> ya
    # Normalize kaf
    text = text.replace('ک', 'ك')  # Persian/Urdu kaf -> Arabic kaf
    # Remove half-space (ZWNJ)
    text = text.replace('‌', '')
    # Strip tatweel
    text = text.replace('ـ', '')
    return text


# Urdu uses Arabic script plus extra letters (retroflex, nasal, ye, he) all
# within U+0600-U+06FF, plus the Arabic Supplement / Extended-A ranges, plus
# U+200C (half-space) within words. This regex also matches the literal '|'
# hemistich separator as a SEPARATE alternative (not part of a word run), so
# a single scan finds both words and hemistich boundaries in source order --
# see tokenize_urdu.
# Word runs exclude the block's punctuation (U+0600-060F, U+061B-061F,
# U+066A-066D, U+06D4: ، ؛ ؟ ۔ and their kin) so a mark never rides on a word.
_WORD_OR_PIPE_RE = re.compile(
    r'[\u0610-\u061A\u0620-\u0669\u066E-\u06D3\u06D5-\u06FF\u0750-\u077F\u08A0-\u08FF\u200C]+|\|')


def tokenize_urdu(text, preserve_case=False):
    """Tokenize Urdu text into words.

    Returns (original_tokens, normalized_tokens, hemistich_breaks).

    DESIGN NOTE -- hemistich fix (gap A6, AUDIT_2026-09-03.md #6).

    Urdu couplets (shers) are stored one per .tess line as two hemistichs
    (misra) joined by a literal '|': "<mir.diwan.1.1>  misra1 | misra2".
    A ghazal's RADIF (the refrain word repeated at the end of every rhyming
    line) and QAFIA (rhyme) sit at the end of EACH hemistich, so the position
    that poetics analysis needs most is exactly the word immediately before
    '|' and the word at the end of the line. The previous tokenizer matched
    only Arabic-script runs, so '|' fell outside every match and was dropped
    with no trace -- the two hemistichs became one undifferentiated token
    run and the boundary was unrecoverable from the stored tokens (confirmed
    against the live ur_index.db by the audit).

    Fix: scan for word-runs and the literal '|' in ONE pass, in source order.
    Only the word-runs are emitted as tokens -- a '|' is never emitted as a
    token itself, so it never lemmatizes, sound-trigrams, edit-distances, or
    doc-frequency-counts as if it were a real word (that would have polluted
    every language-agnostic channel). Instead each '|' seen is recorded as a
    hemistich break AFTER the most recently emitted token, in a separate
    `hemistich_breaks` list returned alongside tokens/original_tokens:
    hemistich_breaks[i] is a 0-based index into `tokens` (and
    `original_tokens`) such that tokens[hemistich_breaks[i]] is the LAST WORD
    OF A HEMISTICH (the word immediately followed by '|' in the source). The
    final word of the whole line is simply tokens[-1] -- already recoverable,
    unchanged.

    A line with no '|' (e.g. both Ghalib editions, which are one hemistich
    per .tess line already) returns an empty hemistich_breaks list --
    behavior for those files is unchanged.

    This makes both of the positions radif/qafia detection needs recoverable
    from the token stream:
      - end of first hemistich:  tokens[hemistich_breaks[0]]
      - end of the line:         tokens[-1]
    without ever inserting a pseudo-word into the arrays the matcher scores.
    """
    text = re.sub(r'<[^>]+>', '', text).strip()
    if not text:
        return [], [], []

    tokens = []
    hemistich_breaks = []
    for m in _WORD_OR_PIPE_RE.finditer(text):
        piece = m.group(0)
        if piece == '|':
            if tokens:
                hemistich_breaks.append(len(tokens) - 1)
        else:
            tokens.append(piece)

    original_tokens = list(tokens)
    normalized = [normalize_urdu(t) for t in tokens]

    return original_tokens, normalized, hemistich_breaks


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


def lemmatize_and_tag_urdu(tokens):
    """Lemmatize and POS-tag Urdu tokens in a SINGLE Stanza call.

    PERF FIX (2026-09-03, index-build phase): lemmatize_urdu() and
    get_pos_tags() each independently called nlp(text) on the same input,
    doubling every build's runtime for no benefit -- Stanza returns lemma
    and upos on the same Word object in one pass. tokenize_and_lemmatize()
    is the hot path used by every corpus build and live search, so it now
    calls this instead. lemmatize_urdu()/get_pos_tags() are left as-is for
    any other caller that only wants one piece.
    """
    if not tokens:
        return [], []

    nlp = _get_stanza()
    if not nlp:
        return [normalize_urdu(t) for t in tokens], ['UNK'] * len(tokens)

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
            tags = [w.upos or 'UNK' for w in stanza_words]
        else:
            lemma_map = {}
            tag_map = {}
            for w in stanza_words:
                if w.start_char is not None:
                    lemma_map[w.start_char] = normalize_urdu(w.lemma) if w.lemma else ''
                    tag_map[w.start_char] = w.upos or 'UNK'

            lemmas = []
            tags = []
            pos = 0
            for token in tokens:
                idx = text.find(token, pos)
                if idx >= 0 and idx in lemma_map:
                    lemmas.append(lemma_map[idx])
                    tags.append(tag_map.get(idx, 'UNK'))
                    pos = idx + len(token)
                else:
                    lemmas.append(normalize_urdu(token))
                    tags.append('UNK')

        return lemmas, tags

    except Exception as e:
        logger.warning(f'Stanza lemmatization failed, using normalized forms: {e}')
        return [normalize_urdu(t) for t in tokens], ['UNK'] * len(tokens)


class UrduLanguageHandler:
    """Language handler registered with text_processor's language registry."""

    def tokenize_and_lemmatize(self, text):
        """Full pipeline: tokenize, lemmatize, POS tag. Returns a 6-tuple;
        the 5th element (variant_lemmas) is always empty for Urdu (no
        qere/ketiv-style variant channel); the 6th (hemistich_breaks) carries
        the '|' boundary fix -- see tokenize_urdu."""
        original_tokens, tokens, hemistich_breaks = tokenize_urdu(text)
        lemmas, pos_tags = lemmatize_and_tag_urdu(tokens)
        return original_tokens, tokens, lemmas, pos_tags, [], hemistich_breaks

    def tokenize(self, text, preserve_case=False):
        original_tokens, tokens, _ = tokenize_urdu(text, preserve_case)
        return original_tokens, tokens

    def get_hemistich_breaks(self, text):
        """Return 0-based token indices that are the last word of a
        hemistich (immediately followed by '|' in the source line)."""
        _, _, hemistich_breaks = tokenize_urdu(text)
        return hemistich_breaks

    def lemmatize(self, tokens):
        return lemmatize_urdu(tokens)

    def get_pos_tags(self, tokens):
        return get_pos_tags(tokens)

    def lemmatize_word(self, word):
        lemmas = lemmatize_urdu([word])
        return lemmas[0] if lemmas else normalize_urdu(word)

    def split_into_phrases(self, text):
        # Urdu uses period, question mark (standard and Arabic ؟), exclamation,
        # and the Urdu full stop ۔
        phrases = re.split(r'[.؟?!۔]', text)
        return [p.strip() for p in phrases if p.strip() and len(p.strip().split()) >= 2]

    def ends_sentence(self, text):
        text = text.rstrip()
        if not text:
            return False
        return text[-1] in '.؟?!۔'
