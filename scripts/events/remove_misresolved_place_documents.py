#!/usr/bin/env python3
"""Remove the documents an event gained through a wrongly resolved place, and add the right place's.

  remove_misresolved_place_documents.py INPUT.sqlite OUTPUT.sqlite --entities PATH --metadata PATH
        [--pleiades-points PATH] [--crosswalk PATH] [--undated {keep,last,drop}] [--max-per-event 50]
        [--max-removals 2000] [--remove-only] [--report PATH] [--apply]

The naming step (add_naming_documents.py) resolved an event's place by its label, so the battle of 435 BCE
labeled "Akri" (Pleiades 530771, Actium) took the documents of Akriai in Laconia, two of them Agrigentum
stones 654 km away (2026-10-24). The step now resolves the place by the event's Pleiades id first. This
script repairs a store built the old way. For every event whose place resolved one way by label (the old way)
and resolves another way now (a different entity, or none because the new rule refuses the label's hit):

  1. remove the event's documents rows whose doc_id the Mentions store links to the OLD place entity, unless
     the document (a) is in the event's distance-rule list (rerun_event_documents.rule_list with the installed
     parameters, margin 10, span at most 50, radius 100 km, cap 50, against --metadata), or (b) is linked to the
     NEW place entity or to any of the event's participant entities;
  2. run the naming step (with the same flags as the 2026-10-19 install, --undated drop by default) on those
     events only and for the place alone, so the right place's documents are added. The participants' documents
     are not touched: their resolution did not change, and an event whose rows were curated by hand (the 31 BCE
     battle of Actium) would otherwise gain fifty dedications to Augustus.

--remove-only skips step 2 (the added rows draw on the Mentions store's links, which carry homonyms and
short adjective stems, see the 2026-10-24 report).

Dry run by default: prints the plan, changes nothing. --apply copies INPUT to OUTPUT and changes OUTPUT only.
Both paths must lie outside /var/www. The run stops before applying when more than --max-removals rows
would go. Every other table is left alone.
"""
import argparse
import json
import os
import shutil
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from add_naming_documents import (DEFAULT_POINTS, event_participants, load_points, make_resolver,  # noqa: E402
                                  plan_rows)
from fix_event_coords import load_crosswalk  # noqa: E402
from rerun_event_documents import rule_list  # noqa: E402

HOME = os.path.expanduser('~')
DEFAULT_CROSSWALK = os.path.join(HOME, 'tesserae-docs', 'stage2', 'crosswalk', 'trismegistos_to_pleiades.tsv')


def linked_docs(ent, eid, cache):
    if eid is None:
        return set()
    if eid not in cache:
        cache[eid] = {r[0] for r in ent.execute('SELECT DISTINCT doc_id FROM document_mentions WHERE eid = ?', (eid,))}
    return cache[eid]


def changed_events(events, resolve, log=None):
    """[(event row, old eid, new eid or None, how)] for the events whose place resolves differently now than
    by label. old is None (nothing wrongly linked, nothing to remove) for an event that resolved no place by label."""
    out = []
    for ev in events:
        if not ev['place']:
            continue
        old = resolve(ev['place'])
        new, how = resolve.place(ev['place'], ev['pleiades_id'], log)
        if new != old:
            out.append((ev, old, new, how))
    return out


def plan_removals(events_conn, ent, meta, resolve, points, cw, changed, margin=10, radius=100, max_span=50, cap=50):
    """{event id: [doc ids to remove]} by the rule in the module docstring."""
    have = {}
    for ev_id, d in events_conn.execute('SELECT event_id, doc_id FROM documents'):
        have.setdefault(ev_id, set()).add(d)
    cache, out = {}, {}
    for ev, old, new, how in changed:
        if old is None:
            continue
        keep = set(rule_list(meta, points, cw, ev, margin, radius, max_span, cap))
        keep |= linked_docs(ent, new, cache)
        for n in event_participants(ev):
            keep |= linked_docs(ent, resolve(n), cache)
        gone = sorted(d for d in have.get(ev['id'], set()) & linked_docs(ent, old, cache) if d not in keep)
        if gone:
            out[ev['id']] = gone
    return out


def run(input_path, output_path, entities_path, metadata_path, points_path, crosswalk_path, undated='drop',
        max_per_event=50, max_removals=2000, apply=False, resolve=None, log=print, remove_only=False):
    for p in (input_path, output_path):
        if os.path.realpath(p).startswith('/var/www'):
            raise SystemExit(f'refusing a path under /var/www: {p}')
    if os.path.abspath(input_path) == os.path.abspath(output_path):
        raise SystemExit('INPUT and OUTPUT must differ')
    resolve = resolve or make_resolver(entities_path)
    ent = sqlite3.connect(f'file:{entities_path}?mode=ro', uri=True)
    meta = sqlite3.connect(f'file:{metadata_path}?mode=ro', uri=True)
    points = {k: (v[0], v[1]) for k, v in load_points(points_path).items()}
    cw = load_crosswalk(crosswalk_path) if crosswalk_path and os.path.exists(crosswalk_path) else {}
    src = sqlite3.connect(f'file:{input_path}?mode=ro', uri=True)
    src.row_factory = sqlite3.Row
    events = src.execute('SELECT * FROM events ORDER BY id').fetchall()
    changed = changed_events(events, resolve, log)
    removals = plan_removals(src, ent, meta, resolve, points, cw, changed)
    total_removed = sum(len(v) for v in removals.values())
    log(f'events whose place resolves differently: {len(changed)}; events losing rows: {len(removals)}; rows to remove: {total_removed}')
    if total_removed > max_removals:
        raise SystemExit(f'STOP: {total_removed} rows to remove exceeds {max_removals}; nothing written')

    # Work on a copy (a memory copy for a dry run) so the naming step sees the rows as they will stand.
    if apply:
        src.close()
        shutil.copyfile(input_path, output_path)
        work = sqlite3.connect(output_path)
    else:
        work = sqlite3.connect(':memory:')
        src.backup(work)
        src.close()
    work.row_factory = sqlite3.Row
    before = {r[0]: r[1] for r in work.execute('SELECT event_id, COUNT(*) FROM documents GROUP BY event_id')}
    total_before = sum(before.values())
    for ev_id, docs in removals.items():
        work.executemany('DELETE FROM documents WHERE event_id = ? AND doc_id = ?', [(ev_id, d) for d in docs])
    only = {c[0]['id'] for c in changed}
    plan = {} if remove_only else plan_rows(work, ent, meta, resolve, points, max_per_event, undated, None, only, log,
                                            place_only=True)
    for rows in plan.values():
        work.executemany('INSERT INTO documents VALUES (?,?,?,?,?,?,?,?,?,?)', rows)
    after = {r[0]: r[1] for r in work.execute('SELECT event_id, COUNT(*) FROM documents GROUP BY event_id')}
    total_after = sum(after.values())
    per_event = {}
    for ev, old, new, how in changed:
        i = ev['id']
        per_event[i] = {'label': ev['label'], 'place': ev['place'], 'pleiades_id': ev['pleiades_id'],
                        'old_eid': old, 'new_eid': new, 'how': how,
                        'before': before.get(i, 0), 'after': after.get(i, 0),
                        'removed': len(removals.get(i, [])), 'added': len(plan.get(i, [])),
                        'removed_ids': removals.get(i, []), 'added_ids': [r[1] for r in plan.get(i, [])]}
    if apply:
        work.commit()
        work.execute('VACUUM')
    work.close()
    total_added = sum(len(v) for v in plan.values())
    log(f'rows removed {total_removed}, rows added {total_added}, documents rows {total_before} -> {total_after}')
    log('the ten events that change most:')
    for i, v in sorted(per_event.items(), key=lambda kv: (-(kv[1]['removed'] + kv[1]['added']), kv[0]))[:10]:
        log(f"  {i} {v['label']} [{v['place']}]: -{v['removed']} +{v['added']} ({v['before']} -> {v['after']})")
    return {'changed': len(changed), 'events_losing_rows': len(removals), 'rows_removed': total_removed,
            'rows_added': total_added, 'rows_before': total_before, 'rows_after': total_after, 'per_event': per_event}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('input')
    ap.add_argument('output')
    ap.add_argument('--entities', required=True)
    ap.add_argument('--metadata', required=True)
    ap.add_argument('--pleiades-points', default=DEFAULT_POINTS)
    ap.add_argument('--crosswalk', default=DEFAULT_CROSSWALK)
    ap.add_argument('--undated', choices=('keep', 'last', 'drop'), default='drop')
    ap.add_argument('--max-per-event', type=int, default=50)
    ap.add_argument('--max-removals', type=int, default=2000)
    ap.add_argument('--remove-only', action='store_true')
    ap.add_argument('--report', default=None)
    ap.add_argument('--apply', action='store_true')
    a = ap.parse_args(argv)
    for p in (a.input, a.entities, a.metadata):
        if not os.path.exists(p):
            sys.exit(f'not found: {p}')
    rep = run(a.input, a.output, a.entities, a.metadata, a.pleiades_points, a.crosswalk, a.undated,
              a.max_per_event, a.max_removals, a.apply, remove_only=a.remove_only)
    if a.report:
        with open(a.report, 'w', encoding='utf-8') as f:
            json.dump(rep, f, ensure_ascii=False, indent=1)
    return 0


if __name__ == '__main__':
    sys.exit(main())
