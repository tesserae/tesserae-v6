"""Tests for scripts/documents/restoration_tokens.py, using small inline
fixtures (no network, no corpus data)."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scripts.documents.restoration_tokens import (
    GAP_PLACEHOLDER as GAP,
    tokenize_with_restoration,
)


def _flags(text, restored_spans):
    """Build a restored_flags list for `text`: True for every index whose
    0-based position falls in one of the (start, end) spans in
    restored_spans (end exclusive)."""
    flags = [False] * len(text)
    for start, end in restored_spans:
        for i in range(start, end):
            flags[i] = True
    return flags


def test_mid_word_gap_splits_into_two_fragments():
    text = "XXV" + GAP + "stipendiorum"
    flags = _flags(text, [(3, 4)])
    toks = tokenize_with_restoration(text, flags)
    assert [t.text for t in toks] == ["XXV", "stipendiorum"]
    assert all(t.fragment for t in toks)


def test_double_gap_mid_word_drops_both_gap_chars():
    text = "Vendon" + GAP + GAP + "i"
    flags = [False] * len(text)
    toks = tokenize_with_restoration(text, flags)
    assert [t.text for t in toks] == ["Vendon", "i"]
    assert all(t.fragment for t in toks)
    assert GAP not in "".join(t.text for t in toks)


def test_mixed_run_plus_clean_token():
    text = "Ca" + GAP + "nio Octavio"
    flags = [False] * len(text)
    toks = tokenize_with_restoration(text, flags)
    assert [t.text for t in toks] == ["Ca", "nio", "Octavio"]
    assert toks[0].fragment and toks[1].fragment
    assert not toks[2].fragment


def test_gap_only_token_dropped_but_position_kept():
    text = "Attedie " + GAP + " Cres"
    flags = [False] * len(text)
    toks = tokenize_with_restoration(text, flags)
    assert [t.text for t in toks] == ["Attedie", "Cres"]
    assert toks[0].gap_before == 0
    assert toks[1].gap_before == 1
    assert not toks[0].fragment and not toks[1].fragment


def test_restored_requires_strict_majority():
    # "D" with 1/1 chars restored -> restored.
    toks = tokenize_with_restoration("D", [True])
    assert toks[0].restored is True

    # "DM" with exactly half (1/2) restored -> NOT restored (needs > 0.5).
    toks = tokenize_with_restoration("DM", [True, False])
    assert toks[0].restored is False

    # "gloria" with 1/6 restored -> not restored.
    text = "gloria"
    flags = [True] + [False] * 5
    toks = tokenize_with_restoration(text, flags)
    assert toks[0].restored is False


def test_fully_restored_whole_word():
    toks = tokenize_with_restoration("manibus", [True] * 7)
    assert toks[0].restored is True
    assert toks[0].fragment is False
    assert toks[0].restored_share == 1.0


def test_multiple_lines_whitespace_only_split_on_single_run():
    text = "Dis Manibus"
    flags = [False] * len(text)
    toks = tokenize_with_restoration(text, flags)
    assert [t.text for t in toks] == ["Dis", "Manibus"]
