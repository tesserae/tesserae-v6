"""Focused tests for admin text-request approval recovery."""

import os
import sys
import types

from flask import Flask

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.blueprints import admin


class FakeCursor:
    def __init__(self, row=None):
        self.row = row
        self.executed = []

    def execute(self, query, params=None):
        self.executed.append((query, params))

    def fetchone(self):
        return self.row


class FakeCursorContext:
    def __init__(self, cursor):
        self.cursor = cursor

    def __enter__(self):
        return self.cursor

    def __exit__(self, exc_type, exc, traceback):
        return False


def test_approval_marks_request_approved_when_later_maintenance_fails(monkeypatch, tmp_path):
    request_row = (
        'Test Author', 'Test Work', 'latin', 'arma virumque',
        None, None, None, None, None, '', '', '', '',
    )
    initial_cursor = FakeCursor(request_row)
    approval_cursor = FakeCursor()
    cursors = iter([initial_cursor, approval_cursor])

    monkeypatch.setattr(admin, 'check_admin_auth', lambda: True)
    monkeypatch.setattr(admin, 'get_admin_username', lambda: 'admin@example.test')
    monkeypatch.setattr(admin, 'get_db_cursor', lambda: FakeCursorContext(next(cursors)))
    monkeypatch.setattr(admin, '_texts_dir', str(tmp_path))
    monkeypatch.setattr(admin, '_text_processor', object())
    monkeypatch.setattr(admin, '_author_dates', {})
    monkeypatch.setattr(admin, 'log_admin_action', lambda *args, **kwargs: None)
    monkeypatch.setattr(admin, 'recalculate_language_frequencies', lambda *args: (_ for _ in ()).throw(RuntimeError('frequency unavailable')))
    monkeypatch.setattr(admin, '_update_corpus_status', lambda *args: None)
    monkeypatch.setattr(admin, '_update_text_provenance', lambda *args: None)
    monkeypatch.setattr(admin, '_add_to_text_sources', lambda *args: None)

    import backend.bigram_frequency
    import backend.blueprints.hapax
    import backend.cache
    import backend.inverted_index
    import backend.precompute_embeddings

    monkeypatch.setattr(backend.bigram_frequency, 'is_bigram_cache_available', lambda language: False)
    monkeypatch.setattr(backend.blueprints.hapax, 'regenerate_rare_words_cache', lambda language: None)
    monkeypatch.setattr(backend.cache, 'clear_cache_for_language', lambda language: None)
    monkeypatch.setattr(backend.inverted_index, 'index_single_text', lambda *args: {'status': 'indexed'})
    monkeypatch.setattr(backend.precompute_embeddings, 'compute_embeddings_for_text', lambda *args, **kwargs: (True, 1))
    monkeypatch.setitem(sys.modules, 'sentence_transformers', types.SimpleNamespace(SentenceTransformer=lambda name: object()))

    app = Flask(__name__)
    with app.test_request_context('/requests/7/approve', method='POST', json={'content': 'arma virumque'}):
        response = admin.approve_and_add_text(7)

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['success'] is True
    assert payload['warnings'] == [{'task': 'frequency recalculation', 'error': 'frequency unavailable'}]
    assert (tmp_path / 'la' / 'test_author.test_work.tess').read_text() == '<test_author.test_work.1> arma virumque'
    assert any("SET status = 'approved'" in query for query, _ in approval_cursor.executed)


def test_mark_approved_recovers_pending_request_without_corpus_processing(monkeypatch):
    cursor = FakeCursor(('pending',))
    audit_events = []

    monkeypatch.setattr(admin, 'check_admin_auth', lambda: True)
    monkeypatch.setattr(admin, 'get_admin_username', lambda: 'admin@example.test')
    monkeypatch.setattr(admin, 'get_db_cursor', lambda: FakeCursorContext(cursor))
    monkeypatch.setattr(admin, 'log_admin_action', lambda *args: audit_events.append(args))

    app = Flask(__name__)
    with app.test_request_context('/requests/7/mark-approved', method='POST'):
        response = admin.mark_request_approved(7)

    assert response.status_code == 200
    assert response.get_json()['success'] is True
    assert any("SET status = 'approved'" in query for query, _ in cursor.executed)
    assert audit_events[0][0] == 'mark_request_approved'


def test_mark_approved_does_not_override_rejected_request(monkeypatch):
    cursor = FakeCursor(('rejected',))

    monkeypatch.setattr(admin, 'check_admin_auth', lambda: True)
    monkeypatch.setattr(admin, 'get_db_cursor', lambda: FakeCursorContext(cursor))

    app = Flask(__name__)
    with app.test_request_context('/requests/7/mark-approved', method='POST'):
        response, status_code = admin.mark_request_approved(7)

    assert status_code == 409
    assert response.get_json()['error'].startswith('Rejected requests')
    assert not any("SET status = 'approved'" in query for query, _ in cursor.executed)
