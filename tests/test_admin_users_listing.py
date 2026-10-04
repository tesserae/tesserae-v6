"""GET /admin/users: the listing, and how many trips to the database it takes.

The listing used to fetch the users, then call _get_user_roles once per user,
and every call opened its own psycopg2 connection: 1 + N connections and
1 + N statements for N users (measured on Postgres: 1 user -> 2, 10 -> 11,
100 -> 101). It now reads every role assignment in one statement on the same
connection, so the count no longer depends on N.

The database is replaced at the module boundary (admin.get_db_cursor) by a
small in-memory one that counts connections and statements and answers both
the bulk role query and the old per-user one, so the functional tests hold
for either shape and only the counting test tells them apart.
"""
import os
import sys
import types
from contextlib import contextmanager

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest  # noqa: E402

from backend.app import app, API_PREFIX  # noqa: E402
from backend.blueprints import admin  # noqa: E402

USERS_URL = f'{API_PREFIX}/admin/users' if API_PREFIX else '/admin/users'


class FakeDB:
    """users: [(id, email, first, last)] in listing order; assignments: [(user_id, role)]."""

    def __init__(self, users, assignments=()):
        self.users = list(users)
        self.assignments = list(assignments)
        self.connections = 0
        self.statements = 0

    @contextmanager
    def cursor(self, commit=True):
        self.connections += 1
        cur = types.SimpleNamespace(rows=[])

        def execute(sql, params=None):
            self.statements += 1
            if 'user_roles' not in sql:
                cur.rows = list(self.users)
            elif params:  # per-user lookup: WHERE ur.user_id = %s
                cur.rows = [(role,) for uid, role in self.assignments if uid == params[0]]
            else:         # bulk lookup: (user_id, role) for everyone
                cur.rows = list(self.assignments)

        cur.execute = execute
        cur.fetchall = lambda: cur.rows
        yield cur


@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as c:
        yield c


def sign_in_as_admin(client, monkeypatch):
    with client.session_transaction() as sess:
        sess['admin_user_id'] = 7
        sess['admin_roles'] = ['ADMIN']
        sess['admin_session_version'] = 1
    user = types.SimpleNamespace(id=7, session_version=1)
    monkeypatch.setattr(admin, 'User', types.SimpleNamespace(
        query=types.SimpleNamespace(get=lambda _id: user)))


def list_users(client, monkeypatch, db):
    monkeypatch.setattr(admin, 'get_db_cursor', db.cursor)
    sign_in_as_admin(client, monkeypatch)
    resp = client.get(USERS_URL)
    assert resp.status_code == 200, resp.data
    return resp.get_json()['users']


def by_id(users):
    return {u['id']: u for u in users}


# ---------------------------------------------------------------------------
# What the listing says.

def test_one_user_one_role(client, monkeypatch):
    db = FakeDB([('a', 'a@x.edu', 'Ada', 'Lovelace')], [('a', 'ADMIN')])
    assert list_users(client, monkeypatch, db) == [
        {'id': 'a', 'email': 'a@x.edu', 'name': 'Ada Lovelace', 'roles': ['ADMIN']},
    ]


def test_a_user_with_two_roles_appears_once_with_both(client, monkeypatch):
    db = FakeDB([('a', 'a@x.edu', None, None)],
                [('a', 'ADMIN'), ('a', 'SUPER_ADMIN')])
    users = list_users(client, monkeypatch, db)
    assert len(users) == 1
    assert sorted(users[0]['roles']) == ['ADMIN', 'SUPER_ADMIN']


def test_each_user_gets_only_their_own_roles(client, monkeypatch):
    db = FakeDB(
        [('a', 'a@x.edu', None, None), ('b', 'b@x.edu', None, None), ('c', 'c@x.edu', None, None)],
        [('c', 'SUPER_ADMIN'), ('a', 'USER'), ('b', 'ADMIN')],
    )
    users = by_id(list_users(client, monkeypatch, db))
    assert users['a']['roles'] == ['USER']
    assert users['b']['roles'] == ['ADMIN']
    assert users['c']['roles'] == ['SUPER_ADMIN']


def test_a_user_with_no_roles_gets_an_empty_list(client, monkeypatch):
    db = FakeDB([('a', 'a@x.edu', None, None), ('b', 'b@x.edu', None, None)],
                [('b', 'ADMIN')])
    users = by_id(list_users(client, monkeypatch, db))
    assert users['a']['roles'] == []


def test_an_assignment_for_a_missing_user_adds_no_one(client, monkeypatch):
    """user_roles has no foreign key to users, so orphaned rows can exist."""
    db = FakeDB([('a', 'a@x.edu', None, None)], [('ghost', 'ADMIN'), ('a', 'USER')])
    users = list_users(client, monkeypatch, db)
    assert [u['id'] for u in users] == ['a']
    assert users[0]['roles'] == ['USER']


def test_role_names_are_normalized_as_before(client, monkeypatch):
    db = FakeDB([('a', 'a@x.edu', None, None)], [('a', ' admin ')])
    assert list_users(client, monkeypatch, db)[0]['roles'] == ['ADMIN']


def test_fields_and_order_are_unchanged(client, monkeypatch):
    """Same four keys, names joined as before, users in the order the query returned."""
    db = FakeDB([
        ('z', 'z@x.edu', 'Zed', None),
        ('m', 'm@x.edu', None, 'Last'),
        ('a', 'a@x.edu', '', ''),
    ])
    assert list_users(client, monkeypatch, db) == [
        {'id': 'z', 'email': 'z@x.edu', 'name': 'Zed', 'roles': []},
        {'id': 'm', 'email': 'm@x.edu', 'name': 'Last', 'roles': []},
        {'id': 'a', 'email': 'a@x.edu', 'name': None, 'roles': []},
    ]


def test_no_users_is_an_empty_list(client, monkeypatch):
    assert list_users(client, monkeypatch, FakeDB([])) == []


# ---------------------------------------------------------------------------
# How many trips it takes. This is the regression test for the N+1.

def _trips_for(n, client, monkeypatch):
    db = FakeDB([(f'u{i}', f'u{i}@x.edu', None, None) for i in range(n)],
                [(f'u{i}', 'ADMIN') for i in range(n)])
    assert len(list_users(client, monkeypatch, db)) == n
    return db.connections, db.statements


def test_database_trips_do_not_grow_with_the_number_of_users(client, monkeypatch):
    trips = {n: _trips_for(n, client, monkeypatch) for n in (1, 10, 100)}
    assert trips[1] == trips[10] == trips[100], trips
    assert trips[100] == (1, 2), trips  # one connection: users, then all roles


# ---------------------------------------------------------------------------
# The guard in front of it.

@pytest.mark.parametrize('roles', [None, ['USER']])
def test_a_non_admin_is_refused_before_the_database_is_touched(client, monkeypatch, roles):
    db = FakeDB([('a', 'a@x.edu', None, None)], [('a', 'ADMIN')])
    monkeypatch.setattr(admin, 'get_db_cursor', db.cursor)
    if roles:
        with client.session_transaction() as sess:
            sess['admin_user_id'] = 7
            sess['admin_roles'] = roles
            sess['admin_session_version'] = 1
    resp = client.get(USERS_URL)
    assert resp.status_code == 401
    assert db.connections == 0
