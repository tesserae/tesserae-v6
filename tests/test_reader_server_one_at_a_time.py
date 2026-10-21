"""The reader service scores one request at a time and turns away one it cannot start in time."""
import importlib.util
import os
import threading
import time

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture
def server():
    spec = importlib.util.spec_from_file_location('reader_server', os.path.join(ROOT, 'services', 'reader_server.py'))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_a_second_request_waits_and_is_turned_away_when_the_first_runs_long(server, monkeypatch):
    started = threading.Event()

    def slow(query, passages):
        started.set()
        time.sleep(0.5)
        return {'a': 1.0}

    monkeypatch.setattr(server, 'score_passages', slow)
    out = {}
    t = threading.Thread(target=lambda: out.setdefault('first', server.score_passages_one_at_a_time('q', [])))
    t.start()
    started.wait(2)
    with pytest.raises(server.Busy):
        server.score_passages_one_at_a_time('q', [], wait=0.05)
    t.join()
    assert out['first'] == {'a': 1.0}
    assert server.score_passages_one_at_a_time('q', [], wait=0.05) == {'a': 1.0}


def test_the_lock_is_released_after_a_failure(server, monkeypatch):
    def boom(query, passages):
        raise RuntimeError('model failed')

    monkeypatch.setattr(server, 'score_passages', boom)
    with pytest.raises(RuntimeError):
        server.score_passages_one_at_a_time('q', [])
    monkeypatch.setattr(server, 'score_passages', lambda q, p: {})
    assert server.score_passages_one_at_a_time('q', [], wait=0.05) == {}
