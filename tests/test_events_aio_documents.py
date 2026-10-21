"""scripts/events/add_aio_documents.py on small fixture stores: the dating rule, the findspot fallbacks,
the cap kept with the rows already held, and that nothing already in the store is touched."""
import os
import sqlite3
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'scripts', 'events'))

import add_aio_documents as A  # noqa: E402

DOC_COLS = '(event_id TEXT, doc_id TEXT, date_start INTEGER, date_end INTEGER, place TEXT, distance_km REAL, ' \
           'text_snippet TEXT, language TEXT, lat REAL, lon REAL)'
POINTS = {'579885': (37.97, 23.72), '580062': (37.94, 23.64), '580097': (38.22, 24.03), '1': (36.0, 14.0)}


@pytest.fixture
def stores(tmp_path):
    ev = tmp_path / 'events.sqlite'
    c = sqlite3.connect(ev)
    c.execute('CREATE TABLE events (id TEXT, label TEXT, date_start INTEGER, date_end INTEGER, place TEXT, lat REAL, lon REAL)')
    c.execute(f'CREATE TABLE documents {DOC_COLS}')
    c.execute("INSERT INTO events VALUES ('E1','Battle near Athens',-415,-413,'Athens',37.97,23.72)")
    c.execute("INSERT INTO events VALUES ('E2','Battle in Sicily',-415,-413,'Sicily',37.6,14.0)")
    c.execute("INSERT INTO events VALUES ('E3','No place',-415,-413,NULL,NULL,NULL)")
    c.execute("INSERT INTO events VALUES ('E4','Full',-415,-413,'Athens',37.97,23.72)")
    c.execute("INSERT INTO documents VALUES ('E1','old_wide',-500,-401,'X',2.0,'x','grc',37.9,23.7)")
    c.execute("INSERT INTO documents VALUES ('E1','old_narrow',-420,-410,'X',30.0,'x','grc',37.9,23.7)")
    for i in range(3):
        c.execute("INSERT INTO documents VALUES ('E4',?,-420,-410,'X',?,'x','grc',37.9,23.7)", (f'old{i}', 1.0 + i))
    c.commit()
    c.close()
    return str(ev), tmp_path


def doc(i, nb, na, place='Agora', pid=None, **k):
    pt, how = A.locate(pid, place, POINTS)
    return {'id': i, 'ds': nb, 'de': na, 'place': place, 'lat': pt[0], 'lon': pt[1], 'snippet': 's'}


def test_findspots_use_the_pleiades_place_then_the_text_then_athens_then_none():
    assert A.locate('580097', 'Rhamnous', POINTS)[1] == 'pleiades'
    assert A.locate(None, 'Eleusis', {**POINTS, '579920': (38.04, 23.53)})[1] == 'text'
    assert A.locate(None, 'Pnyx', POINTS) == (POINTS['579885'], 'text')
    assert A.locate(None, 'Unknown', POINTS) == (POINTS['579885'], 'athens')
    assert A.locate(None, 'Tunisia', POINTS) == (None, 'none')
    assert A.locate('999', 'Agora', POINTS)[1] == 'text'            # an id the points table lacks falls to the text


def test_dating_span_overlap_and_distance_decide(stores):
    ev, _ = stores
    aio = [doc('aio:in', -420, -410), doc('aio:wide', -480, -400), doc('aio:late', -300, -290),
           doc('aio:edge', -405, -400), doc('aio:far', -420, -410, pid='1')]
    plan, _d = A.plan_rows(sqlite3.connect(ev), aio)
    ids = [r[1] for r in plan['E1']]
    assert ids == ['aio:in', 'aio:edge'] or set(ids) == {'aio:in', 'aio:edge'}
    assert 'aio:wide' not in ids and 'aio:late' not in ids          # span over 50, outside the years plus ten
    assert 'E2' not in plan and 'E3' not in plan                    # far from Athens, no place
    assert all(len(r) == 10 and r[7] == 'grc' for r in plan['E1'])


def test_the_cap_is_kept_with_the_rows_already_held(stores):
    ev, _ = stores
    aio = [doc(f'aio:{i}', -420, -410, 'Piraeus', '580062') for i in range(5)]       # about 8 km, past the held 1 to 3 km
    plan, displaced = A.plan_rows(sqlite3.connect(ev), aio, max_per_event=4)
    assert len(plan['E4']) == 1                      # three narrow rows held, so one place is left
    plan, displaced = A.plan_rows(sqlite3.connect(ev), aio, max_per_event=50)
    assert len(plan['E4']) == 5 and displaced['E4'] == 0


def test_apply_adds_rows_and_changes_nothing_else(stores):
    ev, tmp = stores
    out = str(tmp / 'out.sqlite')
    meta = tmp / 'metadata.db'
    m = sqlite3.connect(meta)
    m.execute('CREATE TABLE documents (id TEXT, source TEXT, date_not_before INTEGER, date_not_after INTEGER, ancient_place TEXT, '
              'pleiades_id TEXT, text_type_label TEXT, object_type_label TEXT, principal_edition TEXT, languages TEXT)')
    m.execute("INSERT INTO documents VALUES ('aio:a','aio',-420,-410,'Agora','579885','decree','stele','IG I3 1','grc')")
    m.execute("INSERT INTO documents VALUES ('edr:b','edr',-420,-410,'Agora','579885','decree','stele','IG I3 1','grc')")
    m.commit()
    m.close()
    pts = tmp / 'points.tsv'
    pts.write_text('pleiades_id\tlat\tlon\ttitle\n579885\t37.97\t23.72\tAthenae\n')
    before = open(ev, 'rb').read()
    A.main([ev, out, '--documents-metadata', str(meta), '--pleiades-points', str(pts), '--apply'])
    assert open(ev, 'rb').read() == before
    c = sqlite3.connect(out)
    rows = c.execute("SELECT doc_id, language, distance_km, text_snippet FROM documents WHERE doc_id LIKE 'aio:%' "
                     "ORDER BY event_id").fetchall()
    assert rows and rows[0][0] == 'aio:a' and rows[0][1] == 'grc' and rows[0][2] == 0.0
    assert rows[0][3] == 'decree / stele; IG I3 1'
    assert c.execute("SELECT COUNT(*) FROM documents WHERE doc_id = 'edr:b'").fetchone()[0] == 0      # only the AIO source
    with pytest.raises(SystemExit):
        A.main([ev, ev, '--documents-metadata', str(meta)])
