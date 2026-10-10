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


# ---------------------------------------------------------------------------
# With the Greek sets (fixture: the 12 Roman types plus one type from each of
# eight Greek catalogues)
# ---------------------------------------------------------------------------

GREEK_FIX = os.path.join(ROOT, 'tests', 'fixtures', 'coins', 'greek_coins.jsonl')
NEW_SOURCES = {'cn', 'sco', 'pella', 'pco', 'bigr', 'iris', 'iacb', 'lco'}


@pytest.fixture(scope='module')
def db_all(tmp_path_factory):
    d = tmp_path_factory.mktemp('coins_all')
    both = d / 'all.jsonl'
    both.write_text(open(FIX, encoding='utf-8').read() + open(GREEK_FIX, encoding='utf-8').read(),
                    encoding='utf-8')
    out = str(d / 'coins.sqlite')
    subprocess.run([sys.executable, '-I', os.path.join(ROOT, 'scripts', 'coins', 'build_coins_db.py'),
                    '--input', str(both), '--out', out], check=True)
    return out


@pytest.fixture
def client_all(db_all, monkeypatch):
    monkeypatch.setenv('TESSERAE_COINS_DB', db_all)
    from backend.app import app
    app.config['TESTING'] = True
    return app.test_client()


def test_source_facet_carries_the_greek_sets(client_all):
    d = client_all.get('/api/coins/facets').get_json()
    assert d['total'] == 20
    assert d['sources'] == {'ocre': 8, 'crro': 4, **{k: 1 for k in NEW_SOURCES}}
    values = {f['value'] for f in d['facets']['source']}
    assert values == {'ocre', 'crro'} | NEW_SOURCES


def test_every_source_has_a_credit_line(client_all):
    for src in NEW_SOURCES:
        d = client_all.get(f'/api/coins?source={src}').get_json()
        assert d['total'] == 1
        credit = d['coins'][0]['credit']
        assert credit.startswith('Type record:') and credit != 'Type record: American Numismatic Society, ODbL'
    assert 'CC BY-NC-SA 3.0' in client_all.get('/api/coins?source=cn').get_json()['coins'][0]['credit']
    assert 'CC BY-NC-SA 4.0' in client_all.get('/api/coins?source=iacb').get_json()['coins'][0]['credit']
    assert 'ODbL' in client_all.get('/api/coins?source=iris').get_json()['coins'][0]['credit']


def test_greek_legend_typed_without_accents_is_found(client_all):
    # catalogued "BA\u03a3\u0399\u039b\u0395\u03a9\u03a3 \u03a3\u0395\u039b\u0395\u03a5\u039a\u039f\u03a5" (Latin B and A, capital sigmas)
    for q in ('\u03b2\u03b1\u03c3\u03b9\u03bb\u03b5\u03c9\u03c3 \u03c3\u03b5\u03bb\u03b5\u03c5\u03ba\u03bf\u03c5',   # lower case, ordinary sigma
              '\u03b2\u03b1\u03c3\u03b9\u03bb\u03b5\u03c9\u03c2 \u03c3\u03b5\u03bb\u03b5\u03c5\u03ba\u03bf\u03c5',   # final sigma
              '\u0392\u0391\u03a3\u0399\u039b\u0395\u03a9\u03a3',                          # capitals
              '\u03b2\u03b1\u03c3\u03b9\u03bb\u03ad\u03c9\u03c2 \u03c3\u03b5\u03bb\u03b5\u03cd\u03ba\u03bf\u03c5'):  # with accents
        d = client_all.get('/api/coins', query_string={'q': q}).get_json()
        assert 'sco:sc.1.1' in [c['id'] for c in d['coins']], q
    d = client_all.get('/api/coins', query_string={'q': '\u03c6\u03b9\u03bb\u03b9\u03c0\u03c0\u03bf\u03c5'}).get_json()
    assert [c['id'] for c in d['coins']] == ['pella:lerider.philip_ii.1.1']


def test_greek_description_is_found(client_all):
    d = client_all.get('/api/coins?q=elephant').get_json()
    assert 'sco:sc.1.1' in [c['id'] for c in d['coins']]
    d = client_all.get('/api/coins?q=butting+bull&source=iacb').get_json()
    assert d['total'] == 1
