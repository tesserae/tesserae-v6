"""refresh_document_distances: rows are recomputed from the document's current place, others left alone."""
import os
import sqlite3
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts', 'events'))
import refresh_document_distances as R  # noqa: E402

AQUILEIA, AALEN = (45.77, 13.37), (48.678, 10.151)


def build():
    e = sqlite3.connect(':memory:')
    e.execute('CREATE TABLE events (id TEXT, lat REAL, lon REAL)')
    e.execute('CREATE TABLE documents (event_id TEXT, doc_id TEXT, date_start INTEGER, date_end INTEGER, place TEXT, '
              'distance_km REAL, text_snippet TEXT, language TEXT, lat REAL, lon REAL)')
    e.executemany('INSERT INTO events VALUES (?,?,?)', [('E1', 45.77, 13.37), ('E2', None, None)])
    e.executemany('INSERT INTO documents VALUES (?,?,?,?,?,?,?,?,?,?)', [
        ('E1', 'stale', 0, 0, 'Aquileia, bei', 404.6, '', 'la', AALEN[0], AALEN[1]),      # old crosswalk value
        ('E1', 'fresh', 0, 0, 'Aquileia', 0.0, '', 'la', AQUILEIA[0], AQUILEIA[1]),       # already right
        ('E1', 'bytm', 0, 0, 'x', 99.0, '', 'la', 1.0, 1.0),                              # place through the crosswalk
        ('E1', 'noplace', 0, 0, 'y', 7.0, '', 'la', 2.0, 2.0),                            # no place: left as it is
        ('E2', 'stale', 0, 0, 'z', 5.0, '', 'la', 3.0, 3.0),
        ('E1', 'stale', 0, 0, 'naming', None, '', 'la', None, None)])                    # naming row: no distance on purpose                             # event has no point: left
    m = sqlite3.connect(':memory:')
    m.execute('CREATE TABLE documents (id TEXT, pleiades_id TEXT, place_tm_id INTEGER)')
    m.executemany('INSERT INTO documents VALUES (?,?,?)', [('stale', '187290', 3327), ('fresh', '187290', None),
                                                           ('bytm', None, 3327), ('noplace', None, None)])
    return e, m


def test_changes_only_rows_whose_current_place_differs():
    e, m = build()
    changes, counts = R.compute_changes(e, m, {'187290': AQUILEIA}, {'3327': '187290'})
    by = {(c[1], c[2]): c for c in changes}
    assert set(by) == {('E1', 'stale'), ('E1', 'bytm')}  # the naming row of 'stale' is not among them
    assert by[('E1', 'stale')][3:5] == (404.6, 0.0) and by[('E1', 'stale')][5:] == AQUILEIA
    assert counts == {'rows': 6, 'no_distance_kept': 1, 'no_event_point': 1, 'no_document_place': 1, 'unchanged': 1, 'changed': 2,
                      'now_beyond_radius': 0}


def test_distance_uses_the_haversine_of_the_rule():
    e, m = build()
    e.execute("UPDATE events SET lat = 48.678, lon = 10.151 WHERE id = 'E1'")
    changes, _ = R.compute_changes(e, m, {'187290': AQUILEIA}, {'3327': '187290'})
    stale = [c for c in changes if c[2] == 'stale'][0]
    assert 400 < stale[4] < 410
