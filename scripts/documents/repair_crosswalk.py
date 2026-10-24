#!/usr/bin/env python3
"""Write the repaired Trismegistos-to-Pleiades crosswalk, with the rows it lacked added.

  repair_crosswalk.py OUTDIR [--crosswalk PATH] [--metadata PATH] [--extract-cache PATH]

1. Every suspect row of check_crosswalk_against_edh.py that has a repair (rule 1: EDH's majority Pleiades id;
   rule 2: the nearest Pleiades place to the center of EDH's findspots whose title matches EDH's ancient name,
   within 25 km) gets the new id and the name of its rule in a fifth column `repair`. A row that is not a suspect
   is never changed. A suspect with no repair is left and listed in OUTDIR/unrepaired_suspects.tsv.
2. Every Trismegistos place id that documents carry (place_tm_id) and the crosswalk lacks gets a row when EDH
   gives it a Pleiades id (geography's majority id, else edh_place_links.tsv weighted by documents) and that id's
   point lies within 25 km of the center of the EDH findspots with that Trismegistos id (the same center test).
   When it fails the test, the nearest same-name place is tried. An id with no findspot in EDH's geography file
   is taken from edh_place_links.tsv unchecked (the repair column says so). The rest is listed in
   OUTDIR/unadded_tm_ids.tsv.

Writes OUTDIR/trismegistos_to_pleiades.repaired.tsv (the four original columns plus `repair`),
OUTDIR/crosswalk_additions.tsv, OUTDIR/repair_counts.json.
"""
import argparse
import collections
import json
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import crosswalk_repair_lib as L  # noqa: E402

REGION_SHARE = 0.8  # a repair needs at least this share of the documents of the row in one region
import check_crosswalk_against_edh as C  # noqa: E402


def missing_tm_ids(metadata, crosswalk_ids):
    c = sqlite3.connect('file:%s?mode=ro' % metadata, uri=True)
    n = collections.Counter()
    n_unplaced = collections.Counter()
    for tm, pid in c.execute('SELECT place_tm_id, pleiades_id FROM documents WHERE place_tm_id IS NOT NULL'):
        if str(tm) not in crosswalk_ids:
            n[str(tm)] += 1
            if not pid:
                n_unplaced[str(tm)] += 1
    c.close()
    return n, n_unplaced


def build_additions(missing, geo, links, points, extract, indexes, max_km=25.0, unplaced=None):
    """Return (additions, unadded): rows {tm, id, source, repair, documents} and reasons."""
    lw = C.link_weights([r for r in links if r['tm_place_id'] in missing])
    adds, unadded = [], []
    for tm, ndoc in sorted(missing.items(), key=lambda kv: -kv[1]):
        feats = geo.get(tm)
        links_here = lw.get(tm)
        if feats:
            s = L.tm_summary(feats, links_here)
            cand = s['edh_id']
            pt = L.point_of(cand, points, extract) if cand else None
            if cand and pt and L.haversine_km(s['center'][0], s['center'][1], pt[0], pt[1]) <= max_km:
                adds.append({'tm': tm, 'id': cand, 'source': 'edh_geography', 'repair': 'added_center_test', 'documents': ndoc})
                continue
            m = L.nearest_name_match(s, points, extract, indexes, max_km)
            if m:
                adds.append({'tm': tm, 'id': m[0], 'source': 'edh_geography', 'repair': 'added_nearest_%s_match' % m[2], 'documents': ndoc})
                continue
            unadded.append((tm, ndoc, (unplaced or {}).get(tm, 0), cand or '', 'fails the center test, no name match'))
        elif links_here:
            cand = sorted(links_here, key=lambda k: (-links_here[k], int(k)))[0]
            adds.append({'tm': tm, 'id': cand, 'source': 'edh_place_links', 'repair': 'added_links_unchecked_no_edh_findspot',
                         'documents': ndoc})
        else:
            unadded.append((tm, ndoc, (unplaced or {}).get(tm, 0), '', 'EDH gives no Pleiades id'))
    return adds, unadded


def region_shares(metadata):
    """{tm_place_id: (top_region, share_of_documents_with_a_region, documents_with_a_region)}.
    A Trismegistos id whose documents lie in several regions is a bucket of homonyms (Neapolis: Naples,
    Kavala, Nablus, Nabeul), and no single Pleiades place is right for all of them."""
    c = sqlite3.connect('file:%s?mode=ro' % metadata, uri=True)
    cnt = collections.defaultdict(collections.Counter)
    for tm, reg in c.execute('SELECT place_tm_id, region FROM documents WHERE place_tm_id IS NOT NULL'):
        r = L.norm_name((reg or '').replace('?', ''))
        if r:
            cnt[str(tm)][r] += 1
    c.close()
    out = {}
    for tm, cn in cnt.items():
        top, k = cn.most_common(1)[0]
        out[tm] = (top, k / sum(cn.values()), sum(cn.values()))
    return out


def unlocated_rows(rows, metadata, points, extract, applied_tm, min_docs=10, share=0.8):
    """Rule 3. Crosswalk rows used by documents whose Pleiades place has no point anywhere (an unlocated place),
    that no earlier rule repaired. The documents' own place strings decide: when at least `share` of the
    documents that carry a string (and at least min_docs of them) have one cleaned name, the repair is the Pleiades
    place that most other documents with that name carry (documents of other Trismegistos ids, at least `share`
    of them, the place having a point). Otherwise the row is listed, unrepaired.
    Returns (repairs {tm: (id, name, docs, sibling_docs)}, listed [(tm, id, title, docs, top name)])."""
    c = sqlite3.connect('file:%s?mode=ro' % metadata, uri=True)
    names = collections.defaultdict(collections.Counter)
    sib = collections.defaultdict(collections.Counter)
    for tm, anc, pid in c.execute('SELECT place_tm_id, ancient_place, pleiades_id FROM documents'):
        n = L.clean_findspot_name(anc)
        if tm is not None:
            names[str(tm)][n] += 1
        if n and pid and str(pid) in points and (tm is None or str(tm) not in applied_tm):
            sib[n][str(pid)] += 1
    c.close()
    repairs, listed = {}, []
    for r in rows:
        tm = str(r['tm_place_id'])
        cn = names.get(tm)
        if not cn or tm in applied_tm or L.point_of(r['pleiades_id'], points, extract):
            continue
        ndoc = sum(cn.values())
        title = extract.get(r['pleiades_id'], {}).get('title', '')
        tot = sum(v for k, v in cn.items() if k)
        top = max(((k, v) for k, v in cn.items() if k), key=lambda kv: kv[1], default=(None, 0))
        if tot >= min_docs and top[1] >= share * tot:
            sc = sib.get(top[0])
            if sc:
                pid, k = sc.most_common(1)[0]
                if k >= share * sum(sc.values()):
                    repairs[tm] = (pid, top[0], ndoc, sum(sc.values()))
                    continue
        listed.append((tm, r['pleiades_id'], title, ndoc, top[0] or ''))
    return repairs, listed


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('outdir')
    ap.add_argument('--crosswalk', default=L.CROSSWALK)
    ap.add_argument('--metadata', default=L.METADATA)
    ap.add_argument('--extract-cache', default=None)
    a = ap.parse_args(argv)
    os.makedirs(a.outdir, exist_ok=True)
    points, ptitles = L.load_points()
    extract = L.load_dump_extract(a.extract_cache or os.path.join(a.outdir, 'dump_extract.json'))
    indexes = L.build_name_indexes(extract)
    rows = L.load_crosswalk_rows(a.crosswalk)
    geo = L.load_edh_geography()
    links = L.load_edh_links()
    ndocs = C.documents_per_tm(a.metadata)
    recs = C.analyze(rows, geo, points, extract, indexes, C.link_weights(links), ndocs)
    shares = region_shares(a.metadata)
    homonym = {x['row']['tm_place_id'] for x in recs if x['rule'] and x['repair_id']
               and shares.get(x['row']['tm_place_id'], ('', 1.0, 0))[1] < REGION_SHARE}
    for x in recs:
        if x['row']['tm_place_id'] in homonym:
            x['repair_blocked'] = x['repair_id']
            x['repair_id'], x['repair'] = None, 'blocked_homonym_bucket'
    fix = {x['row']['tm_place_id']: x for x in recs if x['rule'] and x['repair_id']}
    out, changed = [], []
    for r in rows:
        x = fix.get(r['tm_place_id'])
        if x and x['repair_id'] != r['pleiades_id']:
            new = dict(r, pleiades_id=x['repair_id'], repair=x['repair'], label=C.title_of(x['repair_id'], ptitles, extract))
            changed.append((r, new, x))
            out.append(new)
        else:
            out.append(dict(r, repair=''))
    # rule 3: rows whose place has no point anywhere
    r3, r3_listed = unlocated_rows(rows, a.metadata, points, extract, {r['tm_place_id'] for r, _, _ in changed})
    for i, r in enumerate(out):
        if r['tm_place_id'] in r3:
            out[i] = dict(r, pleiades_id=r3[r['tm_place_id']][0], repair='rule3_unlocated_place_documents_name_siblings',
                          label=C.title_of(r3[r['tm_place_id']][0], ptitles, extract))
    with open(os.path.join(a.outdir, 'rule3_unlocated_rows.tsv'), 'w', encoding='utf-8') as f:
        f.write('tm_place_id\tcrosswalk_pleiades_id\tcrosswalk_title\tdocuments\tdocuments_top_name\tstatus\tnew_id\tnew_title\n')
        for tm, (pid, nm, nd, ns) in sorted(r3.items(), key=lambda kv: -kv[1][2]):
            old = next(r['pleiades_id'] for r in rows if r['tm_place_id'] == tm)
            f.write('\t'.join([tm, old, C.title_of(old, ptitles, extract), str(nd), nm, 'repaired', pid,
                               C.title_of(pid, ptitles, extract)]) + '\n')
        for tm, pid, title, nd, nm in sorted(r3_listed, key=lambda x: -x[3]):
            f.write('\t'.join([tm, pid, title, str(nd), nm, 'listed, unrepaired', '', '']) + '\n')
    # unrepaired suspects
    with open(os.path.join(a.outdir, 'unrepaired_suspects.tsv'), 'w', encoding='utf-8') as f:
        f.write('tm_place_id\tcrosswalk_pleiades_id\tcrosswalk_title\trule\tcrosswalk_km\tdocuments\tedh_ancient_name\treason\n')
        for x in sorted((x for x in recs if x['rule'] and not x['repair_id']), key=lambda x: -x['docs']):
            f.write('\t'.join([x['row']['tm_place_id'], x['row']['pleiades_id'], C.title_of(x['row']['pleiades_id'], ptitles, extract),
                               str(x['rule']), '%.1f' % x['dc'], str(x['docs']),
                               x['summary']['names'][0] if x['summary']['names'] else '', x['repair'] or 'no_candidate']) + '\n')
    have = {r['tm_place_id'] for r in rows}
    missing, missing_unplaced = missing_tm_ids(a.metadata, have)
    adds, unadded = build_additions(missing, geo, links, points, extract, indexes, unplaced=missing_unplaced)
    for ad in adds:
        out.append({'tm_place_id': ad['tm'], 'pleiades_id': ad['id'], 'source': ad['source'],
                    'label': C.title_of(ad['id'], ptitles, extract), 'repair': ad['repair']})
    with open(os.path.join(a.outdir, 'trismegistos_to_pleiades.repaired.tsv'), 'w', encoding='utf-8') as f:
        f.write('\t'.join(L.CW_COLUMNS + ['repair']) + '\n')
        for r in out:
            f.write('\t'.join(str(r[k]) for k in L.CW_COLUMNS + ['repair']) + '\n')
    with open(os.path.join(a.outdir, 'crosswalk_additions.tsv'), 'w', encoding='utf-8') as f:
        f.write('tm_place_id\tpleiades_id\ttitle\tsource\trepair\tdocuments\n')
        for ad in adds:
            f.write('\t'.join([ad['tm'], ad['id'], C.title_of(ad['id'], ptitles, extract), ad['source'], ad['repair'],
                               str(ad['documents'])]) + '\n')
    with open(os.path.join(a.outdir, 'unadded_tm_ids.tsv'), 'w', encoding='utf-8') as f:
        f.write('tm_place_id\tdocuments\tdocuments_without_pleiades_id\tcandidate\treason\n')
        for u in unadded:
            f.write('\t'.join(str(v) for v in u) + '\n')
    counts = {'rows_in': len(rows), 'rows_changed': len(changed), 'rule3_rows_repaired': len(r3), 'rule3_documents': sum(v[2] for v in r3.values()),
              'rule3_rows_listed_unrepaired': len(r3_listed), 'rule3_listed_documents': sum(x[3] for x in r3_listed),
              'changed_by_rule': dict(collections.Counter(n['repair'] for _, n, _ in changed)),
              'documents_under_changed_rows': sum(x['docs'] for _, _, x in changed),
              'suspects_blocked_homonym_bucket': len(homonym), 'documents_blocked_homonym_bucket': sum(x['docs'] for x in recs if x['row']['tm_place_id'] in homonym),
              'suspects_left_unrepaired': sum(1 for x in recs if x['rule'] and not x['repair_id']),
              'unrepaired_documents': sum(x['docs'] for x in recs if x['rule'] and not x['repair_id']),
              'missing_tm_ids': len(missing), 'documents_with_missing_tm_id': sum(missing.values()),
              'documents_with_missing_tm_id_and_no_pleiades_id': sum(missing_unplaced.values()),
              'rows_added': len(adds), 'documents_under_added_rows': sum(x['documents'] for x in adds),
              'documents_under_added_rows_and_no_pleiades_id': sum(missing_unplaced.get(x['tm'], 0) for x in adds),
              'added_by_rule': dict(collections.Counter(x['repair'] for x in adds)),
              'tm_ids_not_added': len(unadded), 'documents_not_added': sum(u[1] for u in unadded),
              'documents_not_added_and_no_pleiades_id': sum(u[2] for u in unadded),
              'rows_out': len(out)}
    with open(os.path.join(a.outdir, 'repair_counts.json'), 'w') as f:
        json.dump(counts, f, indent=1)
    print(json.dumps(counts, indent=1))
    return 0


if __name__ == '__main__':
    sys.exit(main())
