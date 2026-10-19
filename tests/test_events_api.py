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


def test_commentary_rows_carry_the_fields_the_cite_control_reads(client, db, monkeypatch, tmp_path):
    """A commentary row on the event page names its commentator, work, note
    reference and edition, taken from the held commentary the title names."""
    import json
    import sqlite3
    from backend import scholarship
    comm = tmp_path / 'comm'
    comm.mkdir()
    (comm / 'how_wells__herodotus.histories.json').write_text(json.dumps({
        'work': 'herodotus.histories', 'commentator': 'W. W. How and J. Wells',
        'title': 'A Commentary on Herodotus',
        'edition': 'W. W. How and J. Wells, A Commentary on Herodotus (Oxford: Clarendon Press, 1912)',
        'units': [{'ref': '7.59.1', 'text': 'x'}]}))
    monkeypatch.setattr(scholarship, 'COMMENTARY_DIR', str(comm))
    monkeypatch.setitem(scholarship._sources_cache, 'stamp', None)
    eid = client.get('/api/events?sort=date').get_json()['events'][0]['id']
    c = sqlite3.connect(db)
    c.executemany("INSERT INTO scholarship (event_id, kind, title, page_ref, url) VALUES (?,?,?,?,?)", [
        (eid, 'commentary', 'W. W. How and J. Wells on herodotus.histories', 'hdt. 7.59.1', ''),
        (eid, 'commentary', 'Nobody Known on lost.work', 'lost 1.1', '')])
    c.commit()
    try:
        rows = client.get(f'/api/events/{eid}').get_json()['scholarship']
        held = next(r for r in rows if r['title'].endswith(' on herodotus.histories'))
        assert held['commentator'] == 'W. W. How and J. Wells' and held['work'] == 'herodotus.histories'
        assert held['ref_start'] == 'hdt. 7.59.1' and held['edition'].endswith('1912)')
        assert held['kind'] == 'commentary' and held['edition_title'] == 'A Commentary on Herodotus'
        lost = next(r for r in rows if r['title'].startswith('Nobody Known on'))
        assert lost['commentator'] == 'Nobody Known' and 'edition' not in lost
    finally:
        c.execute("DELETE FROM scholarship WHERE title IN ('W. W. How and J. Wells on herodotus.histories', 'Nobody Known on lost.work')")
        c.commit()
        scholarship._sources_cache.update(stamp=None, rows=None)


def test_edition_lookup_never_raises_when_the_held_list_or_a_field_is_missing(monkeypatch):
    from backend import scholarship
    monkeypatch.setattr(scholarship, 'commentary_sources', lambda: None)
    assert scholarship.commentary_edition_fields(commentator='A', work='w.x') == {}
    assert E._commentary_cite_fields('A on w.x', 'w 1.1') == {'commentator': 'A', 'work': 'w.x', 'ref_start': 'w 1.1'}
    monkeypatch.setattr(scholarship, 'commentary_sources', lambda: [{'commentator': 'A', 'works': None}])
    assert scholarship.commentary_edition_fields(commentator='A')['edition'] is None


def _doc(doc_id, a, b, km):
    return {'doc_id': doc_id, 'date_start': a, 'date_end': b, 'distance_km': km}


def test_documents_wider_than_fifty_years_are_left_out_and_naming_ones_come_first():
    docs = [_doc('wide', -450, -401, 1), _doc('limit', -460, -410, 2),   # spans 49 and 50
            _doc('toowide', -470, -410, 0.5),                            # 60 years
            _doc('tight_far', -415, -413, 90), _doc('tight_near', -415, -413, 3),
            _doc('named_wide_span', -430, -400, 80), _doc('named_tight', -414, -414, 70)]
    out = E.rank_documents(docs, {'named_wide_span', 'named_tight', 'toowide'})
    ids = [d['doc_id'] for d in out]
    assert 'toowide' not in ids
    assert [d['group'] for d in out] == ['names', 'names'] + ['dated'] * 4
    assert ids[:2] == ['named_tight', 'named_wide_span']             # tighter dating first
    assert ids[2:] == ['tight_near', 'tight_far', 'wide', 'limit']   # span, then distance, then id order
    assert E.MAX_DOCUMENT_SPAN == 50


def test_detail_documents_carry_group_counts_and_record_ids(client, monkeypatch):
    first = client.get('/api/events/' + _id(client, 'pharsalus')).get_json()
    stored = first['documents']
    assert len(stored) == 2 and all(d['group'] == 'dated' for d in stored)   # the 99-year one is left out
    assert first['document_counts'] == {'names': 0, 'dated': 2, 'left_out': 1}
    pick = stored[-1]['doc_id']
    monkeypatch.setattr(E, '_documents_naming', lambda ids, names: {pick})
    d = client.get('/api/events/' + _id(client, 'pharsalus')).get_json()
    assert d['documents'][0]['doc_id'] == pick and d['documents'][0]['group'] == 'names'
    assert d['document_counts']['names'] == 1
    assert d['document_counts']['names'] + d['document_counts']['dated'] + d['document_counts']['left_out'] == len(stored) + 1
    assert all(x['doc_id'] for x in d['documents'])
