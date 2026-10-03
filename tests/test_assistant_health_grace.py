"""A failed health check shortly after a good one does not mark Tessa unavailable."""
import io
from unittest import mock
from backend.assistant import model


def _reset(monkeypatch):
    monkeypatch.setattr(model, '_availability', {'at': 0.0, 'ok': False, 'last_ok': 0.0})


def test_good_check_then_slow_check_stays_available(monkeypatch):
    _reset(monkeypatch)
    clock = {'t': 1000.0}
    monkeypatch.setattr(model.time, 'time', lambda: clock['t'])
    with mock.patch.object(model, '_open', return_value=io.BytesIO(b'{"healthy_count": 0}')):
        assert model.is_available() is True
    clock['t'] += 60
    with mock.patch.object(model, '_open', side_effect=TimeoutError('slow')):
        assert model.is_available() is True


def test_long_failure_marks_unavailable(monkeypatch):
    _reset(monkeypatch)
    clock = {'t': 1000.0}
    monkeypatch.setattr(model.time, 'time', lambda: clock['t'])
    with mock.patch.object(model, '_open', return_value=io.BytesIO(b'{}')):
        assert model.is_available() is True
    clock['t'] += model._AVAILABILITY_GRACE + 30
    with mock.patch.object(model, '_open', side_effect=TimeoutError('slow')):
        assert model.is_available() is False
