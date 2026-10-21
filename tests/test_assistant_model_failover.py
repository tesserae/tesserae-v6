"""Tessa switches to a backup model when hers fails, checks it again, and continues a broken stream.

2026-10-21: two gateway models returned HTTP 500 for every request, and an answer broke off
mid-sentence and was shown as if finished.
"""
import io
import json
import urllib.error

import pytest

from backend.assistant import model as M


class FakeResp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _sse(pieces, finish='stop'):
    lines = [b'data: ' + json.dumps({'choices': [{'delta': {'content': p}, 'finish_reason': None}]}).encode()
             for p in pieces]
    if finish:
        lines.append(b'data: ' + json.dumps({'choices': [{'delta': {}, 'finish_reason': finish}]}).encode())
        lines.append(b'data: [DONE]')
    return FakeResp(b'\n'.join(lines) + b'\n')


@pytest.fixture
def gateway(monkeypatch):
    monkeypatch.setattr(M, 'API_KEY', 'k')
    monkeypatch.setattr(M, 'MODEL_NAME', 'main')
    monkeypatch.setattr(M, 'FALLBACK_MODELS', ['backup1', 'backup2'])
    monkeypatch.setattr(M, '_model_down', {})
    monkeypatch.setattr(M, '_model_probe', {})
    monkeypatch.setattr(M, '_recheck_down_models', lambda: None)
    calls = []

    def install(handler):
        def fake(req, timeout=None):
            body = json.loads(req.data)
            calls.append(body)
            return handler(body)
        monkeypatch.setattr(M.urllib.request, 'urlopen', fake)
        return calls
    return install


def _http500(body):
    raise urllib.error.HTTPError('u', 500, 'Internal Server Error', {}, io.BytesIO(b''))


def test_a_failing_model_is_marked_down_and_the_backup_answers(gateway):
    def handler(body):
        if body['model'] == 'main':
            _http500(body)
        return FakeResp(json.dumps({'choices': [{'message': {'content': 'from the backup'}}]}).encode())
    calls = gateway(handler)
    assert M.complete('s', 'u') == 'from the backup'
    assert [c['model'] for c in calls] == ['main', 'backup1']
    assert M.models_in_order()[0] == 'backup1'
    assert calls[1].get('chat_template_kwargs') == {'enable_thinking': False}


def test_a_model_that_answers_its_check_is_used_again(gateway):
    gateway(lambda body: FakeResp(json.dumps({'choices': [{'message': {'content': 'OK'}}]}).encode()))
    M._model_down['main'] = 0.0
    assert M.current_model() == 'backup1'
    M._probe('main')
    assert M.current_model() == 'main'


def test_a_broken_stream_is_continued_from_the_text_already_sent(gateway):
    def handler(body):
        if body.get('continue_final_message'):
            assert body['messages'][-1] == {'role': 'assistant', 'content': 'poetry, prose, and '}
            return _sse(['epistolary letters.'])
        return _sse(['poetry, ', 'prose, and '], finish=None)   # no finish_reason, no [DONE]
    calls = gateway(handler)
    assert ''.join(M.stream('s', 'u')) == 'poetry, prose, and epistolary letters.'
    assert calls[1]['model'] == 'backup1' and calls[1]['add_generation_prompt'] is False


def test_a_finished_stream_is_not_continued(gateway):
    calls = gateway(lambda body: _sse(['A whole answer.']))
    assert ''.join(M.stream('s', 'u')) == 'A whole answer.'
    assert len(calls) == 1 and M.current_model() == 'main'


def test_without_a_gateway_key_there_is_no_backup(gateway, monkeypatch):
    monkeypatch.setattr(M, 'API_KEY', '')
    gateway(_http500)
    assert M.models_in_order() == ['main']
    assert M.complete('s', 'u') is None
