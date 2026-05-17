"""
Urdu function words / stopwords for Tesserae V6.

Curated list of high-frequency Urdu particles, postpositions, pronouns,
auxiliaries, and conjunctions. Classical Urdu poetry shares many function
words with Persian (via literary register) and Arabic (via religious register).

Forms are normalized (diacritics stripped, standard letter forms).
"""

URDU_STOP_WORDS = {
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
