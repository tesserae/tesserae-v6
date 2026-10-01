"""Theme Comparison joined against cached word-level (fusion) results.

Part A: GET /api/passages/compare?with_phrases=1 (backend/blueprints/
passages.py, _attach_phrase_parallels and friends) joins each theme pair
against whatever fusion search has already cached for the same two works,
keeping only the cached parallels whose two lines fall inside that pair's
two windows. Part B: backend.passage_index.pair_lift, the reverse direction
(a word-level result's theme-similarity reading), on a small synthetic index
copied from tests/test_theme_comparison.py's fixture.
"""
import numpy as np
import pytest

from backend import passage_index as pi
from backend.blueprints import passages as passages_bp


# -- Part A: phrase parallels inside a theme pair --------------------------

def _fake_compare_output():
    """One theme pair between a window of verg.aen.part.1 and one of
    lucan.bellum_civile.part.1, shaped like passage_index.compare_works's
    real output (just the fields _attach_phrase_parallels reads)."""
    return {
        'pairs': [{
            'score': 0.9, 'lift': 0.2, 'strong': True,
            'a': {'work': 'verg.aen.part.1', 'language': 'la',
                  'ref_start': 'verg. aen. 1.289', 'ref_end': 'verg. aen. 1.300'},
            'b': {'work': 'lucan.bellum_civile.part.1', 'language': 'la',
                  'ref_start': 'lucan. 1.1', 'ref_end': 'lucan. 1.10'},
        }],
    }


def test_phrases_join_keeps_only_rows_inside_both_windows(monkeypatch):
    rows = [
        # inside both windows: verg. aen. 1.295 is in [1.289, 1.300], lucan. 1.5 is in [1.1, 1.10]
        {'source': {'ref': 'verg. aen. 1.295', 'text': 'src inside'},
         'target': {'ref': 'lucan. 1.5', 'text': 'tgt inside'},
         'fused_score': 5.0, 'matched_words': [{'lemma': 'arma'}]},
        # outside work_a's window (1.400 not in [1.289, 1.300])
        {'source': {'ref': 'verg. aen. 1.400', 'text': 'src outside'},
         'target': {'ref': 'lucan. 1.5', 'text': 'tgt outside'},
         'fused_score': 3.0, 'matched_words': [{'lemma': 'virum'}]},
    ]

    def fake_get_cached_results(source_id, target_id, language, settings):
        assert source_id == 'verg.aen.part.1.tess'
        assert target_id == 'lucan.bellum_civile.part.1.tess'
        assert language == 'la'
        return rows, {}

    monkeypatch.setattr('backend.cache.get_cached_results', fake_get_cached_results)
    monkeypatch.setattr('backend.blueprints.fusion._poll_use_meter', lambda *a, **k: False)

    out = _fake_compare_output()
    passages_bp._attach_phrase_parallels(out, 'verg.aen.part.1', 'lucan.bellum_civile.part.1')

    assert out['phrases'] == {'available': True, 'pairs_with_phrases': 1}
    phrases = out['pairs'][0]['phrases']
    assert len(phrases) == 1
    assert phrases[0] == {
        'source_ref': 'verg. aen. 1.295', 'target_ref': 'lucan. 1.5',
        'matched_words': [{'lemma': 'arma'}], 'score': 5.0,
        'source_text': 'src inside', 'target_text': 'tgt inside',
    }


def test_phrases_unavailable_when_nothing_cached(monkeypatch):
    monkeypatch.setattr('backend.cache.get_cached_results', lambda *a, **k: (None, None))
    monkeypatch.setattr('backend.blueprints.fusion._poll_use_meter', lambda *a, **k: False)

    out = _fake_compare_output()
    passages_bp._attach_phrase_parallels(out, 'verg.aen.part.1', 'lucan.bellum_civile.part.1')

    assert out['phrases']['available'] is False
    assert 'phrases' not in out['pairs'][0]
    run_url = out['phrases']['run_url']
    assert run_url.startswith('/?')
    assert 'source=verg.aen.part.1.tess' in run_url
    assert 'target=lucan.bellum_civile.part.1.tess' in run_url
    assert 'lang=la' in run_url


def test_phrases_skipped_for_cross_lingual_pairs(monkeypatch):
    """No single-language fusion cache key exists for a pair whose two
    windows are in different languages, so the join never calls the cache."""
    calls = []
    monkeypatch.setattr('backend.cache.get_cached_results',
                        lambda *a, **k: calls.append(a) or (None, None))
    monkeypatch.setattr('backend.blueprints.fusion._poll_use_meter', lambda *a, **k: False)

    out = _fake_compare_output()
    out['pairs'][0]['b']['language'] = 'grc'
    passages_bp._attach_phrase_parallels(out, 'verg.aen.part.1', 'some.greek_work')

    assert out['phrases']['available'] is False
    assert calls == []


# -- Part B: pair_lift (the reverse direction) ------------------------------

def _fake_index(monkeypatch):
    vecs = np.array([
        [1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0],          # A0 A1 A2
        [0.2, 0.98, 0, 0], [0.99, 0.1, 0, 0], [0, 0, 0, 1],  # B0 B1 B2
        [0.5, 0.5, 0.5, 0.5],                              # C0
    ], dtype=np.float32)
    vecs /= np.linalg.norm(vecs, axis=1, keepdims=True)
    ids = ['a.work.part.1:fine:0', 'a.work.part.1:fine:1', 'a.work.part.2:fine:0',
           'b.work:fine:0', 'b.work:fine:1', 'b.work:coarse:0', 'c.work:fine:0']
    records = []
    for wid in ids:
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
    monkeypatch.setattr(pi, '_PAIR_BASELINE_CACHE', {})


def test_pair_lift_scores_a_strongly_related_pair(monkeypatch):
    _fake_index(monkeypatch)
    out = pi.pair_lift('a.work.part.1', 'a.work.part.1 0', 'b.work', 'b.work 1')
    assert out is not None
    assert out['score'] == pytest.approx(0.995, abs=0.01)   # A0 ~ B1, see test_theme_comparison
    assert out['lift'] > 0.3
    assert out['level'] == 'strong'
    # the baseline for (a.work, b.work) is now cached
    assert (pi._norm_work('a.work.part.1'), pi._norm_work('b.work'), 'fine') in pi._PAIR_BASELINE_CACHE


def test_pair_lift_is_none_when_no_window_covers_a_line(monkeypatch):
    _fake_index(monkeypatch)
    out = pi.pair_lift('a.work.part.1', 'a.work.part.1 999', 'b.work', 'b.work 1')
    assert out is None


# -- Connector tool: theme_pair_lift ----------------------------------------

def test_theme_pair_lift_tool_passes_pairs_through_and_caps_at_100(monkeypatch):
    import backend.blueprints.mcp_http as M

    seen = {}

    def fake_post(path, body, timeout=None):
        seen['path'] = path
        seen['body'] = body
        return {'results': [{'score': 0.9, 'lift': 0.3, 'level': 'strong'}]}

    monkeypatch.setattr(M, '_post', fake_post)
    pairs = [{'work_a': 'a', 'ref_a': '1', 'work_b': 'b', 'ref_b': '2'}] * 150
    out = M._t_theme_pair_lift({'pairs': pairs})

    assert seen['path'] == '/passages/pair-lift'
    assert len(seen['body']['pairs']) == 100   # capped
    assert out['results'] == [{'score': 0.9, 'lift': 0.3, 'level': 'strong'}]
    assert 'presentation' in out


def test_theme_pair_lift_tool_requires_pairs():
    import backend.blueprints.mcp_http as M
    assert 'error' in M._t_theme_pair_lift({})
    assert 'error' in M._t_theme_pair_lift({'pairs': []})


# -- POST /passages/pair-lift, end to end -----------------------------------

def _pair_lift_route():
    from backend.app import app
    return next(str(r) for r in app.url_map.iter_rules()
                if str(r).endswith('/passages/pair-lift'))


def test_pair_lift_route_end_to_end(monkeypatch):
    _fake_index(monkeypatch)
    from backend.app import app
    client = app.test_client()
    body = {'pairs': [
        {'work_a': 'a.work.part.1', 'ref_a': 'a.work.part.1 0',
         'work_b': 'b.work', 'ref_b': 'b.work 1'},
        {'work_a': 'a.work.part.1', 'ref_a': 'a.work.part.1 999',
         'work_b': 'b.work', 'ref_b': 'b.work 1'},
    ]}
    r = client.post(_pair_lift_route(), json=body)
    assert r.status_code == 200
    data = r.get_json()
    assert len(data['results']) == 2
    assert data['results'][0]['level'] == 'strong'
    assert data['results'][1] == {'score': None, 'lift': None, 'level': None}


def test_pair_lift_route_requires_pairs():
    from backend.app import app
    client = app.test_client()
    r = client.post(_pair_lift_route(), json={})
    assert r.status_code == 200
    assert r.get_json()['results'] == []
    assert 'error' in r.get_json()
