#!/usr/bin/env python3
"""Rebuild a language index's lemma_doc_freq table with the CANONICAL rule,
on a copy, then swap the copy in with a dated backup.

The canonical rule is scripts/build_inverted_index.build_lemma_doc_freq:
book files (homer.iliad.part.3.tess) collapse to their base work
(homer.iliad.tess), so a lemma counts once per WORK however many files hold
it. It is the same expression the app falls back to at run time
(_base_filename_expr in backend/blueprints/hapax.py). Any script that
deletes from or rebuilds this table must call that function; a plain
COUNT(DISTINCT text_id) over postings counts every file and inflates
document frequency for every partitioned work (this happened on
2026-09-12 and was corrected on 2026-09-13).

    cd /var/www/tesseraev6_flask
    venv/bin/python scripts/corpus/rebuild_docfreq.py --language la [--apply]

Dry run reports the document count under the rule and a few sample df
values; --apply copies the database, rebuilds the table there, VACUUMs,
renames the old file to <db>.bak-docfreq-<stamp> and the copy into place.
Then `touch tesseraev6_flask.wsgi`.
"""
import argparse
import os
import shutil
import sqlite3
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, ROOT)
from scripts.build_inverted_index import build_lemma_doc_freq  # noqa: E402

BASE = ("CASE WHEN instr(filename,'.part.')>0 "
        "THEN substr(filename,1,instr(filename,'.part.')-1)||'.tess' ELSE filename END")
SAMPLE = {'la': ['et', 'qui', 'aether', 'hospitium', 'togatus'], 'grc': ['και', 'δε', 'θυμος', 'ξιφος']}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', default=ROOT)
    ap.add_argument('--language', required=True)
    ap.add_argument('--apply', action='store_true')
    a = ap.parse_args()
    db = os.path.join(a.root, 'data', 'inverted_index', f'{a.language}_index.db')
    con = sqlite3.connect(f'file:{db}?mode=ro', uri=True)
    n_files = con.execute('select count(*) from texts').fetchone()[0]
    n_works = con.execute(f'select count(distinct {BASE}) from texts').fetchone()[0]
    before = {l: con.execute('select df from lemma_doc_freq where lemma=?', (l,)).fetchone()
              for l in SAMPLE.get(a.language, [])}
    con.close()
    print(f'{db}: {n_files} files, {n_works} works under the canonical rule; sample df before: '
          + ', '.join(f'{l}={v[0] if v else None}' for l, v in before.items()))
    if not a.apply:
        print('dry run; pass --apply to rebuild on a copy and swap'); return
    stamp = time.strftime('%Y%m%d-%H%M%S')
    new = db + '.new'
    shutil.copy2(db, new)
    c = sqlite3.connect(new)
    build_lemma_doc_freq(c)
    after = {l: c.execute('select df from lemma_doc_freq where lemma=?', (l,)).fetchone()
             for l in SAMPLE.get(a.language, [])}
    assert c.execute('pragma integrity_check').fetchone()[0] == 'ok'
    c.execute('VACUUM'); c.close()
    os.replace(db, f'{db}.bak-docfreq-{stamp}')
    os.replace(new, db)
    print(f'swapped; backup {os.path.basename(db)}.bak-docfreq-{stamp}; sample df after: '
          + ', '.join(f'{l}={v[0] if v else None}' for l, v in after.items()))
    print('now: touch tesseraev6_flask.wsgi')


if __name__ == '__main__':
    main()
