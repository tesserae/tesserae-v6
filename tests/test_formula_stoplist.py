"""Tests for scripts/documents/formula_stoplist.py."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scripts.documents.formula_stoplist import build_doc_frequencies, classify, tokenize


def test_tokenize_drops_gap_placeholder_and_digits():
    words = tokenize("Dis█Manibus annos12 XVII")
    assert "dis" in words
    assert "manibus" in words
    assert "xvii" in words
    assert all("█" not in w for w in words)
    assert all(not any(c.isdigit() for c in w) for w in words)


def test_classify_latin_formula_and_function():
    assert classify("la", "dis") == (True, False, False)
    assert classify("la", "et") == (False, True, False)
    assert classify("la", "xvii") == (False, False, True)
    assert classify("la", "marcus") == (False, False, False)


def test_classify_greek_matches_through_accents():
    # "ετη" (unaccented, in GREEK_FORMULA) must match the accented
    # surface form "ἔτη" that the real corpus actually uses.
    formula, function, numeral = classify("grc", "ἔτη")
    assert formula is True
    formula2, _, _ = classify("grc", "καὶ")
    assert formula2 is False  # not a formula word, but...
    _, function2, _ = classify("grc", "καὶ")
    assert function2 is True


def test_classify_single_greek_letter_is_numeral_like():
    _, _, numeral = classify("grc", "ι")
    assert numeral is True
    _, _, numeral2 = classify("grc", "λογος")
    assert numeral2 is False


def test_build_doc_frequencies_counts_distinct_words_once_per_doc(tmp_path):
    path = tmp_path / "toy.jsonl"
    path.write_text(
        '{"id": "a", "languages": ["la"], "text": "dis manibus dis"}\n'
        '{"id": "b", "languages": ["la", "grc"], "text": "manibus kai"}\n'
        '{"id": "c", "languages": ["la,grc"], "text": "vixit"}\n',
        encoding="utf-8",
    )
    doc_freq, examples, doc_counts = build_doc_frequencies(str(path))
    # "dis" appears twice in doc a but counts as doc frequency 1.
    assert doc_freq["la"]["dis"] == 1
    assert doc_freq["la"]["manibus"] == 2  # docs a and b
    # "la,grc" comma-joined language entry is split into both buckets.
    assert doc_counts["la"] == 3
    assert doc_counts["grc"] == 2
    assert doc_freq["grc"]["kai"] == 1
