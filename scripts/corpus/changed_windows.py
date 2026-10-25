#!/usr/bin/env python3
"""Which passage windows change when some .tess files are replaced by corrected copies?

    changed_windows.py --db window_texts.db --ids ids.json --old-dir texts/grc --new-dir NEWDIR \
        --files FILELIST --out OUTDIR [--language grc]

Reads (never writes) a window_texts.db and the passage index's ids.json. For each file in FILELIST it
rebuilds the fine and coarse windows (build_batch_windows.windows_for) and, for a work that has prose windows in
the database, the prose windows (prose_windows.windows_for_file, merged, 1200 characters) from the new file, and
compares them with the stored rows by id. Writes to OUTDIR:
  windows_new.jsonl     every rebuilt window row of the listed files (id, language, work, ref_start, ref_end, text, scale)
  windows_changed.jsonl rebuilt rows whose id is new or whose text differs from the stored row
  windows_to_describe.jsonl  windows_changed.jsonl as the describer reads it (fine and coarse text cut at 1,400 characters,
                        as the 2026-10-24 run did)
  windows_gone.json     stored ids of those works with no rebuilt window of the same id
  changed_report.json   counts per work: stored, rebuilt, text changed, new ids, gone ids, and how many of the
                        changed ids are in the passage index (ids.json), that is, already described and encoded
Window ids end in an index (":prosem:<n>"), so when an edit shifts a window boundary the ids after it can change;
a text that moves to another id is counted under new and gone, not as unchanged.
"""
import argparse
import collections
import json
import os
import sqlite3
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import build_batch_windows as BW   # noqa: E402
import prose_windows as PW         # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--db', required=True)
    ap.add_argument('--ids', required=True)
    ap.add_argument('--new-dir', required=True)
    ap.add_argument('--files', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--language', default='grc')
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    con = sqlite3.connect(f'file:{a.db}?mode=ro', uri=True)
    indexed = set(json.load(open(a.ids)))
    files = [l.strip() for l in open(a.files) if l.strip()]
    works = [f[:-5] for f in files]
    stored = collections.defaultdict(dict)
    for w in works:
        for i, t in con.execute('SELECT id, text FROM window_texts WHERE work = ?', (w,)):
            stored[w][i] = t
    new_rows, changed, gone, report = [], [], {}, {}
    for f in files:
        w = f[:-5]
        path = os.path.join(a.new_dir, f)
        old = stored[w]
        if not old:
            report[f] = dict(stored=0, skipped='no window rows stored for this file (a whole work whose windows belong to its parts)')
            continue
        built = {}
        for x in BW.windows_for(path, a.language, {}, {}, 0, 4):
            built[x['id']] = dict(id=x['id'], language=a.language, work=w, scale=x['scale'],
                                  ref_start=x['ref_start'], ref_end=x['ref_end'], text=x['text'])
        if any(':prosem:' in i or ':prose:' in i for i in old):
            wins, _skipped = PW.windows_for_file(a.language, w, path, 1200, 40, True)
            for x in wins:
                built[x['id']] = dict(id=x['id'], language=a.language, work=w, scale='prose',
                                      ref_start=x['ref_start'], ref_end=x['ref_end'], text=x['text'],
                                      **{k: x[k] for k in ('sub', 'char_start', 'char_end', 'units') if k in x})
        new_rows += built.values()
        txt = [i for i, r in built.items() if i in old and old[i] != r['text']]
        new = [i for i in built if i not in old]
        gn = [i for i in old if i not in built]
        changed += [built[i] for i in txt + new]
        gone[w] = gn
        report[f] = dict(stored=len(old), rebuilt=len(built), text_changed=len(txt), new_ids=len(new), gone_ids=len(gn),
                         changed_in_index=sum(1 for i in txt + new if i in indexed),
                         gone_in_index=sum(1 for i in gn if i in indexed))
    with open(os.path.join(a.out, 'windows_new.jsonl'), 'w', encoding='utf-8') as fh:
        for r in new_rows:
            fh.write(json.dumps(r, ensure_ascii=False) + '\n')
    with open(os.path.join(a.out, 'windows_changed.jsonl'), 'w', encoding='utf-8') as fh:
        for r in changed:
            fh.write(json.dumps(r, ensure_ascii=False) + '\n')
    with open(os.path.join(a.out, 'windows_to_describe.jsonl'), 'w', encoding='utf-8') as fh:
        for r in changed:
            d = dict(r)
            if d['scale'] != 'prose':
                d['text'] = d['text'][:1400]
            fh.write(json.dumps(d, ensure_ascii=False) + '\n')
    json.dump(gone, open(os.path.join(a.out, 'windows_gone.json'), 'w'), ensure_ascii=False)
    json.dump(report, open(os.path.join(a.out, 'changed_report.json'), 'w'), indent=1)
    tot = collections.Counter()
    for r in report.values():
        tot.update({k: v for k, v in r.items() if isinstance(v, int)})
    print(dict(tot))


if __name__ == '__main__':
    main()
