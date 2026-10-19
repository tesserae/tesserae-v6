"""Tests for the documents formula-word rank step and the hide_formulas
early drop (2026-10-19).

The rank step: a hit whose matched lemmas all belong to the lemmas of
data/documents/formula_words_<language>.txt sorts behind every hit that
matched something else, under the default 'relevance' sort only.

The early drop: with hide_formulas set and no other filter, hits above the
threshold are counted and removed before their metadata is fetched. Results
and formulas_hidden_count must equal the single-path outcome.

Builds its own tiny fixture documents index with the same helpers as
tests/test_documents_stage4_polish.py. No corpus data, no network.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import backend.documents as docs
from backend.blueprints import documents as bd
from test_documents_stage4_polish import (
    _build_index, _line, _make_metadata_db, _point_env, _post, _rec,
)


def test_formula_word_lists_load_for_latin_greek_and_coptic():
    docs.reset_caches()
    for lang in ('la', 'grc', 'cop'):
        words = docs.formula_words(lang)
        assert words, lang
        assert all(not w.startswith('#') and w == w.strip() for w in words)
    assert {'manibus', 'dis', 'vixit'} <= docs.formula_words('la')
    assert 'ἔτους' in docs.formula_words('grc')
    assert docs.formula_words('xx') == frozenset()


def test_coptic_list_is_made_of_function_words_only():
    from backend.coptic.stopwords import COPTIC_STOP_WORDS
    assert docs.formula_words('cop') <= set(COPTIC_STOP_WORDS)


def test_is_formula_only():
    stock = frozenset({'deus', 'manus'})
    assert bd._is_formula_only({'deus', 'manus'}, stock)
    assert bd._is_formula_only({'manus'}, stock)
    assert not bd._is_formula_only({'manus', 'caesar'}, stock)
    assert not bd._is_formula_only(set(), stock)


def test_formula_lemmas_cover_the_list_words():
    docs.reset_caches()
    lemmas = bd._formula_lemmas('la')
    assert {'deus', 'manus'} <= lemmas
    assert 'caesar' not in lemmas


def test_sort_key_puts_formula_only_hits_last_in_relevance_only():
    base = {'adjacency': 0, 'restored_rank': 0, 'extra_restorations': 0,
            'date': None, 'region': None}
    stock = dict(base, formula_only=True, doc_id='a')
    other = dict(base, formula_only=False, doc_id='b', adjacency=1)
    assert bd._document_sort_key('relevance', other) < bd._document_sort_key('relevance', stock)
    # the date and region sorts ignore the flag
    assert bd._document_sort_key('region', stock) < bd._document_sort_key('region', other)
    assert bd._document_sort_key('oldest', stock) < bd._document_sort_key('oldest', other)
    # a rank dict without the key (older callers) is treated as not formula-only
    assert bd._document_sort_key('relevance', {k: v for k, v in other.items()
                                                if k != 'formula_only'})


@pytest.fixture
def formula_env(tmp_path, monkeypatch):
    """B is an adjacent "Dis Manibus" (stock words only) and A has the
    query's other word with "manibus" two tokens apart. By adjacency alone B
    leads, with the formula penalty A leads. Four more "Dis Manibus" lines
    give the formula count something to exceed."""
    recs = [
        _rec("edh:A", "edh", [_line(1, "Caesaris pro manibus")]),
        _rec("edh:B", "edh", [_line(1, "Dis Manibus")]),
    ] + [_rec(f"edh:S{i}", "edh", [_line(1, "Dis Manibus")]) for i in range(4)]
    index_dir = _build_index(tmp_path, recs)
    metadata_db = os.path.join(tmp_path, "metadata.db")
    _make_metadata_db(metadata_db, [
        {"id": r["id"], "collection": "documents", "source": "edh", "principal_edition": r["id"]}
        for r in recs])
    _point_env(monkeypatch, tmp_path, index_dir, metadata_db)
    yield
    docs.reset_caches()


def test_a_hit_with_a_distinctive_word_outranks_a_formula_only_hit(formula_env):
    data = _post({'query': 'dis manibus Caesaris'}).get_json()
    order = [row['doc_id'] for row in data['results']]
    assert order[0] == 'edh:A'
    assert set(order[1:]) == {'edh:B'} | {f'edh:S{i}' for i in range(4)}


def test_without_the_penalty_the_adjacent_formula_hit_would_lead(formula_env, monkeypatch):
    monkeypatch.setattr(bd, '_is_formula_only', lambda m, f: False)
    data = _post({'query': 'dis manibus Caesaris'}).get_json()
    assert data['results'][0]['doc_id'] != 'edh:A'


def test_date_sort_is_not_touched_by_the_penalty(formula_env):
    a = _post({'query': 'dis manibus Caesaris', 'sort': 'newest'}).get_json()
    assert len(a['results']) == 6


def test_early_drop_gives_the_same_results_and_count_as_the_single_path(formula_env, monkeypatch):
    out = {}
    for name, floor in (('early', 1), ('single', 10 ** 9)):
        monkeypatch.setattr(bd, '_FORMULA_PREHIDE_MIN', floor)
        out[name] = _post({'query': 'dis manibus Caesaris', 'hide_formulas': 2}).get_json()
    for key in ('total', 'formulas_hidden_count', 'documents_by_source_region'):
        assert out['early'].get(key) == out['single'].get(key), key
    assert [r['doc_id'] for r in out['early']['results']] == [r['doc_id'] for r in out['single']['results']]
    assert out['early']['formulas_hidden_count'] == 5
    assert [r['doc_id'] for r in out['early']['results']] == ['edh:A']


def test_early_drop_is_skipped_when_a_filter_is_active(formula_env, monkeypatch):
    monkeypatch.setattr(bd, '_FORMULA_PREHIDE_MIN', 1)
    a = _post({'query': 'dis manibus Caesaris', 'hide_formulas': 2, 'region': 'testregio'}).get_json()
    monkeypatch.setattr(bd, '_FORMULA_PREHIDE_MIN', 10 ** 9)
    b = _post({'query': 'dis manibus Caesaris', 'hide_formulas': 2, 'region': 'testregio'}).get_json()
    assert a['formulas_hidden_count'] == b['formulas_hidden_count']
    assert [r['doc_id'] for r in a['results']] == [r['doc_id'] for r in b['results']]
