#!/usr/bin/env python3
"""Find out what the stored point of each event without a Wikidata point stands for.

  classify_event_points.py INPUT.sqlite OUTPUT.sqlite WIKIDATA_RAW PLEIADES_RAW
                           --corrections-out PATH --classification-out PATH
                           [--pleiades-points PATH] [--apply]

For every event whose own Wikidata item has no coordinate (P625) the script compares the stored point
with the items the event is tied to (P276 location, and P17 country) and with the Pleiades place of the
event, and puts the event in one class.
  a  the stored point lies within 1 km of a settlement or site (a Wikidata location whose classes name a
     city, town, village, archaeological site, fortress and the like, a Pleiades place of such a type, or
     a Pleiades place whose title is not marked as a region)
  b  the stored point lies within 1 km of the center of a region, country, province, sea, river or the
     like (the same three sources, with region-type classes)
  c  nothing of the two found
For class b the event's English Wikipedia page is read for a primary coordinate (prop=coordinates). It is
taken when it lies in or beside the region, which is inside the Pleiades bounding box of the event's place
widened by one degree, or where the event has no Pleiades box within 400 km of the stored point. The change
is written to the corrections file (key use_wikipedia, read by fix_event_coords.py). A class b event with no
such coordinate gets events.location_approximate = 1 in OUTPUT, which the Map tab states. INPUT is never
modified. Dry run (nothing written but the two reports) unless --apply. OUTPUT may not be under /var/www.
"""
import argparse
import glob
import json
import os
import re
import shutil
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from add_naming_documents import haversine_km  # noqa: E402
from fetch_wikidata_places import claim_ids, load_entities  # noqa: E402

NEAR_KM = 1.0
BOX_MARGIN_DEG = 1.0
NO_BOX_KM = 400.0

# Class labels (Wikidata, English) read as a point feature, tested first.
SITE_WORDS = ('city', 'town', 'village', 'settlement', 'municipality', 'commune', 'comune', 'archaeological',
              'polis', 'fort', 'castle', 'castrum', 'castellum', 'ruins', 'battlefield', 'bridge', 'temple',
              'colony', 'port', 'oppidum', 'vicus', 'citadel', 'stronghold', 'capital', 'locality', 'deme',
              'monastery', 'museum', 'grave', 'hill', 'cape', 'headland', 'promontory', 'pass', 'gap', 'narrows',
              'volcano', 'tell', 'frazione', 'neighborhood', 'quarter', 'site', 'sanctuary', 'emporium',
              'hieron', 'tripolis', 'metropolis', 'market', 'harbor', 'harbour')
SITE_EXACT = ('mountain', 'inselberg', 'canyon', 'grotto')
REGION_WORDS = ('region', 'country', 'province', 'sea', 'river', 'state', 'empire', 'kingdom', 'satrapy',
                'territory', 'gulf', 'bay', 'strait', 'lake', 'ocean', 'peninsula', 'island', 'mountain range',
                'massif', 'plain', 'valley', 'plateau', 'isthmus', 'continent', 'prefecture', 'district',
                'county', 'department', 'principality', 'geographical', 'geographic location', 'drainage',
                'waterway', 'delta', 'dynasty', 'area', 'republic', 'nation', 'realm', 'exarchate',
                'administrative', 'landscape', 'civilization', 'ethnic', 'body of water', 'desert')
TITLE_REGION_TYPES = ('region', 'river', 'lake', 'island', 'plain', 'valley', 'sea', 'bay', 'gulf', 'strait',
                      'peninsula', 'province', 'mountain range', 'isthmus', 'country', 'territory', 'ocean')
PLEIADES_REGION = {'region', 'river', 'water-open', 'island', 'province', 'province-2', 'lake', 'peninsula',
                   'plain', 'valley', 'isthmus', 'strait'}


def title_is_region(title):
    """Pleiades titles end in the place type in parentheses: 'Euphrates (river)', 'Lydia/Maionia (region)'."""
    m = re.search(r'\(([^)]*)\)\s*$', title or '')
    return bool(m) and any(w in m.group(1).lower() for w in TITLE_REGION_TYPES)


def kind_of_classes(labels):
    """'site', 'region' or None from the English labels of an item's instance-of classes."""
    low = [x.lower() for x in labels if x]
    if any(lab in SITE_EXACT or any(w in lab for w in SITE_WORDS) for lab in low):
        return 'site'
    if any(any(w in lab for w in REGION_WORDS) for lab in low):
        return 'region'
    return None


def p625(ent):
    for c in (ent.get('claims') or {}).get('P625', []):
        v = ((c.get('mainsnak') or {}).get('datavalue') or {}).get('value')
        if isinstance(v, dict) and 'latitude' in v:
            return v['latitude'], v['longitude']
    return None


def label(ent):
    return ((ent.get('labels') or {}).get('en') or {}).get('value')


def wikipedia_coordinates(paths):
    """{title: (lat, lon)} of the primary coordinate of each page, following normalization and redirects."""
    pages, alias = {}, {}
    for p in paths:
        q = (json.load(open(p)).get('query') or {})
        for x in (q.get('normalized') or []) + (q.get('redirects') or []):
            alias[x['from']] = x['to']
        for pg in q.get('pages') or []:
            co = [c for c in pg.get('coordinates') or [] if c.get('primary') and c.get('globe', 'earth') == 'earth']
            if co:
                pages[pg['title']] = (co[0]['lat'], co[0]['lon'])
    out = {}
    for frm in list(alias) + list(pages):
        t = frm
        for _ in range(3):
            t = alias.get(t, t)
        if t in pages:
            out[frm] = pages[t]
    return out


def classify(stored, locs, pleiades, titles_region, other_points):
    """Return (class, evidence) for one event. locs is [(qid, label, (lat, lon), kind)],
    pleiades is (point, types, bbox) or None, titles_region is {(lat, lon): is_region} of nearby Pleiades points."""
    lat, lon = stored
    ev = []
    for qid, lab, pt, kind in locs:
        if pt and kind and haversine_km(lat, lon, pt[0], pt[1]) <= NEAR_KM:
            ev.append(('wikidata ' + kind, lab))
    if pleiades and pleiades[0] and haversine_km(lat, lon, pleiades[0][0], pleiades[0][1]) <= NEAR_KM:
        types = pleiades[1]
        if set(types) & PLEIADES_REGION:
            ev.append(('pleiades region', ','.join(types)))
        elif types:
            ev.append(('pleiades site', ','.join(types)))
    for pt, is_region, title in other_points:
        if haversine_km(lat, lon, pt[0], pt[1]) <= NEAR_KM:
            ev.append(('pleiades points ' + ('region' if is_region else 'site'), title))
    if any(k.endswith('region') for k, _ in ev):
        return 'b', ev
    if ev:
        return 'a', ev
    return 'c', ev


def in_or_beside(new, stored, bbox):
    if bbox:
        w, s, e, n = bbox
        return (s - BOX_MARGIN_DEG <= new[0] <= n + BOX_MARGIN_DEG) and (w - BOX_MARGIN_DEG <= new[1] <= e + BOX_MARGIN_DEG)
    return haversine_km(stored[0], stored[1], new[0], new[1]) <= NO_BOX_KM


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('input')
    ap.add_argument('output')
    ap.add_argument('wikidata_raw')
    ap.add_argument('pleiades_raw')
    ap.add_argument('--corrections-out', required=True)
    ap.add_argument('--classification-out', required=True)
    ap.add_argument('--pleiades-points', default=os.path.expanduser('~/tesserae-backups/events_proto/pleiades_points.tsv'))
    ap.add_argument('--apply', action='store_true')
    a = ap.parse_args(argv)
    if os.path.abspath(a.input) == os.path.abspath(a.output) or os.path.realpath(a.output).startswith('/var/www'):
        sys.exit('OUTPUT must differ from INPUT and may not be under /var/www')

    ents = load_entities(glob.glob(os.path.join(a.wikidata_raw, 'events_*.json')))
    lents = load_entities(glob.glob(os.path.join(a.wikidata_raw, 'locations_*.json')))
    cents = load_entities(glob.glob(os.path.join(a.wikidata_raw, 'classes_*.json')))
    wp = wikipedia_coordinates(glob.glob(os.path.join(a.wikidata_raw, 'wikipedia_*.json')))
    pts = []
    with open(a.pleiades_points, encoding='utf-8') as f:
        next(f)
        for line in f:
            pid, la, lo, title = (line.rstrip('\n').split('\t') + [''] * 4)[:4]
            try:
                pts.append(((float(la), float(lo)), title_is_region(title), title))
            except ValueError:
                continue

    con = sqlite3.connect('file:%s?mode=ro' % a.input, uri=True)
    con.row_factory = sqlite3.Row
    rows = con.execute('SELECT id, label, place, lat, lon, pleiades_id, wikipedia_title FROM events').fetchall()
    result, corrections, approximate, kept = {}, {}, [], {}
    counts = {'with_wikidata_point': 0, 'no_stored_point': 0}
    for r in rows:
        ent = ents.get(r['id']) or {}
        if p625(ent):
            counts['with_wikidata_point'] += 1
            continue
        if r['lat'] is None or r['lon'] is None:
            counts['no_stored_point'] += 1
            result[r['id']] = {'class': 'c', 'label': r['label'], 'note': 'no stored point'}
            continue
        stored = (r['lat'], r['lon'])
        locs = []
        for prop in ('P276', 'P17'):
            for q in claim_ids(ent, prop):
                le = lents.get(q) or {}
                klabels = [label(cents.get(c) or {}) for c in claim_ids(le, 'P31')]
                locs.append((q, label(le) or q, p625(le), kind_of_classes(klabels)))
        pl = None
        if r['pleiades_id']:
            path = os.path.join(a.pleiades_raw, 'places', r['pleiades_id'] + '.json')
            if os.path.exists(path):
                d = json.load(open(path))
                rp = d.get('reprPoint')
                pl = ((rp[1], rp[0]) if rp else None, d.get('placeTypes') or [], d.get('bbox'))
        near_pts = [p for p in pts if abs(p[0][0] - stored[0]) < 0.02 and abs(p[0][1] - stored[1]) < 0.03]
        cls, evidence = classify(stored, locs, pl, None, near_pts)
        entry = {'class': cls, 'label': r['label'], 'place': r['place'], 'stored': list(stored),
                 'evidence': [list(e) for e in evidence]}
        if cls == 'b':
            new = wp.get(r['wikipedia_title'] or '')
            bbox = pl[2] if pl else None
            if new and in_or_beside(new, stored, bbox) and haversine_km(stored[0], stored[1], new[0], new[1]) > NEAR_KM:
                km = round(haversine_km(stored[0], stored[1], new[0], new[1]), 1)
                corrections[r['id']] = {'label': r['label'], 'place': r['place'], 'from': list(stored),
                                        'to': [new[0], new[1]], 'km': km, 'wikipedia_title': r['wikipedia_title']}
                entry['outcome'] = 'wikipedia point'
            else:
                approximate.append(r['id'])
                entry['outcome'] = 'approximate'
                if new:
                    entry['wikipedia_point_rejected'] = list(new)
                    kept[r['id']] = {'label': r['label'], 'reason': 'Wikipedia point outside the region or at the center'}
        result[r['id']] = entry
    tally = {k: sum(1 for v in result.values() if v['class'] == k) for k in 'abc'}
    summary = {'events_without_wikidata_point': len(result) , 'classes': tally, 'wikipedia_points': len(corrections),
               'approximate': len(approximate), **counts}
    with open(a.classification_out, 'w') as f:
        json.dump({'summary': summary, 'events': result}, f, indent=1, ensure_ascii=False)
    with open(a.corrections_out, 'w') as f:
        json.dump({'_note': 'Event coordinates to correct (2026-10-20, events without a Wikidata point). Source: the primary '
                            'coordinate of the event\'s English Wikipedia page, taken where the stored point is the center '
                            'of a region, sea, river or country and the page\'s point lies in or beside that region. '
                            'Events in kept_stored keep their stored point; the ones in approximate_ids are flagged '
                            'location_approximate.',
                   'use_wikipedia': corrections, 'kept_stored': kept, 'approximate_ids': approximate},
                  f, indent=1, ensure_ascii=False)
    print(json.dumps(summary))
    if not a.apply:
        print('dry run, no store written')
        return 0
    shutil.copyfile(a.input, a.output)
    oc = sqlite3.connect(a.output)
    if 'location_approximate' not in [x[1] for x in oc.execute('PRAGMA table_info(events)')]:
        oc.execute('ALTER TABLE events ADD COLUMN location_approximate INTEGER')
    oc.execute('UPDATE events SET location_approximate = NULL')
    oc.executemany('UPDATE events SET location_approximate = 1 WHERE id = ?', [(i,) for i in approximate])
    oc.commit()
    oc.close()
    print('written', a.output)
    return 0


if __name__ == '__main__':
    sys.exit(main())
