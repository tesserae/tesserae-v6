"""The Septuagint pivot's moving parts.

The pivot answers Hebrew-Greek biblical searches Greek-to-Greek against the
Septuagint and maps each hit back to the Hebrew verse. Two things here can be
wrong invisibly and are therefore pinned: the book map (a wrong entry pairs
one prophet's Greek with another prophet's Hebrew) and the Psalms verse
conversion (a wrong rule misnumbers a whole psalter silently).
"""
import os
import re

import pytest

from backend import lxx_pivot as L

TEXTS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'texts')


def test_every_routed_book_has_its_septuagint_file():
    """A map entry pointing at a text we do not hold would route searches into
    a FileNotFound at request time. Checked here instead."""
    missing = []
    for he, lxx in L.BOOKS.items():
        p = os.path.join(TEXTS, 'grc', f'septuaginta.{lxx}.tess')
        if not os.path.exists(p):
            missing.append((he, lxx))
    assert not missing, f'routed books without a Septuagint file: {missing}'


def test_excluded_books_do_not_route():
    for book in L.EXCLUDED:
        assert L.lxx_counterpart(f'hebrew_bible.{book}') is None


def test_lamentations_stays_excluded_until_the_greek_is_repaired():
    """The corpus's Septuagint Lamentations is defective (issue #276: 88 of
    150 lines are bare acrostic letters). Routing it would search a broken
    text. If this test fails because someone removed the exclusion, make sure
    the repair landed first."""
    assert 'lamentations' in L.EXCLUDED


def test_psalm_conversion_round_trips_over_the_real_psalter():
    """Every actual MT verse must survive MT -> LXX -> MT unchanged. Bounded
    by the real verse counts, because the merge/split rules are only defined
    on verses that exist."""
    path = os.path.join(TEXTS, 'he', 'hebrew_bible.psalms.tess')
    if not os.path.exists(path):
        pytest.skip('Hebrew psalms not present')
    counts = {}
    for line in open(path, encoding='utf-8'):
        m = re.match(r'^<hebrew_bible\.psalms\.(\d+)\.(\d+)>', line)
        if m:
            c, v = int(m.group(1)), int(m.group(2))
            counts[c] = max(counts.get(c, 0), v)
    bad = []
    for c, mx in counts.items():
        for v in range(1, mx + 1):
            lc, lv = L.hebrew_to_lxx_verse('psalms', c, v)
            back = L.lxx_to_hebrew_verse('psalms', lc, lv)
            if back != (c, v):
                bad.append((c, v, (lc, lv), back))
    assert not bad, f'{len(bad)} round-trip failures, first: {bad[:3]}'


def test_the_tsk_anchor_pair():
    """MT Psalm 118:6 is LXX Psalm 117:6, the anchor the TSK benchmarks were
    built on (Heb 13:6). If the conversion disagrees with the benchmark's own
    rule, every pivot result in the Psalms is off by a psalm."""
    assert L.hebrew_to_lxx_verse('psalms', 118, 6) == (117, 6)
    assert L.lxx_to_hebrew_verse('psalms', 117, 6) == (118, 6)


def test_non_psalm_books_are_identity():
    assert L.hebrew_to_lxx_verse('isaiah', 53, 1) == (53, 1)
    assert L.lxx_to_hebrew_verse('isaiah', 53, 1) == (53, 1)


def test_ref_rewrite_reads_urn_style_refs():
    """Septuagint refs carry a CTS URN; only the trailing chapter.verse
    matters, and the rewrite must survive the noise."""
    ref = 'septuaginta.psalmi urn:cts:greekLit:tlg0527.tlg027.1st1K-grc1.117.6'
    out = L.hebrew_ref_for_lxx_ref(ref, 'hebrew_bible.psalms', 'psalms')
    assert out == 'hebrew_bible.psalms.118.6'


def test_biblical_greek_profile_exists_and_greek_default_is_untouched():
    """The pivot asks for biblical_greek by name. The GREEK DEFAULT must stay
    latin_epic: classical Greek searches must not inherit quotation-heavy
    biblical weights because a profile was added for the pivot."""
    from backend import fusion
    assert 'biblical_greek' in fusion.WEIGHT_PROFILES
    assert fusion.get_weight_profile('grc') == fusion.WEIGHT_PROFILES['latin_epic']
    assert fusion.WEIGHT_PROFILES['biblical_greek']['quotation'] > 0
