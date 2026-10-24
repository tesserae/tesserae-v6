#!/usr/bin/env python3
"""Redo the dated, nearby documents of every event after documents gained a Pleiades place, keeping every other row.

  rerun_event_documents.py INPUT.sqlite OUTPUT.sqlite --old-metadata OLD.db --new-metadata NEW.db
                           [--pleiades-points PATH] [--crosswalk PATH] [--margin 10] [--radius-km 100]
                           [--max-per-event 50] [--max-span 50] [--report PATH] [--apply]

The installed rule (build_event_dossier.documents(), the same as `fix_event_coords.py`): documents dated within
the event's years widened by --margin, with a dating span of at most --max-span years, within --radius-km of the
event's point, ordered by span, distance, id, at most --max-per-event. `fix_event_coords.py` rewrites an event's
whole document list, which would also drop the rows that other steps added (documents naming the event's
participants or place, the Aegean inscriptions, a hand-added row), so this script instead computes the rule's
list twice for each event, once on the old metadata and once on the new, and then

  - removes only the rows that were in the old list and are no longer in the new one (pushed out by closer or
    more tightly dated documents that gained a place), and
  - adds the rows that are in the new list and not already in the event's rows.

Every other row is left alone. Events without a date or a point are left alone. Dry run unless --apply; INPUT is
never modified; OUTPUT may not be under /var/www. The report lists, per event, rows before and after, and the ten
events that gain most.
"""
import argparse
import json
import os
import shutil
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from add_naming_documents import load_points  # noqa: E402
from fix_event_coords import candidates, load_crosswalk  # noqa: E402

HOME = os.path.expanduser('~')


def rule_list(meta, points, cw, ev, margin, radius, max_span, cap):
    x = ev['date_start'] if ev['date_start'] is not None else ev['date_end']
    y = ev['date_end'] if ev['date_end'] is not None else ev['date_start']
    if x is None or ev['lat'] is None or ev['lon'] is None:
        return []
    c = candidates(meta, points, cw, ev['lat'], ev['lon'], min(x, y) - margin, max(x, y) + margin, radius, max_span)
    return [r[1] for r in c[:cap]]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('input')
    ap.add_argument('output')
    ap.add_argument('--old-metadata', required=True)
    ap.add_argument('--new-metadata', required=True)
    ap.add_argument('--pleiades-points', default=os.path.join(HOME, 'tesserae-backups', 'events_proto', 'pleiades_points.tsv'))
    ap.add_argument('--crosswalk', default=os.path.join(HOME, 'tesserae-docs', 'stage2', 'crosswalk', 'trismegistos_to_pleiades.tsv'))
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
    cw = load_crosswalk(a.crosswalk)
    old = sqlite3.connect('file:%s?mode=ro' % a.old_metadata, uri=True)
    new = sqlite3.connect('file:%s?mode=ro' % a.new_metadata, uri=True)
    ec = sqlite3.connect('file:%s?mode=ro' % a.input, uri=True)
    ec.row_factory = sqlite3.Row
    events = ec.execute('SELECT id, label, date_start, date_end, lat, lon FROM events ORDER BY id').fetchall()
    existing = {}
    for r in ec.execute('SELECT event_id, doc_id FROM documents'):
        existing.setdefault(r[0], set()).add(r[1])

    add, remove, per_event = [], [], {}
    same_as_installed = 0  # events whose old rule list is wholly present in the installed rows
    checked = 0
    for ev in events:
        o = rule_list(old, points, cw, ev, a.margin, a.radius_km, a.max_span, a.max_per_event)
        n = rule_list(new, points, cw, ev, a.margin, a.radius_km, a.max_span, a.max_per_event)
        have = existing.get(ev['id'], set())
        if o:
            checked += 1
            if all(r[0] in have for r in o):
                same_as_installed += 1
        o_ids, n_ids = {r[0] for r in o}, {r[0] for r in n}
        gone = [d for d in o_ids - n_ids if d in have]
        come = [r for r in n if r[0] not in have]
        for d in gone:
            remove.append((ev['id'], d))
        for r in come:
            add.append((ev['id'],) + tuple(r))
        before = len(have)
        per_event[ev['id']] = {'label': ev['label'], 'before': before, 'after': before - len(gone) + len(come),
                               'added': len(come), 'removed': len(gone)}
    gained = sorted(((v['added'] - v['removed'], k) for k, v in per_event.items() if v['added'] or v['removed']), reverse=True)
    report = {'events': len(events), 'events_with_rule_list': checked,
              'events_whose_installed_rows_hold_the_old_rule_list': same_as_installed,
              'rows_added': len(add), 'rows_removed': len(remove),
              'events_changed': len(gained),
              'top_ten': [dict(event=k, **per_event[k]) for _, k in gained[:10]],
              'per_event': per_event}
    if a.apply:
        ec.close()
        shutil.copyfile(a.input, a.output)
        oc = sqlite3.connect(a.output)
        before = oc.execute('SELECT COUNT(*) FROM documents').fetchone()[0]
        oc.executemany('DELETE FROM documents WHERE event_id = ? AND doc_id = ?', remove)
        oc.executemany('INSERT INTO documents VALUES (?,?,?,?,?,?,?,?,?,?)', add)
        oc.commit()
        after = oc.execute('SELECT COUNT(*) FROM documents').fetchone()[0]
        report['document_rows_before'], report['document_rows_after'] = before, after
        oc.execute('VACUUM')
        oc.close()
    print(json.dumps({k: v for k, v in report.items() if k != 'per_event'}, indent=1, ensure_ascii=False))
    if a.report:
        with open(a.report, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=1)
    return 0


if __name__ == '__main__':
    sys.exit(main())
