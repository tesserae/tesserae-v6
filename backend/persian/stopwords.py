"""
Persian function words / stopwords for Tesserae V6.
"""

PERSIAN_STOP_WORDS = {
    # Conjunctions
    'و', 'یا', 'اما', 'ولی', 'که', 'تا', 'چون', 'اگر', 'گر',
    # Prepositions
    'از', 'به', 'با', 'در', 'بر', 'تا', 'برای', 'بی', 'مگر',
    # Pronouns
    'من', 'تو', 'او', 'ما', 'شما', 'ایشان', 'آن', 'این',
    # Demonstratives
    'آن', 'این', 'همان', 'همین', 'چنین', 'چنان',
    # Ezafe / copula
    'است', 'بود', 'شد', 'هست', 'نیست', 'باشد', 'بودن',
    # Auxiliary / common verbs
    'کرد', 'کردن', 'شدن', 'داشتن', 'داشت', 'دارد',
    # Negation
    'نه', 'نی', 'نیست', 'مگر',
    # Common particles
    'هم', 'هر', 'چه', 'کی', 'کجا', 'چرا', 'بس',
    'را', 'می', 'نمی', 'بر',
    # Relative / interrogative
    'کدام', 'چگونه', 'چند',
    # Very common words in poetry
    'ای', 'اندر', 'مرا', 'ترا', 'ز', 'بر', 'همه', 'یک',
}
