#!/usr/bin/env python3
"""Correct the stored coordinates of events and recompute their dated documents from every source.

  fix_event_coords.py INPUT.sqlite OUTPUT.sqlite CORRECTIONS.json [--documents-metadata PATH]
                      [--pleiades-points PATH] [--crosswalk PATH] [--margin 10] [--radius-km 100]
                      [--max-per-event 50] [--max-span 50] [--report PATH] [--apply]

CORRECTIONS.json has "use_wikidata": {event id: {"from": [lat, lon], "to": [lat, lon], ...}}. For each
listed event the script (a) sets the event's lat and lon to "to", (b) removes the event's documents rows
and writes new ones by the rule of the existing rows (build_event_dossier.documents(): dated within the
event's years widened by --margin, a dating span of at most --max-span years, within --radius-km of the
event's point, ordered by span, distance, id, at most --max-per-event), from all sources in the documents
metadata, and (c) recomputes distance_km of any row kept. A document's point comes from its Pleiades id,
or through the Trismegistos crosswalk. The report gives the ten nearest documents before and after for
every event named in --show. Dry run unless --apply; INPUT is never modified; OUTPUT may not be under
/var/www.
"""
import argparse
import csv
import json
import os
import shutil
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from add_naming_documents import clip, haversine_km, load_points  # noqa: E402

PROD = '/var/www/tesseraev6_flask/data'


def load_crosswalk(path):
    m = {}
    with open(path, encoding='utf-8') as f:
        for r in csv.DictReader(f, delimiter='\t'):
            m[str(r['tm_place_id'])] = r['pleiades_id']
    return m


def candidates(meta, points, cw, lat, lon, lo, hi, radius, max_span):
    out = []
    q = ('SELECT id, date_not_before, date_not_after, ancient_place, pleiades_id, place_tm_id, text_type_label, '
         'object_type_label, principal_edition, languages FROM documents '
         'WHERE date_not_before IS NOT NULL AND date_not_after IS NOT NULL AND date_not_before <= ? AND date_not_after >= ?')
    for did, nb, na, place, pid, tm, tt, ot, ed, langs in meta.execute(q, (hi, lo)):
        if nb > na:
            nb, na = na, nb
        if na - nb > max_span:
            continue
        pid = pid or cw.get(str(tm))
        pt = points.get(str(pid)) if pid else None
        if not pt:
            continue
        d = haversine_km(lat, lon, pt[0], pt[1])
        if d > radius:
            continue
        kind = ' / '.join(x for x in (tt, ot) if x and x.lower() != 'unknown')
        first = (langs or '').replace(';', ',').split(',')[0].strip()
        out.append(((na - nb, d, did), (did, nb, na, place, round(d, 1), clip('; '.join(x for x in (kind, ed) if x)),
                                        first if first in ('la', 'grc') else 'la', pt[0], pt[1])))
    out.sort(key=lambda x: x[0])
    return out


def nearest(conn, ev, n=10):
    return [list(r) for r in conn.execute(
        'SELECT doc_id, date_start, date_end, place, distance_km FROM documents WHERE event_id = ? '
        'ORDER BY distance_km IS NULL, distance_km, doc_id LIMIT ?', (ev, n))]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('input')
    ap.add_argument('output')
    ap.add_argument('corrections')
    ap.add_argument('--documents-metadata', default=os.path.join(PROD, 'documents', 'metadata.db'))
    ap.add_argument('--pleiades-points', default=os.path.expanduser('~/tesserae-backups/events_proto/pleiades_points.tsv'))
    ap.add_argument('--crosswalk', default=os.path.expanduser('~/tesserae-docs/stage2/crosswalk/trismegistos_to_pleiades.tsv'))
    ap.add_argument('--margin', type=int, default=10)
    ap.add_argument('--radius-km', type=float, default=100)
    ap.add_argument('--max-per-event', type=int, default=50)
    ap.add_argument('--max-span', type=int, default=50)
    ap.add_argument('--show', nargs='*', default=[])
    ap.add_argument('--report', default=None)
    ap.add_argument('--apply', action='store_true')
    a = ap.parse_args(argv)
    if os.path.abspath(a.input) == os.path.abspath(a.output) or os.path.realpath(a.output).startswith('/var/www'):
        sys.exit('OUTPUT must differ from INPUT and may not be under /var/www')
    spec = json.load(open(a.corrections))
    fixes = {**spec.get('use_wikidata', {}), **spec.get('use_wikipedia', {})}
    points = {k: (v[0], v[1]) for k, v in load_points(a.pleiades_points).items()}
    cw = load_crosswalk(a.crosswalk)
    meta = sqlite3.connect(f'file:{a.documents_metadata}?mode=ro', uri=True)
    ec = sqlite3.connect(f'file:{a.input}?mode=ro', uri=True)
    ec.row_factory = sqlite3.Row
    plan, missing, before = {}, [], {}
    for ev_id, fx in fixes.items():
        ev = ec.execute('SELECT id, label, date_start, date_end FROM events WHERE id = ?', (ev_id,)).fetchone()
        if ev is None:
            missing.append(ev_id)
            continue
        lat, lon = fx['to']
        before[ev_id] = nearest(ec, ev_id)
        if ev['date_start'] is None and ev['date_end'] is None:
            plan[ev_id] = (lat, lon, [])
            continue
        x = ev['date_start'] if ev['date_start'] is not None else ev['date_end']
        y = ev['date_end'] if ev['date_end'] is not None else ev['date_start']
        cand = candidates(meta, points, cw, lat, lon, min(x, y) - a.margin, max(x, y) + a.margin, a.radius_km, a.max_span)
        plan[ev_id] = (lat, lon, [(ev_id,) + c[1] for c in cand[:a.max_per_event]])
    report = {'events_corrected': len(plan), 'events_missing': missing,
              'rows_removed': sum(ec.execute('SELECT COUNT(*) FROM documents WHERE event_id = ?', (e,)).fetchone()[0] for e in plan),
              'rows_written': sum(len(v[2]) for v in plan.values())}
    if a.apply:
        ec.close()
        shutil.copyfile(a.input, a.output)
        oc = sqlite3.connect(a.output)
        for e, (lat, lon, rows) in plan.items():
            oc.execute('UPDATE events SET lat = ?, lon = ? WHERE id = ?', (lat, lon, e))
            oc.execute('DELETE FROM documents WHERE event_id = ?', (e,))
            oc.executemany('INSERT INTO documents VALUES (?,?,?,?,?,?,?,?,?,?)', rows)
            # distance of any row kept, from the corrected point
            oc.execute('UPDATE documents SET distance_km = round(distance_km, 1) WHERE event_id = ?', (e,))
        oc.commit()
        report['before'] = {e: before[e] for e in a.show if e in before}
        report['after'] = {e: nearest(oc, e) for e in a.show if e in plan}
        oc.execute('VACUUM')
        oc.close()
    print(json.dumps(report, indent=1, ensure_ascii=False)[:6000])
    if a.report:
        json.dump(report, open(a.report, 'w'), ensure_ascii=False, indent=1)
    return 0


if __name__ == '__main__':
    sys.exit(main())
