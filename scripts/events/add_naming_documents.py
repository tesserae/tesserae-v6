#!/usr/bin/env python3
"""Add to each event the inscriptions and papyri that name its participants or its place.

  add_naming_documents.py INPUT.sqlite OUTPUT.sqlite [--entities PATH] [--documents-metadata PATH]
                          [--pleiades-points PATH] [--max-per-event N] [--undated {keep,last,drop}] [--apply]

The events store keeps for each event the fifty documents nearest its place among those
dated within its years. For a region such as Sicily none of the fifty names a participant
or the place. This script resolves each event's participants and place to Mentions-store
entities (backend.entity_extras.resolve_name_to_eid, the resolver the Events page uses), takes every document the store's
document_mentions table links to them, drops those already in the event's documents rows,
keeps those whose dating overlaps the event's years widened by 50 on each side (or that
have no dating at all), and inserts at most N per event, nearest first.

--undated keep (the default, as specified) treats a document with no dating like any other and
orders by distance. last puts the undated ones after the dated ones before the cap is applied.
drop leaves them out. On the 2026-10-18 copy 79 percent of the added rows are undated.

Dry run by default: prints a plan and writes nothing. --apply copies INPUT to OUTPUT and
inserts the rows there. INPUT is never modified.

The new rows carry the loader's columns. Place is the metadata's ancient_place, language is
the language the Mentions store gives the document, and the snippet is built the way the
dossier builder built it (text type / object type; principal edition). Findspot coordinates
come from the document's Pleiades id through a table of Pleiades points (pleiades_id, lat,
lon, title); a document with no point has no coordinates and no distance.
"""
import argparse
import math
import os
import shutil
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

PROD = '/var/www/tesseraev6_flask/data'
DEFAULT_ENTITIES = os.path.join(PROD, 'entity_index', 'entities.sqlite')
DEFAULT_METADATA = os.path.join(PROD, 'documents', 'metadata.db')
DEFAULT_POINTS = os.path.expanduser('~/tesserae-backups/events_proto/pleiades_points.tsv')
WIDEN = 50
SNIPPET = 300


def haversine_km(lat1, lon1, lat2, lon2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = (math.sin((p2 - p1) / 2) ** 2
         + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2)
    return 6371.0088 * 2 * math.asin(math.sqrt(a))


def clip(text, n=SNIPPET):
    text = ' '.join((text or '').split())
    return text if len(text) <= n else text[:n - 1].rstrip() + '…'


def overlaps(nb, na, lo, hi):
    """True when the document's dating [nb, na] meets [lo, hi]. No dating at all keeps the
    document. One bound alone is a single year."""
    if nb is None and na is None:
        return True
    if nb is None:
        nb = na
    if na is None:
        na = nb
    if nb > na:
        nb, na = na, nb
    return nb <= hi and na >= lo


def load_points(path):
    pts = {}
    if path and os.path.exists(path):
        with open(path, encoding='utf-8') as f:
            next(f, None)
            for line in f:
                parts = line.rstrip('\n').split('\t')
                if len(parts) >= 3:
                    try:
                        pts[parts[0]] = (float(parts[1]), float(parts[2]))
                    except ValueError:
                        pass
    return pts


def make_resolver(entities_path):
    """name -> entity id through backend.entity_extras.resolve_name_to_eid, the plain function
    the Events route shares with the Mentions search, so the two never resolve a name differently."""
    from backend import entity_extras
    cache = {}

    def resolve(name):
        if name not in cache:
            cache[name] = entity_extras.resolve_name_to_eid(entities_path, name)
        return cache[name]
    return resolve


def event_names(ev):
    import json
    try:
        parts = json.loads(ev['participants'] or '[]')
    except ValueError:
        parts = []
    names = [p for p in parts if p]
    if ev['place']:
        names.append(ev['place'])
    return names


def plan_rows(events_conn, entities_conn, meta_conn, resolve, points, max_per_event=50, undated='keep'):
    """{event_id: [row tuples in documents-table order]} for every event gaining rows."""
    out = {}
    events_conn.row_factory = sqlite3.Row
    have = {}
    for r in events_conn.execute('SELECT event_id, doc_id FROM documents'):
        have.setdefault(r[0], set()).add(r[1])
    mention_cache = {}
    for ev in events_conn.execute('SELECT * FROM events').fetchall():
        eids = sorted({x for x in (resolve(n) for n in event_names(ev)) if x is not None})
        if not eids:
            continue
        docs = {}
        for eid in eids:
            if eid not in mention_cache:
                mention_cache[eid] = entities_conn.execute(
                    'SELECT doc_id, MIN(language) FROM document_mentions WHERE eid = ? GROUP BY doc_id',
                    (eid,)).fetchall()
            for doc_id, lang in mention_cache[eid]:
                docs.setdefault(doc_id, lang)
        skip = have.get(ev['id'], set())
        cand = [d for d in docs if d not in skip]
        if not cand:
            continue
        ds, de = ev['date_start'], ev['date_end']
        if ds is None and de is None:
            lo, hi = -10 ** 9, 10 ** 9
        else:
            a = ds if ds is not None else de
            b = de if de is not None else ds
            lo, hi = min(a, b) - WIDEN, max(a, b) + WIDEN
        meta = {}
        for i in range(0, len(cand), 400):
            chunk = cand[i:i + 400]
            for r in meta_conn.execute(
                    'SELECT id, date_not_before, date_not_after, ancient_place, pleiades_id, text_type_label, '
                    'object_type_label, principal_edition FROM documents WHERE id IN (%s)' % ','.join('?' * len(chunk)),
                    chunk):
                meta[r[0]] = r
        rows = []
        for d in cand:
            m = meta.get(d)
            if m is None:
                continue  # the id is not in the documents metadata, nothing to date or describe
            if not overlaps(m[1], m[2], lo, hi):
                continue
            if undated == 'drop' and m[1] is None and m[2] is None:
                continue
            lat = lon = dist = None
            pt = points.get(str(m[4])) if m[4] else None
            if pt:
                lat, lon = pt
                if ev['lat'] is not None and ev['lon'] is not None:
                    dist = round(haversine_km(ev['lat'], ev['lon'], lat, lon), 1)
            kind = ' / '.join(x for x in (m[5], m[6]) if x and x.lower() != 'unknown')
            snippet = '; '.join(x for x in (kind, m[7]) if x)
            rows.append((ev['id'], d, m[1], m[2], m[3], dist, clip(snippet), docs[d], lat, lon))
        rows.sort(key=lambda r: ((r[2] is None and r[3] is None) if undated == 'last' else 0,
                                 r[5] is None, r[5] if r[5] is not None else 0, r[1]))
        if rows:
            out[ev['id']] = rows[:max_per_event]
    return out


def add_naming_documents(input_path, output_path, entities_path, metadata_path, points_path,
                         max_per_event=50, apply=False, resolve=None, log=print, undated='keep'):
    ec = sqlite3.connect(f'file:{input_path}?mode=ro', uri=True)
    ent = sqlite3.connect(f'file:{entities_path}?mode=ro', uri=True)
    meta = sqlite3.connect(f'file:{metadata_path}?mode=ro', uri=True)
    resolve = resolve or make_resolver(entities_path)
    plan = plan_rows(ec, ent, meta, resolve, load_points(points_path), max_per_event, undated)
    total = sum(len(v) for v in plan.values())
    before = ec.execute('SELECT COUNT(*) FROM documents').fetchone()[0]
    log(f'events touched {len(plan)}, rows to add {total}, documents rows {before} -> {before + total}')
    label = dict(ec.execute('SELECT id, label FROM events'))
    log('the twenty events gaining most:')
    for eid, rows in sorted(plan.items(), key=lambda kv: (-len(kv[1]), kv[0]))[:20]:
        log(f'  {eid} {label[eid]}: +{len(rows)}')
    if apply:
        ec.close()
        shutil.copyfile(input_path, output_path)
        oc = sqlite3.connect(output_path)
        for rows in plan.values():
            oc.executemany('INSERT INTO documents VALUES (?,?,?,?,?,?,?,?,?,?)', rows)
        oc.commit()
        after = oc.execute('SELECT COUNT(*) FROM documents').fetchone()[0]
        oc.execute('VACUUM')
        oc.close()
        log(f'wrote {output_path}: documents rows {after}')
    return plan


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('input')
    ap.add_argument('output')
    ap.add_argument('--entities', default=DEFAULT_ENTITIES)
    ap.add_argument('--documents-metadata', default=DEFAULT_METADATA)
    ap.add_argument('--pleiades-points', default=DEFAULT_POINTS)
    ap.add_argument('--max-per-event', type=int, default=50)
    ap.add_argument('--undated', choices=('keep', 'last', 'drop'), default='keep')
    ap.add_argument('--apply', action='store_true')
    a = ap.parse_args(argv)
    if os.path.abspath(a.input) == os.path.abspath(a.output):
        sys.exit('INPUT and OUTPUT must differ')
    for p in (a.input, a.entities, a.documents_metadata):
        if not os.path.exists(p):
            sys.exit(f'not found: {p}')
    if not os.path.exists(a.pleiades_points):
        print(f'warning: no Pleiades points at {a.pleiades_points}, new rows get no coordinates', file=sys.stderr)
    add_naming_documents(a.input, a.output, a.entities, a.documents_metadata, a.pleiades_points,
                         a.max_per_event, a.apply, undated=a.undated)


if __name__ == '__main__':
    main()
