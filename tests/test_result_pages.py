"""Server-side paging of finished search results (backend/result_pages.py).

The invariant: with sort=score and no filter, page 1 + page 2 + ... is the
list the unpaged response sent, and every sort/filter runs over the whole
stored list before slicing.
"""
import json
import os
import sys
import time
import uuid

import pytest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend import result_pages, search_cancellation


def _row(i, score, src, tgt):
    return {'overall_score': score, 'source': {'ref': src, 'text': f's{i}'},
            'target': {'ref': tgt, 'text': f't{i}'}, 'id': i}


# 23 rows, already in descending score order with ties, loci across 3 books.
ROWS = [_row(i, 10 - i // 2, f'{1 + i % 3}.{100 - i}', f'{1 + i % 2}.{i * 7 + 1}')
        for i in range(23)]


@pytest.fixture(autouse=True)
def result_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(result_pages, 'RESULT_DIR', str(tmp_path / 'results'))
    return tmp_path / 'results'


def _pages(rows, limit, **args):
    out, offset = [], 0
    while True:
        page = result_pages.query_page(rows, {'offset': offset, 'limit': limit, **args})
        out.extend(page['results'])
        offset += limit
        if offset >= page['total']:
            return out, page['total']


# ---- module ----------------------------------------------------------------

@pytest.mark.parametrize('limit', [10, 20, 50, 100, 7])
def test_pages_reconstruct_the_original_ordered_list(limit):
    rows = result_pages.load(result_pages.store(ROWS))
    assert rows == ROWS
    joined, total = _pages(rows, limit)
    assert joined == ROWS
    assert total == len(ROWS)


def test_last_page_is_partial_and_beyond_total_is_empty():
    last = result_pages.query_page(ROWS, {'offset': 20, 'limit': 10})
    assert [r['id'] for r in last['results']] == [20, 21, 22]
    beyond = result_pages.query_page(ROWS, {'offset': 50, 'limit': 10})
    assert beyond == {'results': [], 'total': 23, 'offset': 50, 'limit': 10}


def test_default_page_is_first_fifty():
    page = result_pages.query_page(ROWS, {})
    assert page['offset'] == 0 and page['limit'] == 50 and len(page['results']) == 23


@pytest.mark.parametrize('args', [
    {'limit': 0}, {'limit': 101}, {'limit': 'x'}, {'offset': -1}, {'offset': '1.5'},
    {'sort': 'random'}, {'filter_view': 'middle', 'filter_book': 'Book 1'},
    {'filter_view': 'source'}, {'filter_view': 'source', 'filter_line_min': 1},
])
def test_invalid_page_requests_are_rejected(args):
    with pytest.raises(ValueError):
        result_pages.query_page(ROWS, args)


def test_score_sort_is_global_and_stable():
    shuffled = ROWS[::-1]
    joined, _ = _pages(shuffled, 5)
    # Same order a stable descending JS sort gives: score desc, ties keep input order.
    assert [r['overall_score'] for r in joined] == sorted(
        (r['overall_score'] for r in ROWS), reverse=True)
    assert joined == sorted(shuffled, key=lambda r: r['overall_score'], reverse=True)


def test_locus_sort_happens_before_slicing_and_is_numeric():
    joined, _ = _pages(ROWS, 4, sort='target_locus')
    keys = [tuple(map(int, r['target']['ref'].split('.'))) for r in joined]
    assert keys == sorted(keys)  # "1.15" after "1.8": numeric, not lexical
    first_page = result_pages.query_page(ROWS, {'limit': 4, 'sort': 'target_locus'})
    assert first_page['results'] == joined[:4]


def test_score_field_precedence_matches_the_browser():
    rows = [{'fused_score': None, 'score': 2, 'id': 'a'}, {'fused_score': 5, 'id': 'b'},
            {'overall_score': 3, 'id': 'c'}, {'id': 'd'}]
    assert [r['id'] for r in result_pages.sort_rows(rows, 'score')] == ['b', 'c', 'a', 'd']


def test_book_filter_runs_before_slicing():
    joined, total = _pages(ROWS, 3, filter_view='source', filter_book='Book 2')
    expected = [r for r in ROWS if r['source']['ref'].startswith('2.')]
    assert joined == expected and total == len(expected)


def test_line_filter_uses_last_number_of_locus():
    page = result_pages.query_page(ROWS, {'filter_view': 'target', 'filter_line_min': '1',
                                          'filter_line_max': '50', 'limit': 100})
    assert page['results'] == [r for r in ROWS if int(r['target']['ref'].split('.')[1]) <= 50]


def test_distribution_by_book_counts_every_row():
    dist = result_pages.distribution(ROWS, 'source')
    assert dist['mode'] == 'book'
    assert dist['labels'] == ['Book 1', 'Book 2', 'Book 3']
    assert sum(dist['counts']) == len(ROWS)


def test_distribution_by_line_band_for_a_single_book():
    rows = [_row(i, 1, '1.1', f'{n}') for i, n in enumerate([1, 9, 10, 11, 175])]
    dist = result_pages.distribution(rows, 'target')
    assert dist['mode'] == 'line' and dist['band'] == 10
    assert len(dist['labels']) == 18 and dist['labels'][0] == '1–10'
    assert dist['counts'][0] == 3 and dist['counts'][1] == 1 and dist['counts'][17] == 1


@pytest.mark.parametrize('bad', ['', '../etc/passwd', 'A' * 32, '0' * 31, None,
                                 '../../cache/' + '0' * 20])
def test_malformed_ids_never_touch_the_filesystem(bad):
    assert result_pages.load(bad) is None


def test_unknown_and_expired_ids(result_dir):
    assert result_pages.load('0' * 32) is None
    rid = result_pages.store(ROWS)
    old = time.time() - result_pages.TTL_SECONDS - 1
    os.utime(result_dir / f'{rid}.json', (old, old))
    assert result_pages.load(rid) is None
    assert not (result_dir / f'{rid}.json').exists()


def test_ids_are_opaque_and_unique():
    ids = {result_pages.store([]) for _ in range(20)}
    assert len(ids) == 20 and all(len(i) == 32 for i in ids)


def test_store_prunes_expired_and_caps_total_bytes(result_dir, monkeypatch):
    stale = result_pages.store(ROWS)
    old = time.time() - result_pages.TTL_SECONDS - 1
    os.utime(result_dir / f'{stale}.json', (old, old))
    size = (result_dir / f'{stale}.json').stat().st_size
    monkeypatch.setattr(result_pages, 'MAX_TOTAL_BYTES', size * 3)
    ids = []
    for i in range(5):
        ids.append(result_pages.store(ROWS))
        t = time.time() - 100 + i
        os.utime(result_dir / f'{ids[-1]}.json', (t, t))
    remaining = {p.name for p in result_dir.iterdir()}
    assert f'{stale}.json' not in remaining
    # Before each write the older files are trimmed to the budget, so at most
    # budget/size old ones plus the one just written survive.
    assert len(remaining) <= 4
    assert f'{ids[-1]}.json' in remaining and f'{ids[0]}.json' not in remaining
    assert result_pages.load(ids[-1]) == ROWS


def test_lookup_does_not_depend_on_process_state(result_dir):
    """A second worker only shares the directory: simulate it by reading the
    file the first one wrote with nothing but the id."""
    rid = result_pages.store(ROWS)
    with open(result_dir / f'{rid}.json', encoding='utf-8') as f:
        assert json.load(f) == ROWS
    import importlib
    fresh = importlib.reload(result_pages)
    fresh.RESULT_DIR = str(result_dir)
    assert fresh.load(rid) == ROWS


def test_paginate_payload_keeps_first_page_and_full_aggregates():
    payload = {'type': 'complete', 'results': list(ROWS), 'total_matches': 23}
    result_pages.paginate_payload(payload, 10)
    assert payload['results'] == ROWS[:10]
    assert payload['result_total'] == 23 and payload['page_size'] == 10
    assert sum(payload['aggregates']['distribution']['source']['counts']) == 23
    assert result_pages.load(payload['result_id']) == ROWS


def test_paginate_payload_leaves_empty_results_alone(result_dir):
    payload = {'results': []}
    assert result_pages.paginate_payload(payload, 10) == {'results': []}
    assert not result_dir.exists() or not list(result_dir.iterdir())


@pytest.mark.parametrize('value,expected', [
    (None, None), (50, 50), (100, 100), (0, None), (101, None), ('50', None), (True, None)])
def test_requested_page_size(value, expected):
    assert result_pages.requested_page_size({'page_size': value}) == expected


# ---- endpoints ---------------------------------------------------------------

def _app(*blueprints):
    from flask import Flask
    app = Flask(__name__)
    for bp in blueprints:
        app.register_blueprint(bp)
    return app.test_client()


def _sse_complete(data):
    for line in data.decode().split('\n'):
        if line.startswith('data: '):
            evt = json.loads(line[6:])
            if evt.get('type') == 'complete':
                return evt
    return None


@pytest.fixture
def stream_stubs(monkeypatch):
    from backend.blueprints import search as sb

    class Slot:
        def __init__(self, cancellation=None):
            pass

        def acquire(self):
            return iter(())

        def set_metadata(self, m):
            pass

        def is_cancelled(self):
            return False

        def release(self):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    class Scorer:
        def score_matches(self, matches, *a):
            return [dict(r) for r in ROWS[::-1]]  # scorer order != final order

    monkeypatch.setattr(sb, 'SearchSlot', Slot)
    monkeypatch.setattr(sb, '_scorer', Scorer())
    monkeypatch.setattr(sb, '_parse_search_request', lambda data: {
        'source_id': 's.tess', 'target_id': 't.tess', 'language': 'la',
        'source_language': 'la', 'target_language': 'la', 'is_crosslingual': False,
        'settings': {'match_type': 'lemma'}})
    monkeypatch.setattr(sb, '_get_processed_units', lambda *a: [{'ref': '1.1'}])
    monkeypatch.setattr(sb, '_load_units', lambda p: ([{'ref': '1.1'}], [{'ref': '1.1'}]))
    monkeypatch.setattr(sb, '_load_corpus_frequencies', lambda *a: None)
    monkeypatch.setattr(sb, '_run_matcher', lambda *a, **k: ([{'m': 1}], 0))
    monkeypatch.setattr(sb, 'get_cached_results', lambda *a: (None, None))
    monkeypatch.setattr(sb, 'save_cached_results', lambda *a: True)
    monkeypatch.setattr(sb, 'log_search', lambda *a, **k: None)
    monkeypatch.setattr(sb, 'annotate_formula_counts', lambda *a: None)
    monkeypatch.setattr(sb, '_corpus_version_or_none', lambda lang: None)
    monkeypatch.setattr(sb, 'get_user_location', lambda: (None, None, None))
    monkeypatch.setattr(sb, 'current_user', None)
    return sb


def test_stream_without_page_size_is_unchanged(stream_stubs):
    client = _app(stream_stubs.search_bp)
    evt = _sse_complete(client.post('/search-stream', json={}).data)
    assert 'result_id' not in evt and len(evt['results']) == 23


def test_stream_pages_reconstruct_the_unpaged_response(stream_stubs):
    client = _app(stream_stubs.search_bp)
    legacy = _sse_complete(client.post('/search-stream', json={}).data)['results']
    evt = _sse_complete(client.post('/search-stream', json={'page_size': 10}).data)
    assert len(evt['results']) == 10 and evt['result_total'] == 23
    joined = list(evt['results'])
    for offset in (10, 20):
        r = client.get(f"/search-results/{evt['result_id']}?offset={offset}&limit=10")
        assert r.status_code == 200
        joined.extend(r.get_json()['results'])
    assert joined == legacy
    export = client.get(f"/search-results/{evt['result_id']}/export").get_json()
    assert export['results'] == legacy and export['total'] == 23


def test_stream_cache_hit_is_pageable(stream_stubs, monkeypatch):
    monkeypatch.setattr(stream_stubs, 'get_cached_results',
                        lambda *a: ([dict(r) for r in ROWS], {'source_lines': 1}))
    client = _app(stream_stubs.search_bp)
    evt = _sse_complete(client.post('/search-stream', json={'page_size': 20}).data)
    assert evt['cached'] is True and evt['results'] == ROWS[:20]
    page = client.get(f"/search-results/{evt['result_id']}?offset=20&limit=20").get_json()
    assert page['results'] == ROWS[20:]


def test_page_endpoint_errors(stream_stubs):
    client = _app(stream_stubs.search_bp)
    assert client.get('/search-results/' + '0' * 32).status_code == 404
    assert client.get('/search-results/nothex').status_code == 404
    assert client.get('/search-results/' + '0' * 32 + '/export').status_code == 404
    rid = result_pages.store(ROWS)
    assert client.get(f'/search-results/{rid}?limit=500').status_code == 400
    assert client.get(f'/search-results/{rid}?sort=bogus').status_code == 400
    body = client.get(f'/search-results/{rid}?limit=5').get_json()
    assert set(body) == {'results', 'total', 'offset', 'limit'}


def test_cancel_during_finalize_writes_no_snapshot(stream_stubs, monkeypatch, tmp_path, result_dir):
    monkeypatch.setattr(search_cancellation, 'CANCELLATION_DIR', str(tmp_path / 'cancel'))
    monkeypatch.setattr(search_cancellation, '_POLL_INTERVAL', 0)  # no 100 ms throttle
    search_id = str(uuid.uuid4())
    # The cancel lands after the last in-matcher check, while results are cached.
    monkeypatch.setattr(stream_stubs, 'save_cached_results',
                        lambda *a: search_cancellation.request_cancellation(search_id))
    client = _app(stream_stubs.search_bp)
    data = client.post('/search-stream', json={'page_size': 10, 'search_id': search_id}).data
    assert _sse_complete(data) is None
    assert not result_dir.exists() or not list(result_dir.iterdir())


def test_cancel_during_scoring_writes_no_snapshot(stream_stubs, monkeypatch, tmp_path, result_dir):
    monkeypatch.setattr(search_cancellation, 'CANCELLATION_DIR', str(tmp_path / 'cancel'))
    monkeypatch.setattr(search_cancellation, '_POLL_INTERVAL', 0)  # no 100 ms throttle
    search_id = str(uuid.uuid4())

    class CancellingScorer:
        def score_matches(self, *a):
            search_cancellation.request_cancellation(search_id)
            return list(ROWS)

    monkeypatch.setattr(stream_stubs, '_scorer', CancellingScorer())
    client = _app(stream_stubs.search_bp)
    data = client.post('/search-stream', json={'page_size': 10, 'search_id': search_id}).data
    assert _sse_complete(data) is None
    assert not result_dir.exists() or not list(result_dir.iterdir())


def test_post_search_pages_and_legacy(stream_stubs):
    client = _app(stream_stubs.search_bp)
    legacy = client.post('/search', json={}).get_json()
    assert 'result_id' not in legacy and len(legacy['results']) == 23
    paged = client.post('/search', json={'page_size': 10}).get_json()
    assert paged['results'] == legacy['results'][:10] and paged['result_total'] == 23
    rest = client.get(f"/search-results/{paged['result_id']}?offset=10&limit=100").get_json()
    assert paged['results'] + rest['results'] == legacy['results']


def test_fusion_cache_hit_is_pageable_and_formula_filtered(monkeypatch):
    from backend.blueprints import fusion as fb
    rows = [dict(r, fused_score=r['overall_score']) for r in ROWS]
    monkeypatch.setattr(fb, 'get_cached_results', lambda *a: ([dict(r) for r in rows], {}))
    monkeypatch.setattr(fb, 'resolve_text_path', lambda *a: '/x')
    monkeypatch.setattr(fb, '_poll_use_meter', lambda *a: False)
    monkeypatch.setattr(fb, 'log_search', lambda *a, **k: None)
    monkeypatch.setattr(fb, 'annotate_formula_counts', lambda *a: None)
    monkeypatch.setattr(fb, 'apply_formula_filter',
                        lambda res, mx, only: ([r for r in res if r['id'] % 2 == 0], 11)
                        if mx else (res, 0))
    monkeypatch.setattr(fb, 'get_user_location', lambda: (None, None, None))
    monkeypatch.setattr(fb, 'current_user', None)
    from backend.blueprints.search import search_bp
    client = _app(fb.fusion_bp, search_bp)
    body = {'source': 's.tess', 'target': 't.tess', 'language': 'la'}

    legacy = _sse_complete(client.post('/search-fusion', json={**body, 'formula_max': 3}).data)
    evt = _sse_complete(client.post('/search-fusion',
                                    json={**body, 'formula_max': 3, 'page_size': 5}).data)
    assert evt['result_total'] == len(legacy['results']) == 12
    joined = list(evt['results'])
    for off in (5, 10):
        joined += client.get(f"/search-results/{evt['result_id']}?offset={off}&limit=5"
                             ).get_json()['results']
    assert joined == legacy['results']
