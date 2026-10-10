"""The Objects API (backend/blueprints/objects.py, backend/objects_theme.py) on the
six-object fixture, with seeded 8-dimension vectors and a stand-in encoder."""
import json
import os
import subprocess
import sys

import numpy as np
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIX = os.path.join(ROOT, 'tests', 'fixtures', 'objects')


@pytest.fixture(scope='module')
def site(tmp_path_factory):
    d = tmp_path_factory.mktemp('objsite')
    db = str(d / 'objects.sqlite')
    subprocess.run([sys.executable, '-I', os.path.join(ROOT, 'scripts', 'objects', 'build_objects_db.py'),
                    '--cleveland', f'{FIX}/cleveland', '--chicago', f'{FIX}/chicago',
                    '--smithsonian', f'{FIX}/smithsonian', '--out', db], check=True, capture_output=True)
    import sqlite3
    ids = [r[0] for r in sqlite3.connect(db).execute('SELECT id FROM objects ORDER BY n')]
    rng = np.random.default_rng(7)
    vecs = rng.normal(size=(len(ids), 8)).astype(np.float32)
    vecs /= np.linalg.norm(vecs, axis=1, keepdims=True)
    np.save(d / 'descriptions.npy', vecs.astype(np.float16))
    (d / 'descriptions_ids.json').write_text(json.dumps(
        [{'text': f'text {i}', 'types': [oid]} for i, oid in enumerate(ids)]))
    return {'db': db, 'ids': ids, 'vecs': vecs, 'dir': d}


@pytest.fixture
def client(site, monkeypatch):
    monkeypatch.setenv('TESSERAE_OBJECTS_DB', site['db'])
    from backend.app import app
    app.config['TESTING'] = True
    return app.test_client()


def test_list_default_sorted_by_date(client):
    d = client.get('/api/objects').get_json()
    assert d['available'] and d['total'] == 6 and d['sort'] == 'date'
    dates = [o['date_start'] for o in d['objects'] if o['date_start'] is not None]
    assert dates == sorted(dates)
    o = d['objects'][0]
    assert o['museum_name'] and o['credit'] and o['object_url'].startswith('http')
    assert 'search_text' not in o


def test_search_text(client):
    d = client.get('/api/objects?q=lekythos').get_json()
    assert d['total'] == 2 and d['sort'] == 'relevance'
    assert client.get('/api/objects?q=banque').get_json()['total'] == 1  # prefix
    assert client.get('/api/objects?q=zzzzqq').get_json()['total'] == 0
    assert client.get('/api/objects?q=%22%28').get_json()['total'] == 6  # punctuation alone is no search
    assert client.get('/api/objects?q=lekythos+banquet').get_json()['total'] == 0  # all words must match
    assert client.get('/api/objects?q=%CE%B6%CF%89%CE%B9%CE%BB%CE%BF%CF%82').get_json()['total'] == 1  # inscription text (Greek)


def test_filters(client):
    d = client.get('/api/objects?museum=chicago').get_json()
    assert d['total'] == 2 and all(o['museum'] == 'chicago' for o in d['objects'])
    d = client.get('/api/objects?object_type=Sculpture').get_json()
    assert d['total'] == 2 and all(o['object_type'] == 'Sculpture' for o in d['objects'])
    d = client.get('/api/objects', query_string={'culture': 'Greek, Attic'}).get_json()
    assert d['total'] >= 1 and all(o['culture'] == 'Greek, Attic' for o in d['objects'])
    d = client.get('/api/objects?material=marble').get_json()
    assert d['total'] >= 1 and all(o['material'] == 'marble' for o in d['objects'])
    d = client.get('/api/objects?date_from=-600&date_to=-300').get_json()
    assert d['total'] >= 2 and all(o['date_start'] <= -300 and (o['date_end'] or o['date_start']) >= -600
                                   for o in d['objects'])
    d = client.get('/api/objects?date_from=100').get_json()
    assert d['total'] >= 1 and all((o['date_end'] or o['date_start']) >= 100 for o in d['objects'])


def test_filters_combine_with_search(client):
    d = client.get('/api/objects?q=lekythos&museum=cleveland').get_json()
    assert d['total'] == 1 and d['objects'][0]['museum'] == 'cleveland'


def test_facets_on_list(client):
    d = client.get('/api/objects?museum=chicago').get_json()
    assert sum(f['count'] for f in d['facets']['museum']) == 6  # a facet ignores its own filter
    assert {f['value'] for f in d['facets']['object_type']} >= {'Sculpture', 'Vessel'}


def test_paging(client):
    a = client.get('/api/objects?per_page=4&page=1').get_json()
    b = client.get('/api/objects?per_page=4&page=2').get_json()
    assert len(a['objects']) == 4 and len(b['objects']) == 2 and a['total'] == 6
    assert not {o['id'] for o in a['objects']} & {o['id'] for o in b['objects']}
    assert client.get('/api/objects?per_page=100000').get_json()['per_page'] == 100


def test_facets_route(client):
    d = client.get('/api/objects/facets').get_json()
    assert d['available'] and d['total'] == 6
    assert d['museums'] == {'cleveland': 2, 'chicago': 2, 'smithsonian': 2}
    assert d['date_min'] <= -500 and d['date_max'] >= 100


def test_detail_and_404(client):
    d = client.get('/api/objects/cma:1966.114').get_json()['object']
    assert d['museum_name'] == 'Cleveland Museum of Art' and 'perfumed oil' in d['description']
    assert d['object_page'] == '/objects/cma%3A1966.114'
    assert client.get('/api/objects/cma:nope').status_code == 404
    assert 'CC BY 4.0' in client.get('/api/objects/aic:1900.001').get_json()['object']['credit']


def test_missing_database(monkeypatch, tmp_path):
    monkeypatch.setenv('TESSERAE_OBJECTS_DB', str(tmp_path / 'absent.sqlite'))
    from backend.app import app
    app.config['TESTING'] = True
    c = app.test_client()
    d = c.get('/api/objects').get_json()
    assert d['available'] is False and d['objects'] == [] and d['total'] == 0
    assert c.get('/api/objects/cma:x').status_code == 404
    assert c.get('/api/objects/facets').get_json()['available'] is False
    assert c.get('/api/objects/theme?q=vase').get_json()['available'] is False


@pytest.fixture
def stub(monkeypatch, site):
    from backend import coins_passage as CP
    calls = []

    def fake(text):
        calls.append(text)
        return site['vecs'][3]  # the query is the fourth object's vector
    monkeypatch.setattr(CP, 'embed', fake)
    return calls


def test_theme_ranks_descriptions(client, stub, site):
    d = client.get('/api/objects/theme?q=a+banquet+scene&limit=3').get_json()
    assert d['available'] and len(d['results']) == 3 and 'catalogue texts' in d['label']
    top = d['results'][0]
    assert top['id'] == site['ids'][3] and top['score'] > 0.99
    assert top['snippet'] and top['credit'] and top['object_url']
    scores = [r['score'] for r in d['results']]
    assert scores == sorted(scores, reverse=True)
    assert stub == ['a banquet scene']


def test_theme_needs_a_query(client):
    assert client.get('/api/objects/theme').get_json()['results'] == []


def test_theme_without_vectors(site, tmp_path, monkeypatch):
    import shutil
    db = tmp_path / 'objects.sqlite'
    shutil.copy(site['db'], db)
    monkeypatch.setenv('TESSERAE_OBJECTS_DB', str(db))
    from backend.app import app
    app.config['TESTING'] = True
    d = app.test_client().get('/api/objects/theme?q=vase').get_json()
    assert d['available'] is False and d['results'] == [] and 'not installed' in d['reason']


def test_theme_encoder_down_is_said_plainly(client, monkeypatch):
    from backend import coins_passage as CP

    def boom(text):
        raise RuntimeError('connection refused')
    monkeypatch.setattr(CP, 'embed', boom)
    d = client.get('/api/objects/theme?q=vase').get_json()
    assert d['unavailable'] is True and 'encoder' in d['error'] and d['results'] == []
