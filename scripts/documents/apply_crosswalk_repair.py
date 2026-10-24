#!/usr/bin/env python3
"""Write the repaired Pleiades ids into a COPY of metadata.db (never the input, never under /var/www).

  apply_crosswalk_repair.py INPUT_METADATA OUTPUT_METADATA --old-crosswalk PATH --repaired PATH --fill PATH
                            [--hermopolites-id 756575] [--report PATH]

A document's Pleiades id is replaced only where it came from the crosswalk or from a name, never when the source
supplied it:

  A  with a place_tm_id whose crosswalk row was repaired:
       fill       the id was filled on 2026-10-24 (listed in the fill file): gets the repaired id;
       crosswalk  the id equals the OLD crosswalk row's id (EDH and EDR carry no Pleiades id of their own, so an
                  id equal to the old row was written from the crosswalk): gets the repaired id;
       source     any other id (kept; counted as "would differ").
     A document whose region is not the region most documents of the row lie in (a homonym: the Aquileia of
     Heidenheim among the stones of Aquileia in Italy) keeps its id.
  B  without a place_tm_id and filled on 2026-10-24 by sibling names or titles with an id that is the old id of a
     repaired row: gets the repaired id of the row whose documents most often carry the document's own place name
     (cleaned), when there is one; otherwise kept and counted.
  C  with --hermopolites-id: documents with neither a Pleiades id nor a place_tm_id whose cleaned place name is the
     Hermopolites nome get that id.

Writes the report as JSON.
"""
import argparse
import collections
import json
import os
import shutil
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import crosswalk_repair_lib as L  # noqa: E402

HERMOPOLITES_NAMES = {'hermopolites', 'hermopolites agypten', 'hermopolites aegypten'}


def load_fill(path):
    fill = {}
    with open(path, encoding='utf-8') as f:
        next(f, None)
        for line in f:
            p = line.rstrip('\n').split('\t')
            if len(p) >= 2:
                fill[p[0]] = p[1]
    return fill


def plan(conn, old_cw, new_cw, fill, hermopolites_id=None):
    """Return ({doc_id: (new_id, kind)}, counts)."""
    changed = {tm for tm, pid in new_cw.items() if old_cw.get(tm) != pid and tm in old_cw}
    old_ids = collections.defaultdict(set)
    for tm in changed:
        old_ids[old_cw[tm]].add(tm)
    names = collections.defaultdict(collections.Counter)  # tm -> cleaned name -> documents
    rows = conn.execute('SELECT id, place_tm_id, pleiades_id, ancient_place, region FROM documents').fetchall()
    regions = collections.defaultdict(collections.Counter)  # tm -> region -> documents
    for did, tm, pid, anc, reg in rows:
        if tm is not None and str(tm) in changed:
            names[str(tm)][L.clean_findspot_name(anc)] += 1
            r = L.norm_name((reg or '').replace('?', ''))
            if r:
                regions[str(tm)][r] += 1
    out, counts = {}, collections.Counter()
    for did, tm, pid, anc, reg in rows:
        pid = str(pid) if pid else None
        if tm is not None and str(tm) in changed:
            tm = str(tm)
            new = new_cw[tm]
            if pid == new:
                continue
            r = L.norm_name((reg or '').replace('?', ''))
            if r and regions[tm] and r != regions[tm].most_common(1)[0][0]:
                counts['A_minority_region_kept'] += 1  # e.g. the Heidenheim stones of the row of Aquileia
                continue
            if did in fill:
                out[did] = (new, 'A_fill')
            elif pid == old_cw[tm]:
                out[did] = (new, 'A_crosswalk')
            elif pid is None:
                out[did] = (new, 'A_no_id')
            else:
                counts['A_source_kept_would_differ'] += 1
        elif tm is None and did in fill and pid in old_ids:
            n = L.clean_findspot_name(anc)
            cands = [t for t in old_ids[pid] if names[t].get(n)]
            best = max(cands, key=lambda t: names[t][n], default=None)
            if best and new_cw[best] != pid:
                out[did] = (new_cw[best], 'B_fill_by_name')
            else:
                counts['B_kept_no_matching_row'] += 1
        elif hermopolites_id and tm is None and not pid and L.clean_findspot_name(anc) in HERMOPOLITES_NAMES:
            out[did] = (str(hermopolites_id), 'C_hermopolites')
    for _, k in out.values():
        counts[k] += 1
    counts['documents_changed'] = len(out)
    return out, dict(counts)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('input')
    ap.add_argument('output')
    ap.add_argument('--old-crosswalk', default=L.CROSSWALK)
    ap.add_argument('--repaired', required=True)
    ap.add_argument('--fill', required=True)
    ap.add_argument('--hermopolites-id', default=None)
    ap.add_argument('--report', default=None)
    a = ap.parse_args(argv)
    if os.path.abspath(a.input) == os.path.abspath(a.output) or os.path.realpath(a.output).startswith('/var/www'):
        sys.exit('OUTPUT must differ from INPUT and may not be under /var/www')
    old_cw = {r['tm_place_id']: r['pleiades_id'] for r in L.load_crosswalk_rows(a.old_crosswalk)}
    new_cw = {r['tm_place_id']: r['pleiades_id'] for r in L.load_crosswalk_rows(a.repaired)}
    ro = sqlite3.connect('file:%s?mode=ro' % a.input, uri=True)
    changes, counts = plan(ro, old_cw, new_cw, load_fill(a.fill), a.hermopolites_id)
    ro.close()
    shutil.copyfile(a.input, a.output)
    c = sqlite3.connect(a.output)
    before = c.execute("SELECT COUNT(*) FROM documents WHERE pleiades_id IS NOT NULL AND pleiades_id != ''").fetchone()[0]
    c.executemany('UPDATE documents SET pleiades_id = ? WHERE id = ?', [(v[0], k) for k, v in changes.items()])
    c.commit()
    after = c.execute("SELECT COUNT(*) FROM documents WHERE pleiades_id IS NOT NULL AND pleiades_id != ''").fetchone()[0]
    ok = c.execute('PRAGMA integrity_check').fetchone()[0]
    rows = c.execute('SELECT COUNT(*) FROM documents').fetchone()[0]
    c.close()
    counts.update({'documents_with_pleiades_id_before': before, 'after': after, 'rows': rows, 'integrity_check': ok})
    if a.report:
        with open(a.report, 'w', encoding='utf-8') as f:
            json.dump({'counts': counts, 'changes': {k: list(v) for k, v in changes.items()}}, f)
    print(json.dumps(counts, indent=1))
    return 0


if __name__ == '__main__':
    sys.exit(main())
