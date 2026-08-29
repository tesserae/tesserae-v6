"""Regression tests for work-key and reference parsing in the passage index.

Both bugs were found by NC in one Coptic reading session (2026-08-29):
selections in shenoute.a22 answered "no indexed window covers that passage"
for every selection, and the selection header displayed lines 1-3 as
"22.1-22.3". Pure function tests; no index files required.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.passage_index import _norm_work, _ref_numbers, _ref_numbers_in


def test_norm_work_strips_tess_from_single_file_works():
    # The old behaviour stripped .tess only as a side effect of the .part
    # split, so single-file works never matched an index key.
    assert _norm_work('shenoute.a22.tess') == 'shenoute.a22'
    assert _norm_work('shenoute.a22') == 'shenoute.a22'


def test_norm_work_strips_language_directory():
    assert _norm_work('cop/shenoute.a22.tess') == 'shenoute.a22'
    assert _norm_work('la/vergil.aeneid.part.1.tess') == 'vergil.aeneid'


def test_norm_work_still_collapses_parts():
    assert _norm_work('vergil.aeneid.part.1.tess') == 'vergil.aeneid'
    assert _norm_work('hom.iliad.part.2') == 'hom.iliad'


def test_ref_numbers_in_ignores_digits_in_work_name():
    # Bare parsing gives (22, 1): the 22 is the work name's.
    assert _ref_numbers('shenoute.a22.1') == (22, 1)
    assert _ref_numbers_in('shenoute.a22', 'shenoute.a22.1') == (1,)
    assert _ref_numbers_in('shenoute.a22.tess', 'shenoute.a22.30') == (30,)


def test_ref_numbers_in_unchanged_for_ordinary_works():
    assert _ref_numbers_in('vergil.aeneid', 'verg. aen. 6.268') == (6, 268)
    assert _ref_numbers_in('bohairic.psalms',
                           'bohairic.psalms.10.3') == (10, 3)


def test_ref_numbers_in_window_rows_and_selection_agree():
    # The window row stores 'shenoute.a22.1'..'shenoute.a22.30'; a selection
    # of lines 1-3 must fall inside it under the same parsing.
    lo = _ref_numbers_in('shenoute.a22', 'shenoute.a22.1')
    hi = _ref_numbers_in('shenoute.a22', 'shenoute.a22.30')
    want = _ref_numbers_in('shenoute.a22.tess', 'shenoute.a22.2')
    assert lo <= want <= hi
