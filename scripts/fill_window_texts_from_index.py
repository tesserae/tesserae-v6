#!/usr/bin/env python3
"""Fill the passage text the vernacular batch never got.

3,317 Italian, 2,217 Middle High German and 933 Old French windows were
described and embedded, so they answer Theme Search, but no row was ever
written to window_texts.db: the batch skipped scripts/build_window_texts.py,
and its window files no longer exist. The .tess sources do exist and are
public, so the rows can be rebuilt from the index's own ref_start/ref_end using
the builder's slicing, which is also what keeps verse as verse rather than
running the lines together as prose.

Inserts only ids that are missing. Existing rows are never touched.
"""
import json, os, sqlite3, sys

sys.path.insert(0, '/home/ncoffee/tesserae-scene/scripts')
from build_window_texts import _tess_index, _lines_of

INDEX = '/var/www/tesseraev6_flask/data/passage_index/'
DB = INDEX + 'window_texts.db'
LANGS = ('it', 'gmh', 'fro')

con = sqlite3.connect(DB)
have = {r[0] for r in con.execute('SELECT id FROM window_texts')}
want = []
for line in open(INDEX + 'descriptions.jsonl', encoding='utf-8'):
    r = json.loads(line)
    if r.get('language') in LANGS and r['id'] not in have:
        want.append(r)
print('windows missing text: %d' % len(want))
by_work = {}
for r in want:
    by_work.setdefault(r.get('work'), []).append(r)
print('works: %d' % len(by_work))

files = _tess_index()
ins, skipped, nofile = [], 0, []
for work, rows in by_work.items():
    path = files.get(work)
    if not path:
        nofile.append(work)
        continue
    lines = _lines_of(path)
    at = {ref: i for i, (ref, _t) in enumerate(lines)}
    for r in rows:
        i, j = at.get(r.get('ref_start')), at.get(r.get('ref_end'))
        if i is None or j is None or j < i:
            skipped += 1
            continue
        ins.append((r['id'], r.get('language'), work, r.get('ref_start'),
                    r.get('ref_end'), '\n'.join(t for _ref, t in lines[i:j + 1])))
print('rows to insert : %d' % len(ins))
print('refs not found : %d' % skipped)
if nofile:
    print('works with no .tess: %d  %s' % (len(nofile), nofile[:5]))
if ins and '--apply' in sys.argv:
    con.executemany('INSERT OR IGNORE INTO window_texts VALUES (?,?,?,?,?,?)', ins)
    con.commit()
    print('inserted; window_texts now holds %d rows'
          % con.execute('SELECT count(*) FROM window_texts').fetchone()[0])
else:
    print('(dry run; pass --apply to write)')
