"""scripts/events/fix_event_coords.py on small fixture stores."""
import json
import os
import sqlite3
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'scripts', 'events'))

import fix_event_coords as F  # noqa: E402


def test_corrected_event_gets_new_point_and_rows_from_every_source(tmp_path):
    ev = tmp_path / 'ev.sqlite'
    c = sqlite3.connect(ev)
    c.execute('CREATE TABLE events (id TEXT, label TEXT, date_start INTEGER, date_end INTEGER, lat REAL, lon REAL)')
    c.execute('CREATE TABLE documents (event_id TEXT, doc_id TEXT, date_start INTEGER, date_end INTEGER, place TEXT, '
              'distance_km REAL, text_snippet TEXT, language TEXT, lat REAL, lon REAL)')
    c.execute("INSERT INTO events VALUES ('E1','Actium',-31,-31,38.0,19.0)")
    c.execute("INSERT INTO events VALUES ('E2','Untouched',-31,-31,38.0,19.0)")
    c.execute("INSERT INTO documents VALUES ('E1','old',-40,-20,'sea',1.0,'x','la',38.0,19.0)")
    c.execute("INSERT INTO documents VALUES ('E2','keep',-40,-20,'sea',1.0,'x','la',38.0,19.0)")
    c.commit(); c.close()
    m = sqlite3.connect(tmp_path / 'm.db')
    m.execute('CREATE TABLE documents (id TEXT, date_not_before INTEGER, date_not_after INTEGER, ancient_place TEXT, pleiades_id TEXT, '
              'place_tm_id TEXT, text_type_label TEXT, object_type_label TEXT, principal_edition TEXT, languages TEXT)')
    m.executemany("INSERT INTO documents VALUES (?,?,?,?,?,?,'t','o','ed',?)", [
        ('edh:near', -35, -30, 'Actium', '1', None, 'la'), ('aio:tm', -35, -30, 'Nicopolis', None, '7', 'grc'),
        ('edh:wide', -100, 50, 'Actium', '1', None, 'la'), ('edh:far', -35, -30, 'Rome', '2', None, 'la')])
    m.commit(); m.close()
    (tmp_path / 'p.tsv').write_text('pleiades_id\tlat\tlon\ttitle\n1\t38.95\t20.76\tA\n2\t41.9\t12.5\tR\n3\t39.0\t20.7\tN\n')
    (tmp_path / 'cw.tsv').write_text('tm_place_id\tpleiades_id\tsource\tlabel\n7\t3\tx\tN\n')
    (tmp_path / 'c.json').write_text(json.dumps({'use_wikidata': {'E1': {'from': [38.0, 19.0], 'to': [38.95, 20.76]}}}))
    out = str(tmp_path / 'out.sqlite')
    F.main([str(ev), out, str(tmp_path / 'c.json'), '--documents-metadata', str(tmp_path / 'm.db'),
            '--pleiades-points', str(tmp_path / 'p.tsv'), '--crosswalk', str(tmp_path / 'cw.tsv'), '--apply'])
    o = sqlite3.connect(out)
    assert o.execute("SELECT lat, lon FROM events WHERE id = 'E1'").fetchone() == (38.95, 20.76)
    assert o.execute("SELECT lat FROM events WHERE id = 'E2'").fetchone() == (38.0,)
    ids = [r[0] for r in o.execute("SELECT doc_id FROM documents WHERE event_id = 'E1' ORDER BY distance_km")]
    assert ids == ['edh:near', 'aio:tm']                      # old row gone, span over 50 and 280 km away left out
    assert o.execute("SELECT COUNT(*) FROM documents WHERE event_id = 'E2'").fetchone()[0] == 1
