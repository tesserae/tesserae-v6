"""The Hebrew cross-lingual dictionaries match lemmas written with final letters (#517).

hebrew_greek.csv and hebrew_latin.csv come from CATSS, which writes a word-final
kaf/mem/nun/pe/tsade in its medial form (אדונ). The Hebrew lemmatizer writes the
final form (אדון), so the loader has to convert the keys or those entries never match.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.blueprints.search import _find_csv_dictionary_matches


def _unit(lemmas):
    return {'lemmas': lemmas}


def test_he_grc_matches_final_form_lemma():
    # The CSV only has the medial spelling אדונ -> κυριοσ.
    matches = _find_csv_dictionary_matches(
        [_unit(['אדון'])], [_unit(['κυριοσ'])], 'he', 'grc')
    assert (0, 0) in matches
    assert matches[(0, 0)][0]['source_lemma'] == 'אדון'


def test_he_la_matches_final_form_lemma():
    matches = _find_csv_dictionary_matches(
        [_unit(['אדון'])], [_unit(['dominus'])], 'he', 'la')
    assert (0, 0) in matches


def test_grc_he_direction_matches_final_form_lemma():
    matches = _find_csv_dictionary_matches(
        [_unit(['κυριοσ'])], [_unit(['אדון'])], 'grc', 'he')
    assert (0, 0) in matches
    assert matches[(0, 0)][0]['target_lemma'] == 'אדון'


def test_medial_form_lemma_no_longer_a_key():
    # A lemma can never end in a medial letter, so nothing should key on one.
    matches = _find_csv_dictionary_matches(
        [_unit(['אדונ'])], [_unit(['κυριοσ'])], 'he', 'grc')
    assert matches == {}
