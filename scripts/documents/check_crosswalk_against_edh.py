#!/usr/bin/env python3
"""Check the Trismegistos-to-Pleiades crosswalk against EDH's own findspots.

  check_crosswalk_against_edh.py OUTDIR [--crosswalk PATH] [--metadata PATH] [--max-suspect-rows 300]

EDH's geography file lists findspots, and one Trismegistos id covers many of them, so the check works on the
whole set. For each Trismegistos id of the crosswalk that EDH's geography carries:

  center       the median latitude and longitude of its findspots;
  EDH's id     the Pleiades id most of the findspots carry (edh_place_links.tsv weighted by documents only when
               no findspot carries one);
  points       the crosswalk's Pleiades point and EDH's id's point, from the points file or else the Pleiades dump
               (reprPoint, then bounding-box center).

A row is a SUSPECT when (rule 1) the crosswalk id differs from EDH's id, the crosswalk point is more than 20 km
from the center and EDH's point is less than half that distance from it, or (rule 2) the crosswalk point is more
than 100 km from the center whatever EDH says. Only rows that at least one document uses (place_tm_id in
metadata.db) count toward the limit of 300 suspect rows, past which the script exits with code 3.

Writes OUTDIR/suspects.tsv, OUTDIR/named_cases.tsv and OUTDIR/check_counts.json.
"""
import argparse
import collections
import json
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import crosswalk_repair_lib as L  # noqa: E402

SUSPECT_COLUMNS = ['tm_place_id', 'crosswalk_pleiades_id', 'crosswalk_title', 'crosswalk_source', 'edh_pleiades_id',
                   'edh_pleiades_title', 'edh_ancient_name', 'findspots', 'center_lat', 'center_lon', 'rule',
                   'crosswalk_km', 'edh_km', 'documents', 'repair_id', 'repair_title', 'repair', 'last_feature_id', 'distinct_edh_ids']


def documents_per_tm(metadata):
    c = sqlite3.connect('file:%s?mode=ro' % metadata, uri=True)
    n = collections.Counter()
    for tm, k in c.execute('SELECT place_tm_id, COUNT(*) FROM documents WHERE place_tm_id IS NOT NULL GROUP BY place_tm_id'):
        n[str(tm)] = k
    c.close()
    return n


def link_weights(links):
    w = {}
    for r in links:
        if r['pleiades_id']:
            w.setdefault(r['tm_place_id'], collections.Counter())[r['pleiades_id']] += 1
    return w


def analyze(rows, geo, points, extract, indexes, lw, ndocs):
    """One record per crosswalk row with an EDH findspot: summary, rule (or None) and repair."""
    out = []
    for r in rows:
        tm = str(r['tm_place_id'])
        feats = geo.get(tm)
        if not feats:
            continue
        s = L.tm_summary(feats, lw.get(tm))
        rule, dc, de = L.classify_row(r['pleiades_id'], s, points, extract)
        rec = {'row': r, 'summary': s, 'rule': rule, 'dc': dc, 'de': de, 'docs': ndocs[tm], 'repair_id': None, 'repair': ''}
        if dc is None:
            rec['unchecked'] = True
        if rule:
            rec['repair_id'], rec['repair'] = L.repair_row(r['pleiades_id'], rule, s, points, extract, indexes)
        out.append(rec)
    return out


def title_of(pid, ptitles, extract):
    if pid and str(pid) in extract:
        return extract[str(pid)]['title']
    return ptitles.get(str(pid), '') if pid else ''


def suspect_line(rec, ptitles, extract):
    r, s = rec['row'], rec['summary']
    return '\t'.join([r['tm_place_id'], r['pleiades_id'], title_of(r['pleiades_id'], ptitles, extract), r['source'],
                      s['edh_id'] or '', title_of(s['edh_id'], ptitles, extract), s['names'][0] if s['names'] else '',
                      str(s['findspots']), '%.4f' % s['center'][0], '%.4f' % s['center'][1], str(rec['rule']),
                      '%.1f' % rec['dc'], '' if rec['de'] is None else '%.1f' % rec['de'], str(rec['docs']),
                      rec['repair_id'] or '', title_of(rec['repair_id'], ptitles, extract), rec['repair'],
                      s['last_feature_id'] or '', str(s['distinct_ids'])])


def named_case_tm_ids(metadata):
    """Trismegistos place ids of the four named cases, found through the documents' own place strings."""
    c = sqlite3.connect('file:%s?mode=ro' % metadata, uri=True)
    q = {'Ostia': "ancient_place = 'Ostia'",
         'Aquileia': "ancient_place = 'Aquileia'",
         'Baden-Baden (Aquae)': "ancient_place LIKE 'Aquae%' AND modern_place LIKE '%Baden-Baden%'",
         'Turris Libisonis': "(ancient_place LIKE 'Turris Libisonis%' OR modern_place LIKE '%Porto Torres%')"}
    out = {}
    for case, where in q.items():
        out[case] = [(str(tm), anc, mod, k) for tm, anc, mod, k in c.execute(
            'SELECT place_tm_id, ancient_place, modern_place, COUNT(*) FROM documents WHERE place_tm_id IS NOT NULL AND %s '
            'GROUP BY place_tm_id, ancient_place, modern_place ORDER BY 4 DESC' % where)]
    c.close()
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('outdir')
    ap.add_argument('--crosswalk', default=L.CROSSWALK)
    ap.add_argument('--metadata', default=L.METADATA)
    ap.add_argument('--extract-cache', default=None)
    ap.add_argument('--max-suspect-rows', type=int, default=300)
    a = ap.parse_args(argv)
    os.makedirs(a.outdir, exist_ok=True)
    points, ptitles = L.load_points()
    extract = L.load_dump_extract(a.extract_cache or os.path.join(a.outdir, 'dump_extract.json'))
    indexes = L.build_name_indexes(extract)
    rows = L.load_crosswalk_rows(a.crosswalk)
    geo = L.load_edh_geography()
    ndocs = documents_per_tm(a.metadata)
    recs = analyze(rows, geo, points, extract, indexes, link_weights(L.load_edh_links()), ndocs)
    suspects = sorted((x for x in recs if x['rule']), key=lambda x: -x['docs'])
    used = [x for x in suspects if x['docs'] > 0]
    with open(os.path.join(a.outdir, 'suspects.tsv'), 'w', encoding='utf-8') as f:
        f.write('\t'.join(SUSPECT_COLUMNS) + '\n')
        for x in suspects:
            f.write(suspect_line(x, ptitles, extract) + '\n')
    by_tm = {x['row']['tm_place_id']: x for x in recs}
    with open(os.path.join(a.outdir, 'named_cases.tsv'), 'w', encoding='utf-8') as f:
        f.write('case\tancient_place\tmodern_place\tdocs_with_string\t' + '\t'.join(SUSPECT_COLUMNS) + '\n')
        for case, hits in named_case_tm_ids(a.metadata).items():
            for tm, anc, mod, k in hits:
                x = by_tm.get(tm)
                if x is None:
                    f.write('\t'.join([case, anc or '', mod or '', str(k), tm, 'NOT A CROSSWALK ROW WITH AN EDH FINDSPOT']) + '\n')
                    continue
                line = suspect_line(x, ptitles, extract) if x['rule'] else None
                if line is None:  # not a suspect: still show the row and its distances
                    r, s = x['row'], x['summary']
                    line = '\t'.join([tm, r['pleiades_id'], title_of(r['pleiades_id'], ptitles, extract), r['source'],
                                      s['edh_id'] or '', title_of(s['edh_id'], ptitles, extract),
                                      s['names'][0] if s['names'] else '', str(s['findspots']), '', '', 'not suspect',
                                      '' if x['dc'] is None else '%.1f' % x['dc'],
                                      '' if x['de'] is None else '%.1f' % x['de'], str(x['docs']), '', '', '', '', ''])
                f.write('\t'.join([case, anc or '', mod or '', str(k)]) + '\t' + line + '\n')
    counts = {'crosswalk_rows': len(rows), 'rows_with_edh_findspot': len(recs),
              'rows_checked': sum(1 for x in recs if x['dc'] is not None),
              'rows_unchecked_no_point': sum(1 for x in recs if x['dc'] is None),
              'suspects': len(suspects), 'suspects_rule1': sum(1 for x in suspects if x['rule'] == 1),
              'suspects_rule2': sum(1 for x in suspects if x['rule'] == 2),
              'suspect_rows_used_by_a_document': len(used), 'documents_affected': sum(x['docs'] for x in used),
              'suspects_by_source': dict(collections.Counter(x['row']['source'] for x in suspects)),
              'repairable': sum(1 for x in suspects if x['repair_id']),
              'repairable_used_by_a_document': sum(1 for x in used if x['repair_id']),
              'documents_under_repairable_rows': sum(x['docs'] for x in used if x['repair_id']),
              'suspects_whose_row_is_the_last_findspots_id': sum(1 for x in suspects if x['summary']['last_feature_id'] == x['row']['pleiades_id']),
              'suspects_with_two_or_more_edh_ids': sum(1 for x in suspects if x['summary']['distinct_ids'] > 1),
              'limit': a.max_suspect_rows}
    with open(os.path.join(a.outdir, 'check_counts.json'), 'w') as f:
        json.dump(counts, f, indent=1)
    print(json.dumps(counts, indent=1))
    if len(used) > a.max_suspect_rows:
        print('ESCALATE: more than %d suspect rows are used by a document' % a.max_suspect_rows, file=sys.stderr)
        return 3
    return 0


if __name__ == '__main__':
    sys.exit(main())
