"""Similar Passages tells an unloaded index apart from an uncovered span
(2026-10-11), and a failed load is retried after a pause instead of marking
the index broken for the life of the worker."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend import passage_index as P  # noqa: E402


def test_similar_reports_unavailable_when_index_not_ok(monkeypatch):
    monkeypatch.setattr(P, '_ensure_loaded', lambda: None)
    monkeypatch.setitem(P._state, 'ok', False)
    monkeypatch.setitem(P._state, 'error', 'MemoryError: boom')
    out = P.find_similar_to_passage('vergil.aeneid.part.1', 'verg. aen. 1.20', 'verg. aen. 1.22')
    assert out['unavailable'] is True
    assert out['results'] == []
    assert 'not loaded' in out['error'] and 'MemoryError' in out['error']


def test_similar_reports_no_window_when_index_ok_but_span_uncovered(monkeypatch):
    monkeypatch.setattr(P, '_ensure_loaded', lambda: None)
    monkeypatch.setitem(P._state, 'ok', True)
    monkeypatch.setattr(P, 'window_for_passage', lambda *a, **k: None)
    out = P.find_similar_to_passage('x.y', '1.1', '1.2')
    assert 'unavailable' not in out
    assert out['error'] == 'no indexed window covers that passage'


def test_failed_load_is_retried_after_the_pause(monkeypatch, tmp_path):
    # Point the loader at an empty folder so the files are "absent": that path
    # returns without raising. Then make it raise to exercise the retry.
    monkeypatch.setitem(P._state, 'loaded', False)
    monkeypatch.setitem(P._state, 'ok', False)
    monkeypatch.setitem(P._state, 'retry_at', None)
    monkeypatch.setattr(P, '_DATA_DIR', str(tmp_path))
    for name in ('ids.json', 'embeddings.npy', 'descriptions.jsonl'):
        (tmp_path / name).write_text('x')
    calls = {'n': 0}
    import json as _json

    def bad_load(*a, **k):
        calls['n'] += 1
        raise ValueError('corrupt')
    monkeypatch.setattr(_json, 'load', bad_load)
    P._ensure_loaded()
    assert calls['n'] == 1 and P._state['ok'] is False and P._state['loaded'] is False
    assert P._state['retry_at'] is not None
    # Within the pause: no second attempt.
    P._ensure_loaded()
    assert calls['n'] == 1
    # After the pause: tried again.
    monkeypatch.setitem(P._state, 'retry_at', 0)
    P._ensure_loaded()
    assert calls['n'] == 2
