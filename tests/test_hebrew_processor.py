"""Hebrew tokenization and the Stanza fallback.

Jerusalem (#480): the pointed text writes Jerusalem with a combining grapheme
joiner (U+034F) between the patah and the hiriq under the lamed. The tokenizer
only accepted Hebrew-block characters, so it broke the word at the joiner: 562
spellings became `ירושל` + `ם`, Jerusalem was never lemmatized, and the index
carried 545 stray `ם` tokens.

Stanza fallback (#481): words missing from the BHSA table go to Stanza, which
splits a word into prefix, stem and suffix. Its words were matched to ours one
for one, so after the first split every lemma landed on the wrong word. These
tests use a fake Stanza that splits the way the real one does, so they run
without Stanza installed; one test checks the real pipeline when it is present.
"""
import sys
from pathlib import Path
from types import SimpleNamespace as NS

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest  # noqa: E402

from backend.hebrew import processor  # noqa: E402
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


# Words that miss the BHSA table, with the split real Stanza gives each one:
# (text, lemma, upos) per syntactic word.
STANZA_SPLITS = {
    'בעציון': [('ב', 'ב', 'ADP'), ('עציון', 'עציון', 'PROPN')],
    'רבשקה': [('רבשקה', 'רבשקה', 'PROPN')],
    'קברותיך': [('קברותי', 'קבר', 'NOUN'), ('ך', 'הוא', 'PRON')],
    'ותבאני': [('ו', 'ו', 'CCONJ'), ('תבאני', 'תבאני', 'PROPN')],
    'למ': [('למ', 'לם', 'ADP')],
}


def fake_stanza(splits=STANZA_SPLITS, shift=0):
    """A stand-in for the Stanza pipeline: one token per space-separated word,
    split into syntactic words as `splits` says. `shift` moves every token's
    character offsets, to imitate output that no longer lines up."""
    def nlp(text):
        tokens, start = [], 0
        for word in text.split(' '):
            parts = splits.get(word, [(word, word, 'PROPN')])
            tokens.append(NS(start_char=start + shift,
                             end_char=start + shift + len(word),
                             words=[NS(text=t, lemma=l, upos=u) for t, l, u in parts]))
            start += len(word) + 1
        return NS(sentences=[NS(tokens=tokens,
                                words=[w for tok in tokens for w in tok.words])])
    return nlp


@pytest.fixture
def stanza(monkeypatch):
    def use(nlp):
        monkeypatch.setattr(processor, '_stanza_nlp', nlp)
        monkeypatch.setattr(processor, '_stanza_cache', {})
    return use


def test_fixture_words_miss_the_table():
    table = processor._get_lemma_table()
    assert all(processor._lookup_lemma(w, table) is None for w in STANZA_SPLITS)


def test_several_misses_in_a_row_keep_their_own_lemmas(stanza):
    stanza(fake_stanza())
    words = ['בעציון', 'רבשקה', 'קברותיך', 'ותבאני']
    assert lemmatize_hebrew(words) == ['עציון', 'רבשקה', 'קבר', 'תבאני']


def test_misses_between_table_words_keep_their_own_lemmas(stanza):
    stanza(fake_stanza())
    # ויאמר and הארץ are table hits; only the other two go to Stanza.
    words = ['ויאמר', 'בעציון', 'הארץ', 'קברותיך']
    assert lemmatize_hebrew(words) == ['אמר', 'עציון', 'ארץ', 'קבר']


def test_a_suffix_does_not_become_the_lemma(stanza):
    # קברותיך "your graves" splits into קברותי + ך; the lemma is the noun,
    # not the pronoun Stanza reads the suffix as.
    stanza(fake_stanza())
    assert lemmatize_hebrew(['קברותיך']) == ['קבר']


def test_a_lone_function_word_keeps_its_lemma(stanza):
    stanza(fake_stanza())
    assert lemmatize_hebrew(['למ']) == ['לם']


def test_output_that_does_not_line_up_falls_back_to_the_word(stanza):
    stanza(fake_stanza(shift=1))
    assert lemmatize_hebrew(['בעציון', 'קברותיך']) == ['בעציון', 'קברותיך']


def test_without_stanza_misses_keep_their_form(stanza):
    stanza(False)
    assert lemmatize_hebrew(['ויאמר', 'בעציון']) == ['אמר', 'בעציון']


def test_a_word_gets_the_same_lemma_whatever_its_neighbours(stanza):
    # Real Stanza splits קברותיך when it is alone but not beside רבשקה, so
    # each word goes to Stanza on its own. This fake splits only a lone word.
    def context_sensitive(text):
        splits = STANZA_SPLITS if ' ' not in text else {}
        return fake_stanza(splits)(text)
    stanza(context_sensitive)
    assert lemmatize_hebrew(['רבשקה', 'קברותיך']) == ['רבשקה', 'קבר']
    assert lemmatize_hebrew(['קברותיך']) == ['קבר']


def test_real_stanza_keeps_lemmas_on_their_own_words(monkeypatch):
    monkeypatch.setattr(processor, '_stanza_nlp', None)
    monkeypatch.setattr(processor, '_stanza_cache', {})
    if processor._get_stanza() is None:
        pytest.skip('Stanza Hebrew pipeline not installed')
    lemmas = lemmatize_hebrew(['בעציון', 'רבשקה', 'לעציון', 'קברותיך'])
    assert lemmas[0] == lemmas[2] == 'עציון'
    assert lemmas[1] == 'רבשקה'
    assert lemmas[3] == 'קבר'
