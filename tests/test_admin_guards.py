"""The admin panel's guards: who may act, and what may never be done.

backend/blueprints/admin.py is 2,683 lines and 60 routes, and it holds the
powers with the most reach in this project: deleting a user, granting and
removing roles, resetting a password, clearing caches, changing settings.
Until now it had no tests at all (code review, 2026-09-21).

These do not test the panel's features. They test the guards, because a
guard is the part that is silent when it fails: a missing session check does
not throw, it just lets someone through. Each test names the rule it holds
in place.

Everything is stubbed at the module boundary: no database, no real user, no
session store. The point is the decision the code makes, not the storage.
"""
import os
import sys
import types

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest  # noqa: E402

from backend.app import app, API_PREFIX  # noqa: E402
from backend.blueprints import admin  # noqa: E402

ADMIN = f'{API_PREFIX}/admin' if API_PREFIX else '/admin'


@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as c:
        yield c


def sign_in(client, user_id=7, roles=('ADMIN',), version=1):
    with client.session_transaction() as sess:
        sess['admin_user_id'] = user_id
        sess['admin_email'] = 'someone@example.edu'
        sess['admin_roles'] = list(roles)
        sess['admin_session_version'] = version


class FakeUser:
    def __init__(self, user_id=7, session_version=1, email='someone@example.edu',
                 password_hash=None):
        self.id = user_id
        self.session_version = session_version
        self.email = email
        self.password_hash = password_hash
        self.must_reset_password = False


def stub_user_lookup(monkeypatch, user):
    """User.query.get(...) returns `user` (or None)."""
    query = types.SimpleNamespace(get=lambda _id: user)
    monkeypatch.setattr(admin, 'User', types.SimpleNamespace(query=query))


# ---------------------------------------------------------------------------
# 1. Nothing dangerous happens without a session.

DANGEROUS = [
    ('DELETE', f'{ADMIN}/users/9'),
    ('POST', f'{ADMIN}/users/9/roles'),
    ('POST', f'{ADMIN}/users'),
    ('POST', f'{ADMIN}/reset-password'),
    ('POST', f'{ADMIN}/settings'),
    ('GET', f'{ADMIN}/users'),
    ('GET', f'{ADMIN}/user-data'),
    ('POST', f'{ADMIN}/lemma-cache/clear'),
    ('POST', f'{ADMIN}/search-cache/clear'),
    ('DELETE', f'{ADMIN}/sources/3'),
]


@pytest.mark.parametrize('method,path', DANGEROUS)
def test_a_stranger_is_refused(client, method, path):
    """No session, no action. 401, and nothing else."""
    resp = client.open(path, method=method, json={})
    assert resp.status_code == 401, f'{method} {path} answered {resp.status_code}'


@pytest.mark.parametrize('method,path', DANGEROUS)
def test_a_signed_in_reader_is_refused(client, method, path, monkeypatch):
    """A session is not enough: the roles have to say ADMIN or SUPER_ADMIN.

    Someone who has logged in to save searches has a session too.
    """
    sign_in(client, roles=('USER',))
    stub_user_lookup(monkeypatch, FakeUser())
    resp = client.open(path, method=method, json={})
    assert resp.status_code == 401, f'{method} {path} answered {resp.status_code}'


# ---------------------------------------------------------------------------
# 2. The session check itself.

class TestTheSessionCheck:
    def test_no_session_is_not_an_admin(self):
        with app.test_request_context():
            assert admin.check_admin_auth() is False

    def test_the_role_has_to_be_an_admin_role(self, monkeypatch):
        stub_user_lookup(monkeypatch, FakeUser())
        with app.test_request_context():
            from flask import session
            session['admin_user_id'] = 7
            session['admin_roles'] = ['USER']
            session['admin_session_version'] = 1
            assert admin.check_admin_auth() is False

    def test_an_admin_with_a_current_session_is_let_in(self, monkeypatch):
        stub_user_lookup(monkeypatch, FakeUser(session_version=3))
        with app.test_request_context():
            from flask import session
            session['admin_user_id'] = 7
            session['admin_roles'] = ['ADMIN']
            session['admin_session_version'] = 3
            assert admin.check_admin_auth() is True

    def test_a_revoked_session_is_refused_and_thrown_away(self, monkeypatch):
        """Raising a user's session_version is how an account is locked out.

        The old session must stop working at once, and the cookie must be
        cleared rather than left to be tried again.
        """
        stub_user_lookup(monkeypatch, FakeUser(session_version=4))
        with app.test_request_context():
            from flask import session
            session['admin_user_id'] = 7
            session['admin_roles'] = ['SUPER_ADMIN']
            session['admin_session_version'] = 3      # stale
            assert admin.check_admin_auth() is False
            assert 'admin_user_id' not in session

    def test_a_deleted_user_cannot_keep_using_a_session(self, monkeypatch):
        stub_user_lookup(monkeypatch, None)
        with app.test_request_context():
            from flask import session
            session['admin_user_id'] = 7
            session['admin_roles'] = ['ADMIN']
            session['admin_session_version'] = 1
            assert admin.check_admin_auth() is False


# ---------------------------------------------------------------------------
# 3. Deleting a user: the two things that must never happen.

class TestDeletingAUser:
    def _arrange(self, monkeypatch, client, target_roles=('USER',), super_admins=5,
                 target=FakeUser(user_id=9)):
        sign_in(client, user_id=7, roles=('SUPER_ADMIN',))
        monkeypatch.setattr(admin, 'check_admin_auth', lambda: True)
        monkeypatch.setattr(admin, '_get_user_roles', lambda _id: list(target_roles))
        monkeypatch.setattr(admin, '_count_super_admins', lambda: super_admins)
        monkeypatch.setattr(admin, 'log_admin_action', lambda *a, **k: None)
        stub_user_lookup(monkeypatch, target)

    def test_an_admin_cannot_delete_their_own_account(self, client, monkeypatch):
        """Deleting yourself locks everyone out of a panel that has no other
        way back in."""
        self._arrange(monkeypatch, client)
        resp = client.delete(f'{ADMIN}/users/7')
        assert resp.status_code == 400
        assert 'currently logged-in' in resp.get_json()['error']

    def test_the_last_super_admins_are_protected(self, client, monkeypatch):
        """Two are kept, not one, so losing an account does not leave the
        panel with a single holder."""
        self._arrange(monkeypatch, client, target_roles=('SUPER_ADMIN',), super_admins=2)
        resp = client.delete(f'{ADMIN}/users/9')
        assert resp.status_code == 400
        assert 'SUPER_ADMIN' in resp.get_json()['error']

    def test_a_super_admin_can_be_deleted_when_others_remain(self, client, monkeypatch):
        deleted = []
        self._arrange(monkeypatch, client, target_roles=('SUPER_ADMIN',), super_admins=5)
        self._stub_orm(monkeypatch, deleted)
        resp = client.delete(f'{ADMIN}/users/9')
        assert resp.status_code == 200
        assert deleted == ['deleted', 'committed']

    def test_a_missing_user_is_a_404_not_a_500(self, client, monkeypatch):
        self._arrange(monkeypatch, client, target=None)
        resp = client.delete(f'{ADMIN}/users/9')
        assert resp.status_code == 404

    def test_a_failure_rolls_back_and_says_so(self, client, monkeypatch):
        """A half-deleted user is worse than a refused delete."""
        events = []
        self._arrange(monkeypatch, client)
        self._stub_orm(monkeypatch, events, fail_on_commit=True)
        resp = client.delete(f'{ADMIN}/users/9')
        assert resp.status_code == 500
        assert 'rolled back' in events

    @staticmethod
    def _stub_orm(monkeypatch, events, fail_on_commit=False):
        def commit():
            if fail_on_commit:
                raise RuntimeError('database went away')
            events.append('committed')

        def rollback():
            events.append('rolled back')

        session = types.SimpleNamespace(
            delete=lambda _obj: events.append('deleted'),
            commit=commit, rollback=rollback,
            execute=lambda *a, **k: None,
        )
        monkeypatch.setattr(admin, 'db', types.SimpleNamespace(session=session))
        empty = types.SimpleNamespace(
            filter_by=lambda **kw: types.SimpleNamespace(
                update=lambda *a, **k: None, delete=lambda *a, **k: None))
        for name in ('Intertext', 'SavedIntertext', 'SavedSearch', 'OAuth'):
            monkeypatch.setattr(admin, name, types.SimpleNamespace(query=empty), raising=False)


# ---------------------------------------------------------------------------
# 4. Logging in.

class TestLoggingIn:
    def test_an_empty_form_is_refused_without_touching_the_database(self, client):
        resp = client.post(f'{ADMIN}/login', json={'email': '', 'password': ''})
        assert resp.status_code == 400

    def test_repeated_failures_are_locked_out(self, client, monkeypatch):
        """Five wrong passwords and the sixth attempt is refused outright,
        with a Retry-After, so a password cannot be guessed at speed.

        The limiter keys on the caller's address as well as the address in
        the form, so the counting happens inside a request context, as it
        does in life.
        """
        monkeypatch.setattr(admin, '_login_failures', {}, raising=False)
        monkeypatch.setattr(admin, '_login_lockouts', {}, raising=False)
        email = 'target@example.edu'
        with app.test_request_context(f'{ADMIN}/login'):
            for _ in range(admin._LOGIN_MAX_ATTEMPTS):
                admin._record_failed_admin_login(email)
            limited, retry_after = admin._check_admin_login_rate_limit(email)
            assert limited is True
            assert retry_after > 0
        resp = client.post(f'{ADMIN}/login', json={'email': email, 'password': 'guess'})
        assert resp.status_code == 429
        assert resp.headers.get('Retry-After')

    def test_a_successful_login_clears_the_failures(self, monkeypatch):
        monkeypatch.setattr(admin, '_login_failures', {}, raising=False)
        monkeypatch.setattr(admin, '_login_lockouts', {}, raising=False)
        email = 'target@example.edu'
        with app.test_request_context(f'{ADMIN}/login'):
            admin._record_failed_admin_login(email)
            admin._clear_admin_login_failures(email)
            assert admin._check_admin_login_rate_limit(email) == (False, 0)


# ---------------------------------------------------------------------------
# 5. Resetting a password.

class TestResettingAPassword:
    def _signed_in(self, client, monkeypatch, user):
        sign_in(client)
        monkeypatch.setattr(admin, 'check_admin_auth', lambda: True)
        stub_user_lookup(monkeypatch, user)
        monkeypatch.setattr(admin, 'log_admin_action', lambda *a, **k: None)
        monkeypatch.setattr(admin, 'db', types.SimpleNamespace(
            session=types.SimpleNamespace(commit=lambda: None)))

    def test_a_short_password_is_refused(self, client, monkeypatch):
        self._signed_in(client, monkeypatch, FakeUser(password_hash='x'))
        resp = client.post(f'{ADMIN}/reset-password', json={
            'current_password': 'whatever', 'new_password': 'short', 'confirm_password': 'short'})
        assert resp.status_code == 400

    def test_a_mistyped_confirmation_is_refused(self, client, monkeypatch):
        self._signed_in(client, monkeypatch, FakeUser(password_hash='x'))
        resp = client.post(f'{ADMIN}/reset-password', json={
            'current_password': 'whatever', 'new_password': 'longenough1',
            'confirm_password': 'longenough2'})
        assert resp.status_code == 400

    def test_the_current_password_must_be_right(self, client, monkeypatch):
        from werkzeug.security import generate_password_hash
        self._signed_in(client, monkeypatch,
                        FakeUser(password_hash=generate_password_hash('the real one')))
        resp = client.post(f'{ADMIN}/reset-password', json={
            'current_password': 'not the real one', 'new_password': 'longenough1',
            'confirm_password': 'longenough1'})
        assert resp.status_code == 401

    def test_the_new_password_cannot_be_the_old_one(self, client, monkeypatch):
        from werkzeug.security import generate_password_hash
        self._signed_in(client, monkeypatch,
                        FakeUser(password_hash=generate_password_hash('longenough1')))
        resp = client.post(f'{ADMIN}/reset-password', json={
            'current_password': 'longenough1', 'new_password': 'longenough1',
            'confirm_password': 'longenough1'})
        assert resp.status_code == 400
