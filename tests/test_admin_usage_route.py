"""GET /admin/usage: admin only, serves the summary file or says it is not built."""
import json
import os
import sys
import types

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest  # noqa: E402

from backend.app import app, API_PREFIX  # noqa: E402
from backend.blueprints import admin  # noqa: E402

URL = f'{API_PREFIX}/admin/usage'


@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as c:
        yield c


def sign_in(client, monkeypatch):
    with client.session_transaction() as sess:
        sess['admin_user_id'] = 7
        sess['admin_roles'] = ['ADMIN']
        sess['admin_session_version'] = 1
    user = types.SimpleNamespace(id=7, session_version=1)
    monkeypatch.setattr(admin, 'User', types.SimpleNamespace(
        query=types.SimpleNamespace(get=lambda _id: user)))


def test_unauthorised(client):
    assert client.get(URL).status_code == 401


def test_missing_file(client, monkeypatch, tmp_path):
    sign_in(client, monkeypatch)
    monkeypatch.setenv('TESSERAE_USAGE_STATS', str(tmp_path / 'none.json'))
    r = client.get(URL)
    assert r.status_code == 200
    assert r.get_json()['available'] is False
    assert r.get_json()['reason']


def test_present_file(client, monkeypatch, tmp_path):
    sign_in(client, monkeypatch)
    f = tmp_path / 'u.json'
    payload = {'built_at': 'x', 'months': [{'month': '2026-09', 'app_loads': 3}]}
    f.write_text(json.dumps(payload))
    monkeypatch.setenv('TESSERAE_USAGE_STATS', str(f))
    r = client.get(URL)
    assert r.status_code == 200
    assert r.get_json() == payload
