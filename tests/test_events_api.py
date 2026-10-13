"""The Events API (backend/blueprints/events.py) against a small database built
from sample dossiers by scripts/events/load_dossiers_sqlite.py."""
import os
import subprocess
import sys

import pytest

from backend.blueprints import events as E

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIX = os.path.join(ROOT, 'tests', 'fixtures', 'events')


@pytest.fixture(scope='module')
def db(tmp_path_factory):
    out = str(tmp_path_factory.mktemp('events') / 'dossiers.sqlite')
    subprocess.run([sys.executable, os.path.join(ROOT, 'scripts', 'events', 'load_dossiers_sqlite.py'),
                    '--dossiers', FIX, '--out', out], check=True)
    return out


@pytest.fixture
def client(db, monkeypatch):
    monkeypatch.setenv('TESSERAE_EVENTS_DB', db)
    from backend.app import app
    app.config['TESTING'] = True
    return app.test_client()


def test_list_all(client):
    d = client.get('/api/events?sort=date').get_json()
    assert d['available'] and d['total'] == 4 and d['total_all'] == 4
    assert d['sort'] == 'date' and d['show'] == 'evidence'
    assert [e['id'] for e in d['events']][0] == 'Q' + d['events'][0]['id'][1:]
    dates = [e['date_start'] for e in d['events']]
    assert dates == sorted(dates)
    assert 'battle' in d['types'] or d['types']
    assert d['type_counts'] and sum(d['type_counts'].values()) == 4
    assert -5 in d['centuries'] and -1 in d['centuries']


def test_default_order_is_most_evidence_first(client):
    """The default list puts the events with the most passages and documents
    first, ties broken by date; `sort=date` is the chronological order."""
    d = client.get('/api/events').get_json()
    assert d['sort'] == 'evidence'
    keys = [(-(e['n_passages'] + e['n_documents']), -e['n_passages'], e['date_start']) for e in d['events']]
    assert keys == sorted(keys)
    assert d['events'][0]['n_passages'] + d['events'][0]['n_documents'] >= \
        d['events'][-1]['n_passages'] + d['events'][-1]['n_documents']


def test_events_without_evidence_hidden_unless_show_all(client, db):
    """An event with no passage and no document is left out of the default
    list and counted in total_all; show=all brings it back. An item with only
    its Q-number for a label is never listed."""
    import sqlite3
    c = sqlite3.connect(db)
    c.execute("INSERT INTO events (id, label, type, date_start, date_end) VALUES ('Q900', 'Battle of Nowhere', 'battle', -300, -300)")
    c.execute("INSERT INTO events (id, label, type, date_start, date_end) VALUES ('Q901', 'Q901', 'treaty', -300, -300)")
    c.commit()
    try:
        d = client.get('/api/events').get_json()
        assert d['total'] == 4 and d['total_all'] == 5
        assert 'Battle of Nowhere' not in [e['label'] for e in d['events']]
        assert d['type_counts'].get('treaty') is None
        d = client.get('/api/events?show=all&sort=date').get_json()
        assert d['total'] == 5 and d['show'] == 'all'
        labels = [e['label'] for e in d['events']]
        assert 'Battle of Nowhere' in labels and 'Q901' not in labels
        assert client.get('/api/events?q=Nowhere').get_json()['total'] == 0
        assert client.get('/api/events?q=Nowhere&show=all').get_json()['total'] == 1
    finally:
        c.execute("DELETE FROM events WHERE id IN ('Q900', 'Q901')")
        c.commit()
        c.close()


def test_search_label_and_place(client):
    d = client.get('/api/events?q=cannae').get_json()
    assert d['total'] == 1 and d['events'][0]['label'] == 'Battle of Cannae'
    assert d['events'][0]['n_passages'] > 0
    assert client.get('/api/events?q=zzzz').get_json()['total'] == 0
    assert client.get('/api/events?q=%25').get_json()['total'] == 0  # % is literal


def test_filter_century_and_type(client):
    d = client.get('/api/events?century=-5').get_json()
    assert {e['label'] for e in d['events']} == {'Battle of Marathon', 'Battle of Salamis'}
    assert client.get('/api/events?century=-1').get_json()['total'] == 1  # Pharsalus, 48 BCE
    assert client.get('/api/events?century=1').get_json()['total'] == 0
    t = client.get('/api/events').get_json()['types'][0]
    assert client.get('/api/events?type=' + t).get_json()['total'] >= 1
    assert client.get('/api/events?type=nonesuch').get_json()['total'] == 0


def test_paging(client):
    a = client.get('/api/events?per_page=3&page=1').get_json()
    b = client.get('/api/events?per_page=3&page=2').get_json()
    assert len(a['events']) == 3 and len(b['events']) == 1 and a['total'] == 4
    assert not {e['id'] for e in a['events']} & {e['id'] for e in b['events']}


def test_century_helpers():
    assert E.century_of(-490) == -5 and E.century_of(-500) == -5 and E.century_of(-501) == -6
    assert E.century_of(9) == 1 and E.century_of(100) == 1 and E.century_of(101) == 2
    assert E.century_range(-5) == (-500, -401) and E.century_range(1) == (1, 100)


def _id(client, q):
    return client.get('/api/events?q=' + q).get_json()['events'][0]['id']


def test_detail_shape(client):
    d = client.get('/api/events/' + _id(client, 'pharsalus')).get_json()
    ev = d['event']
    assert ev['label'] == 'Battle of Pharsalus' and ev['place'] == 'Farsala'
    assert ev['participants'] == ['populares', 'optimates']
    assert ev['wikipedia_url'] == 'https://en.wikipedia.org/wiki/Battle_of_Pharsalus'
    labels = [p['llm_label'] for p in d['passages']]
    assert 'no' not in labels
    order = [{'yes': 0, 'mention': 1}.get(x, 2) for x in labels]
    assert order == sorted(order)
    p = d['passages'][0]
    assert p['reader_url'].startswith('/read?work=') and '&lang=' in p['reader_url'] and '&ref=' in p['reader_url']
    assert p['language'] in ('la', 'grc')
    assert d['passage_counts']
    assert d['documents'] and d['documents'][0]['view_url'].startswith('/document?doc=')
    assert d['documents'][0]['distance_km'] is not None
    assert d['scholarship'] and {'kind', 'title', 'page_ref', 'url'} <= set(d['scholarship'][0])
    kinds = [m['kind'] for m in d['map']]
    assert kinds[0] == 'event' and 'findspot' in kinds


def test_detail_all_includes_no(client):
    i = _id(client, 'cannae')
    n_default = len(client.get(f'/api/events/{i}').get_json()['passages'])
    n_all = len(client.get(f'/api/events/{i}?all=1').get_json()['passages'])
    assert n_all >= n_default


def test_unknown_event_404(client):
    assert client.get('/api/events/Q0').status_code == 404


def test_missing_database(monkeypatch, tmp_path):
    monkeypatch.setenv('TESSERAE_EVENTS_DB', str(tmp_path / 'nope.sqlite'))
    from backend.app import app
    c = app.test_client()
    d = c.get('/api/events').get_json()
    assert d['available'] is False and d['events'] == []
    assert c.get('/api/events/Q1').status_code == 404
