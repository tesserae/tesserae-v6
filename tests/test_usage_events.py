"""Usage events: each kind of use writes one row, and logging never breaks a request."""
import json


def test_connector_call_logs_an_event(monkeypatch):
    from backend.app import create_app
    from backend.blueprints import mcp_http, mcp_oauth
    from backend import usage
    rows = []
    monkeypatch.setattr(usage, 'get_user_location', lambda: ('Buffalo', 'United States', '1.2.3.4'))

    class Cur:
        def execute(self, sql, params): rows.append(params)
        def __enter__(self): return self
        def __exit__(self, *a): return False
    monkeypatch.setattr(usage, 'get_db_cursor', lambda: Cur())
    monkeypatch.setattr(mcp_oauth, 'verify_access_token', lambda tok: tok == 'ok')
    app = create_app()
    c = app.test_client()
    r = c.post('/api/mcp', headers={'Authorization': 'Bearer ok'}, json={
        'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call', 'params': {'name': 'get_languages', 'arguments': {}}})
    assert r.status_code == 200
    kinds = [p[0] for p in rows]
    assert 'connector:get_languages' in kinds
    row = rows[kinds.index('connector:get_languages')]
    assert row[1] == 'connector' and row[10] == 'Buffalo' and row[11] == 'United States'


def test_logging_failure_does_not_break_the_request(monkeypatch):
    from backend import usage
    monkeypatch.setattr(usage, 'get_user_location', lambda: (None, None, None))

    def boom(): raise RuntimeError('db down')
    monkeypatch.setattr(usage, 'get_db_cursor', boom)
    from flask import Flask
    app = Flask(__name__)
    with app.test_request_context('/'):
        usage.log_event('theme_search', query_text='x')  # must not raise
