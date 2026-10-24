#!/usr/bin/env python3
"""Give a point to the Pleiades ids that documents use and the points file lacks.

  fill_missing_points.py OUTDIR [--metadata PATH] [--crosswalk PATH] [--delay 1.1] [--no-fetch]

The ids come from documents.pleiades_id and from the Pleiades ids of the crosswalk file given (the repaired one,
so a repair's new id is covered too). For each id with no row in pleiades_points.tsv: the representative point
(reprPoint) of the place, read from the local Pleiades dump; for a place without one, the center of its bounding
box, noted in the `how` column. A place with neither in the dump is fetched as JSON from pleiades.stoa.org (one
request per --delay seconds, the project's user agent, cached under OUTDIR/pleiades_json/) in case the live page
holds a point the dump lacks. Pleiades answering 403 or 429 stops the fetching and the rest is finished from the
dump. A place with no point anywhere is listed in OUTDIR/points_unavailable.tsv with the number of documents.

Writes OUTDIR/pleiades_points.additions.tsv (id, lat, lon, title, how), OUTDIR/points_unavailable.tsv and
OUTDIR/points_counts.json.
"""
import argparse
import collections
import json
import os
import sqlite3
import sys
import time
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import crosswalk_repair_lib as L  # noqa: E402

UA = 'Tesserae Project, University at Buffalo (tesserae.caset.buffalo.edu)'


def ids_used(metadata, crosswalk_path):
    c = sqlite3.connect('file:%s?mode=ro' % metadata, uri=True)
    n = collections.Counter()
    for (pid,) in c.execute("SELECT pleiades_id FROM documents WHERE pleiades_id IS NOT NULL AND pleiades_id != ''"):
        n[str(pid)] += 1
    tm = collections.Counter()
    for (t,) in c.execute('SELECT place_tm_id FROM documents WHERE place_tm_id IS NOT NULL'):
        tm[str(t)] += 1
    c.close()
    cw_ids = {}
    for r in L.load_crosswalk_rows(crosswalk_path):
        cw_ids[r['tm_place_id']] = r['pleiades_id']
    via_cw = collections.Counter()
    for t, k in tm.items():
        if t in cw_ids:
            via_cw[cw_ids[t]] += k
    return n, via_cw


def fetch_json(pid, cache_dir, delay, state):
    path = os.path.join(cache_dir, '%s.json' % pid)
    if os.path.exists(path):
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    if state['stopped']:
        return None
    time.sleep(delay)
    req = urllib.request.Request('https://pleiades.stoa.org/places/%s/json' % pid, headers={'User-Agent': UA})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            data = json.loads(r.read())
    except urllib.error.HTTPError as e:
        if e.code in (403, 429):
            state['stopped'] = 'HTTP %d' % e.code
            return None
        with open(path, 'w', encoding='utf-8') as f:
            json.dump({'error': e.code}, f)
        return {'error': e.code}
    except Exception as e:  # network trouble: do not cache
        state['errors'] += 1
        return None
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False)
    return data


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('outdir')
    ap.add_argument('--metadata', default=L.METADATA)
    ap.add_argument('--crosswalk', default=None)
    ap.add_argument('--extract-cache', default=None)
    ap.add_argument('--delay', type=float, default=1.1)
    ap.add_argument('--no-fetch', action='store_true')
    a = ap.parse_args(argv)
    os.makedirs(a.outdir, exist_ok=True)
    cache_dir = os.path.join(a.outdir, 'pleiades_json')
    os.makedirs(cache_dir, exist_ok=True)
    cw_path = a.crosswalk or os.path.join(a.outdir, 'trismegistos_to_pleiades.repaired.tsv')
    points, _ = L.load_points()
    extract = L.load_dump_extract(a.extract_cache or os.path.join(a.outdir, 'dump_extract.json'))
    direct, via_cw = ids_used(a.metadata, cw_path)
    need = {pid for pid in list(direct) + list(via_cw) if pid not in points}
    state = {'stopped': None, 'errors': 0}
    adds, unavailable = [], []
    for pid in sorted(need, key=lambda k: -(direct.get(k, 0) + via_cw.get(k, 0))):
        e = extract.get(pid)
        pt = L.point_of(pid, {}, extract) if e else None
        title = e['title'] if e else ''
        how = pt[2] if pt else None
        lat, lon = (pt[0], pt[1]) if pt else (None, None)
        if not pt and not a.no_fetch:
            d = fetch_json(pid, cache_dir, a.delay, state)
            if d and not d.get('error'):
                title = d.get('title') or title
                if d.get('reprPoint'):
                    lon, lat = d['reprPoint']
                    how = 'reprPoint (live JSON)'
                elif d.get('bbox'):
                    w, s, ea, n = d['bbox']
                    lat, lon, how = (s + n) / 2, (w + ea) / 2, 'bbox center (live JSON)'
        if how:
            if 'bbox' in how:
                how += ' (no representative point)'
            adds.append((pid, lat, lon, title, how))
        else:
            unavailable.append((pid, title, direct.get(pid, 0), via_cw.get(pid, 0)))
    with open(os.path.join(a.outdir, 'pleiades_points.additions.tsv'), 'w', encoding='utf-8') as f:
        f.write('pleiades_id\tlat\tlon\ttitle\thow\n')
        for pid, lat, lon, title, how in adds:
            f.write('%s\t%.6f\t%.6f\t%s\t%s\n' % (pid, lat, lon, title, how))
    with open(os.path.join(a.outdir, 'points_unavailable.tsv'), 'w', encoding='utf-8') as f:
        f.write('pleiades_id\ttitle\tdocuments_by_own_id\tdocuments_by_crosswalk\n')
        for u in sorted(unavailable, key=lambda u: -(u[2] + u[3])):
            f.write('\t'.join(str(v) for v in u) + '\n')
    got = {x[0] for x in adds}
    counts = {'ids_used_without_point': len(need),
              'ids_used_by_documents_directly_without_point': sum(1 for p in direct if p not in points),
              'documents_with_such_id': sum(direct[p] for p in direct if p not in points),
              'additions': len(adds), 'additions_by_how': dict(collections.Counter(x[4] for x in adds)),
              'documents_gaining_a_point_by_own_id': sum(direct.get(p, 0) for p in got),
              'documents_gaining_a_point_by_crosswalk': sum(via_cw.get(p, 0) for p in got),
              'ids_with_no_point_anywhere': len(unavailable),
              'documents_still_without_point_by_own_id': sum(u[2] for u in unavailable),
              'fetching_stopped': state['stopped'], 'fetch_network_errors': state['errors'],
              'json_files_cached': len(os.listdir(cache_dir))}
    with open(os.path.join(a.outdir, 'points_counts.json'), 'w') as f:
        json.dump(counts, f, indent=1)
    print(json.dumps(counts, indent=1))
    return 0


if __name__ == '__main__':
    sys.exit(main())
