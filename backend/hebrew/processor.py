"""
Hebrew text processing for Tesserae V6.

Provides tokenization, normalization, and lemmatization for Hebrew text.
Uses a two-tier lemmatization system:
1. Primary: BHSA lookup table (data/lemma_tables/hebrew_lemmas.json)
2. Fallback: Stanza Hebrew pipeline (Modern Hebrew model, less accurate on Biblical)
Part-of-speech tags follow the same two tiers, from the BHSA table
data/lemma_tables/hebrew_pos.json.

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

# BHSA lemma and part-of-speech lookup tables - lazy loaded
_hebrew_lemma_table = None
_hebrew_pos_table = None


def _load_table(filename, what):
    table_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        'data', 'lemma_tables', filename
    )
    if os.path.exists(table_path):
        with open(table_path, 'r', encoding='utf-8') as f:
            table = json.load(f)
        logger.info(f'Hebrew {what} table loaded: {len(table)} entries')
        return table
    logger.warning(f'Hebrew {what} table not found at {table_path}')
    return {}


def _get_lemma_table():
    """Lazy-load the BHSA Hebrew lemma lookup table."""
    global _hebrew_lemma_table
    if _hebrew_lemma_table is None:
        _hebrew_lemma_table = _load_table('hebrew_lemmas.json', 'lemma')
    return _hebrew_lemma_table


def _get_pos_table():
    """Lazy-load the BHSA Hebrew part-of-speech lookup table. Its keys are the
    same consonantal forms as the lemma table's; its values are BHSA labels."""
    global _hebrew_pos_table
    if _hebrew_pos_table is None:
        _hebrew_pos_table = _load_table('hebrew_pos.json', 'part-of-speech')
    return _hebrew_pos_table


def _get_stanza():
    """Lazy-load the Stanza Hebrew pipeline.

    Stanza is an OPTIONAL fallback lemmatizer (about 0.1% of tokens are not in
    the BHSA lookup table, mostly rare proper names). If it is not installed (e.g. absent from the production
    environment) or fails to load, Hebrew degrades gracefully to the lookup
    table plus surface forms rather than erroring the search.
    """
    global _stanza_nlp
    if _stanza_nlp is None:
        try:
            import stanza
            _stanza_nlp = stanza.Pipeline(
                'he',
                processors='tokenize,mwt,lemma,pos',
                verbose=False,
                use_gpu=False,
            )
            logger.info('Stanza Hebrew pipeline loaded')
        except Exception as e:
            logger.warning(f'Stanza Hebrew pipeline unavailable ({e}); using lookup table only')
            _stanza_nlp = False  # sentinel to avoid repeated attempts
    return _stanza_nlp if _stanza_nlp is not False else None


# Combining grapheme joiner (U+034F). The pointed text writes Jerusalem as
# יְרוּשָׁלַ͏ִם with a CGJ between the patah and the hiriq so both vowels stay on
# the lamed (562 times in texts/he). It lies outside the Hebrew block, so it
# must be removed before words are split or Jerusalem breaks in two (#480).
_CGJ = '\u034F'


def normalize_hebrew(text):
    """Normalize Hebrew text for consistent matching.

    - Strip nikkud (vowel points) and cantillation marks (te'amim)
    - Strip maqaf (Hebrew hyphen)
    - Unicode NFC normalization
    """
    # NFC first so composed forms are handled consistently
    text = unicodedata.normalize('NFC', text)
    text = text.replace(_CGJ, '')
    # Strip nikkud (U+0591-U+05BD, U+05BF-U+05C7) - vowel points and cantillation
    text = re.sub(r'[\u0591-\u05BD\u05BF-\u05C7]', '', text)
    # Strip maqaf (Hebrew hyphen U+05BE) - treat hyphenated words as separate
    text = text.replace('\u05BE', ' ')
    # Strip sof pasuq (U+05C3) and other punctuation marks
    text = text.replace('\u05C3', '')
    return text


# Hebrew Unicode block: U+0590-U+05FF (Hebrew), U+FB1D-U+FB4F (presentation forms).
_HE_WORD_RE = re.compile(r'[\u0590-\u05FF\uFB1D-\uFB4F]+')
# Qere/ketiv pair, both print orders: "[qere] (ketiv)" or "(ketiv) [qere]". The
# qere (read form) is bracketed and pointed; the ketiv (written consonants) is
# parenthesized. Groups 1/2 = qere/ketiv (first order), groups 3/4 = ketiv/qere.
_QERE_KETIV_RE = re.compile(
    r'\[([^\[\]]+)\]\s*\(([^()]+)\)|\(([^()]+)\)\s*\[([^\[\]]+)\]')


def _he_words(segment):
    """Maqaf-split a segment and return its Hebrew-letter word runs. Maqaf
    (U+05BE) sits in the Hebrew block, so it must be split or maqaf-joined words
    fuse into one token (~7% of biblical tokens)."""
    return _HE_WORD_RE.findall(segment.replace('\u05BE', ' '))


def tokenize_hebrew_with_variants(text):
    """Tokenize Hebrew, keeping the qere reading and recording the ketiv as a
    positional variant.

    Returns (original_tokens, normalized_tokens, variant_forms), all equal
    length. variant_forms[i] is a list of extra normalized surface forms at
    position i: empty for ordinary tokens, and the ketiv word(s) at a qere/ketiv
    pair's first qere position. The caller lemmatizes these so the ketiv lemma is
    indexed at the same position as the qere. The qere reading is kept in the
    token stream so the pair counts once and phrase adjacency runs through it;
    display is unaffected (it comes from the raw line text).
    """
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'\{[^}]*\}', ' ', text)
    text = text.replace(_CGJ, '')

    original, variants = [], []
    last = 0
    for m in _QERE_KETIV_RE.finditer(text):
        for w in _he_words(text[last:m.start()]):
            original.append(w)
            variants.append([])
        if m.group(1) is not None:          # [qere] (ketiv)
            qere, ketiv = m.group(1), m.group(2)
        else:                                # (ketiv) [qere]
            ketiv, qere = m.group(3), m.group(4)
        ketiv_words = _he_words(ketiv)
        for j, w in enumerate(_he_words(qere)):
            original.append(w)
            variants.append(ketiv_words if j == 0 else [])
        last = m.end()
    for w in _he_words(text[last:]):
        original.append(w)
        variants.append([])

    kept_o, kept_n, kept_v = [], [], []
    for o, v in zip(original, variants):
        n = normalize_hebrew(o)
        if n.strip():
            kept_o.append(o)
            kept_n.append(n)
            kept_v.append([vn for vn in (normalize_hebrew(x) for x in v) if vn.strip()])
    return kept_o, kept_n, kept_v


def tokenize_hebrew(text, preserve_case=False):
    """Tokenize Hebrew text into words.

    Returns (original_tokens, normalized_tokens) matching the pattern used by
    other language handlers. Qere/ketiv handling and the variant channel live in
    tokenize_hebrew_with_variants; this wrapper drops the variant channel.
    """
    original_tokens, normalized, _ = tokenize_hebrew_with_variants(text)
    return original_tokens, normalized


# Hebrew proclitic letters (conjunction waw, article he, and the inseparable
# prepositions be/ke/le/me, plus relative she) that BHSA stores as SEPARATE
# morphemes. Biblical surface tokens fuse them (e.g. ויאמר = ו + יאמר,
# בארץ = ב + ארץ), so on a direct table miss we strip 1-3 leading clitic letters
# and retry the lookup against the BHSA table before falling back to Stanza.
_HE_PREFIX = set('והבכלמש')


def _lookup_lemma(form, table):
    """Table lookup with Hebrew clitic-prefix stripping on a miss. Used for
    both the lemma and the part-of-speech table, which share their keys."""
    if form in table:
        return table[form]
    for k in (1, 2, 3):
        if len(form) > k + 1 and all(c in _HE_PREFIX for c in form[:k]):
            rest = form[k:]
            if rest in table:
                return table[rest]
    return None


# Universal POS tags Stanza gives the prefixes (ו, ה, ב/כ/ל/מ, ש) and the
# pronoun suffixes it splits off a word. The stem is the first word of a token
# outside these.
_CLITIC_UPOS = {'ADP', 'CCONJ', 'SCONJ', 'DET', 'PRON'}


# Stanza results per normalized word, so a word gets the same lemma wherever it
# occurs and each distinct word is analysed once per process.
_stanza_cache = {}


def _stanza_word(nlp, word):
    """Stanza's (lemma, upos) for one normalized word, or None when its output
    is not a single token covering the word."""
    if word not in _stanza_cache:
        result = None
        try:
            doc = nlp(word)
            tokens = [t for sent in doc.sentences for t in sent.tokens]
            if len(tokens) == 1 and (tokens[0].start_char, tokens[0].end_char) == (0, len(word)):
                parts = tokens[0].words
                stem = next((w for w in parts if w.upos not in _CLITIC_UPOS), None)
                if stem is None:
                    stem = max(parts, key=lambda w: len(w.text))
                result = (normalize_hebrew(stem.lemma or stem.text), stem.upos or 'UNK')
        except Exception as e:
            logger.warning(f'Stanza fallback failed on {word!r}: {e}')
        _stanza_cache[word] = result
    return _stanza_cache[word]


def _stanza_by_word(words):
    """Run Stanza on each normalized word and return one (lemma, upos) per
    word, or None where Stanza is unavailable or its output cannot be used.

    Stanza splits one word into several syntactic words, prefixes and suffixes
    alike (בירושל → ב + ירושל, קברותיך → קברותי + ך). The missed words of a line
    used to go to Stanza as one string with its words matched to ours one for
    one, so every lemma after the first split landed on the wrong word (#481).
    Each word now goes on its own: the missed words of a line are not a
    sentence, and in a batch Stanza's analysis of a word changes with its
    neighbours (קברותיך splits alone but not beside רבשקה), so the same word
    could get different lemmas in different lines. Within the word the stem is
    the first syntactic word that is not a clitic, or else the longest.
    """
    nlp = _get_stanza()
    if not nlp:
        return [None] * len(words)
    return [_stanza_word(nlp, word) for word in words]


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
    for idx, hit in zip(stanza_indices, _stanza_by_word(stanza_needed)):
        if hit is not None:
            lemmas[idx] = hit[0]

    # Tokens Stanza could not lemmatize keep their normalized form
    return [l if l is not None else normalize_hebrew(tokens[i]) for i, l in enumerate(lemmas)]


# BHSA part-of-speech labels mapped to the Universal POS tags the other
# languages' taggers produce.
_BHSA_TO_UPOS = {
    'verb': 'VERB',
    'subs': 'NOUN',    # substantive
    'nmpr': 'PROPN',   # proper noun
    'adjv': 'ADJ',
    'advb': 'ADV',
    'prep': 'ADP',
    'conj': 'CCONJ',
    'art': 'DET',
    'prps': 'PRON',    # personal pronoun
    'prde': 'PRON',    # demonstrative pronoun
    'prin': 'PRON',    # interrogative pronoun
    'inrg': 'ADV',     # interrogative particle
    'nega': 'PART',    # negative particle
    'intj': 'INTJ',
}


def get_pos_tags(tokens, language='he'):
    """Get POS tags for Hebrew tokens: the BHSA table first, with the same
    prefix stripping as lemmas (so ויאמר is tagged as יאמר, a verb), and
    Stanza only for tokens the table lacks.

    Tags used to come from Stanza on the whole verse, matched to our tokens one
    for one although Stanza splits prefixes into words of their own, so after
    the first prefix every tag sat on the wrong token (#482). It was also a
    Modern Hebrew model, run on every verse.
    """
    if not tokens:
        return []

    table = _get_pos_table()
    tags = []
    missed_indices, missed_words = [], []
    for i, token in enumerate(tokens):
        normalized = normalize_hebrew(token)
        label = _lookup_lemma(normalized, table)
        if label is not None:
            tags.append(_BHSA_TO_UPOS.get(label, 'X'))
        else:
            tags.append('UNK')
            missed_indices.append(i)
            missed_words.append(normalized)

    for i, hit in zip(missed_indices, _stanza_by_word(missed_words)):
        if hit is not None:
            tags[i] = hit[1]
    return tags


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
        """Full pipeline: tokenize, lemmatize, POS tag, plus a qere/ketiv
        variant-lemma channel. Returns a 5-tuple; the 5th element,
        variant_lemmas, is a list parallel to tokens where entry i holds any
        extra lemmas at position i (the ketiv lemma at a qere/ketiv pair's qere
        position, empty elsewhere), so the index builder can post the ketiv
        lemma on the same verse position as the qere."""
        original_tokens, tokens, variant_forms = tokenize_hebrew_with_variants(text)
        lemmas = lemmatize_hebrew(tokens)
        variant_lemmas = [lemmatize_hebrew(vf) if vf else [] for vf in variant_forms]
        pos_tags = get_pos_tags(tokens)
        return original_tokens, tokens, lemmas, pos_tags, variant_lemmas

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
