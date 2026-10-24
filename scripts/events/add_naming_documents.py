#!/usr/bin/env python3
"""Add to each event the inscriptions and papyri that name its participants or its place.

  add_naming_documents.py INPUT.sqlite OUTPUT.sqlite [--entities PATH] [--documents-metadata PATH]
                          [--pleiades-points PATH] [--max-per-event N] [--undated {keep,last,drop}]
                          [--only-prefix PREFIX] [--only-events ID,ID,...]
                          [--report-place-resolution OUT.tsv] [--apply]

The events store keeps for each event the fifty documents nearest its place among those
dated within its years. For a region such as Sicily none of the fifty names a participant
or the place. This script resolves each event's participants and place to Mentions-store
entities (the same resolver the Events page uses), takes every document the store's
document_mentions table links to them, drops those already in the event's documents rows,
keeps those whose dating overlaps the event's years widened by 50 on each side (or that
have no dating at all), and inserts at most N per event, nearest first.

--undated keep (the default, as specified) treats a document with no dating like any other and
orders by distance. last puts the undated ones after the dated ones before the cap is applied.
drop leaves them out. On the 2026-10-18 copy 79 percent of the added rows are undated.

--only-prefix keeps only the documents whose id starts with it (for example 'aio:'), so a collection
added to the Mentions store later can be given to the events without the rest of the store's
documents.

The place is resolved by the event's Pleiades id first (the Mentions entity that carries that id; of
several, a place before other types, then the one with most lines), never by its label. Only when no
entity carries the id does the label resolve as the Events page resolves a name, and then a hit whose own
Pleiades id differs from the event's is refused ("place label resolves to another Pleiades place"). The
battle of 435 BCE labeled "Akri" (Pleiades 530771, Actium) had resolved by label to Akriai in Laconia and
took Agrigentum stones 654 km away (2026-10-24). An event with no Pleiades id keeps the label resolution.
Participants resolve by name as before.

--only-events limits the run to the listed event ids. --report-place-resolution OUT.tsv writes, for every
event with a place label, the entity the label resolves to and the entity the id resolves to, prints the
counts (equal, different, only new, only old, neither) and changes nothing else.

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


REFUSED = 'place label resolves to another Pleiades place'


def entity_by_pleiades(entities, pid):
    """The eid of the entity whose own Pleiades id (the store's pleiades_id column, one id, not the list of
    candidate ids that a merged heading such as "Antiochia/Theoupolis" carries) is `pid`, among `entities`
    (dicts with eid, type, total and pleiades_id): a place before any other type, then the most lines, then the
    lowest eid. None when no entity carries it."""
    pid = str(pid).strip() if pid is not None else ''
    if not pid:
        return None
    hits = [e for e in entities if str(e.get('pleiades_id') or '').strip() == pid]
    if not hits:
        return None
    hits.sort(key=lambda e: (e.get('type') != 'place', -(e.get('total') or 0), e['eid']))
    return hits[0]['eid']


def resolve_place_entity(label, pid, entities_by_eid, by_label, log=None):
    """(eid or None, how) for an event's place. how is 'id' (the entity of the event's Pleiades id), 'label'
    (the label's first hit, the way names resolve), 'refused' (the label's hit carries a different Pleiades id
    than the event's, and no entity carries the event's) or 'none'. `by_label` is the name resolver."""
    eid = entity_by_pleiades(entities_by_eid.values(), pid)
    if eid is not None:
        return eid, 'id'
    hit = by_label(label) if label else None
    if hit is None:
        return None, 'none'
    own = str(entities_by_eid.get(hit, {}).get('pleiades_id') or '').strip()
    if pid and own and str(pid).strip() != own:
        if log:
            log(f'{REFUSED}: {label!r} (event Pleiades {pid}) -> eid {hit} ({entities_by_eid[hit]["label"]}, Pleiades {own})')
        return None, 'refused'
    return hit, 'label'


def make_resolver(entities_path):
    """name -> entity id, the way /api/entities/search puts the first hit: a list entity
    ranked by backend.blueprints.entities._rank, then a corpus name. The route's own ranking
    and catalog are used, so the two never resolve a name differently.

    The returned function also carries .place(label, pleiades_id, log) -> (eid, how), the event's place by
    its Pleiades id first (see resolve_place_entity), and .entity(eid) -> the catalog entry (list entities carry pleiades_id)."""
    os.environ['TESSERAE_ENTITY_STORE'] = entities_path
    from backend.blueprints import entities as E
    cat = E._catalog(entities_path)
    c = sqlite3.connect(f'file:{entities_path}?mode=ro', uri=True)
    own_pid = dict(c.execute('select eid, pleiades_id from entities where pleiades_id is not null'))
    c.close()
    for eid, e in cat['by_eid'].items():
        e['pleiades_id'] = own_pid.get(eid)
    cache = {}

    def resolve(name):
        if not name or len(name.strip()) < 2:
            return None
        if name in cache:
            return cache[name]
        f = E.ei.fold(name.strip())
        hits = []
        for e in cat['by_eid'].values():
            r = E._rank(e, f, name.strip())
            if r is not None:
                hits.append((r, -e['total'], e['label'], e))
        hits.sort(key=lambda x: x[:3])
        if not hits:
            for n in cat['names'].values():
                if n['duplicate'] or n['total'] == 0:
                    continue
                r = E._rank(n, f, name.strip())
                if r is not None:
                    hits.append((r, -n['total'], n['label'], n))
            hits.sort(key=lambda x: x[:3])
        cache[name] = hits[0][3]['eid'] if hits else None
        return cache[name]

    def entity(eid):
        return cat['by_eid'].get(eid) or cat['names'].get(eid)

    def place(label, pleiades_id, log=None):
        return resolve_place_entity(label, pleiades_id, cat['by_eid'], resolve, log)

    resolve.place = place
    resolve.by_id = lambda pid: entity_by_pleiades(cat['by_eid'].values(), pid)
    resolve.entity = entity
    return resolve


def event_participants(ev):
    import json
    try:
        parts = json.loads(ev['participants'] or '[]')
    except ValueError:
        parts = []
    return [p for p in parts if p]


def event_names(ev):
    names = event_participants(ev)
    if ev['place']:
        names.append(ev['place'])
    return names


def event_eids(ev, resolve, log=None, place_only=False):
    """The sorted entity ids of an event's participants and place (the place by its Pleiades id first).
    place_only leaves the participants out (a repair of the place alone)."""
    eids = set() if place_only else {resolve(n) for n in event_participants(ev)}
    if ev['place']:
        if hasattr(resolve, 'place'):
            eids.add(resolve.place(ev['place'], ev['pleiades_id'], log)[0])
        else:
            eids.add(resolve(ev['place']))
    return sorted(x for x in eids if x is not None)


def plan_rows(events_conn, entities_conn, meta_conn, resolve, points, max_per_event=50, undated='keep',
              only_prefix=None, only_events=None, log=None, place_only=False):
    """{event_id: [row tuples in documents-table order]} for every event gaining rows."""
    out = {}
    events_conn.row_factory = sqlite3.Row
    have = {}
    for r in events_conn.execute('SELECT event_id, doc_id FROM documents'):
        have.setdefault(r[0], set()).add(r[1])
    mention_cache = {}
    for ev in events_conn.execute('SELECT * FROM events').fetchall():
        if only_events is not None and ev['id'] not in only_events:
            continue
        eids = event_eids(ev, resolve, log, place_only)
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
        cand = [d for d in docs if d not in skip and (not only_prefix or d.startswith(only_prefix))]
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


def place_resolution_report(events_conn, resolve, out_path, log=print):
    """Write a TSV with, for every event that has a place label, the entity the label resolves to (the way
    the 2026-10-19 run did) and the entity its Pleiades id resolves to. Returns the counts and the rows."""
    events_conn.row_factory = sqlite3.Row
    rows, refused, counts = [], [], {'equal': 0, 'different': 0, 'only_new': 0, 'only_old': 0, 'neither': 0}

    def desc(eid):
        e = resolve.entity(eid) if eid is not None else None
        if e is None:
            return ('', '', '')
        return (eid, e['label'], e.get('pleiades_id') or '')

    for ev in events_conn.execute("SELECT * FROM events WHERE place IS NOT NULL AND place <> '' ORDER BY id"):
        old = resolve(ev['place'])
        new = resolve.by_id(ev['pleiades_id']) if ev['pleiades_id'] else None
        kind = ('neither' if old is None and new is None else 'only_new' if old is None else
                'only_old' if new is None else 'equal' if old == new else 'different')
        counts[kind] += 1
        eff, how = resolve.place(ev['place'], ev['pleiades_id'])
        if how == 'refused':
            refused.append((ev['id'], ev['label'], ev['place'], ev['pleiades_id'], old))
        rows.append((kind, ev['id'], ev['label'], ev['place'], ev['pleiades_id'] or '') + desc(old) + desc(new) + (how,))
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write('\t'.join(('kind', 'event_id', 'event_label', 'place_label', 'event_pleiades_id', 'old_eid', 'old_label',
                           'old_pleiades', 'new_eid', 'new_label', 'new_pleiades', 'new_rule_result')) + '\n')
        for r in rows:
            f.write('\t'.join(str(x).replace('\t', ' ') for x in r) + '\n')
    log('place resolution, events with a place label: ' + ', '.join(f'{k} {v}' for k, v in counts.items()))
    log(f'refused by the new rule (the label hit carries another Pleiades id, no entity carries the event\'s): {len(refused)}')
    for r in refused:
        log(f'  refused {r[0]} {r[1]} [{r[2]} / Pleiades {r[3]}] (label hit eid {r[4]})')
    for r in rows:
        if r[0] == 'different':
            log(f'  different {r[1]} {r[2]} [{r[3]} / Pleiades {r[4]}]: label -> {r[6]} ({r[7]}), id -> {r[9]} ({r[10]})')
    return counts, rows


def add_naming_documents(input_path, output_path, entities_path, metadata_path, points_path,
                         max_per_event=50, apply=False, resolve=None, log=print, undated='keep', only_prefix=None,
                         only_events=None):
    ec = sqlite3.connect(f'file:{input_path}?mode=ro', uri=True)
    ent = sqlite3.connect(f'file:{entities_path}?mode=ro', uri=True)
    meta = sqlite3.connect(f'file:{metadata_path}?mode=ro', uri=True)
    resolve = resolve or make_resolver(entities_path)
    plan = plan_rows(ec, ent, meta, resolve, load_points(points_path), max_per_event, undated, only_prefix,
                     only_events, log)
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
    ap.add_argument('--only-prefix', default=None)
    ap.add_argument('--only-events', default=None, help='comma-separated event ids; the run touches only these')
    ap.add_argument('--report-place-resolution', default=None, metavar='OUT.tsv')
    ap.add_argument('--apply', action='store_true')
    a = ap.parse_args(argv)
    if os.path.abspath(a.input) == os.path.abspath(a.output):
        sys.exit('INPUT and OUTPUT must differ')
    for p in (a.input, a.entities, a.documents_metadata):
        if not os.path.exists(p):
            sys.exit(f'not found: {p}')
    if a.report_place_resolution:
        ec = sqlite3.connect(f'file:{a.input}?mode=ro', uri=True)
        place_resolution_report(ec, make_resolver(a.entities), a.report_place_resolution)
        return
    if not os.path.exists(a.pleiades_points):
        print(f'warning: no Pleiades points at {a.pleiades_points}, new rows get no coordinates', file=sys.stderr)
    add_naming_documents(a.input, a.output, a.entities, a.documents_metadata, a.pleiades_points,
                         a.max_per_event, a.apply, undated=a.undated, only_prefix=a.only_prefix,
                         only_events=set(a.only_events.split(',')) if a.only_events else None)


if __name__ == '__main__':
    main()
