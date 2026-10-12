"""The object picture route: served from our disk cache, fetched once from an
allowed museum host, only for open licences. The upstream fetch is mocked."""
import sqlite3

import pytest

from backend.blueprints import objects as ob

JPEG = b'\xff\xd8\xff\xe0fakejpeg'
GOOD = 'https://openaccess-cdn.clevelandart.org/1/1_web.jpg'


@pytest.fixture
def client(tmp_path, monkeypatch):
    db = str(tmp_path / 'objects.sqlite')
    c = sqlite3.connect(db)
    c.execute('CREATE TABLE objects (id TEXT, image_url TEXT, licence TEXT)')
    c.executemany('INSERT INTO objects VALUES (?,?,?)', [
        ('cma:1', GOOD, 'CC0'),
        ('aic:2', 'https://www.artic.edu/iiif/2/x/full/843,/0/default.jpg',
         'Catalogue record CC0, description CC BY 4.0'),
        ('x:3', 'https://evil.example.org/a.jpg', 'CC0'),
        ('x:4', 'https://www.artic.edu/iiif/2/y/full/843,/0/default.jpg', 'All rights reserved'),
        ('x:5', None, 'CC0'),
        ('cma:6/7', GOOD.replace('/1/1_', '/6/6_'), 'CC0'),
    ])
    c.commit()
    c.close()
    monkeypatch.setenv('TESSERAE_OBJECTS_DB', db)
    monkeypatch.setenv('TESSERAE_OBJECT_IMAGES', str(tmp_path / 'images'))
    from backend.app import app
    app.config['TESTING'] = True
    return app.test_client()


def _count(monkeypatch, result=(JPEG, 'image/jpeg')):
    calls = []

    def fake(url):
        calls.append(url)
        if isinstance(result, Exception):
            raise result
        return result
    monkeypatch.setattr(ob, 'fetch_image', fake)
    return calls


def test_miss_then_hit(client, monkeypatch):
    calls = _count(monkeypatch)
    r = client.get('/api/objects/image/cma:1')
    assert r.status_code == 200 and r.data == JPEG
    assert r.headers['Content-Type'] == 'image/jpeg'
    assert r.headers['Cache-Control'] == 'public, max-age=2592000'
    assert r.headers['X-Image-Source'] == 'openaccess-cdn.clevelandart.org'
    r2 = client.get('/api/objects/image/cma:1')
    assert r2.status_code == 200 and r2.data == JPEG
    assert len(calls) == 1  # the second request came from disk


def test_id_with_slash(client, monkeypatch):
    _count(monkeypatch)
    assert client.get('/api/objects/image/cma:6/7').status_code == 200


def test_chicago_composite_licence_served(client, monkeypatch):
    _count(monkeypatch)
    r = client.get('/api/objects/image/aic:2')
    assert r.status_code == 200 and r.headers['X-Image-Source'] == 'www.artic.edu'


def test_host_allow_list(client, monkeypatch):
    calls = _count(monkeypatch)
    assert client.get('/api/objects/image/x:3').status_code == 404
    assert calls == []
    assert ob.image_host_allowed('https://www.artic.edu/a.jpg')
    assert not ob.image_host_allowed('https://www.artic.edu.evil.org/a.jpg')
    assert not ob.image_host_allowed('file:///etc/passwd')


def test_licence_gate_and_missing(client, monkeypatch):
    calls = _count(monkeypatch)
    assert client.get('/api/objects/image/x:4').status_code == 404  # not an open licence
    assert client.get('/api/objects/image/x:5').status_code == 404  # no image_url
    assert client.get('/api/objects/image/nope').status_code == 404
    assert calls == []
    assert ob.image_open_licence('CC0') and ob.image_open_licence('CC BY 4.0')
    assert ob.image_open_licence('Public Domain') and not ob.image_open_licence(None)


def test_error_is_502_and_not_cached(client, monkeypatch, tmp_path):
    calls = _count(monkeypatch, ValueError('upstream status 500'))
    r = client.get('/api/objects/image/cma:1')
    assert r.status_code == 502 and 'error' in r.get_json()
    assert not list((tmp_path / 'images').glob('*')) if (tmp_path / 'images').exists() else True
    ok = _count(monkeypatch)
    assert client.get('/api/objects/image/cma:1').status_code == 200  # retried, not a cached failure
    assert len(ok) == 1 and len(calls) == 1
