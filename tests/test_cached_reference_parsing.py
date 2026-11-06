"""The reference parsers remember their answers and return what they always did (2026-10-27)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backend import fusion  # noqa: E402
from backend.utils import format_short_locus  # noqa: E402


def test_parse_ref_values():
    assert fusion.parse_ref('verg. aen. 6.268') == (6, 268)
    assert fusion.parse_ref('verg. aen. 6.268') == (6, 268)
    assert fusion.parse_ref('hafez 7') == (None, None)


def test_parse_range_ref_values():
    assert fusion.parse_range_ref('luc. 1.1-luc. 1.2') == (1, 1, 2)
    assert fusion.parse_range_ref('luc. 1.1-luc. 2.2') == (1, 1, 1)
    assert fusion.parse_range_ref('luc. 3.9') == (3, 9, 9)
    assert fusion.parse_range_ref('none') == (None, None, None)


def test_format_short_locus_values_and_odd_arguments():
    assert format_short_locus('hebrew_bible.isaiah.34.11') == '34.11'
    assert format_short_locus('hebrew_bible.isaiah.34.11') == '34.11'
    assert format_short_locus('hamlet III.1.66') == 'III.1.66'
    assert format_short_locus('') == ''
    assert format_short_locus(None) == ''
    from backend.utils import _format_short_locus
    for odd in (['1.5'], 1, True, 1.0, {'a': 1}):
        assert format_short_locus(odd) == _format_short_locus(odd)
    assert format_short_locus(True) == _format_short_locus(True)
    assert format_short_locus(1) == '1'
