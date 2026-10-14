"""Windows of scale "prose": a work that has them is ranked, covered and mapped at
that scale, and its fine windows are left out; other works are unchanged."""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backend import passage_index as pi  # noqa: E402

TAC = 'tacitus.annales.part.1'
OTH = 'livy.ab_urbe_condita.part.1'


def _rec(i, work, scale, ref, sub=None, lang='la'):
    r = {'id': i, 'work': work, 'scale': scale, 'language': lang,
         'ref_start': ref, 'ref_end': ref if scale == 'prose' else ref + '9',
         'desc': {'gist': f'gist of {i}', 'themes': []}}
    if sub is not None:
        r['sub'] = sub
    return r


RECS = [
    _rec('tac:fine:0', TAC, 'fine', 'Tac. Ann. 1.1'),
    _rec('tac:prose:0', TAC, 'prose', 'Tac. Ann. 1.1', sub=1),
    _rec('tac:prose:1', TAC, 'prose', 'Tac. Ann. 1.1', sub=2),
    _rec('tac:prose:2', TAC, 'prose', 'Tac. Ann. 1.2', sub=1),
    _rec('liv:fine:0', OTH, 'fine', 'Liv. 1.1'),
    _rec('liv:fine:1', OTH, 'fine', 'Liv. 2.1'),
    _rec('fill:fine:0', 'filler.work', 'fine', 'F 1.1'),
    _rec('fill:fine:1', 'filler.work', 'fine', 'F 2.1'),
    _rec('fill:fine:2', 'filler.work', 'fine', 'F 3.1'),
    _rec('fill:fine:3', 'filler.work', 'fine', 'F 4.1'),
]


def _install(monkeypatch, scores_for_query):
    works, shadowed = pi._compute_prose_sets(RECS)
    by = {}
    for i, r in enumerate(RECS):
        by.setdefault(pi._norm_work(r['work']), []).append(i)
    emb = np.eye(len(RECS), dtype=np.float32)
    monkeypatch.setattr(pi, '_records', RECS)
    monkeypatch.setattr(pi, '_ids', [r['id'] for r in RECS])
    monkeypatch.setattr(pi, '_emb', emb)
    monkeypatch.setattr(pi, '_by_work', by)
    monkeypatch.setattr(pi, '_by_language', {'la': np.arange(len(RECS))})
    monkeypatch.setattr(pi, '_undescribed', set())
    monkeypatch.setattr(pi, '_prose_works', works)
    monkeypatch.setattr(pi, '_shadowed', shadowed)
    monkeypatch.setattr(pi, '_ensure_loaded', lambda: None)
    monkeypatch.setitem(pi._state, 'ok', True)
    monkeypatch.setattr(pi, 'embed_query', lambda text: np.zeros(len(RECS), dtype=np.float32))
    monkeypatch.setattr(pi, '_score_all', lambda q: np.array(scores_for_query, dtype=np.float64))
    monkeypatch.setattr(pi, '_lexical_boost', lambda q, s: 0)
    monkeypatch.setattr(pi, 'held_languages', lambda: set())
    monkeypatch.setattr(pi, '_dating', lambda w, l: {})
    monkeypatch.setattr(pi, '_naming', lambda w: {})


def test_prose_sets():
    works, shadowed = pi._compute_prose_sets(RECS)
    assert works == {TAC}
    assert shadowed == {0}


def test_find_by_text_ranks_prose_not_fine_for_that_work(monkeypatch):
    # the Tacitus fine window scores highest of all; it must not be returned
    _install(monkeypatch, [0.95, 0.80, 0.79, 0.78, 0.77, 0.76, .1, .1, .1, .1])
    out = pi.find_by_text('mutinies of the legions', limit=10, only_works={TAC, OTH}, per_work=10)
    ids = [r['id'] for r in out['results']]
    assert 'tac:fine:0' not in ids
    assert {'tac:prose:0', 'tac:prose:1', 'tac:prose:2'} <= set(ids)
    # the other work keeps its fine windows
    assert 'liv:fine:0' in ids and 'liv:fine:1' in ids
    subs = {r['id']: r.get('sub') for r in out['results']}
    assert subs['tac:prose:1'] == 2


def test_prose_pieces_of_one_chapter_are_not_collapsed_by_overlap_dedup(monkeypatch):
    _install(monkeypatch, [0.10, 0.80, 0.79, 0.78, 0.10, 0.10, .1, .1, .1, .1])
    out = pi.find_by_text('x', limit=10, only_works={TAC})
    got = [r['id'] for r in out['results']]
    assert got.count('tac:prose:0') == 1 and 'tac:prose:1' in got


def test_window_for_passage_prefers_prose(monkeypatch):
    _install(monkeypatch, [0] * 10)
    assert pi.window_for_passage(TAC, 'Tac. Ann. 1.1', 'Tac. Ann. 1.1') == 'tac:prose:0'
    assert pi.window_for_passage(TAC, 'Tac. Ann. 1.2', 'Tac. Ann. 1.2') == 'tac:prose:2'
    # a work without prose windows still gets its fine window
    assert pi.window_for_passage(OTH, 'Liv. 1.1', 'Liv. 1.1') == 'liv:fine:0'


def test_fine_windows_covering_returns_prose_pieces_with_sub(monkeypatch):
    _install(monkeypatch, [0] * 10)
    got = pi.fine_windows_covering(TAC, 'Tac. Ann. 1.1', 'Tac. Ann. 1.1')
    assert [g['id'] for g in got] == ['tac:prose:0', 'tac:prose:1']
    assert [g['sub'] for g in got] == [1, 2]
    got = pi.fine_windows_covering(OTH, 'Liv. 1.1', 'Liv. 1.1')
    assert [g['id'] for g in got] == ['liv:fine:0']


def test_similar_to_window_leaves_out_the_fine_window(monkeypatch):
    _install(monkeypatch, [0.95, 0.80, 0.79, 0.78, 0.77, 0.76, .1, .1, .1, .1])
    out = pi.find_similar_to_window('liv:fine:1', limit=10)
    ids = [r['id'] for r in out['results']]
    assert 'tac:fine:0' not in ids


def test_unrestricted_search_never_returns_the_fine_window(monkeypatch):
    _install(monkeypatch, [0.95, 0.80, 0.79, 0.78, 0.77, 0.76, .1, .1, .1, .1])
    out = pi.find_by_text('mutinies of the legions', limit=10)
    ids = [r['id'] for r in out['results']]
    assert 'tac:fine:0' not in ids
    assert any(i.startswith('tac:prose') for i in ids)


def test_mentions_list_pieces_of_a_chapter_and_skips_the_fine_window(monkeypatch):
    recs = [
        {'id': 'f', 'work': TAC, 'scale': 'fine', 'ref_start': 'Tac. Ann. 4.1', 'ref_end': 'Tac. Ann. 4.12',
         'desc': {'gist': 'Sejanus rises.'}},
        {'id': 'p1', 'work': TAC, 'scale': 'prose', 'sub': 1, 'ref_start': 'Tac. Ann. 4.1',
         'ref_end': 'Tac. Ann. 4.1', 'desc': {'gist': 'Sejanus rises.'}},
        {'id': 'p2', 'work': TAC, 'scale': 'prose', 'sub': 2, 'ref_start': 'Tac. Ann. 4.1',
         'ref_end': 'Tac. Ann. 4.1', 'desc': {'gist': 'Sejanus commands the guard.'}},
    ]
    works, shadowed = pi._compute_prose_sets(recs)
    monkeypatch.setattr(pi, '_records', recs)
    monkeypatch.setattr(pi, '_by_work', {pi._norm_work(TAC): [0, 1, 2]})
    monkeypatch.setattr(pi, '_prose_works', works)
    monkeypatch.setattr(pi, '_shadowed', shadowed)
    monkeypatch.setattr(pi, '_ensure_loaded', lambda: None)
    monkeypatch.setitem(pi._state, 'ok', True)
    out = pi.mentions_in_work('tacitus.annales', ['Sejanus'])
    assert sorted(h['id'] for h in out['hits']) == ['p1', 'p2']
    assert {h['id']: h['sub'] for h in out['hits']} == {'p1': 1, 'p2': 2}
