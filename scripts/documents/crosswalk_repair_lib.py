"""Shared pieces for checking and repairing the Trismegistos-to-Pleiades crosswalk against EDH's own coordinates.

Nothing here writes under /var/www. The Pleiades dump is read from the local file (no fetch).
"""
import csv
import gzip
import json
import math
import os
import re
import sys
import unicodedata

HOME = os.path.expanduser('~')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

CROSSWALK = os.path.join(HOME, 'tesserae-docs', 'stage2', 'crosswalk', 'trismegistos_to_pleiades.tsv')
EDH_LINKS = os.path.join(HOME, 'tesserae-docs', 'stage2', 'crosswalk', 'edh_place_links.tsv')
EDH_GEOGRAPHY = os.path.join(HOME, 'tesserae-docs', 'raw', 'edh_geography', 'edhGeographicData.json')
POINTS = os.path.join(HOME, 'tesserae-backups', 'events_proto', 'pleiades_points.tsv')
DUMP = os.path.join(HOME, 'tesserae-docs', 'raw', 'pleiades', 'pleiades-places-latest.json.gz')
METADATA = '/var/www/tesseraev6_flask/data/documents/metadata.db'
THRESHOLD_KM = 25.0
CW_COLUMNS = ['tm_place_id', 'pleiades_id', 'source', 'label']


def haversine_km(lat1, lon1, lat2, lon2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dl = math.radians(lon2 - lon1)
    dp = p2 - p1
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * 6371.0088 * math.asin(min(1.0, math.sqrt(a)))


def norm_name(s):
    s = unicodedata.normalize('NFKD', s or '')
    s = ''.join(c for c in s if not unicodedata.combining(c)).lower()
    return re.sub(r'[^a-z0-9]+', ' ', s).strip()


def id_from_uri(uri):
    m = re.search(r'/(\d+)/?$', uri or '')
    return m.group(1) if m else None


def load_points(path=POINTS):
    pts, titles = {}, {}
    with open(path, encoding='utf-8') as f:
        next(f, None)
        for line in f:
            p = line.rstrip('\n').split('\t')
            if len(p) >= 3:
                try:
                    pts[p[0]] = (float(p[1]), float(p[2]))
                except ValueError:
                    continue
                titles[p[0]] = p[3] if len(p) > 3 else ''
    return pts, titles


def load_crosswalk_rows(path=CROSSWALK):
    with open(path, encoding='utf-8') as f:
        return [dict(r) for r in csv.DictReader(f, delimiter='\t')]


def load_edh_geography(path=EDH_GEOGRAPHY):
    """{tm_place_id: [feature, ...]} where a feature is {pleiades, name, lat, lon, edh_uri}."""
    with open(path, encoding='utf-8') as f:
        data = json.load(f)
    out = {}
    for ft in data['features']:
        pr = ft.get('properties') or {}
        tm = id_from_uri(pr.get('trismegistos_geo_uri'))
        co = (ft.get('geometry') or {}).get('coordinates')
        if not tm or not co or len(co) < 2:
            continue
        out.setdefault(tm, []).append({
            'pleiades': id_from_uri(pr.get('pleiades_uri')),
            'name': pr.get('ancient_findspot') or '',
            'lat': co[1], 'lon': co[0], 'edh_uri': pr.get('uri') or ''})
    return out


def load_edh_links(path=EDH_LINKS):
    with open(path, encoding='utf-8') as f:
        return [dict(r) for r in csv.DictReader(f, delimiter='\t')]


def iter_graph(path=DUMP, chunk=1 << 22):
    """Yield the places of the dump's "@graph" array one at a time (the whole file is large)."""
    dec = json.JSONDecoder()
    with gzip.open(path, 'rt', encoding='utf-8') as f:
        buf = ''
        while '"@graph"' not in buf:
            more = f.read(chunk)
            if not more:
                return
            buf += more
        pos = buf.index('[', buf.index('"@graph"')) + 1
        while True:
            while pos < len(buf) and buf[pos] in ' \n\r\t,':
                pos += 1
            if pos < len(buf) and buf[pos] == ']':
                return
            try:
                if pos >= len(buf):
                    raise json.JSONDecodeError('end', buf, pos)
                obj, end = dec.raw_decode(buf, pos)
            except json.JSONDecodeError:
                more = f.read(chunk)
                if not more:
                    return
                buf = buf[pos:] + more
                pos = 0
                continue
            yield obj
            pos = end


def build_dump_extract(dump=DUMP):
    """{id: {title, names, repr (lat, lon) or None, bbox [w,s,e,n] or None, types}} for every place of the dump."""
    out = {}
    for p in iter_graph(dump):
        pid = str(p.get('id'))
        names = [p.get('title') or '']
        for n in p.get('names') or []:
            for k in ('attested', 'romanized'):
                if n.get(k):
                    names.extend(x.strip() for x in n[k].split(',') if x.strip())
        rp = p.get('reprPoint')
        bb = p.get('bbox')
        out[pid] = {'title': p.get('title') or '', 'names': sorted(set(names)),
                    'repr': [rp[1], rp[0]] if rp and len(rp) == 2 else None,
                    'bbox': list(bb) if bb and len(bb) == 4 else None,
                    'types': p.get('placeTypes') or []}
    return out


def load_dump_extract(cache, dump=DUMP):
    if os.path.exists(cache):
        with open(cache, encoding='utf-8') as f:
            return json.load(f)
    ex = build_dump_extract(dump)
    with open(cache, 'w', encoding='utf-8') as f:
        json.dump(ex, f, ensure_ascii=False)
    return ex


def point_of(pid, points, extract=None):
    """(lat, lon, how) for a Pleiades id: the points file, else the dump's representative point, else its bounding-box center."""
    pid = str(pid)
    if pid in points:
        return points[pid][0], points[pid][1], 'points file'
    e = (extract or {}).get(pid)
    if e:
        if e['repr']:
            return e['repr'][0], e['repr'][1], 'reprPoint'
        if e['bbox']:
            w, s, ea, n = e['bbox']
            return (s + n) / 2, (w + ea) / 2, 'bbox center'
    return None


def median(xs):
    xs = sorted(xs)
    n = len(xs)
    return xs[n // 2] if n % 2 else (xs[n // 2 - 1] + xs[n // 2]) / 2


def tm_summary(features, link_weights=None):
    """Summary of the EDH findspots that carry one Trismegistos id.

    center: the median latitude and longitude of the findspots. edh_id: the Pleiades id most findspots carry
    (ties broken by the document weight of edh_place_links.tsv, then by the smaller id). When no findspot carries a
    uri, the id with the most documents in edh_place_links.tsv (link_weights: {pleiades_id: documents}).
    names: the ancient findspot names, folded and stripped of ', bei', ', aus', '?', most frequent first."""
    lat = median([f['lat'] for f in features])
    lon = median([f['lon'] for f in features])
    votes = {}
    for f in features:
        if f['pleiades']:
            votes[f['pleiades']] = votes.get(f['pleiades'], 0) + 1
    lw = link_weights or {}
    if votes:
        edh_id = sorted(votes, key=lambda k: (-votes[k], -lw.get(k, 0), int(k)))[0]
    elif lw:
        edh_id = sorted(lw, key=lambda k: (-lw[k], int(k)))[0]
    else:
        edh_id = None
    cnt = {}
    for f in features:
        n = clean_findspot_name(f['name'])
        if n:
            cnt[n] = cnt.get(n, 0) + 1
    names = sorted(cnt, key=lambda k: (-cnt[k], k))
    last = [f['pleiades'] for f in features if f['pleiades']]
    return {'center': (lat, lon), 'edh_id': edh_id, 'names': names, 'findspots': len(features),
            'last_feature_id': last[-1] if last else None, 'distinct_ids': len(votes)}


def clean_findspot_name(name):
    n = re.sub(r',\s*(bei|aus|inter|prope|iuxta)\b.*$', '', name or '')
    n = n.replace('?', '')
    return norm_name(n)


def classify_row(cw_id, summary, points, extract=None, near_km=20.0, far_km=100.0):
    """Suspect test for one crosswalk row. Returns (rule, d_crosswalk, d_edh) with rule 1, 2 or None.

    1: the crosswalk id differs from EDH's majority id, its point is more than near_km from the center, and the
       majority id's point is less than half that distance from the center.
    2: the crosswalk point is more than far_km from the center, whatever EDH says."""
    c = summary['center']
    pc = point_of(cw_id, points, extract)
    if not pc:
        return None, None, None
    dc = haversine_km(c[0], c[1], pc[0], pc[1])
    de = None
    if summary['edh_id']:
        pe = point_of(summary['edh_id'], points, extract)
        if pe:
            de = haversine_km(c[0], c[1], pe[0], pe[1])
    if (summary['edh_id'] and str(cw_id) != str(summary['edh_id']) and dc > near_km and de is not None
            and de < dc / 2):
        return 1, dc, de
    if dc > far_km:
        return 2, dc, de
    return None, dc, de


def title_parts(extract_entry):
    t = extract_entry['title']
    parts = [t] + [p for p in re.split(r'[/]', t)]
    parts += [re.sub(r'\s*\(.*?\)', '', p) for p in parts]
    return {norm_name(p) for p in parts if p.strip()}


def build_name_indexes(extract):
    """(title_index, name_index): folded title part (or other name) -> set of Pleiades ids."""
    tidx, nidx = {}, {}
    for pid, e in extract.items():
        for k in title_parts(e):
            tidx.setdefault(k, set()).add(pid)
        for n in e['names']:
            k = norm_name(n)
            if k:
                nidx.setdefault(k, set()).add(pid)
    return tidx, nidx


def nearest_name_match(summary, points, extract, indexes, max_km=25.0):
    """Nearest Pleiades place to the center whose title (any slash part) matches an ancient name of the
    findspots after folding; places with no point are skipped. Falls back to the places' other names.
    Returns (pleiades_id, distance_km, how) or None."""
    c = summary['center']
    for how, idx in (('title', indexes[0]), ('name', indexes[1])):
        best = None
        for name in summary['names']:
            for pid in idx.get(name, ()):
                pt = point_of(pid, points, extract)
                if not pt:
                    continue
                d = haversine_km(c[0], c[1], pt[0], pt[1])
                if d <= max_km and (best is None or d < best[1]):
                    best = (pid, d, how)
        if best:
            return best
    return None


def repair_row(cw_id, rule, summary, points, extract, indexes, max_km=25.0):
    """The repair for a suspect: rule 1 takes EDH's majority id, rule 2 the nearest name match to the center.
    Returns (pleiades_id, repair_label) or (None, reason)."""
    if rule == 1:
        return summary['edh_id'], 'rule1_edh_majority_id'
    m = nearest_name_match(summary, points, extract, indexes, max_km)
    if m:
        return m[0], 'rule2_nearest_%s_match' % m[2]
    return None, 'no_candidate'
