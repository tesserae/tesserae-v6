"""Tests for the parts of scripts/documents/lemmatizer_gaps.py that do not
need the full backend.text_processor models loaded (is_roman_numeral,
build_name_candidates)."""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scripts.documents.lemmatizer_gaps import build_name_candidates, is_roman_numeral


def test_is_roman_numeral_accepts_irregular_epigraphic_forms():
    # Stage 1's own examples of irregular (non-subtractive) numerals.
    for tok in ["XXXX", "XXI", "XXXV", "CXVI", "LX", "IIII", "iiii", "Xvii"]:
        assert is_roman_numeral(tok), tok


def test_is_roman_numeral_rejects_real_words_outside_the_numeral_charset():
    for tok in ["Marcus", "filius", "manibus", ""]:
        assert not is_roman_numeral(tok), tok


def test_is_roman_numeral_charset_only_check_has_a_known_false_positive_risk():
    # "id", "dux", "lux" are real Latin words built entirely from letters
    # that also spell numerals (i/d, d/u/x, l/u/x). is_roman_numeral()
    # is a pure charset check and flags them too: this is a DOCUMENTED,
    # accepted limitation (see the function's own docstring), made safe
    # in the real pipeline only because it is applied exclusively to
    # tokens that already failed ordinary dictionary lookup, where a
    # common word like "id" or "dux" would already have resolved before
    # ever reaching this check.
    assert is_roman_numeral("id")
    assert is_roman_numeral("dux")
    assert is_roman_numeral("lux")


def test_is_roman_numeral_accepts_v_or_u_spelling():
    assert is_roman_numeral("XVII")
    assert is_roman_numeral("XUII")  # classical v/u interchange


def test_build_name_candidates_from_toy_corpus(tmp_path):
    path = tmp_path / "toy.jsonl"
    # "Lucius" capitalized every time (3/3); "filius" always lowercase;
    # "Terra" capitalized only 1 of 3 times (not a name candidate at the
    # 0.9 share threshold).
    records = [
        {"text": "Lucius Satrienus filius terra"},
        {"text": "Lucius Vettius filius Terra"},
        {"text": "Lucius Marius filius terra"},
    ]
    with open(path, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")

    candidates = build_name_candidates([str(path)], min_count=2, min_capitalized_share=0.9)
    assert "lucius" in candidates
    assert candidates["lucius"]["count"] == 3
    assert candidates["lucius"]["capitalized_share"] == 1.0
    assert "filius" not in candidates
    assert "terra" not in candidates  # only 1/3 capitalized, below threshold
