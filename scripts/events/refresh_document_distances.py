#!/usr/bin/env python3
"""Recompute the lat, lon and distance_km of every row of an events store's documents table from the documents' current places.

  refresh_document_distances.py INPUT.sqlite OUTPUT.sqlite --metadata PATH [--crosswalk PATH] [--pleiades-points PATH] [--apply]

A document's place is its `pleiades_id` in the metadata database, else its `place_tm_id` through the
Trismegistos-to-Pleiades crosswalk. The row's lat and lon become that place's point and its distance_km the
distance (haversine, rounded to 0.1 km, as the events documents rule computes it) from the event's own
coordinates. A row with no distance_km (a naming row, shown without one on purpose) is left as it is, and so is a row whose document has no place with a point, whose document is not in the metadata, or whose
event has no coordinates is left as it is. This repairs rows that earlier steps kept (naming rows, unchanged rule
rows) with values computed under an older crosswalk.

Dry run unless --apply: prints how many rows change the number of rows that fell from inside the rule's 100 km radius to outside it (not removed), and the twenty largest changes. INPUT is never modified,
OUTPUT may not be under /var/www.
"""
import argparse
import os
import shutil
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from add_naming_documents import haversine_km, load_points  # noqa: E402
from fix_event_coords import load_crosswalk  # noqa: E402

HOME = os.path.expanduser('~')
RADIUS_KM = 100.0  # the events documents rule's radius
EPS = 0.05  # a distance within rounding, in km, is no change


def compute_changes(events_conn, meta_conn, points, cw):
    """Return (changes, counts). A change is (rowid, event_id, doc_id, old_distance, new_distance, new_lat, new_lon)."""
    ev = {r[0]: (r[1], r[2]) for r in events_conn.execute('SELECT id, lat, lon FROM events')}
    place = {}
    for did, pid, tm in meta_conn.execute('SELECT id, pleiades_id, place_tm_id FROM documents'):
        pid = str(pid) if pid else cw.get(str(tm)) if tm is not None else None
        if pid and pid in points:
            place[did] = points[pid]
    changes, counts = [], {'rows': 0, 'no_distance_kept': 0, 'no_event_point': 0, 'no_document_place': 0, 'unchanged': 0}
    for rowid, eid, did, dist, lat, lon in events_conn.execute(
            'SELECT rowid, event_id, doc_id, distance_km, lat, lon FROM documents'):
        counts['rows'] += 1
        if dist is None:  # a naming row: shown without a distance on purpose
            counts['no_distance_kept'] += 1
            continue
        e = ev.get(eid)
        if not e or e[0] is None or e[1] is None:
            counts['no_event_point'] += 1
            continue
        pt = place.get(did)
        if not pt:
            counts['no_document_place'] += 1
            continue
        d = round(haversine_km(e[0], e[1], pt[0], pt[1]), 1)
        same_pt = lat is not None and lon is not None and abs(lat - pt[0]) < 1e-5 and abs(lon - pt[1]) < 1e-5
        if abs(dist - d) <= EPS and same_pt:
            counts['unchanged'] += 1
            continue
        changes.append((rowid, eid, did, dist, d, pt[0], pt[1]))
    counts['changed'] = len(changes)
    # rows that were inside the rule's radius and are now outside it: the rule would no longer list them, and this
    # script does not remove rows (they are counted so that they can be looked at)
    counts['now_beyond_radius'] = sum(1 for c in changes if c[3] is not None and c[3] <= RADIUS_KM < c[4])
    return changes, counts


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('input')
    ap.add_argument('output')
    ap.add_argument('--metadata', required=True)
    ap.add_argument('--crosswalk', default=os.path.join(HOME, 'tesserae-docs', 'stage2', 'crosswalk', 'trismegistos_to_pleiades.tsv'))
    ap.add_argument('--pleiades-points', default=os.path.join(HOME, 'tesserae-backups', 'events_proto', 'pleiades_points.tsv'))
    ap.add_argument('--apply', action='store_true')
    a = ap.parse_args(argv)
    if os.path.abspath(a.input) == os.path.abspath(a.output) or os.path.realpath(a.output).startswith('/var/www'):
        sys.exit('OUTPUT must differ from INPUT and may not be under /var/www')
    points = {k: (v[0], v[1]) for k, v in load_points(a.pleiades_points).items()}
    cw = load_crosswalk(a.crosswalk)
    ec = sqlite3.connect('file:%s?mode=ro' % a.input, uri=True)
    mc = sqlite3.connect('file:%s?mode=ro' % a.metadata, uri=True)
    changes, counts = compute_changes(ec, mc, points, cw)
    ec.close()
    mc.close()
    print(counts)
    print('twenty largest changes (event, document, old km, new km):')
    for c in sorted(changes, key=lambda c: -abs((c[3] or 0) - c[4]))[:20]:
        print('  %s %s %s -> %s' % (c[1], c[2], c[3], c[4]))
    if a.apply:
        shutil.copyfile(a.input, a.output)
        oc = sqlite3.connect(a.output)
        oc.executemany('UPDATE documents SET distance_km = ?, lat = ?, lon = ? WHERE rowid = ?',
                       [(c[4], c[5], c[6], c[0]) for c in changes])
        oc.commit()
        n = oc.execute('SELECT COUNT(*) FROM documents').fetchone()[0]
        ok = oc.execute('PRAGMA integrity_check').fetchone()[0]
        oc.execute('VACUUM')
        oc.close()
        print('written %s: %d rows, integrity_check %s' % (a.output, n, ok))
    return 0


if __name__ == '__main__':
    sys.exit(main())
