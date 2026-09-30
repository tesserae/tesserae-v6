"""The assistant's model client is configured by environment: a local
llama-server by default, or a keyed OpenAI-compatible gateway. These tests
pin the request shape for both arrangements without any network."""
import importlib
import json


def _reload(monkeypatch, **env):
    for k in ('TESSERAE_LLM_URL', 'TESSERAE_LLM_MODEL', 'TESSERAE_LLM_API_KEY', 'TESSERAE_LLM_EXTRA_JSON'):
        monkeypatch.delenv(k, raising=False)
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    from backend.assistant import model
    return importlib.reload(model)


def test_local_default_has_no_key_and_no_extra_fields(monkeypatch):
    m = _reload(monkeypatch)
    assert m.ENDPOINT == 'http://127.0.0.1:8081'
    assert m.MODEL_NAME == 'local'
    assert 'Authorization' not in m._headers()
    body = json.loads(m._body('sys', 'usr', 100, 0.2))
    assert body == {'model': 'local', 'messages': [{'role': 'system', 'content': 'sys'},
                                                   {'role': 'user', 'content': 'usr'}],
                    'temperature': 0.2, 'max_tokens': 100}


def test_gateway_sends_bearer_key_and_extra_fields(monkeypatch):
    m = _reload(monkeypatch, TESSERAE_LLM_URL='https://gw.example/', TESSERAE_LLM_MODEL='Some/Model',
                TESSERAE_LLM_API_KEY='sk-test',
                TESSERAE_LLM_EXTRA_JSON='{"chat_template_kwargs": {"enable_thinking": false}}')
    assert m.ENDPOINT == 'https://gw.example'
    assert m._headers()['Authorization'] == 'Bearer sk-test'
    body = json.loads(m._body('s', 'u', 50, 0.0, stream=True))
    assert body['model'] == 'Some/Model'
    assert body['stream'] is True
    assert body['chat_template_kwargs'] == {'enable_thinking': False}


def test_malformed_extra_json_is_ignored(monkeypatch):
    m = _reload(monkeypatch, TESSERAE_LLM_EXTRA_JSON='{not json')
    assert m.EXTRA_FIELDS == {}


def test_availability_is_cached(monkeypatch):
    m = _reload(monkeypatch)
    calls = []

    class _Resp:
        def __init__(self, payload):
            self._p = payload

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return json.dumps(self._p).encode()

    def fake_urlopen(req, timeout=0):
        calls.append(req.full_url)
        return _Resp({'healthy_endpoints': []})  # gateway-style body, no 'status'

    monkeypatch.setattr(m.urllib.request, 'urlopen', fake_urlopen)
    assert m.is_available() is True
    assert m.is_available() is True
    assert len(calls) == 1


def test_llama_server_status_not_ok_means_unavailable(monkeypatch):
    m = _reload(monkeypatch)

    class _Resp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return b'{"status": "loading model"}'

    monkeypatch.setattr(m.urllib.request, 'urlopen', lambda req, timeout=0: _Resp())
    assert m.is_available() is False
