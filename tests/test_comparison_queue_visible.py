"""A comparison that has to wait says so: place in line (gate), the GET poll
answering "queued", the plain message when the wait runs out."""
import json
import os
import sys
import time

import pytest
from flask import Flask

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import backend.blueprints.fusion as F
import backend.concurrency_gate as G
from backend.cache import get_cache_key


@pytest.fixture
def gate_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(G, 'LOCK_DIR', str(tmp_path))
    monkeypatch.setattr(G.MemoryReaper, 'start', classmethod(lambda cls: None))
    monkeypatch.setattr(G.ConcurrencyConfig, 'get_queue_poll_interval',
                        classmethod(lambda cls: 0.0))
    return tmp_path


def _block(monkeypatch, kind='slots'):
    def fake(self):
        self.block_kind = kind
        self.running = 3
        return False, 'blocked'
    monkeypatch.setattr(G.SearchSlot, '_can_proceed', fake)


def test_position_counts_the_requests_waiting_ahead(gate_dir, monkeypatch):
    _block(monkeypatch)
    first, second = G.SearchSlot(), G.SearchSlot()
    g1, g2 = first.acquire(), second.acquire()
    e1 = next(g1)
    e2 = next(g2)
    assert (e1['position'], e2['position']) == (1, 2)
    assert e1['kind'] == 'slots' and e1['running'] == 3 and e1['status'] == 'queued'
    # The first gives up: the second moves to the head of the line.
    g1.close()
    assert next(g2)['position'] == 1
    g2.close()
    assert [n for n in os.listdir(gate_dir) if n.endswith('.wait')] == []


def test_a_dead_waiters_ticket_is_ignored_and_removed(gate_dir):
    stale = gate_dir / 'wait_1_2_3.wait'
    stale.write_text('')
    assert G._live_waiter_tickets() == []
    assert not stale.exists()


def test_free_slot_goes_to_the_head_of_the_line(gate_dir, monkeypatch):
    _block(monkeypatch)
    older, newer = G.SearchSlot(), G.SearchSlot()
    go, gn = older.acquire(), newer.acquire()
    next(go)
    assert next(gn)['position'] == 2
    monkeypatch.setattr(G.SearchSlot, '_can_proceed', lambda self: (True, ''))
    # The newer request sees a free slot but stays behind the older one.
    event = next(gn)
    assert event['position'] == 2
    with pytest.raises(StopIteration):
        next(go)
    older.release()
    go.close()
    gn.close()


def test_queued_line_wording():
    slots = G.queued_line({'kind': 'slots', 'running': 3, 'position': 1,
                           'max_searches': 3, 'wait_time': 75,
                           'queue_timeout': 1800})
    assert slots == ('Waiting to start: 3 comparisons are ahead of yours '
                     '(the server lets three run at once). Waiting for 1:15 so far. '
                     'The server holds a request for up to thirty minutes, then stops it '
                     'and offers the comparison as a prepared file.')
    memory = G.queued_line({'kind': 'memory', 'wait_time': 9})
    assert memory.startswith("Waiting to start: the server's memory is in use by other searches")
    assert memory.endswith('Waiting for 0:09 so far.')  # no limit given, no limit sentence


def test_timeout_message_is_plain():
    text = G.queue_timeout_message(1800)
    assert text == ('The server stayed busy for thirty minutes and your comparison was not '
                    'started. Try again later, or ask for it as a prepared file.')
    assert 'timeout' not in text.lower()


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(F, 'CACHE_DIR', str(tmp_path))
    monkeypatch.setattr(F, 'resolve_text_path', lambda d, lang, tid: f'/x/{tid}.tess')
    monkeypatch.setattr(F, '_poll_use_meter', lambda s, t, l: False)
    monkeypatch.setattr(F, 'ensure_cache_dir', lambda: None)
    monkeypatch.setattr(F, '_cached_fusion_view', lambda *a, **k: (None, None, None))
    monkeypatch.setattr(F.compare_limit, 'check_size', lambda *a, **k: None)
    app = Flask(__name__)
    app.register_blueprint(F.fusion_bp)
    key = get_cache_key('a', 'b', 'la', F._default_fusion_cache_settings('la', 5000, False))
    return app.test_client(), key


def _poll(c):
    return c.get('/fusion-search?source=a&target=b&language=la')


def test_poll_answers_queued_from_a_status_file(client):
    c, key = client
    open(F._fusion_marker(key, 'running'), 'w').close()
    F._write_queued_status(key, {'reason': 'Server memory low', 'kind': 'memory',
                                 'wait_time': 42.0, 'position': 2, 'running': 1,
                                 'max_searches': 3})
    body = _poll(c).get_json()
    assert body['status'] == 'queued'
    assert body['kind'] == 'memory' and body['position'] == 2
    assert body['wait_seconds'] == 42.0 and body['reason'] == 'Server memory low'
    assert "memory is in use" in body['message']


def test_poll_answers_running_once_the_wait_is_over(client):
    c, key = client
    open(F._fusion_marker(key, 'running'), 'w').close()
    F._write_queued_status(key, {'kind': 'slots', 'wait_time': 1})
    F._clear_fusion_status(key)
    assert _poll(c).get_json()['status'] == 'running'


def test_poll_reports_a_timeout_in_plain_words_once(client):
    c, key = client
    with open(F._fusion_marker(key, 'timeout'), 'w') as f:
        f.write(G.queue_timeout_message(1800))
    r = _poll(c)
    body = r.get_json()
    assert r.status_code == 503
    assert body['status'] == 'error' and body['code'] == 'queue_timeout'
    assert body['message'].startswith('The server stayed busy for thirty minutes')
    assert not os.path.exists(F._fusion_marker(key, 'timeout'))


def test_job_writes_queue_status_and_a_timeout_marker(tmp_path, monkeypatch):
    monkeypatch.setattr(F, 'CACHE_DIR', str(tmp_path))
    seen = []

    class FakeSlot:
        def acquire(self):
            yield {'status': 'queued', 'reason': 'r', 'kind': 'slots', 'wait_time': 2,
                   'position': 1, 'running': 3, 'max_searches': 3}
            seen.append(F._read_fusion_status('k'))
            raise TimeoutError('Search queue timeout after 1800s: r')

        def release(self):
            pass

    monkeypatch.setattr(F, 'SearchSlot', FakeSlot)
    monkeypatch.setattr(G.ConcurrencyConfig, 'get_queue_timeout', classmethod(lambda cls: 1800))
    open(F._fusion_marker('k', 'running'), 'w').close()
    F._run_fusion_job('a', 'b', 'la', 5000, 'k')
    assert seen[0]['phase'] == 'queued' and seen[0]['position'] == 1
    assert 'thirty minutes' in open(F._fusion_marker('k', 'timeout')).read()
    assert not os.path.exists(F._fusion_marker('k', 'running'))
