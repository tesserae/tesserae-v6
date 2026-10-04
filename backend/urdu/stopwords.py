"""
Urdu function words / stopwords for Tesserae V6.

Curated list of high-frequency Urdu particles, postpositions, pronouns,
auxiliaries, and conjunctions. Classical Urdu poetry shares many function
words with Persian (via literary register) and Arabic (via religious register).

Forms are normalized (diacritics stripped, standard letter forms).

Entries are written in native Urdu orthography for readability and folded
through `normalize_urdu()` at import time (2026-09-05): the indexed lemma
stream is normalized (Urdu ye/kaf/he to their Arabic-script counterparts),
and until this was done 33 of the 80 entries never matched anything.
"""

from backend.urdu.processor import normalize_urdu

_RAW_STOP_WORDS = {
    # Conjunctions
    'اور', 'و', 'مگر', 'لیکن', 'پر', 'کہ', 'یا', 'نہ',
    # Postpositions
    'کا', 'کی', 'کے', 'کو', 'سے', 'میں', 'پر', 'تک', 'نے',
    'پہ', 'بر',
    # Pronouns
    'میں', 'تو', 'وہ', 'یہ', 'ہم', 'تم', 'آپ', 'کوئی', 'کچھ',
    'اس', 'ان', 'جو', 'جس', 'کون', 'کیا',
    # Demonstratives
    'یہ', 'وہ', 'اس', 'ان', 'اسی', 'انہی',
    # Auxiliaries / copulas
    'ہے', 'ہیں', 'تھا', 'تھی', 'تھے', 'ہو', 'ہوا', 'ہوئی',
    'ہوں', 'رہا', 'رہی', 'رہے', 'گا', 'گی', 'گے',
    # Negation
    'نہ', 'نہیں', 'مت', 'بغیر', 'بنا',
    # Common particles (literary/classical)
    'بھی', 'ہی', 'تو', 'پھر', 'اب', 'جب', 'کب', 'ابھی',
    # Persian-origin function words (common in classical Urdu poetry)
    'ز', 'بر', 'در', 'از', 'تا', 'بہ', 'چہ', 'ہر', 'اگر',
    'مگر', 'زیر', 'بالا', 'پیش',
    # Arabic-origin particles
    'لا', 'و', 'بل', 'ف',
    # Very common verbs used as auxiliaries
    'کر', 'جا', 'آ', 'لے', 'دے', 'رکھ',
}

# Arabic-script punctuation marks that the tokenizers currently keep as
# standalone tokens (comma, question mark, semicolon, full stop). Found in
# the Urdu web test 2026-09-05; the tokenizer fix is an open item because it
# forces an index rebuild.
_PUNCTUATION_TOKENS = {'\u060c', '\u061f', '\u061b', '\u06d4'}
URDU_STOP_WORDS = {normalize_urdu(w) for w in _RAW_STOP_WORDS} | _PUNCTUATION_TOKENS
