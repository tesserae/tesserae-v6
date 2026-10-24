#!/usr/bin/env python3
"""Remove the document rows that the distance refresh moved from inside the rule's radius to outside it and that do not name the event.

  drop_stale_rule_rows.py INPUT.sqlite OUTPUT.sqlite --live LIVE.sqlite [--entities PATH] [--radius-km 100] [--apply]

INPUT is the events store after refresh_document_distances.py, LIVE the store it was refreshed from. A row is
a candidate when LIVE gives it a distance_km of at most the radius and INPUT gives it one over the radius (joined
on event_id and doc_id). A distance alone never marks a row for removal: the store holds thousands of naming
rows past 100 km that carry a distance. A candidate row that names the event is kept. It names the event when its
document is linked in the People & Places document_mentions table to one of the event's participant entities
(resolved by name, as add_naming_documents.py does) or to the event's place entity (by the event's Pleiades id
first, the label as the fallback, as add_naming_documents.py does since #1170). Every other candidate row is
a stale rule row, listed in the dry run and removed with --apply. No other row is touched.

Dry run unless --apply: prints the counts and the ten events that lose most. INPUT is never modified and OUTPUT
may not be under /var/www.
"""
import argparse
import collections
import os
import shutil
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from add_naming_documents import DEFAULT_ENTITIES, event_eids, make_resolver  # noqa: E402


def plan_removals(events_conn, live_conn, entities_conn, resolve, radius=100.0):
    """Return (remove, kept_naming, candidates): lists of (event_id, doc_id)."""
    live = {(e, d): dist for e, d, dist in live_conn.execute('SELECT event_id, doc_id, distance_km FROM documents')}
    cands = [(e, d) for e, d, dist in events_conn.execute('SELECT event_id, doc_id, distance_km FROM documents')
             if dist is not None and dist > radius and live.get((e, d)) is not None and live[(e, d)] <= radius]
    by_event = collections.defaultdict(list)
    for e, d in cands:
        by_event[e].append(d)
    events_conn.row_factory = sqlite3.Row
    remove, kept = [], []
    for eid, docs in by_event.items():
        ev = events_conn.execute('SELECT * FROM events WHERE id = ?', (eid,)).fetchone()
        named = set()
        for ent in (event_eids(ev, resolve) if ev is not None else []):
            named.update(r[0] for r in entities_conn.execute(
                'SELECT DISTINCT doc_id FROM document_mentions WHERE eid = ?', (ent,)))
        for d in docs:
            (kept if d in named else remove).append((eid, d))
    events_conn.row_factory = None
    return remove, kept, cands


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('input')
    ap.add_argument('output')
    ap.add_argument('--live', required=True)
    ap.add_argument('--entities', default=DEFAULT_ENTITIES)
    ap.add_argument('--radius-km', type=float, default=100.0)
    ap.add_argument('--apply', action='store_true')
    a = ap.parse_args(argv)
    if os.path.abspath(a.input) == os.path.abspath(a.output) or os.path.realpath(a.output).startswith('/var/www'):
        sys.exit('OUTPUT must differ from INPUT and may not be under /var/www')
    ec = sqlite3.connect('file:%s?mode=ro' % a.input, uri=True)
    lc = sqlite3.connect('file:%s?mode=ro' % a.live, uri=True)
    ent = sqlite3.connect('file:%s?mode=ro' % a.entities, uri=True)
    remove, kept, cands = plan_removals(ec, lc, ent, make_resolver(a.entities), a.radius_km)
    label = dict(ec.execute('SELECT id, label FROM events'))
    rows = ec.execute('SELECT COUNT(*) FROM documents').fetchone()[0]
    print('candidates (inside the radius in LIVE, outside in INPUT): %d' % len(cands))
    print('kept as naming rows: %d' % len(kept))
    print('to remove: %d (documents rows %d -> %d)' % (len(remove), rows, rows - len(remove)))
    print('the ten events that lose most:')
    for eid, n in collections.Counter(e for e, _ in remove).most_common(10):
        print('  %s %s: -%d' % (eid, label.get(eid), n))
    ec.close()
    if a.apply:
        shutil.copyfile(a.input, a.output)
        oc = sqlite3.connect(a.output)
        oc.executemany('DELETE FROM documents WHERE event_id = ? AND doc_id = ?', remove)
        oc.commit()
        after = oc.execute('SELECT COUNT(*) FROM documents').fetchone()[0]
        ok = oc.execute('PRAGMA integrity_check').fetchone()[0]
        oc.execute('VACUUM')
        oc.close()
        print('written %s: %d rows, integrity_check %s' % (a.output, after, ok))
    return 0


if __name__ == '__main__':
    sys.exit(main())
