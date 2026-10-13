"""Characterization tests for backend/distance_filter.py.

Expected values come from running the current code and reading each one.

Whether a text is prose is decided by file-name markers and, failing those,
by reading the text file from the texts folder. The second step would make
the answer depend on which machine runs the test, so the fixture below turns
it off: only the name-based tiers are in play, and CI (which has no texts)
gives the same answers as a developer machine.
"""
import pytest

import backend.utils as utils
from backend import distance_filter as df


@pytest.fixture(autouse=True)
def no_text_files(monkeypatch):
    monkeypatch.setattr(utils, '_resolve_text_filepath', lambda *a, **k: None)


POETRY = 'vergil.aeneid.tess'
PROSE = 'cicero.in_catilinam.tess'


def test_limits():
    assert df.POETRY_MAX_DISTANCE == 10 and df.PROSE_MAX_DISTANCE == 4


@pytest.mark.parametrize('text_id,lang,prose', [
    (PROSE, 'la', True),                    # Cicero is on the prose list
    ('livy.ab_urbe_condita.tess', 'la', True),
    (POETRY, 'la', False),
    ('homer.iliad.tess', 'grc', False),
    ('plato.republic.tess', 'grc', True),
    ('milton.paradise_lost.tess', 'en', False),
    ('', 'la', False),                      # no id: treated as poetry
    (None, 'la', False),
])
def test_is_prose_text(text_id, lang, prose):
    assert df.is_prose_text(text_id, lang) is prose


def test_get_max_distance():
    assert df.get_max_distance(POETRY) == 10
    assert df.get_max_distance(PROSE) == 4
    assert df.get_max_distance('plato.republic.tess', 'grc') == 4
    assert df.get_max_distance('') == 10


def test_normalize_greek():
    assert df.normalize_greek('Ἄνδρα') == 'ανδρα'            # accents and breathings gone, lower case
    assert df.normalize_greek('μοῦσα,') == 'μουσα'           # punctuation dropped
    assert df.normalize_greek('Ἄνδρα, μοι 12!') == 'ανδραμοι12'   # digits kept, spaces dropped
    assert df.normalize_greek('') == ''


def test_normalize_latin_is_the_shared_fold():
    assert df.normalize_latin('Iam') == 'iam'               # lower case
    assert df.normalize_latin('jam') == 'iam'               # iam and jam fold to the same key
    assert df.normalize_latin('Virum') == 'uirum'           # v to u
    assert df.normalize_latin('servom') == 'seruom'         # -om is NOT folded here
    assert df.normalize_latin('') == ''


# ---- calculate_match_distance ----------------------------------------------

@pytest.mark.parametrize('text,matched,lang,expected', [
    # Latin
    ('arma virumque cano troiae qui primus ab oris', ['arma', 'cano'], 'la', 2),   # one word between
    ('Iam uirum iam arma', ['jam', 'virum'], 'la', 1),       # j/i and u/v folded; nearest pair counts
    ('cano arma cano uirum', ['cano', 'uirum'], 'la', 1),    # repeated word: the closer occurrence
    ('arma virumque cano', ['arma', 'absent'], 'la', 0),     # one matched word missing: no pair
    ('arma virumque cano', ['arma', 'virum'], 'la', 0),      # virum is not virumque: no pair
    ('arma virumque cano', ['arma'], 'la', 0),               # fewer than two matched words
    ('', ['a', 'b'], 'la', 0),                               # empty text
    ('arma virumque cano', [], 'la', 0),
    # Greek
    ('ἄνδρα μοι ἔννεπε μοῦσα πολύτροπον', ['ἄνδρα', 'μοῦσα'], 'grc', 3),
    ('ἀνδρα μοι ἐννεπε μουσα', ['ανδρα', 'μουσα'], 'grc', 3),   # accents do not matter
    # English
    ('Sing, heavenly Muse, that on the secret top', ['sing', 'muse'], 'en', 2),   # case and comma ignored
    ('Sing, heavenly Muse, that on the secret top', ['Sing', 'top'], 'en', 7),    # far apart
    ('Sing, heavenly Muse', ['sing', 'sing'], 'en', 0),      # the same word twice is one word
    ('virum arma', ['arma', 'virum'], 'en', 1),              # adjacent
])
def test_calculate_match_distance(text, matched, lang, expected):
    assert df.calculate_match_distance(text, matched, lang) == expected


def test_match_distance_english_keeps_v_and_u_apart():
    # Only Latin is folded: in English, "virum" and "uirum" are different words.
    assert df.calculate_match_distance('uirum arma', ['virum', 'arma'], 'en') == 0
    assert df.calculate_match_distance('uirum arma', ['virum', 'arma'], 'la') == 1


# ---- passes_distance_filter, exactly at the limits -------------------------

def _line(gap):
    """'a' and 'b' with `gap` filler words between: distance is gap + 1."""
    return ' '.join(['a'] + ['x'] * gap + ['b'])


@pytest.mark.parametrize('distance,prose_ok,poetry_ok', [
    (3, True, True),
    (4, True, True),       # prose limit itself passes
    (5, False, True),      # one over the prose limit
    (10, False, True),     # poetry limit itself passes
    (11, False, False),    # one over the poetry limit
])
def test_passes_distance_filter_boundaries(distance, prose_ok, poetry_ok):
    text = _line(distance - 1)
    assert df.calculate_match_distance(text, ['a', 'b'], 'en') == distance
    assert df.passes_distance_filter(text, ['a', 'b'], PROSE, 'la') is prose_ok
    assert df.passes_distance_filter(text, ['a', 'b'], POETRY, 'la') is poetry_ok


def test_passes_filter_when_nothing_to_measure():
    assert df.passes_distance_filter('anything', [], PROSE) is True           # no matches
    assert df.passes_distance_filter('anything', ['a'], PROSE) is True        # one match
    assert df.passes_distance_filter('arma cano', ['zzz', 'yyy'], PROSE) is True   # distance 0 passes
    assert df.passes_distance_filter(_line(30), ['a', 'b'], '', 'la') is False     # poetry limit, far apart
