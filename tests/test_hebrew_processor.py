"""Hebrew tokenization of Jerusalem (#480).

The pointed text writes Jerusalem with a combining grapheme joiner (U+034F)
between the patah and the hiriq under the lamed. The tokenizer only accepted
Hebrew-block characters, so it broke the word at the joiner: 562 spellings
became `ירושל` + `ם`, Jerusalem was never lemmatized, and the index carried
545 stray `ם` tokens.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.hebrew.processor import (lemmatize_hebrew, normalize_hebrew,  # noqa: E402
                                      tokenize_hebrew,
                                      tokenize_hebrew_with_variants)

CGJ = '\u034F'
# וּבִירוּשָׁלַ͏ִם, "and in Jerusalem", as texts/he spells it: patah, CGJ, hiriq.
AND_IN_JERUSALEM = 'וּבִירוּשָׁלַ' + CGJ + 'ִם'


def test_joiner_is_really_in_the_fixture():
    assert CGJ in AND_IN_JERUSALEM


def test_jerusalem_is_one_token():
    _, normalized = tokenize_hebrew(AND_IN_JERUSALEM)
    assert normalized == ['ובירושלם']


def test_jerusalem_lemmatizes_to_jerusalem():
    _, normalized = tokenize_hebrew(AND_IN_JERUSALEM)
    assert lemmatize_hebrew(normalized) == ['ירושלם']


def test_jerusalem_inside_a_verse_keeps_its_neighbours():
    # מֶלֶךְ בִּירוּשָׁלַ͏ִם שָׁנָה: the words around it stay separate tokens.
    verse = ('מֶלֶךְ '
             + AND_IN_JERUSALEM[2:]
             + ' שָׁנָה׃')
    _, normalized = tokenize_hebrew(verse)
    assert normalized == ['מלך', 'בירושלם', 'שנה']


def test_joiner_in_a_qere_is_removed_too():
    text = '(ירושלם) [' + AND_IN_JERUSALEM + ']'
    _, normalized, variants = tokenize_hebrew_with_variants(text)
    assert normalized == ['ובירושלם']
    assert variants == [['ירושלם']]


def test_normalize_removes_the_joiner():
    # A pointed Jerusalem pasted into a search box looks up like the index.
    assert normalize_hebrew(AND_IN_JERUSALEM) == 'ובירושלם'
