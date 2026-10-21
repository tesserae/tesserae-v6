#!/usr/bin/env python3
"""Add the Attic Inscriptions Online stones to the dated documents of each event.

  add_aio_documents.py INPUT.sqlite OUTPUT.sqlite [--documents-metadata PATH] [--pleiades-points PATH]
                       [--margin 10] [--radius-km 100] [--max-per-event 50] [--max-span 50]
                       [--report PATH] [--apply]

The events store keeps, for each event, the documents dated within the event's years (widened by
ten years on each side) and found within 100 km of its place, narrowest dating first, then nearest,
at most fifty (the rule of origin/feat/event-anchor, scripts/events/build_event_dossier.py,
documents(), as build_all_dossiers.py calls it), and the Events page shows only those dated within
fifty years (backend/blueprints/events.py MAX_DOCUMENT_SPAN, rank_documents). The AIO stones are in
none of these rows. This script applies the same rule to them: dated both ways, a dating span of at
most --max-span years, overlapping the event's years, within --radius-km of the event's place,
ordered by (span, distance, id).

The fifty is kept with the rows the store already holds: the AIO stones and the rows the store has
with a dating span of at most --max-span are ordered together, and an AIO stone is added only when
it ranks among the best --max-per-event. No existing row is changed or removed (rows past the
fifty stay in the store), so the added rows are the only difference. Run
scripts/events/add_naming_documents.py on the output afterwards for the stones that name an
event's participants or place.

Findspots. A stone's findspot is its Pleiades place (the metadata's pleiades_id, taken from the AIO
page) and the coordinates come from the Pleiades points table. A stone without a Pleiades place is
placed from the findspot text by FINDSPOT_WORDS (a deme or a quarter of Athens by name), then at
Athens when its region is Attica (the collection is Attic) and the text names no other place, and has no
coordinates (and so no row) otherwise. The report counts each of the four.

Dry run by default. --apply copies INPUT to OUTPUT and inserts the rows there. INPUT is never
modified, and OUTPUT may not be under /var/www.
"""
import argparse
import collections
import json
import os
import shutil
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from add_naming_documents import clip, haversine_km, load_points  # noqa: E402

PROD = '/var/www/tesseraev6_flask/data'
DEFAULT_METADATA = os.path.join(PROD, 'documents', 'metadata.db')
DEFAULT_POINTS = os.path.expanduser('~/tesserae-backups/events_proto/pleiades_points.tsv')
ATHENS = '579885'
# Findspot text (lower case, a word or phrase in it) -> Pleiades id. Only places of the Attic collection that
# the AIO pages leave without a Pleiades id. 'Athens' and the quarters and monuments of the city itself.
FINDSPOT_WORDS = (
    ('acharnai', '579842'),
    ('eleusis', '579920'), ('rhamnous', '580097'), ('piraeus', '580062'), ('peiraieus', '580062'),
    ('marathon', '580021'), ('sounion', '580107'), ('oropos', '580044'), ('thorikos', '772835485'),
    ('brauron', '579879'), ('kephisia', '579972'), ('ikarion', '579958'),
    ('athens', ATHENS), ('pnyx', ATHENS), ('acropolis', ATHENS), ('agora', ATHENS), ('odeon', ATHENS),
    ('street', ATHENS), ('kerameikos', ATHENS), ('theatre of dionys', ATHENS), ('areopagos', ATHENS),
)
OUTSIDE = ('tunisia', 'delos', 'delphi', 'thebes', 'aigina', 'aegina', 'samos', 'rome', 'egypt')


def locate(pid, place, points):
    """(point or None, how) for a stone: how is 'pleiades', 'text', 'athens' or 'none'."""
    if pid and str(pid) in points:
        return points[str(pid)], 'pleiades'
    text = (place or '').lower()
    if not pid or str(pid) not in points:
        for word, pl in FINDSPOT_WORDS:
            if word in text and pl in points:
                return points[pl], 'text'
        if any(w in text for w in OUTSIDE):
            return None, 'none'
        if ATHENS in points:
            return points[ATHENS], 'athens'
    return None, 'none'


def load_aio(meta_conn, points):
    docs = []
    how = collections.Counter()
    for (did, nb, na, place, pid, tt, ot, ed, langs) in meta_conn.execute(
            "SELECT id, date_not_before, date_not_after, ancient_place, pleiades_id, text_type_label, "
            "object_type_label, principal_edition, languages FROM documents WHERE source = 'aio'"):
        pt, h = locate(pid, place, points)
        how[h] += 1
        if nb is None or na is None or pt is None:
            continue
        if nb > na:
            nb, na = na, nb
        kind = ' / '.join(x for x in (tt, ot) if x and x.lower() != 'unknown')
        snippet = '; '.join(x for x in (kind, ed) if x)
        docs.append({'id': did, 'ds': nb, 'de': na, 'place': place, 'lat': pt[0], 'lon': pt[1], 'snippet': clip(snippet)})
    return docs, how


def plan_rows(events_conn, aio, margin=10, radius_km=100, max_per_event=50, max_span=50):
    events_conn.row_factory = sqlite3.Row
    out = {}
    displaced = collections.Counter()
    for ev in events_conn.execute('SELECT id, label, date_start, date_end, lat, lon FROM events').fetchall():
        if ev['lat'] is None or ev['lon'] is None or (ev['date_start'] is None and ev['date_end'] is None):
            continue
        a = ev['date_start'] if ev['date_start'] is not None else ev['date_end']
        b = ev['date_end'] if ev['date_end'] is not None else ev['date_start']
        lo, hi = min(a, b) - margin, max(a, b) + margin
        have = {}
        for r in events_conn.execute('SELECT doc_id, date_start, date_end, distance_km FROM documents WHERE event_id = ?', (ev['id'],)):
            have[r[0]] = r
        new = []
        for d in aio:
            if d['id'] in have or d['de'] - d['ds'] > max_span or d['ds'] > hi or d['de'] < lo:
                continue
            dist = haversine_km(ev['lat'], ev['lon'], d['lat'], d['lon'])
            if dist > radius_km:
                continue
            new.append(((d['de'] - d['ds'], dist, d['id']), d, round(dist, 1)))
        if not new:
            continue
        # the rows already held that the page can show (dated within max_span), in the builder's order
        old = []
        for did, ds, de, dist in have.values():
            if ds is not None and de is not None and 0 <= de - ds <= max_span:
                old.append(((de - ds, dist if dist is not None else 1e12, did), None, None))
        ranked = sorted(old + new, key=lambda x: x[0])[:max_per_event]
        added = [(k, d, dist) for k, d, dist in ranked if d is not None]
        if added:
            out[ev['id']] = [(ev['id'], d['id'], d['ds'], d['de'], d['place'], dist, d['snippet'], 'grc', d['lat'], d['lon'])
                             for _k, d, dist in added]
            displaced[ev['id']] = max(0, len(old) + len(added) - max_per_event) if len(old) + len(added) > max_per_event else 0
    return out, displaced


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('input')
    ap.add_argument('output')
    ap.add_argument('--documents-metadata', default=DEFAULT_METADATA)
    ap.add_argument('--pleiades-points', default=DEFAULT_POINTS)
    ap.add_argument('--margin', type=int, default=10)
    ap.add_argument('--radius-km', type=float, default=100)
    ap.add_argument('--max-per-event', type=int, default=50)
    ap.add_argument('--max-span', type=int, default=50)
    ap.add_argument('--report', default=None)
    ap.add_argument('--apply', action='store_true')
    a = ap.parse_args(argv)
    if os.path.abspath(a.input) == os.path.abspath(a.output) or os.path.realpath(a.output).startswith('/var/www'):
        sys.exit('OUTPUT must differ from INPUT and may not be under /var/www')
    points = {k: (v[0], v[1]) for k, v in load_points(a.pleiades_points).items()}
    meta = sqlite3.connect(f'file:{a.documents_metadata}?mode=ro', uri=True)
    aio, how = load_aio(meta, points)
    ec = sqlite3.connect(f'file:{a.input}?mode=ro', uri=True)
    plan, displaced = plan_rows(ec, aio, a.margin, a.radius_km, a.max_per_event, a.max_span)
    label = dict(ec.execute('SELECT id, label FROM events'))
    total = sum(len(v) for v in plan.values())
    before = ec.execute('SELECT COUNT(*) FROM documents').fetchone()[0]
    top = sorted(plan.items(), key=lambda kv: (-len(kv[1]), kv[0]))[:20]
    report = {'aio_documents_dated_and_placed': len(aio), 'findspot': dict(how), 'events_touched': len(plan),
              'rows_to_add': total, 'documents_rows_before': before, 'documents_rows_after': before + total,
              'existing_rows_past_the_cap_after': sum(displaced.values()),
              'top_events': [[e, label[e], len(r)] for e, r in top]}
    print(json.dumps(report, indent=1, ensure_ascii=False))
    if a.apply:
        ec.close()
        shutil.copyfile(a.input, a.output)
        oc = sqlite3.connect(a.output)
        for rows in plan.values():
            oc.executemany('INSERT INTO documents VALUES (?,?,?,?,?,?,?,?,?,?)', rows)
        oc.commit()
        report['documents_rows_after_written'] = oc.execute('SELECT COUNT(*) FROM documents').fetchone()[0]
        oc.execute('VACUUM')
        oc.close()
    if a.report:
        with open(a.report, 'w', encoding='utf-8') as f:
            json.dump(report | {'plan': {e: [[r[1], r[2], r[3], r[5]] for r in rows] for e, rows in plan.items()}}, f,
                      ensure_ascii=False, indent=1)
    return 0


if __name__ == '__main__':
    sys.exit(main())
