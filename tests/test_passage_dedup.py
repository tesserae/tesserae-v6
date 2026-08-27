"""Overlap dedup in Theme Search ranking: a pure-function regression suite.

Split out of test_theme_export.py deliberately. These need no index and no
database, so they RUN IN CI, which is where a regression in ranking would
otherwise go unnoticed until someone read a results page carefully.

The bug they exist for was found by the automated review on PR #269, which
flagged the tuple comparison as suspicious without knowing it already had a
victim in the live corpus.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.passage_index import _ref_coords  # noqa: E402


def overlaps(a_start, a_end, b_start, b_end):
    """The predicate _rank uses, in isolation."""
    lo1, hi1 = _ref_coords(a_start), _ref_coords(a_end)
    lo2, hi2 = _ref_coords(b_start), _ref_coords(b_end)
    return lo1 <= hi2 and lo2 <= hi1


def test_passages_in_different_books_do_not_count_as_overlapping():
    """The bug the PR review caught, with the victim it already had.

    _ref_numbers keeps only the last two numeric coordinates, so Ammianus
    'amm. 21.13.14' became (13, 14) and 'amm. 17.13.30' became (13, 30). The
    book was discarded, two passages four books apart compared as overlapping,
    and the dedup dropped one of them from a live Theme Search page without
    saying so.
    """
    assert not overlaps('amm. 21.13.14', 'amm. 21.16.13',
                        'amm. 17.13.30', 'amm. 17.14.3')


def test_a_real_overlap_inside_one_book_is_still_caught():
    """The other side of the fix. Caesar came back as both 2.31.6-2.35.4 and
    2.32.10-2.34.4, one wholly inside the other."""
    assert overlaps('caes. bel. civ. 2.31.6', 'caes. bel. civ. 2.35.4',
                    'caes. bel. civ. 2.32.10', 'caes. bel. civ. 2.34.4')


def test_adjacent_but_disjoint_spans_do_not_overlap():
    assert not overlaps('verg. aen. 6.1', 'verg. aen. 6.12',
                        'verg. aen. 6.13', 'verg. aen. 6.24')


def test_touching_spans_do_overlap():
    assert overlaps('verg. aen. 6.1', 'verg. aen. 6.12',
                    'verg. aen. 6.12', 'verg. aen. 6.24')


def test_single_number_references_still_work():
    """Persian and Urdu references carry one coordinate, not book.line."""
    assert _ref_coords('ferdowsi.diwan.27931') == (27931,)
    assert overlaps('ferdowsi.diwan.27931', 'ferdowsi.diwan.27942',
                    'ferdowsi.diwan.27935', 'ferdowsi.diwan.27950')
    assert not overlaps('ferdowsi.diwan.27931', 'ferdowsi.diwan.27942',
                        'ferdowsi.diwan.30000', 'ferdowsi.diwan.30010')
