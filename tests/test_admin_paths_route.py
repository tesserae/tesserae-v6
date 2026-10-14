"""GET /admin/paths: authorization, the empty case, and figures for three visits."""
import os
import sys
import types
from contextlib import contextmanager
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest  # noqa: E402

from backend.app import app, API_PREFIX  # noqa: E402
from backend.blueprints import admin  # noqa: E402

URL = f'{API_PREFIX}/admin/paths' if API_PREFIX else '/admin/paths'


def fake_db(rows, fail=False):
    @contextmanager
    def cursor(commit=True):
        if fail:
            raise RuntimeError('relation "page_views" does not exist')
        cur = types.SimpleNamespace()
        cur.execute = lambda sql, params=None: setattr(cur, 'params', params)
        cur.fetchall = lambda: list(rows)
        yield cur
    return cursor


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


def test_requires_admin(client):
    assert client.get(URL).status_code == 401


def test_empty(client, monkeypatch):
    monkeypatch.setattr(admin, 'get_db_cursor', fake_db([]))
    sign_in(client, monkeypatch)
    d = client.get(URL).get_json()
    assert d['available'] is True
    assert d['visits'] == 0 and d['page_views'] == 0 and d['top_paths'] == []


def test_missing_table_reports_unavailable(client, monkeypatch):
    monkeypatch.setattr(admin, 'get_db_cursor', fake_db([], fail=True))
    sign_in(client, monkeypatch)
    assert client.get(URL).get_json()['available'] is False


def test_days_clamped(client, monkeypatch):
    monkeypatch.setattr(admin, 'get_db_cursor', fake_db([]))
    sign_in(client, monkeypatch)
    assert client.get(URL + '?days=9999').get_json()['days'] == 365
    assert client.get(URL + '?days=abc').get_json()['days'] == 30


def test_three_visits(client, monkeypatch):
    t = lambda d, h: datetime(2026, 10, d, h)  # noqa: E731
    rows = [
        # visit a: search, read, about (France, referred)
        ('a', 'search', 'France', 'example.org', t(8, 9)),
        ('a', 'read', 'France', 'example.org', t(8, 10)),
        ('a', 'about', 'France', 'example.org', t(8, 11)),
        # visit b: search, read (France)
        ('b', 'search', 'France', None, t(9, 9)),
        ('b', 'read', 'France', None, t(9, 10)),
        # visit c: one page (Peru)
        ('c', 'theme-search', 'Peru', None, t(9, 12)),
    ]
    monkeypatch.setattr(admin, 'get_db_cursor', fake_db(rows))
    sign_in(client, monkeypatch)
    d = client.get(URL).get_json()
    assert d['visits'] == 3 and d['page_views'] == 6
    assert d['pages_per_visit_median'] == 2
    assert d['one_page_visits'] == 1
    assert d['visits_by_day'] == [
        {'date': '2026-10-08', 'visits': 1, 'page_views': 3},
        {'date': '2026-10-09', 'visits': 2, 'page_views': 3},
    ]
    assert d['entry_pages'][0] == {'page': 'search', 'visits': 2}
    assert d['top_paths'] == [
        {'path': 'search > read', 'visits': 1},
        {'path': 'search > read > about', 'visits': 1},
    ]
    reached = {p['page']: p['visits'] for p in d['pages_reached']}
    assert reached == {'search': 2, 'read': 2, 'about': 1, 'theme-search': 1}
    assert d['countries'][0] == {'country': 'France', 'visits': 2}
    assert d['referrer_hosts'] == [{'host': 'example.org', 'visits': 1}]
