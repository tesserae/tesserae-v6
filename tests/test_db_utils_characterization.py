"""Characterization tests for backend/db_utils.py with a fake psycopg2.

No database is touched. The fake connection records what was done to it, so
each test can say what happened and in what order.
"""
import psycopg2
import pytest

from backend import db_utils


class FakeCursor:
    def __init__(self, log, rows=None):
        self.log, self.rows = log, rows or []

    def execute(self, q, params=None):
        self.log.append(('execute', q, params))

    def fetchone(self):
        return self.rows[0] if self.rows else None

    def fetchall(self):
        return self.rows

    def close(self):
        self.log.append(('cursor_close',))


class FakeConn:
    def __init__(self, rows=None):
        self.log, self.rows = [], rows

    def cursor(self):
        return FakeCursor(self.log, self.rows)

    def commit(self):
        self.log.append(('commit',))

    def rollback(self):
        self.log.append(('rollback',))

    def close(self):
        self.log.append(('conn_close',))


@pytest.fixture
def conn(monkeypatch):
    c = FakeConn()
    monkeypatch.setattr(db_utils, 'DATABASE_URL', 'postgresql://fake')
    monkeypatch.setattr(db_utils.psycopg2, 'connect', lambda url: c)
    return c


def test_cursor_commits_on_success_and_closes_both(conn):
    with db_utils.get_db_cursor() as cur:
        cur.execute('select 1')
    # cursor is closed before the connection; commit comes first
    assert [e[0] for e in conn.log] == ['execute', 'commit', 'cursor_close', 'conn_close']


def test_cursor_without_commit(conn):
    with db_utils.get_db_cursor(commit=False) as cur:
        cur.execute('select 1')
    assert [e[0] for e in conn.log] == ['execute', 'cursor_close', 'conn_close']


def test_cursor_rolls_back_on_exception_and_reraises(conn):
    with pytest.raises(ValueError):
        with db_utils.get_db_cursor() as cur:
            cur.execute('select 1')
            raise ValueError('boom')
    assert [e[0] for e in conn.log] == ['execute', 'rollback', 'cursor_close', 'conn_close']


def test_connection_requires_url(monkeypatch):
    monkeypatch.setattr(db_utils, 'DATABASE_URL', None)
    with pytest.raises(db_utils.DatabaseError, match='DATABASE_URL not configured'):
        with db_utils.get_db_connection():
            pass


def test_connection_failure_becomes_database_error(monkeypatch):
    monkeypatch.setattr(db_utils, 'DATABASE_URL', 'postgresql://fake')

    def refuse(url):
        raise psycopg2.OperationalError('no route')

    monkeypatch.setattr(db_utils.psycopg2, 'connect', refuse)
    with pytest.raises(db_utils.DatabaseError, match='Database connection failed: no route'):
        with db_utils.get_db_connection():
            pass


def test_close_error_is_swallowed(monkeypatch, conn):
    def bad_close():
        raise RuntimeError('already closed')

    conn.close = bad_close
    with db_utils.get_db_connection() as c:
        assert c is conn          # no exception escapes on close


def test_execute_query_fetch_modes(conn):
    conn.rows = [(1, 'a'), (2, 'b')]
    assert db_utils.execute_query('q', (1,), fetch_one=True) == (1, 'a')
    assert db_utils.execute_query('q', fetch_all=True) == [(1, 'a'), (2, 'b')]
    assert db_utils.execute_query('q') is None             # neither flag: nothing returned
    assert ('execute', 'q', (1,)) in conn.log


def test_execute_query_wraps_other_errors(conn, monkeypatch):
    monkeypatch.setattr(FakeCursor, 'execute', lambda self, q, p=None: (_ for _ in ()).throw(KeyError('x')))
    with pytest.raises(db_utils.DatabaseError, match='Query failed'):
        db_utils.execute_query('q')
    assert ('rollback',) in conn.log


def test_execute_query_passes_database_error_through(monkeypatch):
    monkeypatch.setattr(db_utils, 'DATABASE_URL', None)
    with pytest.raises(db_utils.DatabaseError, match='DATABASE_URL not configured'):
        db_utils.execute_query('q')


def test_execute_insert_returning(conn):
    conn.rows = [(42,)]
    assert db_utils.execute_insert('insert', ('x',), returning=True) == 42
    conn.rows = []
    assert db_utils.execute_insert('insert', returning=True) is None   # no row came back
    assert db_utils.execute_insert('insert') is None
    assert ('commit',) in conn.log


def test_execute_insert_wraps_errors(conn, monkeypatch):
    monkeypatch.setattr(FakeCursor, 'execute', lambda self, q, p=None: (_ for _ in ()).throw(KeyError('x')))
    with pytest.raises(db_utils.DatabaseError, match='Insert failed'):
        db_utils.execute_insert('insert')
