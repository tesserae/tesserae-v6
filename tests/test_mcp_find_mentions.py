"""The connector tool find_mentions: hidden unless TESSERAE_ENTITY_TOOLS=1, and both forms of the
call answered from the fixture entity store through the real /entities routes."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pytest  # noqa: E402

import backend.blueprints.mcp_http as M  # noqa: E402
from backend.app import app  # noqa: E402
from test_entities_routes import P, store  # noqa: E402,F401  (the fixture store)


@pytest.fixture
def through_site(store, monkeypatch):  # noqa: F811
    """Route the tool's internal GETs to the Flask test client, so the fixture store answers."""
    client = app.test_client()

    class Resp:
        def __init__(self, r):
            self.r = r
            self.status_code = r.status_code

        def json(self):
            return self.r.get_json()

        def raise_for_status(self):
            if self.r.status_code >= 400:
                import requests
                raise requests.HTTPError(response=self)

    def fake_get(path, params=None):
        r = Resp(client.get(f'{P[:-len("/entities")]}{path}', query_string=params or {}))
        r.raise_for_status()
        return r.json()

    monkeypatch.setattr(M, '_get', fake_get)


def _call(mid, args):
    return M._handle({"jsonrpc": "2.0", "id": mid, "method": "tools/call",
                      "params": {"name": "find_mentions", "arguments": args}})


def test_find_mentions_hidden_and_refused_when_flag_is_unset(monkeypatch):
    monkeypatch.delenv('TESSERAE_ENTITY_TOOLS', raising=False)
    monkeypatch.setenv('TESSERAE_SCHOLARSHIP_TOOLS', '1')
    names = {t['name'] for t in M._handle({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})["result"]["tools"]}
    assert 'find_mentions' not in names and 'find_scholarship' in names
    assert _call(2, {'name': 'Troy'})['error']['code'] == -32602


def test_find_mentions_listed_when_flag_is_set(monkeypatch):
    monkeypatch.setenv('TESSERAE_ENTITY_TOOLS', '1')
    monkeypatch.delenv('TESSERAE_SCHOLARSHIP_TOOLS', raising=False)
    names = {t['name'] for t in M._handle({"jsonrpc": "2.0", "id": 3, "method": "tools/list"})["result"]["tools"]}
    assert 'find_mentions' in names and 'find_scholarship' not in names


def test_by_name_returns_entities_with_headings_and_counts(through_site, monkeypatch):
    monkeypatch.setenv('TESSERAE_ENTITY_TOOLS', '1')
    out = M._t_find_mentions({'name': 'troia'})
    assert out['results'][0]['id'] == 'ln:E1'
    assert out['results'][0]['heading']
    assert out['results'][0]['type'] == 'place'
    assert out['results'][0]['mention_counts'] == {'la': 1, 'grc': 1}
    assert 'trial' in out['presentation']


def test_by_entity_id_returns_lines_with_work_reference_and_text(through_site):
    out = M._t_find_mentions({'entity_id': 'ln:E2'})
    assert out['total_lines'] == 2 and out['page'] == 1 and out['has_more'] is False
    assert out['entity']['id'] == 'ln:E2'
    first = out['results'][0]
    assert first['work'] == 'vergil.aeneid' and first['text'] and first['reference']
    assert first['matched_form'] == 'Mars'
    assert first['name_shared_with'] == ['Mars (Roman family)']


def test_by_entity_id_with_language_filters(through_site):
    out = M._t_find_mentions({'entity_id': 'ln:E1', 'language': 'grc'})
    assert out['total_lines'] == 1 and out['results'][0]['language'] == 'grc'


def test_page_two_is_an_offset_of_one_page_and_is_capped_at_fifty(monkeypatch):
    seen = {}

    def fake_get(path, params=None):
        seen.update(params)
        return {'entity': {'id': 'x'}, 'total': 120, 'results': []}
    monkeypatch.setattr(M, '_get', fake_get)
    out = M._t_find_mentions({'entity_id': 'x', 'page': 2})
    assert seen == {'offset': 50, 'limit': 50} and out['has_more'] is True


def test_missing_arguments_and_unknown_entity_answer_plainly(through_site):
    assert 'error' in M._t_find_mentions({})
    assert M._t_find_mentions({'entity_id': 'ln:nope'})['error'] == 'No entity ln:nope.'
