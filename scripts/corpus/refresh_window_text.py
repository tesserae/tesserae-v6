#!/usr/bin/env python3
"""Update the stored wording of passage windows from the corpus files.

WHAT THIS IS FOR, AND WHAT IT DELIBERATELY IS NOT.

The passage index keeps, for every window, the text of its lines, and that
text is what the site quotes in Similar Passages and Theme Search. When a
corpus file is corrected the stored copy goes stale. Rebuilding the index
properly means describing every window through a language model again, which
is the expensive part; this does not do that, and must not be used when the
words have changed enough to change what a passage MEANS.

It is for the case measured on 2026-09-22: of 5,980 windows across the works
corrected the night before, 353 differed, and the differences were
punctuation (curly quotation marks made straight in Ovid, elision marks and
editorial brackets in Arrian). The descriptions and the embeddings computed
from those windows remain valid, because the words are the same; only the
quotation shown on screen was out of date.

Dry run by default. Makes a dated copy of window_texts.db before writing.

    python scripts/corpus/refresh_window_text.py --root . --works la/ovid.metamorphoses
    python scripts/corpus/refresh_window_text.py --root . --works-file list.txt --apply
"""
import argparse
import os
import re
import shutil
import sqlite3
import time
import unicodedata

LINE = re.compile(r'^<([^>]*)>\s*(.*)$')


def file_lines(root, lang, name):
    """ref -> text, in file order, plus the order of refs."""
    path = os.path.join(root, 'texts', lang, name)
    out, order = {}, []
    if not os.path.exists(path):
        return out, order
    with open(path, encoding='utf-8', errors='replace') as fh:
        for raw in fh:
            m = LINE.match(raw)
            if m:
                ref = m.group(1).strip()
                out[ref] = m.group(2).rstrip('\n')
                order.append(ref)
    return out, order


def norm(s):
    return unicodedata.normalize('NFC', ' '.join(s.split()))


def refresh(root, works, apply_):
    db_path = os.path.join(root, 'data', 'passage_index', 'window_texts.db')
    if apply_:
        stamp = time.strftime('%Y%m%d-%H%M%S')
        shutil.copy2(db_path, f'{db_path}.bak-textrefresh-{stamp}')
        print(f'  backup: window_texts.db.bak-textrefresh-{stamp}')
    con = sqlite3.connect(db_path)
    windows_changed = lines_changed = 0

    for entry in works:
        lang, name = entry.split('/', 1)
        if not name.endswith('.tess'):
            name += '.tess'
        work = name[:-5]
        current, order = file_lines(root, lang, name)
        if not current:
            print(f'  {work}: no such file, skipped')
            continue

        # the lines table first: one row per line
        for ref, text in current.items():
            row = con.execute('SELECT text FROM lines WHERE work=? AND ref=?',
                              (work, ref)).fetchone()
            if row and norm(row[0]) != norm(text):
                lines_changed += 1
                if apply_:
                    con.execute('UPDATE lines SET text=? WHERE work=? AND ref=?',
                                (text, work, ref))

        # then each window, rebuilt from its own span of lines
        rows = con.execute('SELECT id, ref_start, ref_end, text FROM window_texts '
                           'WHERE work=?', (work,)).fetchall()
        index = {ref: i for i, ref in enumerate(order)}
        for wid, rs, re_, stored in rows:
            if rs not in index or re_ not in index:
                continue
            span = order[index[rs]: index[re_] + 1]
            rebuilt = '\n'.join(current[r] for r in span)
            if norm(rebuilt) != norm(stored):
                windows_changed += 1
                if apply_:
                    con.execute('UPDATE window_texts SET text=? WHERE id=?', (rebuilt, wid))
        print(f'  {work}: {len(rows)} windows examined')

    if apply_:
        con.commit()
    con.close()
    print(f'{windows_changed} window(s) and {lines_changed} line(s) '
          f'{"updated" if apply_ else "would be updated"}')
    return windows_changed


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--root', default='.')
    ap.add_argument('--works', nargs='*', default=[], help='e.g. la/ovid.metamorphoses')
    ap.add_argument('--works-file', help='a file of the same, one per line')
    ap.add_argument('--apply', action='store_true')
    args = ap.parse_args()
    works = list(args.works)
    if args.works_file:
        works += [l.strip() for l in open(args.works_file) if l.strip()]
    print('APPLY' if args.apply else 'DRY RUN')
    refresh(args.root, works, args.apply)


if __name__ == '__main__':
    main()
