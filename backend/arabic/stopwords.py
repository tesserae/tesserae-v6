"""
Arabic function words / stopwords for Tesserae V6.

Curated list of high-frequency Arabic particles, prepositions, pronouns,
and conjunctions that should be penalized in scoring (analogous to
DEFAULT_LATIN_STOP_WORDS in matcher.py).
"""

ARABIC_STOP_WORDS = {
    # Conjunctions
    'و', 'ف', 'ثم', 'أو', 'أم', 'لكن', 'بل',
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
    'كان', 'يكون', 'كانت', 'كانوا',
    'إن', 'أن', 'إذا', 'إذ', 'لو', 'قد',
    # Interrogatives
    'من', 'ما', 'ماذا', 'أين', 'متى', 'كيف', 'لماذا', 'هل', 'أ',
    # Common function particles
    'عند', 'بين', 'فوق', 'تحت', 'بعد', 'قبل', 'كل', 'بعض', 'غير',
    'ذو', 'ذات', 'ذي',
    # Very common verbs often functioning as auxiliaries
    'كان', 'قال', 'يقول',
}

# Normalized forms (stripped of diacritics) for matching
# Since our pipeline strips diacritics, this set works as-is
