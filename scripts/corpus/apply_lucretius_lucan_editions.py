#!/usr/bin/env python3
"""Downstream repair for the 2026-09-13 edition change (Lucretius book files
regenerated from the Perseus whole with "lucr. N.L" tags; six Lucan
misreadings corrected in the whole file). The text files come from git;
this script brings the stores that copied the old text or the old tags into
line, on the production root, dry run by default.

    cd /var/www/tesseraev6_flask
    venv/bin/python scripts/corpus/apply_lucretius_lucan_editions.py [--apply]

Steps (each reported; --apply writes, with dated backups):
  1. passage index: descriptions.jsonl and window_texts.db rows of the
     whole Lucretius get their refs renamed "lucr. de_r. X" -> "lucr. X";
     the six book works get their line texts replaced from the new files
     (windows keep their locus ranges: the Perseus and Latin Library
     lineation agree except for a few lines at book ends).
  2. translation map data/translations/la__lucretius.de_rerum_natura.json:
     the "lucr. de_r." key family, aligned to the Perseus whole, becomes
     the "lucr." family; the old plain family (aligned to the Latin Library
     book files) is dropped first so nothing collides.
  3. cached fusion results naming any of the eight texts are deleted.
Not done here (run separately, in this order, before this script):
  scripts/batch_lemma_cache.py la          (rebuilds the eight stale caches)
  scripts/corpus/add_texts_to_index.py --replace <eight files> on a copy of
     la_index.db, then swap; it rebuilds lemma_doc_freq canonically.
After this script: scripts/corpus/rebuild_bigrams.py la, then
  touch tesseraev6_flask.wsgi and the reference checks.
"""
import glob
import json
import os
import shutil
import sqlite3
import sys
import time

ROOT = os.getcwd()
APPLY = '--apply' in sys.argv
STAMP = time.strftime('%Y%m%d-%H%M%S')
WHOLE = 'lucretius.de_rerum_natura'
PARTS = [f'{WHOLE}.part.{i}' for i in range(1, 7)]
OLD, NEW = 'lucr. de_r. ', 'lucr. '
TEXTS = [f'{WHOLE}.tess', 'lucan.bellum_civile.tess'] + [p + '.tess' for p in PARTS]


def backup(path):
    if APPLY:
        shutil.copy2(path, f'{path}.bak-editions-{STAMP}')


def units(path):
    out = []
    for line in open(path, encoding='utf-8'):
        if line.startswith('<') and '>' in line:
            e = line.index('>')
            out.append((line[1:e].strip(), line[e + 1:].strip()))
    return out


def passage_index():
    dpath = os.path.join(ROOT, 'data', 'passage_index', 'descriptions.jsonl')
    n = 0
    out_path = dpath + '.new'
    with open(dpath, encoding='utf-8') as fh, open(out_path, 'w', encoding='utf-8') as out:
        for line in fh:
            if f'"work": "{WHOLE}"' in line and OLD in line:
                r = json.loads(line)
                for k in ('ref_start', 'ref_end'):
                    if r.get(k, '').startswith(OLD):
                        r[k] = NEW + r[k][len(OLD):]
                n += 1
                out.write(json.dumps(r, ensure_ascii=False) + '\n')
            else:
                out.write(line)
    print(f'  descriptions.jsonl: {n} rows of the whole work renamed')
    if APPLY:
        backup(dpath); os.replace(out_path, dpath)
    else:
        os.remove(out_path)
    wdb = os.path.join(ROOT, 'data', 'passage_index', 'window_texts.db')
    c = sqlite3.connect(f'file:{wdb}?mode=ro', uri=True)
    w_rows = c.execute('select rowid, ref_start, ref_end from window_texts where work=?', (WHOLE,)).fetchall()
    l_rows = c.execute('select rowid, ref from lines where work=?', (WHOLE,)).fetchall()
    part_counts = {p: c.execute('select count(*) from lines where work=?', (p,)).fetchone()[0] for p in PARTS}
    c.close()
    w_upd = [(NEW + a[len(OLD):] if a.startswith(OLD) else a, NEW + b[len(OLD):] if b.startswith(OLD) else b, rid)
             for rid, a, b in w_rows if a.startswith(OLD) or b.startswith(OLD)]
    l_upd = [(NEW + r[len(OLD):], rid) for rid, r in l_rows if r.startswith(OLD)]
    print(f'  window_texts.db: whole work {len(w_upd)} windows and {len(l_upd)} lines renamed')
    new_lines = {p: units(os.path.join(ROOT, 'texts', 'la', p + '.tess')) for p in PARTS}
    for p in PARTS:
        print(f'  window_texts.db: {p}: {part_counts[p]} stored lines -> {len(new_lines[p])} from the new file')
    if not APPLY:
        return
    new = wdb + '.new'
    shutil.copy2(wdb, new)
    c = sqlite3.connect(new)
    c.executemany('update window_texts set ref_start=?, ref_end=? where rowid=?', w_upd)
    c.executemany('update lines set ref=? where rowid=?', l_upd)
    for p in PARTS:
        c.execute('delete from lines where work=?', (p,))
        c.executemany('insert into lines (work, ord, ref, text) values (?,?,?,?)',
                      [(p, i, ref, text) for i, (ref, text) in enumerate(new_lines[p])])
    c.commit(); c.close()
    os.replace(wdb, f'{wdb}.bak-editions-{STAMP}'); os.replace(new, wdb)


def translation_map():
    path = os.path.join(ROOT, 'data', 'translations', f'la__{WHOLE}.json')
    if not os.path.exists(path):
        print('  translation map: none'); return
    d = json.load(open(path, encoding='utf-8'))
    r2u = d.get('ref_to_unit') or {}
    old_family = {k: v for k, v in r2u.items() if k.startswith(OLD)}
    plain = {k: v for k, v in r2u.items() if not k.startswith(OLD)}
    renamed = {NEW + k[len(OLD):]: v for k, v in old_family.items()}
    print(f'  translation map: {len(plain)} plain keys dropped, {len(old_family)} Perseus-aligned keys renamed')
    if APPLY:
        backup(path)
        d['ref_to_unit'] = renamed
        tmp = path + '.new'
        json.dump(d, open(tmp, 'w', encoding='utf-8'), ensure_ascii=False)
        os.replace(tmp, path)


def fusion_cache():
    names = set(TEXTS) | {t[:-5] for t in TEXTS}
    hit = []
    for p in glob.glob(os.path.join(ROOT, 'cache', '*.json')):
        try:
            d = json.load(open(p, encoding='utf-8'))
        except Exception:
            continue
        if isinstance(d, dict) and (d.get('source') in names or d.get('target') in names):
            hit.append(p)
    print(f'  fusion cache: {len(hit)} cached results involve the eight texts')
    if APPLY:
        for p in hit:
            os.remove(p)


if __name__ == '__main__':
    print(('APPLY' if APPLY else 'DRY RUN') + ' on ' + ROOT)
    first = units(os.path.join(ROOT, 'texts', 'la', WHOLE + '.tess'))[0][0]
    if not first.startswith(NEW) or first.startswith(OLD):
        raise SystemExit('the whole-work file still carries the old tags; pull the merged texts first')
    passage_index(); translation_map(); fusion_cache()
