"""
Hebrew function words / stopwords for Tesserae V6.

Curated list of high-frequency Biblical Hebrew particles, prepositions,
pronouns, and conjunctions. All forms are consonantal (no nikkud),
matching our normalized pipeline output.
"""

HEBREW_STOP_WORDS = {
    # Conjunctions
    'כי', 'גם', 'אף', 'או', 'פן',
    # Prepositions (standalone forms; clitic ב/ל/כ/מ handled by segmentation)
    'אל', 'על', 'עם', 'את', 'מן', 'אצל', 'בין', 'תחת', 'עד', 'אחר',
    'לפני', 'אחרי', 'נגד',
    # Definite article (standalone; usually clitic ה)
    'ה',
    # Independent pronouns
    'אני', 'אנכי', 'אתה', 'את', 'הוא', 'היא',
    'אנחנו', 'אתם', 'אתן', 'הם', 'הן', 'נחנו',
    # Demonstratives
    'זה', 'זאת', 'זו', 'אלה', 'אלו', 'ההוא', 'ההיא',
    # Relative / subordinating
    'אשר', 'כאשר',
    # Interrogatives
    'מי', 'מה', 'איה', 'אנה', 'מתי', 'איך', 'למה', 'מדוע', 'האם',
    # Negation
    'לא', 'אין', 'אל', 'בלי', 'בל',
    # Existential
    'יש', 'אין',
    # Common particles
    'הנה', 'נא', 'רק', 'אך', 'כל', 'עוד', 'כן', 'לכן', 'שם',
    # Discourse markers
    'ויהי', 'והנה',
}
