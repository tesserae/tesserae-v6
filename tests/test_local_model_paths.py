"""Query expansion and note translation go through the assistant's model
client (the gateway on production) rather than posting to the local
llama-server on their own (2026-10-12)."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from backend import passage_index as pi  # noqa: E402
from backend.assistant import model  # noqa: E402


def test_expansion_uses_the_model_client(tmp_path, monkeypatch):
    monkeypatch.delenv('TESSERAE_EXPAND_ENDPOINT', raising=False)
    monkeypatch.setattr(pi, 'EXPAND_CACHE_PATH', str(tmp_path / 'exp.jsonl'))
    pi._expand_cache.clear()
    pi._expand_cache_mtime[0] = 0.0
    seen = {}

    def fake_complete(system, user, max_tokens, temperature):
        seen.update(system=system, user=user, max_tokens=max_tokens, temperature=temperature)
        return '{"forms": ["a warrior puts on his armour", "a hero arms for battle"]}'
    monkeypatch.setattr(model, 'complete', fake_complete)
    assert pi.expand_query('warrior arming') == ['a warrior puts on his armour', 'a hero arms for battle']
    assert seen['user'] == 'warrior arming' and seen['temperature'] == 0.0


def test_expansion_survives_a_silent_model(tmp_path, monkeypatch):
    monkeypatch.delenv('TESSERAE_EXPAND_ENDPOINT', raising=False)
    monkeypatch.setattr(pi, 'EXPAND_CACHE_PATH', str(tmp_path / 'exp.jsonl'))
    pi._expand_cache.clear()
    pi._expand_cache_mtime[0] = 0.0
    monkeypatch.setattr(model, 'complete', lambda *a, **k: None)
    assert pi.expand_query('plague at athens') == []


def _client(monkeypatch, tmp_path, answer):
    from backend.app import app
    from backend.blueprints import scholarship as bp
    monkeypatch.setattr(bp, '_held_note', lambda work, ref, text, commentator=None: {'commentator': 'Servius', 'language': 'la'})
    monkeypatch.setattr(bp, '_XLAT_DIR', str(tmp_path / 'xlat'))
    monkeypatch.delenv('TESSERAE_LOCAL_LLM', raising=False)
    monkeypatch.setattr(model, 'complete', lambda *a, **k: answer)
    app.config['TESTING'] = True
    return app.test_client()


def test_translation_uses_the_model_client(tmp_path, monkeypatch):
    c = _client(monkeypatch, tmp_path, '"arma" means weapons here.')
    r = c.post('/api/scholarship/translate', json={'work': 'vergil.aeneid', 'ref': '1.1', 'text': 'arma: tela.'})
    assert r.status_code == 200
    assert r.get_json()['available'] is True
    assert r.get_json()['text'] == '"arma" means weapons here.'


def test_translation_says_when_the_model_is_silent(tmp_path, monkeypatch):
    c = _client(monkeypatch, tmp_path, None)
    r = c.post('/api/scholarship/translate', json={'work': 'vergil.aeneid', 'ref': '1.1', 'text': 'arma: tela.'})
    assert r.get_json()['available'] is False
    assert 'did not answer' in r.get_json()['reason']
