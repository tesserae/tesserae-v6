"""GET /admin/requests (one page of list fields) and GET /admin/requests/<id> (the full request).

The listing used to SELECT every request with its full uploaded text and leave
paging, filtering and sorting to the browser. It now filters, counts, sorts and
pages in SQL and returns only what the table renders; the review modal fetches
the one request it opens.

Validation and auth tests run anywhere. The query tests need real Postgres
(COUNT ... FILTER, NULLS LAST, LIMIT/OFFSET): set TESSERAE_TEST_PG_URL, e.g.
postgresql://localhost:5432/postgres. They create a TEMP table on a single
connection, so nothing outlives the test.
"""
import os
import sys
import types
from contextlib import contextmanager
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest  # noqa: E402

from backend.app import app, API_PREFIX  # noqa: E402
from backend.blueprints import admin  # noqa: E402

URL = f'{API_PREFIX}/admin/requests'
PG_URL = os.environ.get('TESSERAE_TEST_PG_URL')
needs_pg = pytest.mark.skipif(not PG_URL, reason='set TESSERAE_TEST_PG_URL to run against Postgres')

LIST_FIELDS = {'id', 'status', 'author', 'work', 'language', 'created_at', 'admin_updated_at'}
BASE_TIME = datetime(2026, 1, 1)


@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as c:
        yield c


def sign_in(client, monkeypatch, roles=('ADMIN',)):
    with client.session_transaction() as sess:
        sess['admin_user_id'] = 7
        sess['admin_roles'] = list(roles)
        sess['admin_session_version'] = 1
    user = types.SimpleNamespace(id=7, session_version=1)
    monkeypatch.setattr(admin, 'User', types.SimpleNamespace(
        query=types.SimpleNamespace(get=lambda _id: user)))


@pytest.fixture
def no_db(monkeypatch):
    @contextmanager
    def refuse(commit=True):
        raise AssertionError('database touched')
        yield  # pragma: no cover
    monkeypatch.setattr(admin, 'get_db_cursor', refuse)


@pytest.fixture
def pg(monkeypatch):
    psycopg2 = pytest.importorskip('psycopg2')
    conn = psycopg2.connect(PG_URL)
    conn.cursor().execute('''
        CREATE TEMP TABLE text_requests (
            id SERIAL PRIMARY KEY, name VARCHAR(255) NOT NULL, email VARCHAR(255) NOT NULL,
            author VARCHAR(255) NOT NULL, work VARCHAR(255) NOT NULL, language VARCHAR(10) DEFAULT 'la',
            notes TEXT, content TEXT, status VARCHAR(50) DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, reviewed_at TIMESTAMP, reviewed_by VARCHAR(255),
            admin_notes TEXT, text_date TEXT, approved_filename VARCHAR(255), official_author VARCHAR(255),
            official_work VARCHAR(255), admin_updated_at TIMESTAMP, author_era VARCHAR(100),
            author_year INTEGER, e_source VARCHAR(255), e_source_url TEXT, print_source TEXT,
            added_by VARCHAR(255))
    ''')
    statements = []

    @contextmanager
    def cursor(commit=True):
        cur = conn.cursor()

        def execute(sql, params=None):
            statements.append(' '.join(sql.split()))
            return cur.execute(sql, params)
        yield types.SimpleNamespace(execute=execute, fetchone=cur.fetchone, fetchall=cur.fetchall)

    def add(status='pending', hours=0, **cols):
        """Insert one request created `hours` after BASE_TIME; returns its id."""
        row = {'name': 'N', 'email': 'n@x.edu', 'author': 'Vergil', 'work': 'Aeneid',
               'content': 'arma virumque cano', 'status': status,
               'created_at': BASE_TIME + timedelta(hours=hours), **cols}
        cur = conn.cursor()
        cur.execute(f"INSERT INTO text_requests ({', '.join(row)}) "
                    f"VALUES ({', '.join(['%s'] * len(row))}) RETURNING id", list(row.values()))
        return cur.fetchone()[0]

    monkeypatch.setattr(admin, 'get_db_cursor', cursor)
    yield types.SimpleNamespace(add=add, statements=statements)
    conn.close()


def get(client, monkeypatch, query=''):
    sign_in(client, monkeypatch)
    return client.get(f'{URL}?{query}' if query else URL)


def ok(client, monkeypatch, query=''):
    resp = get(client, monkeypatch, query)
    assert resp.status_code == 200, resp.data
    return resp.get_json()


def ids(body):
    return [r['id'] for r in body['requests']]


# ---------------------------------------------------------------------------
# Auth: unchanged, and checked before anything else.

@pytest.mark.parametrize('path', ['', '/1'])
def test_unauthenticated_is_401(client, no_db, path):
    assert client.get(URL + path).status_code == 401


@pytest.mark.parametrize('path', ['', '/1'])
def test_non_admin_role_is_401(client, monkeypatch, no_db, path):
    sign_in(client, monkeypatch, roles=('USER',))
    assert client.get(URL + path).status_code == 401


# ---------------------------------------------------------------------------
# Parameter validation: 400 before any query runs.

@pytest.mark.parametrize('query', [
    'page=0', 'page=-1', 'page=abc', 'page=',
    'per_page=51', 'per_page=10000', 'per_page=abc', 'per_page=0',
    'status=archived', 'hide_completed=yes',
    'sort_by=content', 'sort_by=id;DROP TABLE text_requests', 'sort_order=sideways',
])
def test_invalid_params_are_400(client, monkeypatch, no_db, query):
    resp = get(client, monkeypatch, query)
    assert resp.status_code == 400
    assert 'error' in resp.get_json()


# ---------------------------------------------------------------------------
# Paging.

@needs_pg
def test_defaults_are_page_1_of_50(client, monkeypatch, pg):
    for h in range(60):
        pg.add(hours=h)
    body = ok(client, monkeypatch)
    assert (body['current_page'], body['per_page'], body['total'], body['pages']) == (1, 50, 60, 2)
    assert len(body['requests']) == 50


@needs_pg
def test_pages_partition_the_requests(client, monkeypatch, pg):
    every = {pg.add(hours=h) for h in range(60)}
    pages = [ids(ok(client, monkeypatch, f'per_page=25&page={p}')) for p in (1, 2, 3)]
    assert [len(p) for p in pages] == [25, 25, 10]  # last page partial
    assert set(pages[0]).isdisjoint(pages[1])
    assert sorted(sum(pages, [])) == sorted(every)


@needs_pg
def test_beyond_last_page_is_empty_and_skips_the_select(client, monkeypatch, pg):
    for h in range(3):
        pg.add(hours=h)
    body = ok(client, monkeypatch, 'page=9')
    assert body['requests'] == [] and body['total'] == 3 and body['pages'] == 1
    assert len(pg.statements) == 1  # COUNT only


@needs_pg
def test_empty_table(client, monkeypatch, pg):
    body = ok(client, monkeypatch)
    assert (body['requests'], body['total'], body['pages'], body['pending_count']) == ([], 0, 0, 0)


@needs_pg
def test_paging_happens_in_sql(client, monkeypatch, pg):
    for h in range(60):
        pg.add(hours=h)
    ok(client, monkeypatch, 'per_page=25&page=2')
    count_sql, list_sql = pg.statements
    assert 'COUNT(*)' in count_sql
    assert list_sql.endswith('LIMIT %s OFFSET %s')
    assert 'content' not in list_sql


# ---------------------------------------------------------------------------
# Filtering happens before paging, so totals describe the filtered set.

@needs_pg
def test_status_filter_runs_before_paging(client, monkeypatch, pg):
    # The 30 completed requests are the newest, so a filter applied after paging
    # would find no pending rows on page 1.
    pending = {pg.add('pending', hours=h) for h in range(30)}
    for h in range(30):
        pg.add('completed', hours=100 + h)
    p1 = ok(client, monkeypatch, 'status=pending&per_page=25&sort_by=created_at&sort_order=desc')
    p2 = ok(client, monkeypatch, 'status=pending&per_page=25&sort_by=created_at&sort_order=desc&page=2')
    assert (p1['total'], p1['pages']) == (30, 2)
    assert set(ids(p1)) | set(ids(p2)) == pending
    assert len(ids(p2)) == 5


@needs_pg
def test_status_filter_matches_the_way_the_ui_normalises(client, monkeypatch, pg):
    null_status = pg.add(None)
    upper = pg.add('Approved')
    assert null_status in ids(ok(client, monkeypatch, 'status=pending'))
    assert ids(ok(client, monkeypatch, 'status=approved')) == [upper]


@needs_pg
def test_hide_completed(client, monkeypatch, pg):
    keep = {pg.add('pending'), pg.add('approved'), pg.add('rejected')}
    pg.add('completed')
    body = ok(client, monkeypatch, 'hide_completed=1')
    assert set(ids(body)) == keep and body['total'] == 3
    assert ok(client, monkeypatch, 'hide_completed=0')['total'] == 4


@needs_pg
def test_status_filter_wins_over_hide_completed(client, monkeypatch, pg):
    done = pg.add('completed')
    assert ids(ok(client, monkeypatch, 'status=completed&hide_completed=1')) == [done]


@needs_pg
def test_pending_count_ignores_the_filter(client, monkeypatch, pg):
    pg.add('pending'), pg.add(None), pg.add('completed')
    assert ok(client, monkeypatch, 'status=completed')['pending_count'] == 2


# ---------------------------------------------------------------------------
# Sorting.

@needs_pg
def test_default_order_is_open_work_first_then_newest(client, monkeypatch, pg):
    completed = pg.add('completed', hours=5)
    approved = pg.add('approved', hours=4)
    old_pending = pg.add('pending', hours=1)
    new_pending = pg.add('pending', hours=3)
    rejected = pg.add('rejected', hours=2)
    assert ids(ok(client, monkeypatch)) == [new_pending, old_pending, rejected, approved, completed]


@needs_pg
def test_created_at_asc_and_desc(client, monkeypatch, pg):
    made = [pg.add(hours=h) for h in (2, 0, 1)]
    by_time = [made[1], made[2], made[0]]
    assert ids(ok(client, monkeypatch, 'sort_by=created_at&sort_order=asc')) == by_time
    assert ids(ok(client, monkeypatch, 'sort_by=created_at&sort_order=desc')) == by_time[::-1]


@needs_pg
def test_never_edited_sorts_last_either_way(client, monkeypatch, pg):
    never = pg.add(hours=0)
    edited = pg.add(hours=1, admin_updated_at=BASE_TIME)
    for order in ('asc', 'desc'):
        assert ids(ok(client, monkeypatch, f'sort_by=admin_updated_at&sort_order={order}')) == [edited, never]


@needs_pg
def test_ties_are_broken_by_id(client, monkeypatch, pg):
    same = [pg.add(hours=0) for _ in range(6)]
    first = ids(ok(client, monkeypatch, 'per_page=25'))
    assert first == sorted(same, reverse=True)
    assert ids(ok(client, monkeypatch, 'per_page=25')) == first


# ---------------------------------------------------------------------------
# Payload: the list carries no uploaded text; the detail carries everything.

@needs_pg
def test_list_rows_are_list_fields_only(client, monkeypatch, pg):
    pg.add(content='x' * 100_000, notes='n', admin_notes='a')
    row = ok(client, monkeypatch)['requests'][0]
    assert set(row) == LIST_FIELDS
    assert 'content' not in row


@needs_pg
def test_detail_has_what_the_review_modal_edits(client, monkeypatch, pg):
    rid = pg.add('approved', content='arma virumque cano\nTroiae qui primus', notes='from OGL',
                 admin_notes='checked', e_source='Perseus', e_source_url='https://x', print_source='Teubner',
                 author_era='Augustan', author_year=-19, added_by='me', text_date='29 BCE')
    sign_in(client, monkeypatch)
    resp = client.get(f'{URL}/{rid}')
    assert resp.status_code == 200
    body = resp.get_json()
    assert body['content'] == 'arma virumque cano\nTroiae qui primus'
    assert {k: body[k] for k in ('id', 'status', 'notes', 'admin_notes', 'e_source', 'e_source_url',
                                 'print_source', 'author_era', 'author_year', 'added_by', 'text_date')} == {
        'id': rid, 'status': 'approved', 'notes': 'from OGL', 'admin_notes': 'checked', 'e_source': 'Perseus',
        'e_source_url': 'https://x', 'print_source': 'Teubner', 'author_era': 'Augustan', 'author_year': -19,
        'added_by': 'me', 'text_date': '29 BCE'}
    # Defaults the modal relies on when the admin has not filled them in yet.
    assert body['official_author'] == 'Vergil' and body['official_work'] == 'Aeneid'
    assert body['approved_filename'] == body['suggested_filename'] == 'vergil.aeneid.tess'


@needs_pg
def test_detail_unknown_id_is_404(client, monkeypatch, pg):
    sign_in(client, monkeypatch)
    assert client.get(f'{URL}/999999').status_code == 404
