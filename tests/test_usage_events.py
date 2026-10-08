"""Usage events: each kind of use writes one row, and logging never breaks a request.

Ported alongside the Scholarship route, which is the one caller of log_event
in this PR. A generic hook that logged every existing connector tool call
was left out of the port: it would change the behaviour of tools that have
nothing to do with scholarship, which this port does not touch."""
import json


def test_scholarship_route_logs_an_event(monkeypatch):
    from backend.app import create_app
    from backend import usage
    import backend.scholarship as S
    rows = []
    monkeypatch.setattr(usage, 'get_user_location', lambda: ('Buffalo', 'United States', '1.2.3.4'))

    class Cur:
        def execute(self, sql, params): rows.append(params)
        def __enter__(self): return self
        def __exit__(self, *a): return False
    monkeypatch.setattr(usage, 'get_db_cursor', lambda: Cur())
    monkeypatch.setattr(S, '_openalex', lambda q: [])
    monkeypatch.setattr(S, '_crossref', lambda q: [])
    monkeypatch.setattr(S, 'commentary_at', lambda *a, **k: [])
    app = create_app()
    c = app.test_client()
    path = next(str(rule) for rule in app.url_map.iter_rules() if rule.endpoint == 'scholarship.scholarship')
    r = c.get(f'{path}?work=vergil.aeneid&ref_start=verg.%20aen.%201.1')
    assert r.status_code == 200
    kinds = [p[0] for p in rows]
    assert 'scholarship' in kinds
    row = rows[kinds.index('scholarship')]
    assert row[1] == 'site' and row[10] == 'Buffalo' and row[11] == 'United States'


def test_logging_failure_does_not_break_the_request(monkeypatch):
    from backend import usage
    monkeypatch.setattr(usage, 'get_user_location', lambda: (None, None, None))

    def boom(): raise RuntimeError('db down')
    monkeypatch.setattr(usage, 'get_db_cursor', boom)
    from flask import Flask
    app = Flask(__name__)
    with app.test_request_context('/'):
        usage.log_event('theme_search', query_text='x')  # must not raise
