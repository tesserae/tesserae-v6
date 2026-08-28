"""Route Hebrew-Greek biblical searches through the Septuagint.

WHY A PIVOT EXISTS

Direct Hebrew-to-Greek search must bridge two languages in one step, and the
only cross-lingual signals available are a bag-of-words dictionary and, one
day, a purpose-trained bilingual encoder. Measured on 22 formula-marked
citations of Isaiah in Romans (2026-08-27), the direct route found 0 of 22 in
the top 100 and 14 of 22 nowhere in the top 10,000.

But the New Testament does not quote the Hebrew Bible. It quotes the
SEPTUAGINT, which is Greek, and which is in our corpus. So the cross-language
question decomposes into two problems we already solve well: find the
quotation GREEK-TO-GREEK against the Septuagint (near-verbatim, the quotation
channel's home ground), then map each Septuagint verse to its Hebrew
counterpart by versification. Same 22 citations, same day: the pivot with the
biblical weight profile found 15 of 22 in the top 100 and 8 in the top ten,
matching the equivalent monolingual Coptic result.

WHAT THIS MODULE KNOWS

  * which Septuagint text answers for which Hebrew text (BOOKS), and which
    books are deliberately not routed (EXCLUDED, each with its reason),
  * how Masoretic and Septuagint versification differ where they differ
    (the Psalms; everywhere else the map is the identity),
  * how to rewrite a Greek-Greek result so the reader sees the Hebrew verse
    the Septuagint line translates, with the Greek kept visible as the
    intermediary rather than hidden.

The verse conversion mirrors evaluation/coptic_recall/build_gold_set.py,
which built the TSK benchmarks with the same rules.
"""
import os
import re

from backend.logging_config import get_logger

logger = get_logger('lxx_pivot')

# Hebrew corpus stem -> Septuagint corpus stem. Only books whose versification
# map we trust. A book absent here falls back to the direct cross-lingual
# route, so an omission costs quality, never correctness.
BOOKS = {
    'genesis': 'genesis',
    'exodus': 'exodus',
    'leviticus': 'levitikon',
    'numbers': 'arithmoi',
    'deuteronomy': 'deuteronomion',
    'joshua': 'josue',
    'judges': 'kritai',
    'ruth': 'ruth',
    '1_samuel': 'basileion_a',
    '2_samuel': 'basileion_b',
    '1_kings': 'basileion_g',
    '2_kings': 'basileion_d',
    '1_chronicles': 'paralipomenon_i_sive_chronicon_i',
    '2_chronicles': 'paralipomenon_b',
    'esther': 'esther',
    'job': 'job',
    'psalms': 'psalmi',
    'proverbs': 'proverbia',
    'song_of_songs': 'canticum',
    'isaiah': 'isaias',
    'ezekiel': 'ezechiel',
    # Theodotion's Daniel is the ecclesiastical text and follows MT
    # chapter-and-verse for the canonical portions.
    'daniel': 'daniel_theodotionis',
    'hosea': 'osee',
    'joel': 'joel',
    'amos': 'amos',
    'obadiah': 'abdias',
    'jonah': 'jonas',
    'micah': 'michaeas',
    'nahum': 'nahum',
    'habakkuk': 'habacuc',
    'zephaniah': 'sophonias',
    'haggai': 'aggaeus',
    'zechariah': 'zacharias',
    'malachi': 'malachias',
}

# Books deliberately NOT routed, so nobody re-derives the decision:
#   jeremiah     LXX Jeremiah reorders the book wholesale (the oracles against
#                the nations move, chapters renumber); a verse map would be a
#                research project, not a table.
#   ezra,        LXX Esdras B runs Ezra and Nehemiah together as one book with
#   nehemiah     continuous chapters; mappable in principle, deferred.
#   lamentations The corpus's Septuagint Lamentations text is defective (88 of
#                150 lines carry only the acrostic letter; issue #276).
#                Route it once the Greek is repaired.
#   ecclesiastes The corpus holds no Septuagint Ecclesiastes. It does hold
#                septuaginta.ecclesiasticus, WHICH IS SIRACH, A DIFFERENT
#                BOOK, and the near-identical name is exactly how Qohelet
#                searches would silently run against Sirach. The unit test
#                that requires every routed book's file to exist caught this
#                on its first run.
EXCLUDED = {'jeremiah', 'ezra', 'nehemiah', 'lamentations', 'ecclesiastes'}


def lxx_counterpart(hebrew_text_id):
    """The Septuagint text stem for a Hebrew corpus text, or None.

    Accepts 'hebrew_bible.isaiah', 'hebrew_bible.isaiah.tess', or a bare book.
    """
    stem = (hebrew_text_id or '').replace('.tess', '')
    book = stem.split('.')[-1] if '.' in stem else stem
    if book in EXCLUDED:
        return None
    lxx = BOOKS.get(book)
    return f'septuaginta.{lxx}' if lxx else None


def hebrew_to_lxx_verse(book, chap, verse):
    """MT (chapter, verse) -> LXX (chapter, verse) for a routed book.

    Identity everywhere except the Psalms, where the two traditions merge and
    split psalms. Returns a single (chapter, verse) tuple: for the merged and
    split psalms the mapping below follows the same rules the TSK benchmarks
    were built with.
    """
    if book != 'psalms':
        return (chap, verse)
    c, v = chap, verse
    if c <= 8:
        return (c, v)
    if c == 9:
        return (9, v)
    if c == 10:
        # Hebrew 10 is the second half of LXX 9, which runs 39 verses; Hebrew
        # 9 has 21.
        return (9, v + 21)
    if 11 <= c <= 113:
        return (c - 1, v)
    if c == 114:
        return (113, v)
    if c == 115:
        # Second half of LXX 113. Hebrew 114 has 8 verses.
        return (113, v + 8)
    if c == 116:
        return (114, v) if v <= 9 else (115, v - 9)
    if 117 <= c <= 146:
        return (c - 1, v)
    if c == 147:
        return (146, v) if v <= 11 else (147, v - 11)
    return (c, v)   # 148-150 align


def lxx_to_hebrew_verse(book, chap, verse):
    """LXX (chapter, verse) -> MT (chapter, verse); inverse of the above."""
    if book != 'psalms':
        return (chap, verse)
    c, v = chap, verse
    if c <= 8:
        return (c, v)
    if c == 9:
        return (9, v) if v <= 21 else (10, v - 21)
    if 10 <= c <= 112:
        return (c + 1, v)
    if c == 113:
        return (114, v) if v <= 8 else (115, v - 8)
    if c == 114:
        return (116, v)
    if c == 115:
        return (116, v + 9)
    if 116 <= c <= 145:
        return (c + 1, v)
    if c == 146:
        return (147, v)
    if c == 147:
        return (147, v + 11)
    return (c, v)


_CV = re.compile(r'(\d+)\.(\d+)\s*$')


def hebrew_ref_for_lxx_ref(lxx_ref, hebrew_stem, book):
    """Rewrite one Septuagint ref to the Hebrew ref its verse translates.

    LXX refs in this corpus carry a URN ('septuaginta.psalmi urn:...grc1.117.6');
    only the trailing chapter.verse matters here.
    """
    m = _CV.search(lxx_ref or '')
    if not m:
        return None
    c, v = lxx_to_hebrew_verse(book, int(m.group(1)), int(m.group(2)))
    return f'{hebrew_stem}.{c}.{v}'


def annotate_results(results, hebrew_text_id, side):
    """Attach Hebrew references to pivot results, keeping the Greek visible.

    side is 'source' or 'target': which half of each result pair is the
    Septuagint text. Every result gains, on that half:
        hebrew_ref   the MT verse the Septuagint line translates
        via_septuagint  True
    and keeps its Greek ref and text untouched, because a reader shown a
    match "in Hebrew" that was actually found in Greek must be able to see
    the Greek it was found in.
    """
    stem = hebrew_text_id.replace('.tess', '')
    book = stem.split('.')[-1]
    n = 0
    for r in results:
        half = r.get(side)
        if not isinstance(half, dict):
            continue
        heb = hebrew_ref_for_lxx_ref(half.get('ref'), stem, book)
        if heb:
            half['hebrew_ref'] = heb
            half['via_septuagint'] = True
            n += 1
    logger.info(f'[LXX_PIVOT] annotated {n}/{len(results)} results with Hebrew refs')
    return results
