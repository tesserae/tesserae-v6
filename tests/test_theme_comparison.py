"""Theme comparison of two works on a small synthetic index."""
import numpy as np

from backend import passage_index as pi


def _fake_index(monkeypatch):
    # Three windows in work A, three in B, one in C; unit vectors so that
    # A0~B1 strongly, A1~B0 moderately, and A2 resembles nothing.
    vecs = np.array([
        [1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0],          # A0 A1 A2
        [0.2, 0.98, 0, 0], [0.99, 0.1, 0, 0], [0, 0, 0, 1],  # B0 B1 B2
        [0.5, 0.5, 0.5, 0.5],                              # C0
    ], dtype=np.float32)
    vecs /= np.linalg.norm(vecs, axis=1, keepdims=True)
    ids = ['a.work.part.1:fine:0', 'a.work.part.1:fine:1', 'a.work.part.2:fine:0',
           'b.work:fine:0', 'b.work:fine:1', 'b.work:coarse:0', 'c.work:fine:0']
    records = []
    for i, wid in enumerate(ids):
        work, scale, n = wid.split(':')
        records.append({'id': wid, 'work': work, 'scale': scale, 'language': 'la',
                        'ref_start': f'{work} {n}', 'ref_end': f'{work} {n}',
                        'desc': {'gist': f'gist of {wid}'}})
    by_work = {}
    for i, r in enumerate(records):
        by_work.setdefault(pi._norm_work(r['work']), []).append(i)
    monkeypatch.setattr(pi, '_ids', ids)
    monkeypatch.setattr(pi, '_records', records)
    monkeypatch.setattr(pi, '_emb', vecs)
    monkeypatch.setattr(pi, '_by_work', by_work)
    monkeypatch.setattr(pi, '_undescribed', set())
    monkeypatch.setattr(pi, '_state', {'loaded': True, 'ok': True, 'error': None})
    monkeypatch.setattr(pi, '_ensure_loaded', lambda: None)
    monkeypatch.setattr(pi, '_naming', lambda w: {'author_display': w, 'title': w})
    monkeypatch.setattr(pi, '_dating', lambda w, l: {})


def test_books_gather_into_the_work_and_the_best_pairs_come_first(monkeypatch):
    _fake_index(monkeypatch)
    out = pi.compare_works('a.work', 'b.work', limit=10)
    assert out['n_a'] == 3 and out['n_b'] == 2      # b.work's coarse window is left out at fine scale
    first = out['pairs'][0]
    assert first['a']['id'] == 'a.work.part.1:fine:0' and first['b']['id'] == 'b.work:fine:1'
    assert out['pairs'][1]['a']['id'] == 'a.work.part.1:fine:1' and out['pairs'][1]['b']['id'] == 'b.work:fine:0'
    assert all(out['pairs'][i]['score'] >= out['pairs'][i + 1]['score'] for i in range(len(out['pairs']) - 1))
    assert set(out['confidence']) == {'top', 'baseline', 'head_lift', 'level'}


def test_a_single_book_can_be_compared_and_unknown_work_is_an_error(monkeypatch):
    _fake_index(monkeypatch)
    out = pi.compare_works('a.work.part.2', 'b.work', limit=10)
    assert out['n_a'] == 1 and all(p['a']['id'] == 'a.work.part.2:fine:0' for p in out['pairs'])
    missing = pi.compare_works('a.work', 'nobody.wrote_this')
    assert missing['error'] and missing['pairs'] == []


def test_pairs_are_deduplicated_on_the_unordered_pair(monkeypatch):
    _fake_index(monkeypatch)
    out = pi.compare_works('a.work', 'a.work', limit=20)
    keys = {tuple(sorted((p['a']['id'], p['b']['id']))) for p in out['pairs']}
    assert len(keys) == len(out['pairs'])
