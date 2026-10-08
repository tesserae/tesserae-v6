"""One key for a scriptural passage across its versions.

The corpus holds the same verse in several forms: hebrew_bible.isaiah (MT),
septuaginta.isaias (LXX), bohairic.isaias and sahidic.isaiah (Coptic),
world_english_bible.prophets.part.7.isaiah (English). Scholarship on the
verse is the same scholarship whichever version a reader is looking at, so
each version's work id and locus is mapped to a canonical key,
("isaiah", 40, 3), and commentaries on scripture are filed by that key
(data/commentaries/<commentator>__bible.<book>.json with refs "isaiah 40:3").

Numbering: the Masoretic chapter and verse is the canonical one. The
Septuagint and the Coptic (which follows it) number the Psalms differently
for most of the book; that offset is applied here, and the result is marked
approximate because a few psalms are split or joined rather than shifted.
Other books' divergences (Jeremiah's chapter order in the LXX, verse shifts
at chapter ends) are not corrected; the mapped key is still right for the
great majority of verses and the note names the version.
"""
import re

# Canonical book ids follow the site's Hebrew files (hebrew_bible.<book>)
# plus the New Testament and deuterocanonical books in the same style.
_ALIASES = {
    # Latinate names used by the Septuagint and the Bohairic files
    'isaias': 'isaiah', 'esaias': 'isaiah', 'psalmi': 'psalms', 'psalm': 'psalms', 'osee': 'hosea',
    'ieremias': 'jeremiah', 'jeremias': 'jeremiah', 'ezechiel': 'ezekiel', 'sophonias': 'zephaniah',
    'malachias': 'malachi', 'michaeas': 'micah', 'ionas': 'jonah', 'jonas': 'jonah', 'ioel': 'joel',
    'iob': 'job', 'aggaeus': 'haggai', 'abdias': 'obadiah', 'habacuc': 'habakkuk', 'zacharias': 'zechariah',
    'deuteronomium': 'deuteronomy', 'deuteronomion': 'deuteronomy', 'numeri': 'numbers', 'arithmoi': 'numbers',
    'levitikon': 'leviticus', 'kritai': 'judges', 'josue': 'joshua', 'canticum': 'song_of_songs',
    'song_of_solomon': 'song_of_songs', 'threni_seu_lamentationes': 'lamentations', 'lamentationes': 'lamentations',
    'proverbia': 'proverbs', 'ecclesiasticus': 'sirach', 'tobias': 'tobit', 'sapientia_salomonis': 'wisdom',
    'basileion_a': '1_samuel', 'basileion_b': '2_samuel', 'basileion_g': '1_kings', 'basileion_d': '2_kings',
    'paralipomenon_i_sive_chronicon_i': '1_chronicles', 'paralipomenon_b': '2_chronicles',
    'esdras_b': 'ezra', 'daniel_theodotionis': 'daniel', 'daniel_translatio_graeca': 'daniel',
    'i_samuel': '1_samuel', 'ii_samuel': '2_samuel', 'i_kings': '1_kings', 'ii_kings': '2_kings',
    'i_chronicles': '1_chronicles', 'ii_chronicles': '2_chronicles', 'ii_maccabees': '2_maccabees',
    'machabaeorum_i': '1_maccabees', 'machabaeorum_b': '2_maccabees',
    # New Testament, Latin and Coptic spellings
    'matthaeus': 'matthew', 'marcus': 'mark', 'lucas': 'luke', 'ioannes': 'john', 'actus_apostolorum': 'acts',
    'acts_of_the_apostles': 'acts', 'ad_romanos': 'romans', 'ad_corinthios_i': '1_corinthians',
    'ad_corinthios_ii': '2_corinthians', 'i_corinthians': '1_corinthians', 'ii_corinthians': '2_corinthians',
    '1corinthians': '1_corinthians', 'ad_galatas': 'galatians', 'galathians': 'galatians', 'ad_ephesios': 'ephesians',
    'ad_philippenses': 'philippians', 'ad_colossenses': 'colossians', 'ad_thessalonicenses_i': '1_thessalonians',
    'ad_thessalonicenses_ii': '2_thessalonians', 'i_thessalonians': '1_thessalonians', 'ii_thessalonians': '2_thessalonians',
    'ad_timotheum_i': '1_timothy', 'ad_timotheum_ii': '2_timothy', 'i_timothy': '1_timothy', 'ii_timothy': '2_timothy',
    'ad_titum': 'titus', 'ad_philemonem': 'philemon', 'ad_hebraeos': 'hebrews', 'iacobi': 'james',
    'petri_i': '1_peter', 'petri_ii': '2_peter', 'i_peter': '1_peter', 'ii_peter': '2_peter',
    'ioannis_i': '1_john', 'ioannis_ii': '2_john', 'ioannis_iii': '3_john', 'i_john': '1_john', 'ii_john': '2_john',
    'iii_john': '3_john', 'iudae': 'jude', 'apocalypsis': 'revelation',
}

# Corpus prefixes that are scripture, with the version's display name and
# whether it follows the Septuagint's Psalm numbering.
_VERSIONS = {
    'hebrew_bible': ('Hebrew Bible', False),
    'septuaginta': ('Septuagint', True),
    'novum_testamentum': ('Greek New Testament', False),
    'bohairic': ('Bohairic Coptic', True),
    'sahidic': ('Sahidic Coptic', True),
    'sahidica': ('Sahidic Coptic', False),
    'world_english_bible': ('World English Bible', False),
}

# English names and the short forms scholars use in citations.
_NAMES = {
    'genesis': ('Genesis', 'Gen'), 'exodus': ('Exodus', 'Exod'), 'leviticus': ('Leviticus', 'Lev'),
    'numbers': ('Numbers', 'Num'), 'deuteronomy': ('Deuteronomy', 'Deut'), 'joshua': ('Joshua', 'Josh'),
    'judges': ('Judges', 'Judg'), 'ruth': ('Ruth', 'Ruth'), '1_samuel': ('1 Samuel', '1 Sam'),
    '2_samuel': ('2 Samuel', '2 Sam'), '1_kings': ('1 Kings', '1 Kgs'), '2_kings': ('2 Kings', '2 Kgs'),
    '1_chronicles': ('1 Chronicles', '1 Chr'), '2_chronicles': ('2 Chronicles', '2 Chr'), 'ezra': ('Ezra', 'Ezra'),
    'nehemiah': ('Nehemiah', 'Neh'), 'esther': ('Esther', 'Esth'), 'job': ('Job', 'Job'), 'psalms': ('Psalms', 'Ps'),
    'proverbs': ('Proverbs', 'Prov'), 'ecclesiastes': ('Ecclesiastes', 'Eccl'), 'song_of_songs': ('Song of Songs', 'Song'),
    'isaiah': ('Isaiah', 'Isa'), 'jeremiah': ('Jeremiah', 'Jer'), 'lamentations': ('Lamentations', 'Lam'),
    'ezekiel': ('Ezekiel', 'Ezek'), 'daniel': ('Daniel', 'Dan'), 'hosea': ('Hosea', 'Hos'), 'joel': ('Joel', 'Joel'),
    'amos': ('Amos', 'Amos'), 'obadiah': ('Obadiah', 'Obad'), 'jonah': ('Jonah', 'Jonah'), 'micah': ('Micah', 'Mic'),
    'nahum': ('Nahum', 'Nah'), 'habakkuk': ('Habakkuk', 'Hab'), 'zephaniah': ('Zephaniah', 'Zeph'),
    'haggai': ('Haggai', 'Hag'), 'zechariah': ('Zechariah', 'Zech'), 'malachi': ('Malachi', 'Mal'),
    'tobit': ('Tobit', 'Tob'), 'judith': ('Judith', 'Jdt'), 'wisdom': ('Wisdom of Solomon', 'Wis'),
    'sirach': ('Sirach', 'Sir'), 'baruch': ('Baruch', 'Bar'), '1_maccabees': ('1 Maccabees', '1 Macc'),
    '2_maccabees': ('2 Maccabees', '2 Macc'),
    'matthew': ('Matthew', 'Matt'), 'mark': ('Mark', 'Mark'), 'luke': ('Luke', 'Luke'), 'john': ('John', 'John'),
    'acts': ('Acts', 'Acts'), 'romans': ('Romans', 'Rom'), '1_corinthians': ('1 Corinthians', '1 Cor'),
    '2_corinthians': ('2 Corinthians', '2 Cor'), 'galatians': ('Galatians', 'Gal'), 'ephesians': ('Ephesians', 'Eph'),
    'philippians': ('Philippians', 'Phil'), 'colossians': ('Colossians', 'Col'), '1_thessalonians': ('1 Thessalonians', '1 Thess'),
    '2_thessalonians': ('2 Thessalonians', '2 Thess'), '1_timothy': ('1 Timothy', '1 Tim'), '2_timothy': ('2 Timothy', '2 Tim'),
    'titus': ('Titus', 'Titus'), 'philemon': ('Philemon', 'Phlm'), 'hebrews': ('Hebrews', 'Heb'), 'james': ('James', 'Jas'),
    '1_peter': ('1 Peter', '1 Pet'), '2_peter': ('2 Peter', '2 Pet'), '1_john': ('1 John', '1 John'),
    '2_john': ('2 John', '2 John'), '3_john': ('3 John', '3 John'), 'jude': ('Jude', 'Jude'), 'revelation': ('Revelation', 'Rev'),
}


TANAKH = {'genesis', 'exodus', 'leviticus', 'numbers', 'deuteronomy', 'joshua', 'judges', 'ruth', '1_samuel',
          '2_samuel', '1_kings', '2_kings', '1_chronicles', '2_chronicles', 'ezra', 'nehemiah', 'esther', 'job',
          'psalms', 'proverbs', 'ecclesiastes', 'song_of_songs', 'isaiah', 'jeremiah', 'lamentations', 'ezekiel',
          'daniel', 'hosea', 'joel', 'amos', 'obadiah', 'jonah', 'micah', 'nahum', 'habakkuk', 'zephaniah',
          'haggai', 'zechariah', 'malachi'}


def book_of(work):
    """(version_prefix, canonical book id) for a scriptural work id, else None."""
    w = (work or '').replace('.tess', '')
    parts = w.split('.')
    if parts[0] not in _VERSIONS:
        return None
    raw = parts[-1]                      # world_english_bible.prophets.part.7.isaiah -> isaiah
    if raw in ('bible', 'ot', 'nt', 'pentateuch', 'prophets', 'writings', 'new_testament') or raw.isdigit():
        return None                      # aggregate files, not a book
    book = _ALIASES.get(raw, raw)
    if book not in _NAMES:
        return None
    return parts[0], book


def _lxx_psalm_to_mt(ch):
    """Septuagint psalm number to the Masoretic one (approximate at the seams)."""
    if 10 <= ch <= 112 or 116 <= ch <= 145:
        return ch + 1
    if ch == 113:
        return 114          # LXX 113 = MT 114-115
    if ch == 114:
        return 116          # LXX 114-115 = MT 116
    if ch == 115:
        return 116
    if ch == 146:
        return 147          # LXX 146-147 = MT 147
    if ch == 147:
        return 147
    return ch


def canonical(work, ref):
    """Canonical key for a scriptural passage: {'book', 'chapter', 'verse',
    'version', 'approximate'} or None when the work is not scripture."""
    b = book_of(work)
    if not b:
        return None
    prefix, book = b
    nums = [int(n) for n in re.findall(r'\d+', str(ref or '').split(work.replace('.tess', ''))[-1])]
    if not nums:
        return None
    chapter = nums[-2] if len(nums) >= 2 else nums[-1]
    verse = nums[-1] if len(nums) >= 2 else None
    version, lxx = _VERSIONS[prefix]
    approximate = False
    if lxx and book == 'psalms':
        chapter, approximate = _lxx_psalm_to_mt(chapter), True
    return {'book': book, 'chapter': chapter, 'verse': verse, 'version': version, 'approximate': approximate}


def citation(book, chapter, verse=None, verse_end=None):
    """("Isaiah 40:3", "Isa 40:3") for searching and display."""
    full, short = _NAMES[book]
    loc = f'{chapter}:{verse}' if verse else str(chapter)
    if verse_end and verse_end != verse:
        loc += f'-{verse_end}'
    return f'{full} {loc}', f'{short} {loc}'


def ref_key(book, chapter, verse):
    """The ref form used inside commentary files on scripture."""
    return f'{book} {chapter}:{verse}'
