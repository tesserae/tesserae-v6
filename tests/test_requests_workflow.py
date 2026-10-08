"""POST /api/feature-request (the requests workflow's unified intake) and
GET /api/requests (the public mirror of what it filed).

Covers: the issue body never carries contact info, labels are "request" +
"request:<type>" for every type, the per-IP rate limit, the GitHub kill
switch (the request still "lands" with filing off), and the public listing's
status mapping and no-body-leak guarantee. GitHub itself is always mocked --
these tests never make a real network call.
"""
import os
import sys
import types
from contextlib import contextmanager

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest  # noqa: E402

from backend.app import app, API_PREFIX  # noqa: E402
from backend.blueprints import feature_request as fr  # noqa: E402
from backend import github_requests as gr  # noqa: E402

URL = f'{API_PREFIX}/feature-request'
REQUESTS_URL = f'{API_PREFIX}/requests'


@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as c:
        yield c


@pytest.fixture(autouse=True)
def _reset_rate_limit():
    """Every test gets a clean bucket; the limiter is per-process state."""
    fr._rl_attempts.clear()
    yield
    fr._rl_attempts.clear()


@pytest.fixture
def no_db(monkeypatch):
    """The DB insert is best-effort (wrapped in try/except in the route), so
    a test can refuse it and still exercise the rest of the flow."""
    @contextmanager
    def refuse(commit=True):
        raise AssertionError('database touched')
        yield  # pragma: no cover
    monkeypatch.setattr(fr, 'get_db_cursor', refuse)


@pytest.fixture
def fake_db(monkeypatch):
    """Records what the route tried to insert, without touching Postgres."""
    inserts = []

    @contextmanager
    def cursor(commit=True):
        class Cur:
            def execute(self, sql, params=None):
                inserts.append(params)

            def fetchone(self):
                return (1,)
        yield Cur()
    monkeypatch.setattr(fr, 'get_db_cursor', cursor)
    return inserts


@pytest.fixture(autouse=True)
def _no_email(monkeypatch):
    monkeypatch.setattr(fr, 'send_notification', lambda *a, **k: True)


def post(client, **payload):
    return client.post(URL, json=payload)


# ---------------------------------------------------------------------------
# Validation

def test_empty_submission_is_400(client, no_db):
    resp = post(client, type='suggestion')
    assert resp.status_code == 400


def test_overlong_message_is_rejected(client, no_db):
    resp = post(client, type='suggestion', message='x' * (fr.MAX_MESSAGE_RAW + 1))
    assert resp.status_code == 400


def test_unknown_type_falls_back_to_other(client, fake_db, monkeypatch):
    captured = {}
    monkeypatch.setattr(fr, 'github_feedback_enabled', lambda: True)
    monkeypatch.setattr(fr, 'create_feedback_issue',
                        lambda title, body, labels: captured.update(title=title, labels=labels) or 'https://x/1')
    resp = post(client, type='not-a-real-type', message='hello')
    assert resp.status_code == 200
    assert resp.get_json()['type'] == 'other'
    assert captured['labels'] == ['request', 'request:other']


# ---------------------------------------------------------------------------
# The issue body never carries contact info.

@pytest.mark.parametrize('req_type', ['feature', 'result-problem', 'text-correction', 'suggestion'])
def test_issue_body_has_no_contact(client, fake_db, monkeypatch, req_type):
    captured = {}

    def fake_create(title, body, labels):
        captured['title'] = title
        captured['body'] = body
        captured['labels'] = labels
        return 'https://github.com/org/repo/issues/42'

    monkeypatch.setattr(fr, 'github_feedback_enabled', lambda: True)
    monkeypatch.setattr(fr, 'create_feedback_issue', fake_create)

    resp = post(client, type=req_type, message='Something is off here',
               name='A Scholar', contact='scholar@example.edu',
               current_text='lorem', corrected_text='lorum')
    assert resp.status_code == 200
    body = resp.get_json()
    assert body['github_filed'] is True
    assert body['issue_url'] == 'https://github.com/org/repo/issues/42'

    assert 'scholar@example.edu' not in captured['body']
    assert 'A Scholar' not in captured['body']
    assert 'scholar@example.edu' not in captured['title']
    assert captured['labels'] == ['request', f'request:{req_type}']

    # The private DB record is the one place contact is allowed to land.
    assert any('scholar@example.edu' in str(p) for p in fake_db)


def test_correction_body_carries_current_and_proposed_text(client, fake_db, monkeypatch):
    captured = {}
    monkeypatch.setattr(fr, 'github_feedback_enabled', lambda: True)
    monkeypatch.setattr(fr, 'create_feedback_issue',
                        lambda title, body, labels: captured.update(body=body) or 'https://x/1')
    post(client, type='text-correction', message='wrong word',
        current_text='arma virumque', corrected_text='arma virum')
    assert 'arma virumque' in captured['body']
    assert 'arma virum' in captured['body']


def test_context_dict_is_formatted_and_html_stripped(client, fake_db, monkeypatch):
    captured = {}
    monkeypatch.setattr(fr, 'github_feedback_enabled', lambda: True)
    monkeypatch.setattr(fr, 'create_feedback_issue',
                        lambda title, body, labels: captured.update(body=body) or 'https://x/1')
    post(client, type='result-problem', message='bad score',
        context={'page_url': 'https://tesserae.example/search?x=1',
                 'language': 'Latin', 'source': 'Vergil, Aen. 1.1',
                 'score': '<script>alert(1)</script>7.2'})
    assert '<script>' not in captured['body']
    assert 'tesserae.example/search' in captured['body']
    assert 'Vergil, Aen. 1.1' in captured['body']


# ---------------------------------------------------------------------------
# Rate limit.

def test_rate_limit_by_ip(client, no_db, monkeypatch):
    monkeypatch.setattr(fr, 'github_feedback_enabled', lambda: False)
    monkeypatch.setattr(fr, '_RL_MAX', 3)
    for _ in range(3):
        assert post(client, type='suggestion', message='hi').status_code == 200
    resp = post(client, type='suggestion', message='hi')
    assert resp.status_code == 429


# ---------------------------------------------------------------------------
# Kill switch: filing off still "lands" the request.

def test_kill_switch_still_succeeds(client, fake_db, monkeypatch):
    def boom(*a, **k):
        raise AssertionError('create_feedback_issue must not be called when filing is off')
    monkeypatch.setattr(fr, 'github_feedback_enabled', lambda: False)
    monkeypatch.setattr(fr, 'create_feedback_issue', boom)
    resp = post(client, type='suggestion', message='please add X')
    assert resp.status_code == 200
    body = resp.get_json()
    assert body['success'] is True
    assert body['github_filed'] is False
    assert body['issue_url'] is None
    assert fake_db  # still landed in the DB


# ---------------------------------------------------------------------------
# GET /api/requests: status mapping and no body leak.

def _issue(number=1, state='open', labels=('request', 'request:feature'),
          state_reason=None, body='Summary: shorter search box\n\nfull detail here',
          title='Add a shorter search box', closed_at=None, created_at='2026-10-01T00:00:00Z'):
    return {
        'number': number, 'state': state, 'state_reason': state_reason,
        'labels': [{'name': l} for l in labels], 'body': body, 'title': title,
        'html_url': f'https://github.com/org/repo/issues/{number}',
        'created_at': created_at, 'closed_at': closed_at,
    }


def test_status_mapping():
    assert gr._status_for(_issue(state='open')) == 'open'
    assert gr._status_for(_issue(state='open', labels=('request', 'in progress'))) == 'in progress'
    assert gr._status_for(_issue(state='closed', state_reason='completed')) == 'done'
    assert gr._status_for(_issue(state='closed', state_reason='not_planned')) == 'declined'


def test_type_label_reads_the_request_colon_label():
    assert gr._type_label(_issue(labels=('request', 'request:text-correction'))) == 'text-correction'
    assert gr._type_label(_issue(labels=('request',))) == 'other'


def test_public_summary_only_reads_the_summary_marker():
    body = "Summary: a short public line\n\nPage: https://x\nMessage: lots of private-ish detail"
    assert gr._public_summary(body) == 'a short public line'
    assert gr._public_summary('no marker here, just prose') == ''


def test_listing_never_returns_the_body(client, monkeypatch):
    monkeypatch.setattr(fr, 'fetch_requests_listing', lambda: [{
        'number': 1, 'title': 'x', 'type': 'feature', 'status': 'open',
        'created_at': '2026-10-01T00:00:00Z', 'closed_at': None,
        'summary': 'short', 'url': 'https://github.com/org/repo/issues/1',
    }])
    monkeypatch.setattr(fr, 'github_feedback_enabled', lambda: True)
    resp = client.get(REQUESTS_URL)
    assert resp.status_code == 200
    data = resp.get_json()
    assert all('body' not in item for item in data['open'] + data['done'])
    assert data['open'][0]['summary'] == 'short'


def test_listing_groups_open_and_done(client, monkeypatch):
    items = [
        {'number': 1, 'title': 'open one', 'type': 'feature', 'status': 'open',
         'created_at': '2026-10-02T00:00:00Z', 'closed_at': None, 'summary': '', 'url': 'u1'},
        {'number': 2, 'title': 'done one', 'type': 'bug', 'status': 'done',
         'created_at': '2026-10-01T00:00:00Z', 'closed_at': '2026-10-03T00:00:00Z', 'summary': '', 'url': 'u2'},
        {'number': 3, 'title': 'declined one', 'type': 'suggestion', 'status': 'declined',
         'created_at': '2026-09-01T00:00:00Z', 'closed_at': '2026-09-05T00:00:00Z', 'summary': '', 'url': 'u3'},
    ]
    monkeypatch.setattr(fr, 'fetch_requests_listing', lambda: items)
    resp = client.get(REQUESTS_URL)
    data = resp.get_json()
    assert [i['number'] for i in data['open']] == [1]
    assert [i['number'] for i in data['done']] == [2, 3]


# ---------------------------------------------------------------------------
# github_requests.py caching.

def test_fetch_requests_listing_caches_in_process(monkeypatch, tmp_path):
    monkeypatch.setattr(gr, '_CACHE_PATH', str(tmp_path / 'cache.json'))
    gr._mem_cache['items'] = None
    gr._mem_cache['ts'] = 0.0
    calls = {'n': 0}

    def fake_fetch():
        calls['n'] += 1
        return [{'number': 1}]

    monkeypatch.setattr(gr, '_fetch_from_github', fake_fetch)
    first = gr.fetch_requests_listing()
    second = gr.fetch_requests_listing()
    assert first == second == [{'number': 1}]
    assert calls['n'] == 1


def test_fetch_requests_listing_force_refresh_bypasses_cache(monkeypatch, tmp_path):
    monkeypatch.setattr(gr, '_CACHE_PATH', str(tmp_path / 'cache.json'))
    gr._mem_cache['items'] = [{'number': 'stale'}]
    gr._mem_cache['ts'] = __import__('time').time()
    monkeypatch.setattr(gr, '_fetch_from_github', lambda: [{'number': 'fresh'}])
    assert gr.fetch_requests_listing(force_refresh=True) == [{'number': 'fresh'}]


# ---------------------------------------------------------------------------
# Label creation (backend/github_feedback.py).

def test_labels_are_created_when_missing(monkeypatch):
    from backend import github_feedback as gf
    monkeypatch.setenv('GITHUB_FEEDBACK_TOKEN', 'tok')
    monkeypatch.setenv('GITHUB_FEEDBACK_REPO', 'org/repo')
    gf._label_cache['ts'] = 0.0
    gf._label_cache['names'] = set()

    calls = []

    def fake_get(url, headers=None, params=None, timeout=None):
        calls.append(('GET', url))
        return types.SimpleNamespace(status_code=200, json=lambda: [{'name': 'request'}])

    def fake_post(url, headers=None, json=None, timeout=None):
        calls.append(('POST', url, json))
        if url.endswith('/labels'):
            return types.SimpleNamespace(status_code=201, json=lambda: {})
        return types.SimpleNamespace(status_code=201, json=lambda: {'html_url': 'https://x/1'})

    monkeypatch.setattr(gf.requests, 'get', fake_get)
    monkeypatch.setattr(gf.requests, 'post', fake_post)

    url = gf.create_feedback_issue('t', 'b', ['request', 'request:suggestion'])
    assert url == 'https://x/1'
    created = [c for c in calls if c[0] == 'POST' and c[1].endswith('/labels')]
    assert created and created[0][2]['name'] == 'request:suggestion'
