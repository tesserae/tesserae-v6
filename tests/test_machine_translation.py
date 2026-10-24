"""The machine translation route: prompt, cache, line cap, ceiling, refusal of paid settings."""
import threading

import pytest

from backend import machine_translation as mt
from backend.app import API_PREFIX, app

P = API_PREFIX
URL = f'{P}/translation/machine'


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(mt, 'CACHE_DIR', str(tmp_path))
    monkeypatch.setattr(mt, '_busy', set())
    app.config['TESTING'] = True
    with app.test_client() as c:
        yield c


def _lines(n):
    return {'lines': [{'ref': f'1.{i}', 'text': f'verbum {i}'} for i in range(1, n + 1)], 'capped': False}


@pytest.fixture
def gateway(monkeypatch):
    calls = []

    def fake(prompt, model):
        calls.append((prompt, model))
        return 'Word one\nWord two'
    monkeypatch.setattr(mt, '_call_gateway', fake)
    monkeypatch.setattr('backend.blueprints.passages.window_texts.quick_lines',
                        lambda *a, **k: _lines(2))
    return calls


def test_prompt_text_and_answer_shape(client, gateway):
    d = client.get(URL, query_string={'work': 'horace.odes', 'refs': '1.1|1.2', 'language': 'la'}).get_json()
    prompt, model = gateway[0]
    assert model == 'zai-org/GLM-5.2'
    assert prompt.startswith('Translate the following Latin passage into plain modern English prose.')
    assert 'Give one version only, with no commentary.' in prompt
    assert prompt.endswith('verbum 1\nverbum 2')
    assert d['available'] and d['model'] == 'GLM-5.2' and d['lines'] == ['Word one', 'Word two']
    assert d['kind']['form'] == 'verse' and d['reliability'] == {'right': 16, 'nearly': 8, 'wrong': 1, 'of': 25}


def test_second_call_is_a_cache_hit(client, gateway):
    q = {'work': 'horace.odes', 'refs': '1.1|1.2', 'language': 'la'}
    client.get(URL, query_string=q)
    d = client.get(URL, query_string=q).get_json()
    assert len(gateway) == 1 and d['cached'] is True


def test_untested_language_has_no_figure(client, gateway):
    d = client.get(URL, query_string={'work': 'ghalib.diwan', 'refs': '1.1', 'language': 'ur'}).get_json()
    assert d['available'] and d['reliability'] is None


def test_line_cap(client, gateway):
    refs = '|'.join(f'1.{i}' for i in range(1, 42))
    r = client.get(URL, query_string={'work': 'horace.odes', 'refs': refs, 'language': 'la'})
    assert r.status_code == 400 and 'limited to 40 lines' in r.get_json()['reason']
    assert gateway == []


def test_ceiling_gives_429(client, gateway, monkeypatch):
    sem = threading.Semaphore(0)
    monkeypatch.setattr(mt, '_gate', sem)
    r = client.get(URL, query_string={'work': 'horace.odes', 'refs': '1.1|1.2', 'language': 'la'})
    assert r.status_code == 429 and 'busy' in r.get_json()['reason']


def test_one_request_per_visitor(client, gateway, monkeypatch):
    monkeypatch.setattr(mt, '_busy', {'127.0.0.1'})
    r = client.get(URL, query_string={'work': 'horace.odes', 'refs': '1.1', 'language': 'la'})
    assert r.status_code == 429 and 'already' in r.get_json()['reason']


@pytest.mark.parametrize('name', ['claude-opus', 'gpt-4o', 'no-slash', 'anthropic/claude-3', 'x/gemini-pro'])
def test_non_gateway_model_names_are_refused(name):
    assert mt.configured_model({'TESSERAE_TRANSLATE_MODEL': name}) == mt.DEFAULT_MODEL


def test_paid_gateway_address_switches_it_off():
    assert mt.configured_model({'TESSERAE_LLM_URL': 'https://api.openai.com'}) is None


def test_gateway_model_name_is_accepted():
    assert mt.configured_model({'TESSERAE_TRANSLATE_MODEL': 'Qwen/Qwen3.6-27B'}) == 'Qwen/Qwen3.6-27B'


def test_quick_lines_reads_a_range_and_falls_back(tmp_path, monkeypatch):
    import sqlite3
    from backend import window_texts
    db = tmp_path / 'w.db'
    c = sqlite3.connect(db)
    c.execute('CREATE TABLE lines (work TEXT, ord INTEGER, ref TEXT, text TEXT)')
    c.executemany('INSERT INTO lines VALUES (?,?,?,?)', [('w', i, f'w. 1.{i}', f'line {i}') for i in range(1, 11)])
    c.commit()
    c.close()
    monkeypatch.setattr(window_texts, 'DB', str(db))
    monkeypatch.setattr(window_texts, '_local', threading.local())
    got = window_texts.quick_lines('w.tess', 'w. 1.3', 'w. 1.6')
    assert [x['text'] for x in got['lines']] == ['line 3', 'line 4', 'line 5', 'line 6'] and not got['capped']
    capped = window_texts.quick_lines('w', 'w. 1.1', 'w. 1.10', cap=4)
    assert capped['capped'] and capped['returned'] == 4 and capped['total'] == 10
    monkeypatch.setattr(window_texts, 'passage_lines', lambda *a, **k: {'lines': [], 'error': 'fallback'})
    assert window_texts.quick_lines('w', 'nope', 'w. 1.2')['error'] == 'fallback'
