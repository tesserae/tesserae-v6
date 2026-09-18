"""Reader-at-top: Theme Search re-ranked by the trained free reader model.

WHY THIS EXISTS

backend/reader_rerank.py takes the top K of a Theme Search ranking, builds
each passage's reader text (gist + translation + original, the same order
evaluation/theme_benchmark/distill_train/common.py trained on), asks
backend/reader_client.py for scores from services/reader_server.py, and
re-orders the top K by reader score descending with index score as the
tiebreak (R1 in evaluation/theme_benchmark/reader_at_top/rerank.py).

These tests stub the network call (backend.reader_client.score) rather than
running the real service, and stub passage_index.find_by_text at the route
level, the same pattern tests/test_theme_search_offset.py already uses for
that route.
"""
import os

import pytest

from backend import reader_rerank
from backend import reader_client


def _result(id_, score, gist='a gist'):
    return {'id': id_, 'work': 'synth.work', 'ref_start': '1.1', 'ref_end': '1.5',
            'score': score, 'gist': gist, 'strong': True}


# ---------------------------------------------------------------------------
# build_passage_text: gist, translation, original, in that order
# ---------------------------------------------------------------------------

def test_build_passage_text_orders_gist_translation_text():
    out = reader_rerank.build_passage_text('a gist', 'a translation', 'original words')
    assert out == 'a gist\n\na translation\n\noriginal words'
    parts = out.split('\n\n')
    assert parts == ['a gist', 'a translation', 'original words']


def test_build_passage_text_drops_missing_parts():
    assert reader_rerank.build_passage_text('', '', 'only text') == 'only text'
    assert reader_rerank.build_passage_text('only gist', None, None) == 'only gist'
    assert reader_rerank.build_passage_text(None, None, None) == ''


# ---------------------------------------------------------------------------
# reader_rerank.apply: the re-ranking itself
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _no_lookups(monkeypatch):
    """These tests care about ordering, not the text-building lookups: stub
    them to empty so apply() never touches a real translations file or the
    window_texts sqlite database."""
    monkeypatch.setattr(reader_rerank.window_texts, 'texts_for', lambda ids: {})
    monkeypatch.setattr(reader_rerank.translations, 'for_passage',
                        lambda work, refs: {'available': False})


def test_apply_reorders_top_k_by_reader_score_index_as_tiebreak(monkeypatch):
    # Index order: w0 > w1 > w2 > w3. Reader disagrees on the top three.
    results = [_result('w0', 0.90), _result('w1', 0.80), _result('w2', 0.70),
              _result('w3', 0.60)]
    monkeypatch.setattr(reader_client, 'score',
                        lambda query, passages, timeout=6.0:
                        {'w0': 0.2, 'w1': 0.9, 'w2': 0.9, 'w3': 0.1})
    out, meta = reader_rerank.apply('a query', results, k=4)
    assert meta['applied'] is True and meta['k'] == 4 and isinstance(meta['ms'], int)
    # w1 and w2 tie on reader score (0.9): index score (already descending,
    # w1 above w2) breaks the tie, exactly R1's ordering.
    assert [r['id'] for r in out] == ['w1', 'w2', 'w0', 'w3']
    assert [r['reader_score'] for r in out] == [0.9, 0.9, 0.2, 0.1]


def test_apply_leaves_the_tail_past_k_untouched(monkeypatch):
    results = [_result(f'w{i}', 1.0 - i * 0.01) for i in range(6)]
    monkeypatch.setattr(reader_client, 'score',
                        lambda query, passages, timeout=6.0:
                        {r['id']: 1.0 - i * 0.1 for i, r in enumerate(reversed(passages))})
    out, meta = reader_rerank.apply('q', results, k=3)
    assert meta['applied'] is True and meta['k'] == 3
    # Only the first 3 were ever sent to the reader (and so eligible to move);
    # the rest keep find_by_text's own order, unscored.
    assert [r['id'] for r in out[3:]] == ['w3', 'w4', 'w5']
    assert all('reader_score' not in r for r in out[3:])


def test_apply_returns_original_order_when_reader_returns_none(monkeypatch):
    results = [_result('w0', 0.9), _result('w1', 0.8)]
    monkeypatch.setattr(reader_client, 'score',
                        lambda query, passages, timeout=6.0: None)
    out, meta = reader_rerank.apply('q', results, k=2)
    assert meta == {'applied': False}
    assert out == results
    assert all('reader_score' not in r for r in out)


def test_apply_on_empty_results_does_nothing(monkeypatch):
    called = []
    monkeypatch.setattr(reader_client, 'score',
                        lambda *a, **k: called.append(1))
    out, meta = reader_rerank.apply('q', [], k=10)
    assert out == [] and meta == {'applied': False}
    assert not called


# ---------------------------------------------------------------------------
# The /passages/theme-search route
# ---------------------------------------------------------------------------

@pytest.fixture
def client():
    from backend.app import app
    return app.test_client()


@pytest.fixture
def route():
    from backend.app import app
    return next(str(r) for r in app.url_map.iter_rules()
                if str(r).endswith('/passages/theme-search'))


def _stub_find_by_text(results):
    def fake(query, limit=25, languages=None, scale=None, expand=True, offset=0):
        return {'query': query, 'results': [dict(r) for r in results],
                'confidence': {'level': 'low'}, 'note': None}
    return fake


def test_route_leaves_response_unchanged_when_reader_is_disabled(monkeypatch, client, route):
    """No THEME_READER_URL set: this is the default, and the whole reader
    mechanism must not touch the response at all -- not even to add a
    'reader' field saying so."""
    monkeypatch.delenv('THEME_READER_URL', raising=False)
    from backend import passage_index as pi
    results = [_result('w0', 0.9), _result('w1', 0.8)]
    monkeypatch.setattr(pi, 'find_by_text', _stub_find_by_text(results))
    r = client.get(f'{route}?q=a+dog')
    assert r.status_code == 200
    body = r.get_json()
    assert 'reader' not in body
    assert [x['id'] for x in body['results']] == ['w0', 'w1']
    assert all('reader_score' not in x for x in body['results'])


def test_route_reranks_when_reader_is_enabled_and_scores_come_back(monkeypatch, client, route):
    monkeypatch.setenv('THEME_READER_URL', 'http://127.0.0.1:8091')
    from backend import passage_index as pi
    results = [_result('w0', 0.9), _result('w1', 0.8)]
    monkeypatch.setattr(pi, 'find_by_text', _stub_find_by_text(results))
    monkeypatch.setattr(reader_client, 'score',
                        lambda query, passages, timeout=6.0: {'w0': 0.1, 'w1': 0.9})
    r = client.get(f'{route}?q=a+dog')
    assert r.status_code == 200
    body = r.get_json()
    assert body['reader']['applied'] is True and body['reader']['k'] == reader_rerank.DEFAULT_K
    assert [x['id'] for x in body['results']] == ['w1', 'w0']


def test_route_opts_out_with_reader_zero(monkeypatch, client, route):
    monkeypatch.setenv('THEME_READER_URL', 'http://127.0.0.1:8091')
    from backend import passage_index as pi
    results = [_result('w0', 0.9), _result('w1', 0.8)]
    monkeypatch.setattr(pi, 'find_by_text', _stub_find_by_text(results))
    called = []
    monkeypatch.setattr(reader_client, 'score', lambda *a, **k: called.append(1))
    r = client.get(f'{route}?q=a+dog&reader=0')
    assert r.status_code == 200
    body = r.get_json()
    assert 'reader' not in body
    assert [x['id'] for x in body['results']] == ['w0', 'w1']
    assert not called


def test_route_reports_applied_false_when_reader_call_fails(monkeypatch, client, route):
    monkeypatch.setenv('THEME_READER_URL', 'http://127.0.0.1:8091')
    from backend import passage_index as pi
    results = [_result('w0', 0.9), _result('w1', 0.8)]
    monkeypatch.setattr(pi, 'find_by_text', _stub_find_by_text(results))
    monkeypatch.setattr(reader_client, 'score', lambda *a, **k: None)
    r = client.get(f'{route}?q=a+dog')
    assert r.status_code == 200
    body = r.get_json()
    assert body['reader'] == {'applied': False}
    assert [x['id'] for x in body['results']] == ['w0', 'w1']


def test_meta_names_the_model(monkeypatch):
    from backend import reader_rerank
    monkeypatch.setattr(reader_rerank.reader_client, 'score', lambda q, ps, timeout=6.0: {p['id']: 0.5 for p in ps})
    monkeypatch.setattr(reader_rerank, '_reader_texts', lambda results: {r['id']: 'text' for r in results})
    results = [{'id': 'a', 'score': 0.9}, {'id': 'b', 'score': 0.8}]
    out, meta = reader_rerank.apply('q', results, k=2)
    assert meta['applied'] is True and meta['model'] == reader_rerank.MODEL_ID


def test_pages_inside_the_top_hundred_come_from_one_reranked_list(monkeypatch):
    """A passage promoted into page one must not appear again on page two,
    and one demoted off page one must land on page two."""
    from backend.app import app
    from backend.blueprints import passages as P
    monkeypatch.setenv('THEME_READER_URL', 'http://127.0.0.1:1')
    calls = []

    def fake_find(q, limit=25, offset=0, languages=None, scale=None, **kw):
        calls.append((limit, offset))
        return {'results': [{'id': f'w{i}', 'work': f'w{i}', 'score': 1.0 - i / 200} for i in range(offset, offset + limit)]}
    monkeypatch.setattr(P.passage_index, 'find_by_text', fake_find)
    monkeypatch.setattr(P.passage_index, 'index_version', lambda: '2026-09-18')
    # The reader promotes w30 to the top and demotes w0 to the bottom of the hundred.
    monkeypatch.setattr(P.reader_rerank.reader_client, 'score',
                        lambda q, ps, timeout=6.0: {p['id']: (1.0 if p['id'] == 'w30' else 0.0 if p['id'] == 'w0' else 0.5) for p in ps})
    monkeypatch.setattr(P.reader_rerank, '_reader_texts', lambda results: {r['id']: 't' for r in results})
    c = app.test_client()
    path = next(str(r) for r in app.url_map.iter_rules() if r.endpoint == 'passages.theme_search')
    p1 = c.get(f'{path}?q=x&limit=25&offset=0').get_json()['results']
    p2 = c.get(f'{path}?q=x&limit=25&offset=25').get_json()['results']
    p5 = c.get(f'{path}?q=x&limit=25&offset=100').get_json()['results']
    ids1, ids2 = [r['id'] for r in p1], [r['id'] for r in p2]
    assert ids1[0] == 'w30' and 'w30' not in ids2 and 'w0' not in ids1
    assert len(ids1) == 25 and len(ids2) == 25 and not set(ids1) & set(ids2)
    assert calls[0] == (100, 0) and calls[1] == (100, 0) and calls[2] == (25, 100)
    assert [r['id'] for r in p5][0] == 'w100'

