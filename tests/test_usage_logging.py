"""Passage searches write to search_logs, and the server's own requests are flagged internal."""
import contextlib
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest  # noqa: E402

from backend.app import app, API_PREFIX  # noqa: E402
from backend import passage_index as pi  # noqa: E402
from backend import services  # noqa: E402
from backend.blueprints import passages  # noqa: E402
from backend.blueprints import mcp_http  # noqa: E402


@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as c:
        yield c


@pytest.fixture
def rows(monkeypatch):
    """Capture log_search calls as dicts; location lookup never leaves the process."""
    got = []

    def fake(search_type, language='la', source_text=None, target_text=None, query_text=None,
             match_type=None, results_count=0, cached=False, user_id=None, city=None,
             country=None, client_ip=None, internal=None):
        got.append(dict(search_type=search_type, language=language, source_text=source_text,
                        target_text=target_text, query_text=query_text, match_type=match_type,
                        results_count=results_count, cached=cached, client_ip=client_ip,
                        internal=internal))
    monkeypatch.setattr(passages, 'log_search', fake)
    monkeypatch.setattr(passages, 'get_user_location',
                        lambda: (None, None, services.get_client_ip()))
    return got


def _theme(monkeypatch, n=3):
    monkeypatch.setattr(pi, 'find_by_text',
                        lambda q, **kw: {'query': q, 'results': [{'id': i} for i in range(n)]})
    monkeypatch.setattr(pi, 'index_version', lambda: 'v1')
    monkeypatch.setattr(pi, 'base_work', lambda w: w.split('.part')[0])


def test_theme_search_whole_corpus(client, rows, monkeypatch):
    _theme(monkeypatch)
    r = client.get(f'{API_PREFIX}/passages/theme-search?q=a+plague&languages=la,grc&scale=coarse&offset=25')
    assert r.status_code == 200
    assert len(rows) == 1
    row = rows[0]
    assert row['search_type'] == 'Theme Search'
    assert row['language'] == 'la,grc'
    assert row['source_text'] == 'corpus' and row['target_text'] is None
    assert row['query_text'] == 'a plague'
    assert row['match_type'] == 'whole corpus, page 2, scale coarse'
    assert row['results_count'] == 3 and row['cached'] is False


def test_theme_search_no_languages_is_all(client, rows, monkeypatch):
    _theme(monkeypatch)
    client.get(f'{API_PREFIX}/passages/theme-search?q=x')
    assert rows[0]['language'] == 'all'


def test_theme_search_two_works_sets_target(client, rows, monkeypatch):
    _theme(monkeypatch)
    monkeypatch.setattr(pi, 'resolve_restriction', lambda **kw: ({'a.one', 'b.two'}, None))
    client.get(f'{API_PREFIX}/passages/theme-search?q=x&works=a.one,b.two')
    assert rows[0]['source_text'] == 'a.one' and rows[0]['target_text'] == 'b.two'
    assert rows[0]['match_type'] == 'two texts'


def test_theme_search_one_work_and_reader(client, rows, monkeypatch):
    _theme(monkeypatch)
    monkeypatch.setenv('THEME_READER_URL', 'http://x')
    monkeypatch.setattr(pi, 'resolve_restriction', lambda **kw: ({'a.one'}, None))
    monkeypatch.setattr(passages.reader_rerank, 'apply',
                        lambda q, res: (res, {'applied': True}))
    client.get(f'{API_PREFIX}/passages/theme-search?q=x&works=a.one')
    assert rows[0]['match_type'] == 'one text, reader'
    assert rows[0]['target_text'] is None


def test_theme_search_restricted_path_logs_zero(client, rows, monkeypatch):
    _theme(monkeypatch)
    monkeypatch.setattr(pi, 'resolve_restriction', lambda **kw: (set(), 'none held'))
    r = client.get(f'{API_PREFIX}/passages/theme-search?q=x&author=nobody')
    assert r.get_json()['restricted'] is True
    assert len(rows) == 1
    assert rows[0]['results_count'] == 0
    assert 'restricted' in rows[0]['match_type']
    assert rows[0]['source_text'] == 'nobody'


def test_similar_passages_row(client, rows, monkeypatch):
    monkeypatch.setattr(pi, 'find_similar_to_window',
                        lambda w, **kw: {'source': {'id': w}, 'results': [{'id': 'r1'}, {'id': 'r2'}]})
    monkeypatch.setattr(pi, 'same_names_for_window', lambda w: None)
    client.get(f'{API_PREFIX}/passages/similar?window=w42&same_names=1')
    row = rows[0]
    assert row['search_type'] == 'Similar Passages'
    assert row['source_text'] == 'w42' and row['query_text'] is None
    assert row['match_type'] == 'window, same names'
    assert row['results_count'] == 2


def test_similar_passages_selection(client, rows, monkeypatch):
    monkeypatch.setattr(pi, 'find_similar_to_passage',
                        lambda *a, **kw: {'source': {}, 'results': []})
    client.get(f'{API_PREFIX}/passages/similar?work=la/x.tess&ref_start=1.1&ref_end=1.9')
    assert rows[0]['source_text'] == 'la/x.tess 1.1-1.9'
    assert rows[0]['match_type'] == 'selection'


def test_compare_row(client, rows, monkeypatch):
    # the route decorates each side, so give it real dicts
    monkeypatch.setattr(pi, 'compare_works', lambda a, b, **kw: {'pairs': [
        {'a': {'work': 'x'}, 'b': {'work': 'y'}} for _ in range(4)]})
    client.get(f'{API_PREFIX}/passages/compare?work_a=x.one&work_b=y.two')
    row = rows[0]
    assert row['search_type'] == 'Compare Works'
    assert row['source_text'] == 'x.one' and row['target_text'] == 'y.two'
    assert row['results_count'] == 4


def test_logging_failure_never_breaks_the_response(client, monkeypatch):
    _theme(monkeypatch)

    def boom(*a, **k):
        raise RuntimeError('db down')
    monkeypatch.setattr(passages, 'log_search', boom)
    monkeypatch.setattr(passages, 'get_user_location', lambda: (None, None, '1.2.3.4'))
    r = client.get(f'{API_PREFIX}/passages/theme-search?q=x')
    assert r.status_code == 200 and len(r.get_json()['results']) == 3


# is_internal_request ------------------------------------------------------------

def test_internal_addresses(monkeypatch):
    monkeypatch.setattr(services, '_internal_ips', None)
    monkeypatch.delenv('TESSERAE_INTERNAL_IPS', raising=False)
    assert services.is_internal_request('127.0.0.1')
    assert services.is_internal_request('::1')
    assert services.is_internal_request('128.205.2.231')
    assert not services.is_internal_request('203.0.113.7')
    assert not services.is_internal_request(None)
    assert not services.is_internal_request('not an address')


def test_internal_ips_from_environment(monkeypatch):
    monkeypatch.setattr(services, '_internal_ips', None)
    monkeypatch.setenv('TESSERAE_INTERNAL_IPS', '198.51.100.4, 198.51.100.5')
    assert services.is_internal_request('198.51.100.5')
    assert not services.is_internal_request('128.205.2.231')
    monkeypatch.setattr(services, '_internal_ips', None)


# log_search ---------------------------------------------------------------------

class _Cur:
    def __init__(self):
        self.calls = []

    def execute(self, sql, params=None):
        self.calls.append((sql, params))


def _fake_cursor(monkeypatch):
    cur = _Cur()

    @contextlib.contextmanager
    def gc(*a, **k):
        yield cur
    monkeypatch.setattr(services, 'get_db_cursor', gc)
    return cur


def test_log_search_passes_internal_into_insert(monkeypatch):
    monkeypatch.setattr(services, '_internal_ips', None)
    monkeypatch.delenv('TESSERAE_INTERNAL_IPS', raising=False)
    cur = _fake_cursor(monkeypatch)
    services.log_search('Theme Search', 'all', None, None, 'q', 'whole corpus', 1, False,
                        None, None, None, '127.0.0.1')
    sql, params = cur.calls[0]
    assert 'internal' in sql and sql.count('%s') == len(params) == 13
    assert params[-1] is True
    services.log_search('Theme Search', 'all', None, None, 'q', 'm', 1, False,
                        None, None, None, '203.0.113.7')
    assert cur.calls[1][1][-1] is False
    services.log_search('Theme Search', 'all', None, None, 'q', 'm', 1, False,
                        None, None, None, '203.0.113.7', internal=True)
    assert cur.calls[2][1][-1] is True


# connector ----------------------------------------------------------------------

def test_connector_forward_headers_carry_caller(monkeypatch):
    with app.test_request_context('/api/mcp', environ_overrides={'REMOTE_ADDR': '203.0.113.9'}):
        h = mcp_http._fwd_headers()
    assert h['X-Tesserae-Connector'] == '1'
    assert h['X-Tesserae-Connector-IP'] == '203.0.113.9'
    assert mcp_http._fwd_headers() == {'X-Tesserae-Connector': '1'}   # outside a request


def test_connector_theme_search_is_not_internal(client, monkeypatch):
    _theme(monkeypatch)
    monkeypatch.setattr(services, '_internal_ips', None)
    monkeypatch.delenv('TESSERAE_INTERNAL_IPS', raising=False)
    cur = _fake_cursor(monkeypatch)
    monkeypatch.setattr(passages, 'get_user_location',
                        lambda: (None, None, services.get_client_ip()))
    # the connector's HTTP call arrives from the server's own address
    r = client.get(f'{API_PREFIX}/passages/theme-search?q=a+plague',
                   headers={'X-Tesserae-Connector': '1', 'X-Tesserae-Connector-IP': '203.0.113.9'},
                   environ_overrides={'REMOTE_ADDR': '128.205.2.231'})
    assert r.status_code == 200
    params = cur.calls[0][1]
    assert params[5].endswith(', connector') and params[5] == 'whole corpus, connector'
    assert params[9] == '203.0.113.9'
    assert params[-1] is False


def test_server_own_theme_search_is_internal(client, monkeypatch):
    _theme(monkeypatch)
    monkeypatch.setattr(services, '_internal_ips', None)
    cur = _fake_cursor(monkeypatch)
    monkeypatch.setattr(passages, 'get_user_location',
                        lambda: (None, None, services.get_client_ip()))
    client.get(f'{API_PREFIX}/passages/theme-search?q=a+plague',
               environ_overrides={'REMOTE_ADDR': '128.205.2.231'})
    assert cur.calls[0][1][-1] is True
    assert 'connector' not in cur.calls[0][1][5]


def test_outside_client_cannot_claim_to_be_the_connector(client, monkeypatch):
    _theme(monkeypatch)
    monkeypatch.setattr(services, '_internal_ips', None)
    cur = _fake_cursor(monkeypatch)
    monkeypatch.setattr(passages, 'get_user_location',
                        lambda: (None, None, services.get_client_ip()))
    client.get(f'{API_PREFIX}/passages/theme-search?q=x',
               headers={'X-Tesserae-Connector': '1', 'X-Tesserae-Connector-IP': '127.0.0.1'},
               environ_overrides={'REMOTE_ADDR': '203.0.113.50'})
    params = cur.calls[0][1]
    assert 'connector' not in params[5]
    assert params[9] == '203.0.113.50'


# admin counts ---------------------------------------------------------------------

def test_admin_analytics_leaves_internal_rows_out(client, monkeypatch):
    import types
    from backend.blueprints import admin
    with client.session_transaction() as sess:
        sess['admin_user_id'] = 7
        sess['admin_roles'] = ['ADMIN']
        sess['admin_session_version'] = 1
    user = types.SimpleNamespace(id=7, session_version=1)
    monkeypatch.setattr(admin, 'User', types.SimpleNamespace(
        query=types.SimpleNamespace(get=lambda _id: user)))
    seen = []

    class Cur:
        def execute(self, sql, params=None):
            seen.append(' '.join(sql.split()))

        def fetchone(self):
            return (5,)

        def fetchall(self):
            return []

    @contextlib.contextmanager
    def gc(*a, **k):
        yield Cur()
    monkeypatch.setattr(admin, 'get_db_cursor', gc)
    r = client.get(f'{API_PREFIX}/admin/analytics')
    assert r.status_code == 200
    assert r.get_json()['internal_searches'] == 5
    on_logs = [q for q in seen if 'FROM search_logs' in q]
    outside = [q for q in on_logs if 'internal IS TRUE' not in q]
    assert outside and all('internal IS NOT TRUE' in q for q in outside)
