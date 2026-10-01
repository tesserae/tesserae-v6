"""Homographs told apart by their vowel points (#483).

One consonantal spelling often covers several Hebrew words. The lemmatizer
now looks a word up by its pointed form first, and homographs carry a
superscript numeral in order of BHSA frequency. These tests run against the
real tables in data/lemma_tables, with Stanza off.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest  # noqa: E402

from backend.hebrew import processor  # noqa: E402
from backend.hebrew.processor import (  # noqa: E402
    HebrewLanguageHandler, base_lemma, is_hebrew_lemma, lemmatize_hebrew,
    pointed_key, get_pos_tags)
from backend.hebrew.stopwords import HEBREW_STOP_WORDS  # noqa: E402


@pytest.fixture(autouse=True)
def no_stanza(monkeypatch):
    monkeypatch.delenv('TESSERAE_HEBREW_STANZA', raising=False)
    monkeypatch.setattr(processor, '_stanza_nlp', False)


# --- the key -----------------------------------------------------------------

def test_key_keeps_vowels_and_drops_accents():
    # Genesis 1:1 בְּרֵאשִׁ֖ית with its tipcha accent
    assert pointed_key('בְּרֵאשִׁ֖ית') == pointed_key('בְּרֵאשִׁית')
    assert pointed_key('בְּרֵאשִׁית') != pointed_key('בראשית')


def test_key_folds_the_two_ways_of_writing_holam_waw():
    # BHSA writes lamed + holam + waw, Sefaria lamed + waw + holam
    assert pointed_key('לֹו') == pointed_key('לוֹ')


def test_key_ignores_dagesh_and_meteg():
    assert pointed_key('הַיּוֹם') == pointed_key('הַיוֹם')
    assert pointed_key('לָֽמֶךְ') == pointed_key('לָמֶךְ')


def test_key_of_an_unpointed_word_is_its_consonants():
    assert pointed_key('אל') == 'אל'


# --- homographs --------------------------------------------------------------

def test_el_to_el_not_and_el_god_are_three_lemmas():
    to, not_, god = lemmatize_hebrew(['אֶל', 'אַל', 'אֵל'])
    assert to == 'אל'
    assert not_ == 'אל²'
    assert god == 'אל³'


def test_the_unpointed_form_takes_the_majority_reading():
    assert lemmatize_hebrew(['אל']) == ['אל']
    assert lemmatize_hebrew(['עם']) == ['עם']          # "people", 1,866 to 1,049


def test_with_and_people_are_told_apart():
    assert lemmatize_hebrew(['עִם', 'עַם']) == ['עם²', 'עם']


def test_king_and_reigned_are_told_apart():
    # 2 Samuel 5:5: both מלך are the verb, tagged NOUN before this change
    assert lemmatize_hebrew(['מֶלֶךְ', 'מָלַךְ']) == ['מלך', 'מלך²']
    assert get_pos_tags(['מֶלֶךְ', 'מָלַךְ']) == ['NOUN', 'VERB']


def test_a_prefixed_pointed_word_is_looked_up_without_its_prefix():
    # וְאֵל "and God": the conjunction's own vowel goes with it
    assert lemmatize_hebrew(['וְאֵל']) == ['אל³']
    # בַּיּוֹם "on the day": prefix stripped, pointed stem found
    assert lemmatize_hebrew(['בַּיּוֹם']) == ['יום']


def test_accents_in_the_text_do_not_block_the_pointed_lookup():
    assert lemmatize_hebrew(['אֵ֣ל']) == ['אל³']


# --- the handler sends the pointed tokens -------------------------------------

def test_handler_lemmatizes_from_the_pointed_text():
    # Psalm 18:3 (BHS 18:3): אֵלִי צוּרִי, "my God, my rock". The consonantal
    # אלי is also "to me"; the points say God.
    original, tokens, lemmas, tags, variants = HebrewLanguageHandler().tokenize_and_lemmatize(
        '<hebrew_bible.psalms.18.3>\tאֵלִ֣י צ֭וּרִי')
    assert tokens == ['אלי', 'צורי']
    assert lemmas[0] == 'אל³'
    assert len(lemmas) == len(tags) == len(variants) == 2


# --- helpers used elsewhere ---------------------------------------------------

def test_base_lemma_strips_the_numeral_only():
    assert base_lemma('אל³') == 'אל'
    assert base_lemma('אל') == 'אל'
    assert base_lemma('') == ''


def test_is_hebrew_lemma_accepts_the_numeral_and_rejects_artifacts():
    assert is_hebrew_lemma('אל³')
    assert is_hebrew_lemma('מלך')
    assert not is_hebrew_lemma('אל-')
    assert not is_hebrew_lemma('12')
    assert not is_hebrew_lemma('אל³³')


def test_stoplist_stops_the_function_readings_and_not_the_content_ones():
    # the preposition and the negative, not God
    assert 'אל' in HEBREW_STOP_WORDS and 'אל²' in HEBREW_STOP_WORDS
    assert 'אל³' not in HEBREW_STOP_WORDS
    # "with", not "people"; "there", not "name"
    assert 'עם²' in HEBREW_STOP_WORDS and 'עם' not in HEBREW_STOP_WORDS
    assert 'שם²' in HEBREW_STOP_WORDS and 'שם' not in HEBREW_STOP_WORDS
    # "even", not "nose"; "opposite", not "report"
    assert 'אף²' in HEBREW_STOP_WORDS and 'אף' not in HEBREW_STOP_WORDS
    assert 'נגד²' in HEBREW_STOP_WORDS and 'נגד' not in HEBREW_STOP_WORDS
