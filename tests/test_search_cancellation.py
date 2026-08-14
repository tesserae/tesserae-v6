"""Regression coverage for cooperative search cancellation."""

import threading
import time
import uuid
import os
import sys

import pytest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend import search_cancellation
from backend.search_cancellation import (
    SearchCancellation,
    SearchCancelled,
    cancellable_pool_map,
    request_cancellation,
)
from backend.concurrency_gate import SearchSlot


def _slow_worker(value):
    """Pickle-safe worker used to ensure a cancelled pool is terminated."""
    time.sleep(2)
    return value


def test_cancellation_marker_is_visible_across_request_instances(tmp_path, monkeypatch):
    monkeypatch.setattr(search_cancellation, 'CANCELLATION_DIR', str(tmp_path))
    search_id = str(uuid.uuid4())
    observer = SearchCancellation(search_id)

    request_cancellation(search_id)

    with pytest.raises(SearchCancelled):
        observer.check()

    observer.close()
    assert not (tmp_path / f'{search_id}.cancel').exists()


def test_cancellable_pool_terminates_in_flight_workers():
    cancellation = SearchCancellation()
    timer = threading.Timer(0.1, cancellation.cancel)
    started = time.monotonic()
    timer.start()
    try:
        with pytest.raises(SearchCancelled):
            cancellable_pool_map(_slow_worker, [1], processes=1,
                                 cancellation=cancellation)
    finally:
        timer.cancel()
        timer.join()

    assert time.monotonic() - started < 1.5


def test_search_slot_observes_cancellation_while_queued(monkeypatch):
    cancellation = SearchCancellation()
    slot = SearchSlot(cancellation=cancellation)
    monkeypatch.setattr(slot, '_can_proceed', lambda: (False, 'busy'))

    queued = slot.acquire()
    assert next(queued)['status'] == 'queued'
    cancellation.cancel()

    with pytest.raises(SearchCancelled):
        next(queued)


def test_cancel_endpoint_records_valid_request(tmp_path, monkeypatch):
    from flask import Flask
    from backend.blueprints.search import search_bp

    monkeypatch.setattr(search_cancellation, 'CANCELLATION_DIR', str(tmp_path))
    app = Flask(__name__)
    app.register_blueprint(search_bp)
    search_id = str(uuid.uuid4())

    response = app.test_client().post('/search-cancel', json={'search_id': search_id})

    assert response.status_code == 202
    assert response.get_json() == {'status': 'cancellation_requested'}
    assert (tmp_path / f'{search_id}.cancel').exists()


def test_heartbeat_generator_cancels_matcher_before_executor_shutdown(monkeypatch):
    from backend.blueprints import search as search_blueprint

    def wait_for_cancellation(*args, cancellation=None, **kwargs):
        cancellation = cancellation or args[-1]
        while True:
            cancellation.check()
            time.sleep(0.01)

    monkeypatch.setattr(search_blueprint, '_run_matcher', wait_for_cancellation)
    cancellation = SearchCancellation()
    stream = search_blueprint._run_matcher_with_heartbeats(
        'lemma', [], [], {}, None, cancellation)

    assert next(stream) == ('heartbeat', None)
    stream.close()
    assert cancellation.cancelled


def test_stream_disconnect_releases_search_slot(monkeypatch):
    from flask import Flask
    from backend.blueprints import search as search_blueprint

    class TrackingSlot:
        released = False

        def __init__(self, cancellation=None):
            pass

        def acquire(self):
            return iter(())

        def release(self):
            TrackingSlot.released = True

    def wait_for_cancellation(*args, cancellation=None, **kwargs):
        cancellation = cancellation or args[-1]
        while True:
            cancellation.check()
            time.sleep(0.01)

    params = {
        'source_id': 'source.tess',
        'target_id': 'target.tess',
        'language': 'la',
        'is_crosslingual': False,
        'settings': {
            'match_type': 'lemma',
            'source_unit_type': 'line',
            'target_unit_type': 'line',
        },
    }
    units = [{'ref': '1.1', 'tokens': ['arma'], 'lemmas': ['arma']}]
    monkeypatch.setattr(search_blueprint, 'SearchSlot', TrackingSlot)
    monkeypatch.setattr(search_blueprint, '_parse_search_request', lambda data: params)
    monkeypatch.setattr(search_blueprint, '_get_processed_units', lambda *args: units)
    monkeypatch.setattr(search_blueprint, '_load_corpus_frequencies', lambda *args: None)
    monkeypatch.setattr(search_blueprint, 'get_cached_results', lambda *args: (None, None))
    monkeypatch.setattr(search_blueprint, 'get_user_location', lambda: (None, None, None))
    monkeypatch.setattr(search_blueprint, '_run_matcher', wait_for_cancellation)
    monkeypatch.setattr(search_blueprint, 'current_user', None)

    app = Flask(__name__)
    app.register_blueprint(search_blueprint.search_bp)
    response = app.test_client().post(
        '/search-stream', json={'search_id': str(uuid.uuid4())}, buffered=False)
    stream = iter(response.response)
    while b'Finding matches' not in next(stream):
        pass
    assert next(stream) == b': keep-alive\n\n'

    response.close()
    assert TrackingSlot.released


def test_stream_cancellation_while_queued_releases_search_slot(tmp_path, monkeypatch):
    from flask import Flask
    from backend.blueprints import search as search_blueprint

    search_id = str(uuid.uuid4())

    class QueuedSlot:
        released = False

        def __init__(self, cancellation=None):
            pass

        def acquire(self):
            request_cancellation(search_id)
            yield {'reason': 'busy', 'wait_time': 0}

        def release(self):
            QueuedSlot.released = True

    monkeypatch.setattr(search_cancellation, 'CANCELLATION_DIR', str(tmp_path))
    monkeypatch.setattr(search_blueprint, 'SearchSlot', QueuedSlot)
    monkeypatch.setattr(search_blueprint, 'current_user', None)
    monkeypatch.setattr(search_blueprint, 'get_user_location', lambda: (None, None, None))
    monkeypatch.setattr(search_blueprint, '_parse_search_request', lambda data: {
        'source_id': 'source.tess',
        'target_id': 'target.tess',
        'language': 'la',
        'is_crosslingual': False,
        'settings': {'match_type': 'lemma'},
    })
    monkeypatch.setattr(search_blueprint, 'get_cached_results', lambda *args: (None, None))

    app = Flask(__name__)
    app.register_blueprint(search_blueprint.search_bp)
    response = app.test_client().post(
        '/search-stream', json={'search_id': search_id}, buffered=True)

    assert response.status_code == 200
    assert b'queued' not in response.data
    assert QueuedSlot.released
    assert not (tmp_path / f'{search_id}.cancel').exists()
