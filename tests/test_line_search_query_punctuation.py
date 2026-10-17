"""Punctuation on the ends of a query word does not reach the lemmatizer.

A Reader line is sent to Line Search as it stands ("Haec finis Priami
fatorum, hic exitus illum"), and lemmatize_word("fatorum,") returned the
token unchanged, so the word was lost from the search (2026-10-17).
"""
import os
import sys
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.blueprints import line_search as ls  # noqa: E402
from backend.line_search_params import _read_params  # noqa: E402


def test_query_words_strip_marks_at_the_ends_only():
    assert ls._query_words('Haec finis Priami fatorum, hic exitus illum') == [
        'Haec', 'finis', 'Priami', 'fatorum', 'hic', 'exitus', 'illum']
    assert ls._query_words('"arma virumque cano;"') == ['arma', 'virumque', 'cano']
    # An elision apostrophe at the end goes too, as the corpus tokenizer drops it.
    assert ls._query_words("δ' ἄρα, τοῖσι·") == ['δ', 'ἄρα', 'τοῖσι']
    assert ls._query_words('--- ...') == []
    # Hebrew vowel points are combining marks, not punctuation, and stay.
    assert ls._query_words('בְּרֵאשִׁית׃') == ['בְּרֵאשִׁית']


def test_lemma_path_lemmatizes_the_bare_words():
    p = _read_params({'query': 'fatorum, exitus;', 'language': 'la', 'search_type': 'lemma'})
    seen = []

    def fake(word, language):
        seen.append(word)
        return {word}

    with mock.patch.object(ls.text_processor, 'lemmatize_word', side_effect=fake):
        ls._query_lemmas(p)
    assert seen == ['fatorum', 'exitus']
