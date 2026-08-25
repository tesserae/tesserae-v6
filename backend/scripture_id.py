"""Identify when two passages are the same scripture in different versions.

The corpus holds the Bible many times over: Hebrew, Greek in the Septuagint and
the New Testament, Latin in the Vulgate, English in the World English Bible, and
Coptic twice in the Sahidic and Bohairic. Content search therefore has a problem
that no other part of the corpus has. Ask what resembles Coptic Genesis 1:1 and
the honest answer is Hebrew Genesis 1:1, Greek Genesis 1:1, Latin Genesis 1:1 and
English Genesis 1:1, which is true, useless, and fills the page.

This module gives every scriptural line one canonical address so those can be
recognised and collapsed. Two problems have to be solved to do it:

  * every tradition names books differently. Numbers is `arithmoi` in the
    Septuagint, `numeri` in the Bohairic, `Numbers` in the Vulgate and the WEB,
    and `numbers` in the Sahidic.
  * every tradition numbers the Psalms differently. The Septuagint joins Hebrew
    9 and 10, so from there to the end of the Psalter it runs one behind, and
    the Coptic and the Vulgate inherit that. Psalm 22 in a Coptic manuscript is
    Psalm 23 in an English Bible. Without this, the shepherd psalm and the gates
    of glory look like different passages, and the collapse silently fails.

Canonical form is (book code, chapter, verse), numbered as the Masoretic and
modern English Bibles do, because that is the numbering a reader will recognise.
"""
import re

# --------------------------------------------------------------------------
# Book names, in every form the corpus uses, to one code.
# --------------------------------------------------------------------------
# Latin and Greek-transliterated forms come from the Vulgate and Septuagint
# files; the Coptic editions use Latin forms in the Bohairic and English forms
# in the Sahidic, which is why both appear here.
_BOOKS = {
    'GEN': ['genesis'],
    'EXO': ['exodus'],
    'LEV': ['leviticus', 'levitikon'],
    'NUM': ['numbers', 'numeri', 'arithmoi'],
    'DEU': ['deuteronomy', 'deuteronomium', 'deuteronomion'],
    'JOS': ['joshua', 'josue', 'iesus_nave'],
    'JDG': ['judges', 'kritai', 'iudicum'],
    'RUT': ['ruth'],
    # The Septuagint counts the four books of Kingdoms where the Hebrew has
    # Samuel and Kings, so basileion a-d are 1 Samuel, 2 Samuel, 1 Kings, 2 Kings.
    '1SA': ['1 samuel', 'i_samuel', 'i samuel', '1_samuel', 'basileion_a', 'samuel_i'],
    '2SA': ['2 samuel', 'ii_samuel', 'ii samuel', '2_samuel', 'basileion_b', 'samuel_ii'],
    '1KI': ['1 kings', 'i_kings', 'i kings', '1_kings', 'basileion_g', 'kings_i'],
    '2KI': ['2 kings', 'ii_kings', 'ii kings', '2_kings', 'basileion_d', 'kings_ii'],
    '1CH': ['1 chronicles', 'i_chronicles', '1_chronicles', 'paralipomenon_i_sive_chronicon_i',
            'paralipomenon_i'],
    '2CH': ['2 chronicles', 'ii_chronicles', '2_chronicles', 'paralipomenon_b'],
    'EZR': ['ezra', 'esdras_b', '1 esdras'],
    'NEH': ['nehemiah', '2 esdras'],
    'EST': ['esther'],
    'JOB': ['job', 'iob'],
    'PSA': ['psalms', 'psalmi', 'psalm', 'old latin psalms'],
    'PRO': ['proverbs', 'proverbia', 'parabolae'],
    'ECC': ['ecclesiastes', 'ekklesiastes'],
    'SNG': ['song of solomon', 'song of songs', 'song_of_solomon', 'canticum', 'canticum_canticorum'],
    'ISA': ['isaiah', 'isaias'],
    'JER': ['jeremiah', 'jeremias', 'ieremias'],
    'LAM': ['lamentations', 'lamentationes', 'threni_seu_lamentationes', 'threni'],
    'EZK': ['ezekiel', 'ezechiel'],
    'DAN': ['daniel', 'daniel_theodotionis', 'daniel_translatio_graeca'],
    'HOS': ['hosea', 'osee'],
    'JOL': ['joel', 'ioel'],
    'AMO': ['amos'],
    'OBA': ['obadiah', 'abdias'],
    'JON': ['jonah', 'jonas', 'ionas'],
    'MIC': ['micah', 'michaeas'],
    'NAM': ['nahum'],
    'HAB': ['habakkuk', 'habacuc', 'habbakuk'],
    'ZEP': ['zephaniah', 'sophonias', 'zephoniah'],
    'HAG': ['haggai', 'aggaeus', 'haggaiah'],
    'ZEC': ['zechariah', 'zacharias'],
    'MAL': ['malachi', 'malachias'],
    # Deuterocanon
    'TOB': ['tobit', 'tobias'],
    'JDT': ['judith'],
    'WIS': ['wisdom', 'sapientia_salomonis', 'sapientia'],
    'SIR': ['sirach', 'ecclesiasticus'],
    'BAR': ['baruch'],
    'LJE': ['epistle_of_jeremiah', 'epistula_jeremiae'],
    'SUS': ['susanna', 'susanna_theodotionis', 'susanna_translatio_graeca'],
    'BEL': ['bel_and_the_dragon', 'bel_et_draco_theodotionis', 'bel_et_draco_translatio_graeca'],
    'MAN': ['prayer_of_manasses', 'prayer of manasseh'],
    '1MA': ['1 maccabees', 'i_maccabees', 'machabaeorum_i'],
    '2MA': ['2 maccabees', 'ii_maccabees', 'machabaeorum_b'],
    # New Testament
    'MAT': ['matthew', 'matthaeus', 'evangelium_secundum_matthaeum'],
    'MRK': ['mark', 'marcus', 'evangelium_secundum_marcum'],
    'LUK': ['luke', 'lucas', 'evangelium_secundum_lucam'],
    'JHN': ['john', 'ioannes', 'evangelium_secundum_ioannem'],
    'ACT': ['acts', 'actus_apostolorum', 'acts_of_the_apostles'],
    'ROM': ['romans', 'ad_romanos'],
    '1CO': ['1 corinthians', 'i_corinthians', '1corinthians', '1_corinthians', 'ad_corinthios_i'],
    '2CO': ['2 corinthians', 'ii_corinthians', '2_corinthians', 'ad_corinthios_ii'],
    'GAL': ['galatians', 'galathians', 'ad_galatas'],
    'EPH': ['ephesians', 'ad_ephesios'],
    'PHP': ['philippians', 'ad_philippenses'],
    'COL': ['colossians', 'ad_colossenses'],
    '1TH': ['1 thessalonians', 'i_thessalonians', '1_thessalonians', 'ad_thessalonicenses_i'],
    '2TH': ['2 thessalonians', 'ii_thessalonians', '2_thessalonians', 'ad_thessalonicenses_ii'],
    '1TI': ['1 timothy', 'i_timothy', '1_timothy', 'ad_timotheum_i'],
    '2TI': ['2 timothy', 'ii_timothy', '2_timothy', 'ad_timotheum_ii'],
    'TIT': ['titus', 'ad_titum'],
    'PHM': ['philemon', 'ad_philemonem'],
    'HEB': ['hebrews', 'ad_hebraeos'],
    'JAS': ['james', 'iacobi'],
    '1PE': ['1 peter', 'i_peter', '1_peter', 'petri_i'],
    '2PE': ['2 peter', 'ii_peter', '2_peter', 'petri_ii'],
    '1JN': ['1 john', 'i_john', '1_john', 'ioannis_i'],
    '2JN': ['2 john', 'ii_john', '2_john', 'ioannis_ii'],
    '3JN': ['3 john', 'iii_john', '3_john', 'ioannis_iii'],
    'JUD': ['jude', 'iudae'],
    'REV': ['revelation', 'apocalypse', 'apocalypsis'],
}

_BOOK_LOOKUP = {}
for _code, _names in _BOOKS.items():
    for _n in _names:
        _BOOK_LOOKUP[_n] = _code
        _BOOK_LOOKUP[_n.replace('_', ' ')] = _code
        _BOOK_LOOKUP[_n.replace(' ', '_')] = _code

# Which scripture collections our works belong to, and whether the collection
# numbers the Psalms as the Septuagint does.
_COLLECTIONS = {
    'sahidic': True,      # Coptic OT renders the Septuagint
    'sahidica': True,
    'bohairic': True,
    'septuaginta': True,
    'hebrew_bible': False,
    'novum_testamentum': False,
    'world_english_bible': False,
    'web': False,
    'vulgate': True,      # the Gallican Psalter follows Septuagint numbering
}

# The Septuagint joins Hebrew 9 and 10 into its 9 and 114 and 115 into its 113,
# and splits Hebrew 116 and 147, so the offset changes at those seams rather
# than being constant. The joined and split psalms have no verse-level
# correspondence at all and are left unmapped rather than mapped approximately.
_PSALM_NO_MAPPING = {9, 113, 114, 115, 146, 147}


def _psalm_septuagint_to_masoretic(ch):
    if ch in _PSALM_NO_MAPPING:
        return None
    if 1 <= ch <= 8 or 148 <= ch <= 150:
        return ch
    if 10 <= ch <= 112 or 116 <= ch <= 145:
        return ch + 1
    return None


def _fold(s):
    return re.sub(r'\s+', ' ', str(s or '').replace('_', ' ').strip().lower())


def _book_of(text):
    """Best book code found in a work name or reference prefix."""
    t = _fold(text)
    if not t:
        return None
    if t in _BOOK_LOOKUP:
        return _BOOK_LOOKUP[t]
    # Work names arrive as collection.book, and Vulgate refs as "Vulgate 1 Kings".
    for part in (t.split('.')[-1], ' '.join(t.split()[1:]), t.split('.', 1)[-1]):
        p = _fold(part)
        if p in _BOOK_LOOKUP:
            return _BOOK_LOOKUP[p]
    return None


def _collection_of(work, ref):
    """Which scripture collection a work belongs to, or None.

    Collection names carry underscores (hebrew_bible, novum_testamentum) that
    _fold turns into spaces, so both spellings are tried.
    """
    candidates = []
    raw = str(work or '').strip().lower()
    if raw:
        candidates += [raw.split('.')[0], _fold(work).split('.')[0]]
    if ref:
        r = str(ref).strip().lower()
        candidates += [r.split()[0] if r.split() else '', r.split('.')[0]]
    for key in candidates:
        key = key.strip()
        if key in _COLLECTIONS:
            return key
        if key.replace(' ', '_') in _COLLECTIONS:
            return key.replace(' ', '_')
    return None


def canonical(work, ref):
    """Canonical (book, chapter, verse) for a scriptural line, else None.

    Handles every reference shape in the corpus:
      hebrew_bible.genesis.1.1        Hebrew
      sahidic.genesis.1.1             Coptic
      novum_testamentum.lucas.1.1     Greek New Testament
      Vulgate Genesis.1.1             Latin
      WEB Genesis 1.1                 English
      septuaginta.tlg001 urn:...1.1   Greek Septuagint, book from the work name
    """
    collection = _collection_of(work, ref)
    if collection is None:
        return None

    book = _book_of(work)
    if book is None and ref:
        # Vulgate and WEB carry the book in the reference, not the work name.
        head = re.split(r'[.\d]', str(ref), 1)[0]
        book = _book_of(head)
    if book is None:
        return None

    nums = re.findall(r'\d+', str(ref or ''))
    if len(nums) < 2:
        return None
    chapter, verse = int(nums[-2]), int(nums[-1])

    if book == 'PSA' and _COLLECTIONS.get(collection):
        chapter = _psalm_septuagint_to_masoretic(chapter)
        if chapter is None:
            return None

    return (book, chapter, verse)


def span(work, ref_start, ref_end=None):
    """Canonical span of a window as (book, first_verse_key, last_verse_key).

    Returns None when the window is not scripture, or when its two ends fall in
    different books, which would make an overlap test meaningless.
    """
    a = canonical(work, ref_start)
    if a is None:
        return None
    b = canonical(work, ref_end) if ref_end else a
    if b is None or b[0] != a[0]:
        b = a
    lo, hi = sorted([(a[1], a[2]), (b[1], b[2])])
    return (a[0], lo, hi)


def overlaps(span_a, span_b):
    """True when two canonical spans cover any verse in common."""
    if not span_a or not span_b or span_a[0] != span_b[0]:
        return False
    return span_a[1] <= span_b[2] and span_b[1] <= span_a[2]


def is_scripture(work):
    return _collection_of(work, None) is not None
