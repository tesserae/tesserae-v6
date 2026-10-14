"""The documents search answers a mid-length query from one index lookup
(2026-10-11): the in-N-documents count is read off the candidates already
fetched, and the distance limit is asked once per bucket file."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import backend.app  # noqa: E402,F401  (the application must be built first)
from backend.blueprints import documents as A  # noqa: E402  (the helpers live here now)
import backend.documents as docs  # noqa: E402
from test_documents_stage3b3 import documents_app_env, _post  # noqa: E402,F401


def _counter(everyone, min_matched=2, cache=None):
    doc_ids = {(f, r): r.split(' ')[0] for f, r, _m in everyone}
    return A._DocumentFormulaCounter('la', everyone, doc_ids, min_matched,
                                     {} if cache is None else cache)


def test_counter_counts_documents_holding_every_lemma_of_the_set():
    everyone = [
        ('f1', 'D1 1', {'a', 'b', 'c'}),
        ('f1', 'D1 2', {'a', 'b'}),      # same document as above: counted once
        ('f2', 'D2 1', {'a', 'b'}),
        ('f2', 'D3 1', {'b', 'c'}),
        ('f3', 'D4 1', {'a', 'c'}),
    ]
    c = _counter(everyone)
    assert c.count({'a', 'b'}) == 2        # D1, D2
    assert c.count({'b', 'c'}) == 2        # D1, D3
    assert c.count({'a', 'b', 'c'}) == 1   # D1
    assert c.count({'a', 'c'}) == 2        # D1, D4
    assert c.count(set()) is None


def test_counter_ignores_candidates_without_a_document():
    c = A._DocumentFormulaCounter('la', [('f', 'X 1', {'a', 'b'})], {('f', 'X 1'): None}, 2, {})
    assert c.count({'a', 'b'}) == 0


def test_counter_prefers_a_seeded_value():
    c = _counter([('f', 'D1 1', {'a', 'b'})], cache={frozenset({'a', 'b'}): 99})
    assert c.count({'a', 'b'}) == 99


def test_counter_equals_the_lookup_it_replaces(documents_app_env):
    r = _post({'query': 'dis manibus avis', 'language': 'la', 'collection': 'documents'})
    results = r.get_json()['results']
    assert results
    for row in results:
        reference = A._documents_formula_count('la', set(row['matched_lemmas']), {})
        assert row['formula_count'] == reference


def test_distance_limit_is_asked_once_per_file(monkeypatch):
    positions = {'a': [0], 'b': [3]}
    rows = [('f1', f'D{i} 1', {'a', 'b'}, positions) for i in range(5)]
    rows += [('f2', f'E{i} 1', {'a', 'b'}, positions) for i in range(5)]
    monkeypatch.setattr(docs, 'find_co_occurring_lemmas', lambda *a, **k: rows)
    calls = []
    import backend.distance_filter as df
    monkeypatch.setattr(df, 'get_max_distance',
                        lambda filename, language: calls.append(filename) or (2 if filename == 'f1' else 5))
    matches, everyone = A._lemma_candidates('la', {'a', 'b'}, 2)
    assert sorted(calls) == ['f1', 'f2']
    assert len(everyone) == 10                       # the count sees the pre-distance set
    assert {m['filename'] for m in matches} == {'f2'}  # f1 is too far apart (3 > 2)
