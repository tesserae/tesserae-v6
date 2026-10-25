#!/usr/bin/env python3
"""Put the corrected text of replaced .tess files into a COPY of window_texts.db.

    stage_changed_window_texts.py --db COPY --new-dir DIR --files FILELIST \
        --windows windows_new.jsonl --gone windows_gone.json

For every file in FILELIST that has `lines` rows (the installs keep them for whole files only): the rows of the work are deleted and written again from the file in
--new-dir (build_batch_windows.tess_lines, the same reading the installs used). For every row of --windows
(the output of changed_windows.py) the window_texts row is inserted or replaced. Every id of --gone is deleted.
Afterwards each window row of the listed works is compared with --windows and the script exits 1 on a
difference. Only the copy is written; never point --db at the production file.
"""
import argparse
import json
import os
import sqlite3
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import build_batch_windows as BW   # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--db', required=True)
    ap.add_argument('--new-dir', required=True)
    ap.add_argument('--files', required=True)
    ap.add_argument('--windows', required=True)
    ap.add_argument('--gone', required=True)
    a = ap.parse_args()
    if '/var/www/' in os.path.abspath(a.db):
        sys.exit('refusing to write under /var/www')
    files = [l.strip() for l in open(a.files) if l.strip()]
    wins = [json.loads(l) for l in open(a.windows, encoding='utf-8')]
    gone = [i for ids in json.load(open(a.gone)).values() for i in ids]
    con = sqlite3.connect(a.db)
    cur = con.cursor()
    before = cur.execute('SELECT (SELECT COUNT(*) FROM window_texts), (SELECT COUNT(*) FROM lines)').fetchone()
    nl = 0
    for f in files:
        work = f[:-5]
        rows = [(work, i, ref, text) for i, (ref, text) in enumerate(BW.tess_lines(os.path.join(a.new_dir, f)))]
        old = cur.execute('SELECT COUNT(*) FROM lines WHERE work = ?', (work,)).fetchone()[0]
        if not old:
            continue                      # the installs store lines rows for whole files only, not for part files
        if old != len(rows):
            sys.exit(f'{work}: {old} stored lines, {len(rows)} in the new file; references would differ')
        cur.execute('DELETE FROM lines WHERE work = ?', (work,))
        cur.executemany('INSERT INTO lines VALUES (?,?,?,?)', rows)
        nl += len(rows)
    cur.executemany('INSERT OR REPLACE INTO window_texts VALUES (?,?,?,?,?,?)',
                    [(w['id'], w['language'], w['work'], w['ref_start'], w['ref_end'], w['text']) for w in wins])
    cur.executemany('DELETE FROM window_texts WHERE id = ?', [(i,) for i in gone])
    con.commit()
    after = cur.execute('SELECT (SELECT COUNT(*) FROM window_texts), (SELECT COUNT(*) FROM lines)').fetchone()
    stored = {}
    for f in files:
        for i, t in cur.execute('SELECT id, text FROM window_texts WHERE work = ?', (f[:-5],)):
            stored[i] = t
    built = {w['id']: w['text'] for w in wins}
    bad = [i for i in set(stored) | set(built) if stored.get(i) != built.get(i)]
    print(f'window_texts {before[0]:,} -> {after[0]:,} ({len(gone)} deleted), lines {before[1]:,} -> {after[1]:,} '
          f'({nl:,} rewritten); rows differing from the rebuilt windows: {len(bad)}')
    con.close()
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
