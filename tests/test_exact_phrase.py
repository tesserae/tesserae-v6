"""Exact-phrase line-search matching (backend.utils.exact_phrase_pattern).

Guards the whole-word-START semantics: a query word must begin at a word
boundary (so it is not matched inside a longer word), but a trailing enclitic is
allowed (so "arma virum" still matches "arma virumque", the canonical arma-virum
reference match). Pure-regex; no app import.
"""
from backend.utils import exact_phrase_pattern


def _matches(query, text):
    p = exact_phrase_pattern(query)
    return bool(p and p.search(text))


def test_enclitic_is_kept_arma_virumque():
    # Reference test depends on this: exact "arma virum" must hit "arma virumque cano".
    assert _matches("arma virum", "arma virumque cano Troiae qui primus ab oris")
    assert _matches("arma virum", "arma virum tabulaeque et Troia gaza per undas")


def test_substring_inside_longer_word_is_excluded_aliquot():
    # The reported bug: "quot annis" must NOT match "aliquot annis".
    assert not _matches("quot annis", "his aliquot annis continuis fuit")
    # ...but the genuine phrase is kept.
    assert _matches("quot annis", "belloque superbum quot annis populum")


def test_leading_boundary_blocks_midword_and_run_together():
    assert not _matches("arma virum", "clamarma virumbus")   # mid-word junk
    assert not _matches("quot annis", "quotannis frumentum")  # run-together = different word


def test_case_insensitive_and_empty():
    assert _matches("arma virum", "ARMA VIRUMQUE")
    assert exact_phrase_pattern("") is None
    assert exact_phrase_pattern("   ") is None
