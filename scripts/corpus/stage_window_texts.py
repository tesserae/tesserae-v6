#!/usr/bin/env python3
"""Stage the window_texts.db rows of newly imported files on a COPY.

Three kinds of row, as the earlier installs wrote them:
  - `lines` rows (work, i, ref, text) for every new file, whole files and parts,
    and a refresh of the `lines` rows of a replaced work (--lines-only);
  - fine and coarse window rows (build_batch_windows.windows_for) for the files
    the windows belong to (part files, or the single file of a work without parts);
  - the prose window rows are added afterwards with
    prose_windows.py --upsert-db DB --upsert-from windows.jsonl.

Usage: stage_window_texts.py --db COPY --index-db la_index.db.new --lemma-table T \
         [--windows-for F ...] [--lines-for F ...] [--lines-only F ...]
Only the copy is written. Always run on a copy of window_texts.db.
"""
import argparse
import os
import sqlite3
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import build_batch_windows as BW  # noqa: E402


def put_lines(cur, path):
    work = os.path.basename(path)[:-5]
    cur.execute('DELETE FROM lines WHERE work = ?', (work,))
    rows = [(work, i, ref, text) for i, (ref, text) in enumerate(BW.tess_lines(path))]
    cur.executemany('INSERT INTO lines VALUES (?,?,?,?)', rows)
    return len(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--db', required=True)
    ap.add_argument('--index-db', required=True)
    ap.add_argument('--lemma-table', required=True)
    ap.add_argument('--language', default='la')
    ap.add_argument('--windows-for', nargs='*', default=[])
    ap.add_argument('--lines-for', nargs='*', default=[])
    ap.add_argument('--lines-only', nargs='*', default=[])
    ap.add_argument('--min-lines', type=int, default=4)
    a = ap.parse_args()
    lemmas, df, n_texts = BW.load_rarity(a.index_db, a.lemma_table)
    con = sqlite3.connect(a.db)
    cur = con.cursor()
    nw = nl = 0
    for p in a.windows_for:
        wins = BW.windows_for(p, a.language, lemmas, df, n_texts, a.min_lines)
        cur.executemany('INSERT OR REPLACE INTO window_texts VALUES (?,?,?,?,?,?)',
                        [(w['id'], w['language'], w['work'], w['ref_start'], w['ref_end'], w['text']) for w in wins])
        nw += len(wins)
        nl += put_lines(cur, p)
    for p in a.lines_for + a.lines_only:
        nl += put_lines(cur, p)
    con.commit()
    tot = cur.execute('SELECT (SELECT COUNT(*) FROM window_texts), (SELECT COUNT(*) FROM lines)').fetchone()
    con.close()
    print(f'fine/coarse rows {nw}, lines rows {nl}; window_texts {tot[0]:,}, lines {tot[1]:,}')


if __name__ == '__main__':
    main()
