"""
Hebrew function words / stopwords for Tesserae V6.
Curated list of high-frequency Biblical Hebrew particles, prepositions,
pronouns, and conjunctions. All forms are consonantal (no nikkud),
matching our normalized pipeline output.
The list is compared against lemmas, so every entry must be a lemma the
BHSA tables can produce. Prefixed surface forms (ויהי, והנה, לפני, אחרי,
כאשר, ההוא, ההיא, האם) and the plural pronouns אתם and אתן never survive
lemmatization and were removed (#483); their lemmas are either already
here or are content words (היה, פנה, אם, נתן) that must not be stopped.
Homographs (#483, 2026-10-01). Words that share a consonantal spelling are
now separate lemmas. The most frequent reading keeps the bare spelling and
the others carry a superscript numeral in order of BHSA frequency;
data/lemma_tables/hebrew_homographs.json lists every group with its gloss.
An entry here therefore stops ONE reading. In most groups the bare
spelling is the function word (אל "to", את the object marker, על "upon",
עד "unto"), so the content readings (אל³ "God", עד² "witness", בין²
"understand") are no longer stopped with it. Where the function reading
is a numbered one, the entry carries the number: אל² "not", את² "together
with", עם² "with", שם² "there", אף² "even", נגד² "opposite", ה² the
interrogative, הנה² "here". The pronoun reading of הנה ("they") never wins
a pointed key, so it has no lemma to stop. Before this change אף and נגד
stopped "nose" and "report" along with "even" and "opposite", and עם and
שם were left off the list because their one lemma also meant "people"
and "name".
"""

HEBREW_STOP_WORDS = {
    # Conjunctions
    'כי', 'גם', 'אף²', 'או', 'פן',
    # Prepositions (standalone forms; clitic ב/ל/כ/מ handled by segmentation)
    'אל', 'על', 'את', 'את²', 'מן', 'אצל', 'בין', 'תחת', 'עד', 'אחר',
    'נגד²', 'עם²',
    # Definite article (standalone; usually clitic ה)
    'ה', 'ה²',
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
    'לא', 'אל²', 'אין', 'בלי', 'בל',
    # Existential (אין is listed under negation)
    'יש',
    # Common particles
    'הנה', 'הנה²', 'שם²', 'נא', 'רק', 'אך', 'כל', 'עוד', 'כן', 'לכן',
}
