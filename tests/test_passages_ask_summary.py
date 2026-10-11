"""POST /passages/ask-summary with the model faked."""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.app import app  # noqa: E402
from backend.assistant import model  # noqa: E402
from backend.blueprints import passages  # noqa: E402

PASSAGES = [{'ref': 'tac. ann. 4.1', 'gist': 'Sejanus gains power.'},
            {'ref': 'tac. ann. 4.2', 'gist': 'He builds a camp.'},
            {'ref': 'tac. ann. 4.3', 'gist': 'Unused.'}]


def _post(body):
    r = app.test_client().post('/api/passages/ask-summary', json=body)
    assert r.status_code == 200
    return json.loads(r.get_data())


def _body():
    return {'question': 'the rise of Sejanus', 'work_label': 'Tacitus, Annals',
            'passages': PASSAGES}


def test_prompt_carries_question_label_and_every_line(monkeypatch):
    seen = {}

    def fake(system, user, max_tokens=0, temperature=0):
        seen['system'], seen['user'] = system, user
        return 'Sejanus rises (tac. ann. 4.1) and builds a camp (tac. ann. 4.2).'

    monkeypatch.setattr(model, 'is_available', lambda: True)
    monkeypatch.setattr(model, 'complete', fake)
    out = _post(_body())
    assert out['available'] is True
    assert 'at most 120 words' in seen['system']
    lines = seen['user'].split('\n')
    assert lines[0] == 'Tacitus, Annals' and lines[1] == 'the rise of Sejanus'
    for p in PASSAGES:
        assert f"{p['ref']}: {p['gist']}" in lines
    assert out['cites'] == ['tac. ann. 4.1', 'tac. ann. 4.2']


def test_unavailable_model(monkeypatch):
    monkeypatch.setattr(model, 'is_available', lambda: False)
    assert _post(_body()) == {'available': False}


def test_model_error(monkeypatch):
    monkeypatch.setattr(model, 'is_available', lambda: True)
    monkeypatch.setattr(model, 'complete', lambda *a, **k: None)
    out = _post(_body())
    assert out['available'] is False and out['error']


def test_timeout(monkeypatch):
    monkeypatch.setattr(model, 'is_available', lambda: True)
    monkeypatch.setattr(model, 'complete', lambda *a, **k: time.sleep(1) or 'late')
    monkeypatch.setattr(passages, '_SUMMARY_TIMEOUT', 0.05)
    out = _post(_body())
    assert out['available'] is False and out['error']


def test_at_most_twelve_passages(monkeypatch):
    seen = {}
    monkeypatch.setattr(model, 'is_available', lambda: True)
    monkeypatch.setattr(model, 'complete',
                        lambda s, u, *a, **k: seen.setdefault('u', u) and 'x')
    body = _body()
    body['passages'] = [{'ref': f'r{i}', 'gist': f'g{i}'} for i in range(20)]
    _post(body)
    assert len(seen['u'].split('\n')) == 2 + 12
