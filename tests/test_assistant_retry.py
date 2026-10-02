"""The assistant retries a request the gateway refuses with 429 (2026-10-01: the
campus gateway refused about four requests in ten, intermittently)."""
import io
import urllib.error
from unittest import mock

from backend.assistant import model


def _http_error(code):
    return urllib.error.HTTPError('http://x', code, 'refused', hdrs=None, fp=io.BytesIO(b''))


def test_open_retries_a_429_then_succeeds(monkeypatch):
    monkeypatch.setattr(model, '_RETRY_PAUSE', 0)
    calls = {'n': 0}

    def fake_urlopen(req, timeout):
        calls['n'] += 1
        if calls['n'] < 3:
            raise _http_error(429)
        return io.BytesIO(b'{"ok": true}')

    with mock.patch.object(model.urllib.request, 'urlopen', fake_urlopen):
        with model._open(object(), 5) as r:
            assert r.read() == b'{"ok": true}'
    assert calls['n'] == 3


def test_open_gives_up_after_the_last_try(monkeypatch):
    monkeypatch.setattr(model, '_RETRY_PAUSE', 0)
    with mock.patch.object(model.urllib.request, 'urlopen', side_effect=_http_error(429)) as m:
        try:
            model._open(object(), 5)
            assert False, 'expected HTTPError'
        except urllib.error.HTTPError as e:
            assert e.code == 429
        assert m.call_count == model._RETRY_TRIES


def test_other_errors_are_not_retried(monkeypatch):
    monkeypatch.setattr(model, '_RETRY_PAUSE', 0)
    with mock.patch.object(model.urllib.request, 'urlopen', side_effect=_http_error(401)) as m:
        try:
            model._open(object(), 5)
            assert False, 'expected HTTPError'
        except urllib.error.HTTPError as e:
            assert e.code == 401
        assert m.call_count == 1
