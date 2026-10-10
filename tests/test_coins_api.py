"""The Coins database builder (scripts/coins/build_coins_db.py) and the Coins
API (backend/blueprints/coins.py) on a fixture of 12 types, both sources."""
import json
import os
import sqlite3
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIX = os.path.join(ROOT, 'tests', 'fixtures', 'coins', 'coins.jsonl')


@pytest.fixture(scope='module')
def db(tmp_path_factory):
    out = str(tmp_path_factory.mktemp('coins') / 'coins.sqlite')
    subprocess.run([sys.executable, '-I', os.path.join(ROOT, 'scripts', 'coins', 'build_coins_db.py'),
                    '--input', FIX, '--out', out], check=True)
    return out


@pytest.fixture
def client(db, monkeypatch):
    monkeypatch.setenv('TESSERAE_COINS_DB', db)
    from backend.app import app
    app.config['TESTING'] = True
    return app.test_client()


def test_loader_rows_and_columns(db):
    c = sqlite3.connect(db)
    assert c.execute('SELECT COUNT(*) FROM coins').fetchone()[0] == 12
    assert dict(c.execute('SELECT source, COUNT(*) FROM coins GROUP BY 1')) == {'ocre': 8, 'crro': 4}
    cols = {r[1] for r in c.execute('PRAGMA table_info(coins)')}
    for need in ('id', 'source', 'uri', 'authority', 'portrait', 'mint', 'mint_pleiades_id', 'region',
                 'denomination', 'material', 'date_start', 'date_end', 'obverse_legend',
                 'reverse_legend', 'obverse_description', 'reverse_description', 'search_text'):
        assert need in cols
    row = c.execute("SELECT mint, mint_pleiades_id, date_start, date_end, uri, search_text FROM coins "
                    "WHERE id = 'ocre:ric.1(2).aug.125'").fetchone()
    assert row[0] and row[1] and row[2] == -18 and row[3] is not None
    assert row[4].startswith('http://numismatics.org/ocre/id/')
    assert row[5] == row[5].lower() and 'capricorn' in row[5]
    assert c.execute("SELECT COUNT(*) FROM coins_fts WHERE coins_fts MATCH 'capricorn'").fetchone()[0] == 1


def test_loader_strips_diacritics(tmp_path):
    rec = {'id': 'x:1', 'source': 'ocre', 'obverse_legend': 'ΡΩΜΑΊΩΝ Ēm', 'mint': {'label': 'M'}}
    src = tmp_path / 'in.jsonl'
    src.write_text(json.dumps(rec, ensure_ascii=False) + '\n')
    out = tmp_path / 'o.sqlite'
    subprocess.run([sys.executable, '-I', os.path.join(ROOT, 'scripts', 'coins', 'build_coins_db.py'),
                    '--input', str(src), '--out', str(out)], check=True)
    st = sqlite3.connect(out).execute('SELECT search_text FROM coins').fetchone()[0]
    assert st == 'ρωμαιων em'


def test_list_default_sorted_by_date(client):
    d = client.get('/api/coins').get_json()
    assert d['available'] and d['total'] == 12 and d['sort'] == 'date'
    dates = [c['date_start'] for c in d['coins']]
    assert dates == sorted(dates)
    c0 = d['coins'][-1]
    assert c0['credit'].startswith('Type record:') and c0['type_url'].startswith('http')


def test_search_text(client):
    d = client.get('/api/coins?q=capricorn').get_json()
    assert d['total'] == 1 and d['coins'][0]['id'] == 'ocre:ric.1(2).aug.125'
    assert d['sort'] == 'relevance'
    assert client.get('/api/coins?q=harbo').get_json()['total'] == 1  # prefix
    assert client.get('/api/coins?q=zzzzqq').get_json()['total'] == 0
    assert client.get('/api/coins?q=%22%28').get_json()['total'] == 12  # punctuation alone is no search
    assert client.get('/api/coins?q=capricorn+harbor').get_json()['total'] == 0  # all words must match


def test_filters(client):
    d = client.get('/api/coins?source=crro').get_json()
    assert d['total'] == 4 and all(c['source'] == 'crro' for c in d['coins'])
    d = client.get('/api/coins?authority=Augustus').get_json()
    assert d['total'] >= 3 and all(c['authority'] == 'Augustus' for c in d['coins'])
    d = client.get('/api/coins?denomination=Denarius').get_json()
    assert d['total'] >= 2 and all(c['denomination'] == 'Denarius' for c in d['coins'])
    d = client.get('/api/coins?material=Gold').get_json()
    assert all(c['material'] == 'Gold' for c in d['coins'])
    mint = client.get('/api/coins').get_json()['coins'][0]['mint']
    d = client.get('/api/coins', query_string={'mint': mint}).get_json()
    assert d['total'] >= 1 and all(c['mint'] == mint for c in d['coins'])
    d = client.get('/api/coins?date_from=-30&date_to=-10').get_json()
    assert d['total'] >= 3
    assert all(c['date_start'] <= -10 and c['date_end'] >= -30 for c in d['coins'])
    d = client.get('/api/coins?date_from=100').get_json()
    assert d['total'] >= 1 and all(c['date_end'] >= 100 for c in d['coins'])


def test_filters_combine_with_search(client):
    d = client.get('/api/coins?q=victory&source=crro').get_json()
    assert d['total'] == 1 and d['coins'][0]['source'] == 'crro'


def test_facets_on_list(client):
    d = client.get('/api/coins?source=ocre').get_json()
    assert sum(f['count'] for f in d['facets']['source']) == 12  # a facet ignores its own filter
    assert sum(f['count'] for f in d['facets']['authority']) == 8
    assert {f['value'] for f in d['facets']['material']} >= {'Gold', 'Silver'}


def test_paging(client):
    a = client.get('/api/coins?per_page=5&page=1').get_json()
    b = client.get('/api/coins?per_page=5&page=3').get_json()
    assert len(a['coins']) == 5 and len(b['coins']) == 2 and a['total'] == 12
    assert not {c['id'] for c in a['coins']} & {c['id'] for c in b['coins']}
    assert client.get('/api/coins?per_page=100000').get_json()['per_page'] == 100


def test_facets_route(client):
    d = client.get('/api/coins/facets').get_json()
    assert d['available'] and d['total'] == 12 and d['sources'] == {'ocre': 8, 'crro': 4}
    assert d['date_min'] <= -326 and d['date_max'] >= 103
    assert d['facets']['authority'][0]['count'] >= d['facets']['authority'][-1]['count']


def test_detail_and_404(client):
    d = client.get('/api/coins/ocre:ric.2.tr.471').get_json()['coin']
    assert d['authority'] == 'Trajan' and 'harbor' in d['reverse_description']
    assert d['pleiades_url'] is None or d['pleiades_url'].startswith('https://pleiades.stoa.org/places/')
    assert d['coin_url'] == '/coins/ocre%3Aric.2.tr.471'
    r = client.get('/api/coins/ocre:nope')
    assert r.status_code == 404
    assert client.get('/api/coins/crro:rrc-100.1a').get_json()['coin']['credit'].startswith('Type record: CRRO')


def test_missing_database(monkeypatch, tmp_path):
    monkeypatch.setenv('TESSERAE_COINS_DB', str(tmp_path / 'absent.sqlite'))
    from backend.app import app
    app.config['TESTING'] = True
    c = app.test_client()
    d = c.get('/api/coins').get_json()
    assert d['available'] is False and d['coins'] == [] and d['total'] == 0
    assert c.get('/api/coins/ocre:x').status_code == 404
    assert c.get('/api/coins/facets').get_json()['available'] is False
