#!/usr/bin/env python3
"""Drop a work's whole-file windows from the passage index once its book files
carry their own.

Works stored both as one file and as book files (`vergil.aeneid.tess` beside
`vergil.aeneid.part.1.tess` and so on) were indexed twice, so the same lines
sat in the index under two names. On 2026-09-27 that was 137 works, 113,850
whole-file windows against 112,185 book-file windows, a third of the index.
A passage could then appear twice in a Similar Passages list, once under each
name, and every corpus-wide figure counted those works double. The book files
are the canonical copies (docs/DECISIONS.md), so their windows stay and the
whole file's go.

WHAT THE READER SEES AFTERWARDS. The whole-work view keeps its gutter marks.
`connection_density(work)` already falls back to the work's whole group when
the caller names the whole work and no window carries that exact name
(backend/passage_index.py, tested in tests/test_density_work_name.py), and the
group is keyed by the base work, so the book files' windows answer for the
whole. Their references are the same line references as the whole file's, the
whole having been regenerated from the books, so the marks land on the same
lines. Reader selections map to windows through the same group.

WHAT IS REFUSED. A work whose book files are not all indexed. A book file with
no windows of its own (a two-line poem, a preface, a fragment) is covered only
by the whole file's windows, so dropping those would leave its lines without
any window at all. Such works are reported and skipped unless
--allow-incomplete is passed. Pass --texts so the check can see the files.
Without it no completeness check is possible and the tool refuses to apply.

WHAT IS TOUCHED. ids.json, embeddings.npy (rows dropped, order otherwise kept),
descriptions.jsonl (records dropped), and the `window_texts` rows of the
dropped windows. The `lines` table is left alone, because the whole work's
line rows serve the Reader's text and /passages/lines and are not windows. Every file
is backed up first as `<name>.bak-<tag>-<stamp>`, which the pruning rule in
scripts/prune_backups.py recognises.

WHAT MUST FOLLOW. The index fingerprint (size and mtime of ids.json and
embeddings.npy) changes, so every cache keyed on it is invalid. Rebuild the
word index (scripts/build_desc_fts.py), rerun the passage density job
(scripts/precompute_passage_density.py) and the connections map
(scripts/build_connections_map.py), then reload the app.

Dry run by default, like every script that writes under data/.

    ./venv/bin/python3 scripts/corpus/drop_whole_file_windows.py \\
        --index data/passage_index --texts texts
    ... --apply --tag whole-windows-20260928
"""
import argparse
import glob
import json
import os
import shutil
import sqlite3
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

from backend.work_names import base_work, is_part  # noqa: E402
from scripts.corpus.corpus_safety import add_apply_argument  # noqa: E402


def work_of(window_id):
    return window_id.split(':', 1)[0]


def missing_books(base, indexed_parts, texts_root):
    """Book files of `base` on disk that have no windows in the index.

    The whole file's language directory is found by the whole file itself, so a
    work filed under two languages (a translation stored beside its original)
    is checked in both.
    """
    missing = []
    for whole in glob.glob(os.path.join(texts_root, '*', base + '.tess')):
        folder = os.path.dirname(whole)
        for path in glob.glob(os.path.join(folder, base + '.part.*.tess')):
            name = os.path.basename(path)[:-len('.tess')]
            if name not in indexed_parts:
                missing.append(name)
    return sorted(missing)


def plan(ids, texts_root):
    """Which whole works can go, and which must stay and why.

    Returns (drop, skipped): `drop` is the sorted list of whole works whose
    book files are all indexed, `skipped` maps a whole work to the book files
    it is still covering for. With no texts root nothing can be checked, and
    every candidate is reported as unverified.
    """
    works = {work_of(i) for i in ids}
    parts_by_base = {}
    for w in works:
        if is_part(w):
            parts_by_base.setdefault(base_work(w), set()).add(w)
    drop, skipped = [], {}
    for base in sorted(parts_by_base):
        if base not in works:
            continue
        if texts_root is None:
            skipped[base] = ['(no --texts given, completeness unchecked)']
            continue
        missing = missing_books(base, parts_by_base[base], texts_root)
        if missing:
            skipped[base] = missing
        else:
            drop.append(base)
    return drop, skipped


def count_rows(index, works):
    marks = ','.join('?' * len(works))
    con = sqlite3.connect(f"file:{os.path.join(index, 'window_texts.db')}?mode=ro",
                          uri=True)
    n_win, = con.execute(
        f'SELECT COUNT(*) FROM window_texts WHERE work IN ({marks})',  # nosec B608
        works).fetchone()
    con.close()
    return n_win


def apply(index, drop, tag):
    import numpy as np
    drop_set = set(drop)
    stamp = time.strftime('%Y%m%d-%H%M%S')
    for name in ('ids.json', 'embeddings.npy', 'descriptions.jsonl',
                 'window_texts.db'):
        src = os.path.join(index, name)
        shutil.copy2(src, f'{src}.bak-{tag}-{stamp}')

    ids_path = os.path.join(index, 'ids.json')
    ids = json.load(open(ids_path, encoding='utf-8'))
    keep = [i for i, wid in enumerate(ids) if work_of(wid) not in drop_set]
    n_before = len(ids)

    emb_path = os.path.join(index, 'embeddings.npy')
    emb = np.load(emb_path, mmap_mode='r')
    assert emb.shape[0] == n_before, \
        f'embeddings hold {emb.shape[0]} rows for {n_before} ids'
    # Fancy indexing on the memory map reads only the kept rows, so this holds
    # one copy of the new matrix, not two of the old one.
    kept_emb = np.ascontiguousarray(emb[keep])
    tmp = emb_path + '.tmp.npy'
    np.save(tmp, kept_emb)
    del kept_emb, emb

    desc_path = os.path.join(index, 'descriptions.jsonl')
    desc_tmp = desc_path + '.tmp'
    n_desc_dropped = 0
    with open(desc_tmp, 'w', encoding='utf-8') as out:
        for line in open(desc_path, encoding='utf-8'):
            try:
                r = json.loads(line)
            except ValueError:
                out.write(line)
                continue
            if str(r.get('work', '')) in drop_set:
                n_desc_dropped += 1
                continue
            out.write(line)

    ids_tmp = ids_path + '.tmp'
    json.dump([ids[i] for i in keep], open(ids_tmp, 'w', encoding='utf-8'))

    # All three written in full before any is moved into place, so a failure
    # above leaves the live index untouched.
    os.replace(tmp, emb_path)
    os.replace(desc_tmp, desc_path)
    os.replace(ids_tmp, ids_path)

    con = sqlite3.connect(os.path.join(index, 'window_texts.db'))
    marks = ','.join('?' * len(drop))
    cur = con.execute(
        f'DELETE FROM window_texts WHERE work IN ({marks})', drop)  # nosec B608
    n_win = cur.rowcount
    con.commit()
    con.close()

    after = json.load(open(ids_path, encoding='utf-8'))
    emb2 = np.load(emb_path, mmap_mode='r')
    assert len(after) == len(keep) == emb2.shape[0], \
        f'ids {len(after)}, kept {len(keep)}, embedding rows {emb2.shape[0]}'
    assert not any(work_of(w) in drop_set for w in after)
    return {'windows before': n_before, 'windows after': len(after),
            'windows dropped': n_before - len(after),
            'descriptions dropped': n_desc_dropped,
            'window_texts rows dropped': n_win, 'stamp': stamp}


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    p.add_argument('--index', required=True, help='the passage_index directory')
    p.add_argument('--texts', default=None,
                   help='the texts directory, for the completeness check')
    p.add_argument('--allow-incomplete', action='store_true',
                   help='drop a whole work even when a book file of it has no windows')
    p.add_argument('--tag', default='whole-windows', help='backup tag')
    add_apply_argument(p, 'write the change (default: report only)')
    args = p.parse_args(argv)

    ids = json.load(open(os.path.join(args.index, 'ids.json'), encoding='utf-8'))
    drop, skipped = plan(ids, args.texts)
    if args.allow_incomplete:
        drop = sorted(set(drop) | set(skipped))
        skipped = {}
    n_windows = sum(1 for i in ids if work_of(i) in set(drop))
    print(f'{len(ids)} windows in the index')
    print(f'{len(drop)} whole works to drop, {n_windows} windows')
    for w in drop:
        print(f'  drop  {w}')
    if skipped:
        print(f'{len(skipped)} whole works kept, a book file of each has no windows:')
        for w, books in sorted(skipped.items()):
            print(f'  keep  {w}: ' + ', '.join(books))
    if args.texts is None and not args.allow_incomplete and skipped:
        print('\nREFUSING to apply without --texts: no completeness check is '
              'possible. Pass --texts, or --allow-incomplete to drop anyway.',
              file=sys.stderr)
        return 2 if args.apply else 0
    if not drop:
        print('nothing to do')
        return 0
    print(f'{count_rows(args.index, drop)} window_texts rows would go with them')
    if not args.apply:
        print('\ndry run, nothing written. Pass --apply to write.')
        return 0
    result = apply(args.index, drop, args.tag)
    for k, v in result.items():
        print(f'  {k:26} {v}')
    print('\nThe index fingerprint has changed. Rebuild desc_fts.sqlite '
          '(scripts/build_desc_fts.py), rerun the density job and the '
          'connections map, then reload the app.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
