"""Characterization tests for the parts of backend/matcher.py no other test reaches.

The per-method list of what existing tests already cover is in the pull
request description. These cover the rest: Coptic transliteration and the
Coptic-Greek phonetic channel, the per-language sound defaults, the capped
candidate list, synonym loading, the function-word lists and the automatic
stoplist. Expected values come from running the current code and reading each.
"""
import math

import pytest

from backend import matcher as m


# ---- transliterate_coptic_to_greek -----------------------------------------

@pytest.mark.parametrize('token,expected', [
    ('ⲡⲛⲟⲩⲧⲉ', 'πνουτε'),     # "the god": near one-to-one letter map
    ('ⲠⲚⲞⲨⲦⲈ', 'πνουτε'),     # capitals lower-cased first
    ('ϣⲟⲟⲡ', 'σοοπ'),         # shei maps to sigma
    ('ϥⲓ', 'φι'),             # fei maps to phi
    ('ϩⲱⲱϥ', 'ωωφ'),          # hori has no Greek counterpart and is dropped
    ('ⲁ̅ⲃ', 'αβ'),            # the supralinear stroke (combining mark) is removed
    ('ⲭⲣⲓⲥⲧⲟⲥ', 'χριστοσ'),   # final sigma is plain sigma here
    ('abc,', 'abc,'),         # non-Coptic characters pass through
    ('', ''),
])
def test_transliterate_coptic_to_greek(token, expected):
    assert m.transliterate_coptic_to_greek(token) == expected


# ---- find_crosslingual_phonetic_matches_cop_grc ----------------------------

COP = [{'tokens': ['ⲡⲛⲟⲩⲧⲉ', 'ⲁⲩⲱ']}, {'tokens': []}]
GRC = [{'tokens': ['θεος', 'πνουτε', 'ὁ']}, {'tokens': ['λογος']}]
HIT = [{'source_original': 'ⲡⲛⲟⲩⲧⲉ', 'target_original': 'πνουτε',
        'source_token': 'πνουτε', 'target_token': 'πνουτε', 'similarity': 1.0}]


def test_cop_grc_matches_when_coptic_is_source():
    assert m.find_crosslingual_phonetic_matches_cop_grc(COP, GRC, 'cop', 'grc') == {(0, 0): HIT}


def test_cop_grc_keys_are_source_then_target_when_greek_is_source():
    # Greek unit 0 is the source now, so the key is (greek index, coptic index)
    assert m.find_crosslingual_phonetic_matches_cop_grc(GRC, COP, 'grc', 'cop') == {(0, 0): HIT}


def test_cop_grc_wrong_pair_and_threshold():
    assert m.find_crosslingual_phonetic_matches_cop_grc(COP, GRC, 'la', 'grc') == {}      # not a Coptic-Greek pair
    assert m.find_crosslingual_phonetic_matches_cop_grc(COP, GRC, 'cop', 'la') == {}
    assert m.find_crosslingual_phonetic_matches_cop_grc([], [], 'cop', 'grc') == {}
    # identical after transliteration, so even a 0.99 threshold keeps it; a short token never enters
    assert m.find_crosslingual_phonetic_matches_cop_grc(COP, GRC, 'cop', 'grc', min_similarity=0.99) == {(0, 0): HIT}
    assert m.find_crosslingual_phonetic_matches_cop_grc(COP, GRC, 'cop', 'grc', min_token_len=7) == {}


# ---- get_sound_channel_defaults --------------------------------------------

def test_sound_channel_defaults():
    assert m.get_sound_channel_defaults('fa') == (0.05, 50)     # Arabic-script languages: looser gate, larger cap
    assert m.get_sound_channel_defaults('ur') == (0.05, 50)
    assert m.get_sound_channel_defaults('ar') == (0.05, 50)
    assert m.get_sound_channel_defaults('la') == (0.25, 10)     # everything else: the general default
    assert m.get_sound_channel_defaults(None) == (0.25, 10)


# ---- BoundedCandidates with a cap ------------------------------------------

def test_bounded_candidates_keeps_the_best_by_idf():
    src = [{'lemmas': ['a', 'b']}, {'lemmas': ['a']}]
    tgt = [{'lemmas': ['a', 'c']}]
    bc = m.BoundedCandidates(2, src, tgt)
    assert bc.total == 3 and dict(bc.freq) == {'a': 3, 'b': 1, 'c': 1}
    for lemmas in (['a'], ['b'], ['c'], ['a', 'b'], ['b', 'c']):
        bc.add({'matched_lemmas': lemmas, 'id': '-'.join(lemmas)})
    out = bc.result()
    # the common lemma 'a' scores lowest, so the two rarer pairs survive, best first
    assert [x['id'] for x in out] == ['b-c', 'a-b']
    assert out[0]['_quick_score'] == pytest.approx(2 * (math.log(4 / 2) + 1))
    assert len(out) == 2                                        # never more than the cap


def test_bounded_candidates_quick_score_unknown_lemma():
    bc = m.BoundedCandidates(1, [{'lemmas': ['a']}], [])
    # a lemma nobody has counts as frequency 1 (one more than zero would be 0): log(2/2)+1 = 1
    assert bc.quick_score(['zzz']) == pytest.approx(1.0)
    assert bc.quick_score([]) == 0


def test_bounded_candidates_first_come_kept_on_ties():
    bc = m.BoundedCandidates(1, [{'lemmas': ['a']}], [])
    bc.add({'matched_lemmas': ['a'], 'id': 'first'})
    bc.add({'matched_lemmas': ['a'], 'id': 'second'})           # equal score does not replace
    assert [x['id'] for x in bc.result()] == ['first']


# ---- Matcher.load_synonyms, function_words, build_stoplist_auto ------------

def test_load_synonyms(tmp_path):
    f = tmp_path / 'syn.tsv'
    f.write_text('arma\tbellum,proelium\nbad line without tab\nuir\thomo\n', encoding='utf-8')
    mt = m.Matcher()
    mt.load_synonyms(str(f))
    assert mt.synonym_dict == {'arma': {'bellum', 'proelium'}, 'uir': {'homo'}}   # the tab-less line is skipped
    mt.load_synonyms(str(tmp_path / 'missing.tsv'))               # a missing file changes nothing, raises nothing
    assert len(mt.synonym_dict) == 2


def test_function_words_per_language():
    assert m.Matcher.function_words('la') is m.DEFAULT_LATIN_STOP_WORDS
    assert m.Matcher.function_words('grc') is m.DEFAULT_GREEK_STOP_WORDS
    assert m.Matcher.function_words('en') is m.DEFAULT_ENGLISH_STOP_WORDS
    assert 'et' in m.Matcher.function_words('la') and 'est' in m.Matcher.function_words('la')
    assert len(m.Matcher.function_words('cop')) == 143            # the Coptic list as shipped
    assert len(m.Matcher.function_words('he')) == 58              # the Hebrew list as shipped
    assert m.Matcher.function_words('xx') == set()                # no list: empty set
    assert m.Matcher.function_words(None) == set()


def test_build_stoplist_auto_is_build_stoplist_on_source_and_target():
    units = [{'lemmas': ['et'] * 5 + ['arma'] * 2 + ['cano'], 'tokens': []}]
    mt = m.Matcher()
    auto = mt.build_stoplist_auto(units, units)
    assert auto == mt.build_stoplist(units, units, 'source_target', 'la')
    assert 'et' in auto                                           # the commonest lemma, also a function word
    assert m.DEFAULT_LATIN_STOP_WORDS <= auto                     # the curated list is always included
