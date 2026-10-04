"""
Arabic function words / stopwords for Tesserae V6.

Curated list of high-frequency Arabic particles, prepositions, pronouns,
and conjunctions that should be penalized in scoring (analogous to
DEFAULT_LATIN_STOP_WORDS in matcher.py).

Two properties matter for the list to have any effect, both learned the hard
way on 2026-09-04/05:

1. Entries are folded through `normalize_arabic()` at import time. The
   indexed lemma stream is normalized (hamza forms to bare alif, alif maqsura
   to ya, no diacritics), so an entry typed as 'على' or 'إلى' never matched
   the lemmas 'علي' / 'الي' until this was done.
2. The lemmatizer leaves proclitics attached (wa-, fa-, ka-, li-, bi-) and
   pronoun enclitics on prepositions, so 'ولا', 'فما', 'كما', 'لهم' reached the
   matcher as content words and topped the Banat Su'ad x Qur'an list. The
   prefixed and suffixed forms below are generated from the base list.
"""

from backend.arabic.processor import normalize_arabic

_BASE = {
    # Conjunctions
    'و', 'ف', 'ثم', 'أو', 'أم', 'لكن', 'بل',
    # exceptive particle, the most frequent shared word in weak Arabic matches
    'إلا', 'الا',
    # Prepositions
    'في', 'من', 'إلى', 'على', 'عن', 'ب', 'ل', 'ك', 'حتى', 'منذ', 'مع',
    # Definite article
    'ال',
    # Pronouns (independent)
    'هو', 'هي', 'هم', 'هن', 'أنت', 'أنتم', 'أنا', 'نحن', 'أنتما', 'هما',
    # Demonstratives
    'هذا', 'هذه', 'ذلك', 'تلك', 'هؤلاء', 'أولئك',
    # Relative pronouns
    'الذي', 'التي', 'الذين', 'اللذين', 'اللتين', 'اللواتي', 'ما',
    # Negation
    'لا', 'لم', 'لن', 'ما', 'ليس',
    # Existential/auxiliary
    'كان', 'يكون', 'كانت', 'كانوا', 'كنت', 'زال', 'يزال',
    'إن', 'أن', 'إذا', 'إذ', 'لو', 'قد', 'إنما', 'لما', 'إني', 'أني',
    # Interrogatives
    'من', 'ما', 'ماذا', 'أين', 'متى', 'كيف', 'لماذا', 'هل', 'أ',
    # Common function particles
    'عند', 'بين', 'فوق', 'تحت', 'بعد', 'قبل', 'كل', 'بعض', 'غير',
    'ذو', 'ذات', 'ذي',
    # Very common verbs often functioning as auxiliaries
    'كان', 'قال', 'يقول',
}

# Prepositions and particles that take pronoun enclitics.
_TAKES_ENCLITIC = {'ل', 'ب', 'في', 'من', 'عن', 'على', 'إلى', 'مع', 'عند', 'بين', 'ك'}
_ENCLITICS = ('ه', 'ها', 'هم', 'هن', 'هما', 'ك', 'كم', 'كما', 'ي', 'نا')
_PROCLITICS = ('و', 'ف', 'ك', 'ل', 'ب')

_GENERATED = set()
for _w in _BASE:
    for _p in _PROCLITICS:
        if _w not in ('و', 'ف', 'ك', 'ل', 'ب', 'ال', 'أ'):
            _GENERATED.add(_p + _w)
for _w in _TAKES_ENCLITIC:
    for _e in _ENCLITICS:
        _GENERATED.add(_w + _e)
        _GENERATED.add('و' + _w + _e)
        _GENERATED.add('ف' + _w + _e)

# Arabic-script punctuation marks that the tokenizers currently keep as
# standalone tokens (comma, question mark, semicolon, full stop). Found in
# the Urdu web test 2026-09-05; the tokenizer fix is an open item because it
# forces an index rebuild.
_PUNCTUATION_TOKENS = {'\u060c', '\u061f', '\u061b', '\u06d4'}
ARABIC_STOP_WORDS = {normalize_arabic(w) for w in (_BASE | _GENERATED)} | _PUNCTUATION_TOKENS
