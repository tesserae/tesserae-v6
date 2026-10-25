"""Tests for the comparison rule of scripts/translations/align_plato_stephanus_rerun.py (Part H, 2026-10-25).

A re-aligned Plato file is a candidate for install only if its coverage is not lower, its names hit rate is not
lower by more than 0.02, and no unit lost English. The fixtures are tiny: one unit grew, one shrank.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'scripts', 'translations'))

import align_plato_stephanus_rerun as rr   # noqa: E402

OLD = {'a': 'one two three', 'b': 'four five six seven', 'c': 'eight nine'}


def test_grown_unit_counts_words_and_passes():
    new = {**OLD, 'a': 'one two three and the recovered tail'}
    cmp = rr.compare_units(OLD, new)
    assert cmp['grew'] == [('a', 4)] and not cmp['shrank'] and not cmp['lost']
    ok, why = rr.decide(0.95, 0.97, 0.80, 0.80, cmp)
    assert ok and why == []


def test_shrunk_unit_blocks_install():
    new = {**OLD, 'b': 'four five'}
    cmp = rr.compare_units(OLD, new)
    assert cmp['shrank'] == [('b', -2)]
    ok, why = rr.decide(0.95, 0.97, 0.80, 0.80, cmp)
    assert not ok and any('shrank' in w for w in why)


def test_lost_reference_gained_reference_and_coverage():
    new = {'a': OLD['a'], 'b': OLD['b'], 'd': 'a brand new unit'}
    cmp = rr.compare_units(OLD, new)
    assert cmp['lost'] == ['c'] and cmp['gained'] == ['d'] and cmp['words_gained'] == 4
    ok, why = rr.decide(1.0, 0.9, 0.8, 0.8, cmp)
    assert not ok and any('coverage' in w for w in why) and any('lost' in w for w in why)


def test_names_tolerance_is_two_hundredths():
    cmp = rr.compare_units(OLD, OLD)
    assert rr.decide(1.0, 1.0, 0.80, 0.79, cmp)[0]
    assert not rr.decide(1.0, 1.0, 0.80, 0.77, cmp)[0]
    assert rr.decide(1.0, 1.0, None, 0.5, cmp)[0]       # no earlier figure to compare with


def test_bare_page_number_takes_the_label_of_a_section_perseus_leaves_out():
    rec = {'chunks': [{'anchors': {'section': '234b'}, 'text': 'x'},
                      {'anchors': {'section': '235'}, 'text': 'y'},
                      {'anchors': {'section': '235a'}, 'text': 'z'}]}
    ours = ['234a', '234b', '234c', '235a']
    new, moved = rr.relabel_bare_chunks(rec, ours)
    assert moved == [('235', '234c')]
    assert [c['anchors']['section'] for c in new['chunks']] == ['234b', '234c', '235a']
    # no section of ours is missing: the bare number stays, and stephanus_text reads it as a tail
    _, moved2 = rr.relabel_bare_chunks(rec, ['234b', '235a'])
    assert moved2 == []
