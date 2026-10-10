"""Closeness fields on Line Search hits (owner's review 2026-10-10: a
four-word query put lines sharing one word on top; the default should be a
near quotation)."""
from backend.app import _is_near_quotation


def test_all_words_adjacent_is_a_quotation():
    q = {'sum', 'tu', 'terra', 'levis'}
    assert _is_near_quotation(q, q, [3, 4, 5, 6], 'sit tibi terra levis')


def test_all_words_within_two_extra_tokens_is_a_quotation():
    q = {'terra', 'levis'}
    assert _is_near_quotation(q, q, [2, 5], 'terra levis')  # width 4 <= 2 + 2


def test_all_words_scattered_is_not():
    q = {'terra', 'levis'}
    assert not _is_near_quotation(q, q, [0, 9], 'terra levis')


def test_missing_a_word_is_not():
    assert not _is_near_quotation({'terra'}, {'terra', 'levis'}, [0], 'terra levis')


def test_one_word_query_is_never_a_quotation():
    assert not _is_near_quotation({'terra'}, {'terra'}, [0], 'terra')


def test_no_positions_is_not():
    q = {'terra', 'levis'}
    assert not _is_near_quotation(q, q, [], 'terra levis')
