"""/api/scope: the live counts behind the scope box on each search page."""
import sqlite3

import pytest

from backend.blueprints import scope


@pytest.fixture(autouse=True)
def fresh_cache():
    scope.reset_cache()
    yield
    scope.reset_cache()


def _db(path, table, n):
    c = sqlite3.connect(path)
    c.execute(f'CREATE TABLE {table} (id INTEGER)')
    c.executemany(f'INSERT INTO {table} VALUES (?)', [(i,) for i in range(n)])
    c.commit()
    c.close()


def test_route_answers_with_every_key():
    from backend.app import app
    app.config['TESTING'] = True
    r = app.test_client().get('/api/scope')
    assert r.status_code == 200
    body = r.get_json()
    for key in ('texts', 'documents', 'passage_windows', 'events', 'coins', 'objects',
                'scholarship_windows'):
        assert key in body
    assert isinstance(body['texts'], dict)


def test_texts_cover_only_served_languages():
    from backend.app import app
    app.config['TESTING'] = True
    client = app.test_client()
    served = {l['code'] for l in client.get('/api/languages').get_json()['languages']}
    assert set(client.get('/api/scope').get_json()['texts']) <= served


def test_counts_read_stand_in_databases(monkeypatch, tmp_path):
    _db(str(tmp_path / 'e.sqlite'), 'events', 4)
    _db(str(tmp_path / 'c.sqlite'), 'coins', 7)
    _db(str(tmp_path / 'o.sqlite'), 'objects', 3)
    monkeypatch.setenv('TESSERAE_EVENTS_DB', str(tmp_path / 'e.sqlite'))
    monkeypatch.setenv('TESSERAE_COINS_DB', str(tmp_path / 'c.sqlite'))
    monkeypatch.setenv('TESSERAE_OBJECTS_DB', str(tmp_path / 'o.sqlite'))
    data = scope.build()
    assert (data['events'], data['coins'], data['objects']) == (4, 7, 3)


def test_missing_collections_are_null(monkeypatch, tmp_path):
    monkeypatch.setenv('TESSERAE_EVENTS_DB', str(tmp_path / 'none1'))
    monkeypatch.setenv('TESSERAE_COINS_DB', str(tmp_path / 'none2'))
    monkeypatch.setenv('TESSERAE_OBJECTS_DB', str(tmp_path / 'none3'))
    monkeypatch.setenv('TESSERAE_DOCUMENTS', '0')
    data = scope.build()
    assert data['events'] is None and data['coins'] is None and data['objects'] is None
    assert data['documents'] == {}


def test_documents_counted_when_the_index_exists(monkeypatch, tmp_path):
    import backend.documents as docs
    _db(str(tmp_path / 'la.db'), 'doc_meta', 5)
    monkeypatch.setenv('TESSERAE_DOCUMENTS', '1')
    monkeypatch.setattr(docs, '_index_db_path',
                        lambda lang: str(tmp_path / 'la.db') if lang == 'la' else str(tmp_path / 'absent.db'))
    assert scope.build()['documents'] == {'la': 5}


def test_the_answer_is_cached(monkeypatch):
    from backend.app import app
    app.config['TESTING'] = True
    calls = []
    monkeypatch.setattr(scope, 'build', lambda: calls.append(1) or {'texts': {}})
    client = app.test_client()
    client.get('/api/scope')
    client.get('/api/scope')
    assert len(calls) == 1
