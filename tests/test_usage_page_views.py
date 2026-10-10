"""POST /usage/page: recording which pages a visit opened.

The database is replaced at the module boundary by a small in-memory table.
"""
import os
import sys
import types
from contextlib import contextmanager

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest  # noqa: E402

from backend.app import app, API_PREFIX  # noqa: E402
from backend.blueprints import usage  # noqa: E402

URL = f'{API_PREFIX}/usage/page' if API_PREFIX else '/usage/page'
VISIT = 'a1b2c3d4e5f60718293a4b5c'
UA = {'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) Firefox/130.0'}


class FakeTable:
    def __init__(self):
        self.rows = []  # dicts

    @contextmanager
    def cursor(self, commit=True):
        cur = types.SimpleNamespace(result=None)

        def execute(sql, params=None):
            if sql.lstrip().upper().startswith('SELECT'):
                mine = [r for r in self.rows if r['visit_id'] == params[0]]
                city = next((r['city'] for r in mine if r['city']), None)
                country = next((r['country'] for r in mine if r['country']), None)
                cur.result = (len(mine), city, country)
            else:
                keys = ('visit_id', 'path', 'page', 'language', 'referrer_host',
                        'client_ip', 'city', 'country')
                self.rows.append(dict(zip(keys, params)))

        cur.execute = execute
        cur.fetchone = lambda: cur.result
        yield cur


@pytest.fixture
def env(monkeypatch):
    table = FakeTable()
    lookups = []

    def fake_lookup():
        lookups.append(1)
        return 'Paris', 'France', '203.0.113.9'

    monkeypatch.setattr(usage, 'get_db_cursor', table.cursor)
    monkeypatch.setattr(usage.services, 'get_user_location', fake_lookup)
    app.config['TESTING'] = True
    with app.test_client() as c:
        yield c, table, lookups


def post(c, body, headers=UA):
    h = dict(headers)
    h['X-Forwarded-For'] = '203.0.113.9, 10.0.0.1'
    return c.post(URL, json=body, headers=h)


def good(**kw):
    b = {'visit': VISIT, 'path': '/read', 'page': 'read', 'language': 'la',
         'referrer': 'https://example.org/x?y=1'}
    b.update(kw)
    return b


def test_good_post_inserts_row_with_geography(env):
    c, table, lookups = env
    assert post(c, good()).status_code == 204
    assert len(table.rows) == 1
    r = table.rows[0]
    assert (r['city'], r['country']) == ('Paris', 'France')
    assert r['client_ip'] == '203.0.113.9'
    assert r['referrer_host'] == 'example.org'
    assert r['page'] == 'read' and r['language'] == 'la'


def test_second_post_copies_geography_without_lookup(env):
    c, table, lookups = env
    post(c, good())
    post(c, good(path='/about', page='about'))
    assert len(table.rows) == 2
    assert (table.rows[1]['city'], table.rows[1]['country']) == ('Paris', 'France')
    assert len(lookups) == 1


def test_bot_user_agent_ignored(env):
    c, table, _ = env
    assert post(c, good(), headers={'User-Agent': 'Googlebot/2.1'}).status_code == 204
    assert table.rows == []


def test_own_host_referrer_dropped(env):
    c, table, _ = env
    post(c, good(referrer='https://tesserae.caset.buffalo.edu/read'))
    assert table.rows[0]['referrer_host'] is None


@pytest.mark.parametrize('body', [
    {}, {'visit': 'XYZ', 'path': '/', 'page': 'search'},
    {'visit': VISIT, 'path': 'no-slash', 'page': 'search'},
    {'visit': VISIT, 'path': '/' + 'a' * 300, 'page': 'search'},
    {'visit': VISIT, 'path': '/', 'page': 'p' * 61},
    {'visit': VISIT, 'path': '/', 'page': ''},
])
def test_malformed_body_ignored(env, body):
    c, table, _ = env
    assert post(c, body).status_code == 204
    assert table.rows == []


def test_non_json_body_ignored(env):
    c, table, _ = env
    r = c.post(URL, data='not json', headers=UA)
    assert r.status_code == 204
    assert table.rows == []


def test_token_and_key_stripped_from_path(env):
    c, table, _ = env
    post(c, good(path='/theme-search?query=love&token=SECRET&Key=abc&lang=la'))
    stored = table.rows[0]['path']
    assert 'SECRET' not in stored and 'abc' not in stored
    assert stored == '/theme-search?query=love&lang=la'


def test_cap_of_200_views_per_visit(env):
    c, table, _ = env
    for _ in range(200):
        post(c, good())
    assert len(table.rows) == 200
    post(c, good())
    assert len(table.rows) == 200


def test_database_failure_still_204(env, monkeypatch):
    c, _, _ = env

    def boom(commit=True):
        raise RuntimeError('db down')

    monkeypatch.setattr(usage, 'get_db_cursor', boom)
    assert post(c, good()).status_code == 204
