"""Punctuation and spacing diacritics inside the Greek Unicode blocks must not
ride along on a word (2026-10-01). The Septuagint text writes "αὐτοῦ·" with an
ano teleia and "᾿Ισραήλ" with a spacing breathing before the capital; the
index held "αυτου·" and "᾿ισραηλ" as tokens and lemmatized them as themselves.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.text_processor import TextProcessor  # noqa: E402


def test_ano_teleia_is_a_boundary_not_a_letter():
    tokens = TextProcessor().tokenize_greek('καὶ εἶπεν αὐτοῦ· ἐγὼ')
    assert tokens == ['καὶ', 'εἶπεν', 'αὐτοῦ', 'ἐγὼ']


def test_spacing_breathing_before_a_capital_is_dropped():
    original, tokens = TextProcessor().tokenize_greek('ἐν ᾿Ισραήλ ᾿Ιδοὺ', preserve_case=True)
    assert all(not t.startswith('᾿') for t in original)
    assert all(not t.startswith('᾿') for t in tokens)
    assert len(tokens) == 3


def test_greek_question_mark_and_middle_dot_split_words():
    tokens = TextProcessor().tokenize_greek('τί λέγεις; οὐδέν·ἄλλο')
    assert tokens == ['τί', 'λέγεις', 'οὐδέν', 'ἄλλο']


def test_ordinary_text_is_unchanged():
    assert TextProcessor().tokenize_greek('μῆνιν ἄειδε θεὰ Πηληϊάδεω') == ['μῆνιν', 'ἄειδε', 'θεὰ', 'πηληϊάδεω']
