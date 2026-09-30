"""
Hebrew function words / stopwords for Tesserae V6.

Curated list of high-frequency Biblical Hebrew particles, prepositions,
pronouns, and conjunctions. All forms are consonantal (no nikkud),
matching our normalized pipeline output.

The list is compared against lemmas, so every entry must be a lemma the
BHSA table can produce. Prefixed surface forms (ויהי, והנה, לפני, אחרי,
כאשר, ההוא, ההיא, האם) and the plural pronouns אתם and אתן never survive
lemmatization and were removed (#483); their lemmas are either already
here or are content words (היה, פנה, אם, נתן) that must not be stopped.

עם and שם are left off although their function readings ("with", "there")
belong here: one consonantal lemma also covers "people" (64% of עם in BHSA)
and "name" (52% of שם), so stopping them lost more content words than
function words. אל ("to"/"not", and 3.6% "God"), את and על stay; all five
can be split once lemmas are looked up by pointed form (#483).
"""

HEBREW_STOP_WORDS = {
    # Conjunctions
    'כי', 'גם', 'אף', 'או', 'פן',
    # Prepositions (standalone forms; clitic ב/ל/כ/מ handled by segmentation)
    'אל', 'על', 'את', 'מן', 'אצל', 'בין', 'תחת', 'עד', 'אחר',
    'נגד',
    # Definite article (standalone; usually clitic ה)
    'ה',
    # Independent pronouns (את is listed under prepositions)
    'אני', 'אנכי', 'אתה', 'הוא', 'היא',
    'אנחנו', 'הם', 'הן', 'נחנו',
    # Demonstratives
    'זה', 'זאת', 'זו', 'אלה', 'אלו',
    # Relative / subordinating
    'אשר',
    # Interrogatives
    'מי', 'מה', 'איה', 'אנה', 'מתי', 'איך', 'למה', 'מדוע',
    # Negation (אל is listed under prepositions)
    'לא', 'אין', 'בלי', 'בל',
    # Existential (אין is listed under negation)
    'יש',
    # Common particles
    'הנה', 'נא', 'רק', 'אך', 'כל', 'עוד', 'כן', 'לכן',
}
