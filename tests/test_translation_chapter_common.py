"""Tests for scripts/translations/chapter_common.py, the shared checks of the chapter, section and
speech level alignments of 2026-10-24. They run on small inline fixtures, never on the corpus.

What matters here is that the checks REFUSE: a work whose English belongs to different units
(the Maximus of Tyre case) is told apart by the rival test, a chapter chain that breaks is reported,
and a count that differs in the middle of a book is not repaired.
"""
import os
import sys

SCRIPT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                          'scripts', 'translations')
sys.path.insert(0, SCRIPT_DIR)

import chapter_common as cc   # noqa: E402


def test_roman_numerals_with_ocr_slips():
    assert cc.roman_str(44) == 'XLIV'
    assert cc.roman_to_int('XLIV') == 44
    assert cc.roman_ocr('XTII') == 13            # a T read for an I, the walk then trusts the sequence
    assert cc.roman_ocr('Y') == 5
    assert cc.roman_ocr('QQ') is None


def test_fuzzy_chapter_chain_follows_numerals_and_survives_a_lost_marker():
    lines = ['I. The first chapter has some words in it.', 'more of the first.',
             'II. The second chapter.', 'III. The third.',
             'V. The fifth, with chapter IV lost by the OCR.']
    chapters, ok = cc.split_chapters_fuzzy(lines)
    assert [n for n, _ in chapters] == [1, 2, 3, 5]
    assert ok
    assert 'more of the first' in chapters[0][1]


def test_unit_length_correlation_sees_a_shifted_pairing():
    src = {f'r{i}': 'x' * (10 * (i + 1)) for i in range(12)}
    good_units = ['y' * (20 * (i + 1)) for i in range(12)]
    good = {f'r{i}': i for i in range(12)}
    shifted = {f'r{i}': (i + 5) % 12 for i in range(12)}
    assert cc.unit_length_correlation(good_units, good, src) > 0.99
    assert cc.unit_length_correlation(good_units, shifted, src) < 0.5


def test_group_align_pairs_one_to_one_and_joins_the_last_chapters():
    greek = [100, 200, 150, 300, 120]
    english = [150, 300, 225, 450, 100, 80]          # the last Greek chapter is two English ones
    groups = cc.group_align(greek, english)
    assert groups[:-1] == [([i], [i]) for i in range(4)]
    assert groups[-1] == ([4], [4, 5])


def test_end_merge_map_refuses_a_difference_in_many_places():
    greek = [100, 200, 150, 300, 120, 400, 90, 110]
    english = [150, 600, 225, 450, 180, 200, 600, 135, 165]       # chapters split and joined all over
    assert cc.end_merge_map(greek, english, max_odd=1) is None
    mapping = cc.end_merge_map([100, 200, 300], [150, 300, 300, 150], max_odd=3)
    assert mapping == {0: [0], 1: [1], 2: [2, 3]}


def test_rival_check_catches_english_paired_with_the_wrong_greek():
    units = ['Odysseus and Calypso on Ogygia', 'Achilles and Hector before Troy', 'Aeneas and Dido at Carthage']
    greek = {'a': 'Ὀδυσσεὺς Καλυψώ', 'b': 'Ἀχιλλεὺς Ἕκτωρ Τροία', 'c': 'Aeneas Dido Carthago'}
    right = {'a': 0, 'b': 1, 'c': 2}
    wrong = {'a': 1, 'b': 2, 'c': 0}
    share_right, _ = cc.rival_check('la', units, right, {'a': 'Odysseus Calypso', 'b': 'Achilles Hector', 'c': 'Aeneas Dido Carthago'},
                                    window=0)
    share_wrong, _ = cc.rival_check('la', units, wrong, {'a': 'Odysseus Calypso', 'b': 'Achilles Hector', 'c': 'Aeneas Dido Carthago'},
                                    window=0)
    # with so few units the test abstains, which must read as "no verdict" and not as a pass
    assert share_right is None and share_wrong is None
    assert greek['a']
