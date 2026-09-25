#!/usr/bin/env python3
"""Rename a work inside the passage index, keeping its descriptions.

Renaming a `.tess` file renames the work everywhere the passage index refers
to it, and the index refers to it in four places at once: the window ids
(`<work>:<scale>:<n>`), the `work` and reference fields of every description,
and the `work` and `ref` columns of `window_texts.db`. Miss one and the
Reader asks for the new name, finds nothing, and the descriptions that were
paid for sit unreachable under the old one.

This came up on 2026-09-23 renaming eleven works of Archimedes off a French
form of his name (`archimède`) onto `archimedes`, which PR #474 did in the
corpus. The pull request called for a Greek index rebuild and was right, but
said nothing about the passage index, where 181 windows, 823 line rows and
181 descriptions carried the old name. Describing them again would have cost
real money for text that had not changed.

WHAT IS NOT TOUCHED: `embeddings.npy`. A rename does not move a row, and the
id at position i still names the vector at position i, so the matrix is left
exactly as it is. The count is asserted before and after all the same.

The match is on the work prefix, so `archimède.arenarius` moves and
`archimedes.fragmenta` is left alone. References are rewritten too, because
the line tags inside a renamed `.tess` file carry the work name
(`<archimède.arenarius 1>` becomes `<archimedes.arenarius 1>`).

Dry run by default, like every script that writes under data/.

    ./venv/bin/python3 scripts/corpus/rename_work_in_passage_index.py \\
        --index data/passage_index --from 'archimède' --to archimedes
    ... --apply
"""
import argparse
import json
import os
import shutil
import sqlite3
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

from scripts.corpus.corpus_safety import add_apply_argument  # noqa: E402


def renamed(value, old, new):
    """`old.foo` becomes `new.foo`; anything else is returned unchanged.

    Matching on `old + '.'` is what keeps `archimedes.fragmenta` out of a
    rename of `archimède`, and what stops a shorter name matching inside a
    longer one.
    """
    if not isinstance(value, str):
        return value
    prefix = old + '.'
    if value.startswith(prefix):
        return new + '.' + value[len(prefix):]
    return value


def count_affected(index, old):
    prefix = old + '.'
    ids = json.load(open(os.path.join(index, 'ids.json'), encoding='utf-8'))
    n_ids = sum(1 for i in ids if i.startswith(prefix))
    n_desc = 0
    with open(os.path.join(index, 'descriptions.jsonl'), encoding='utf-8') as fh:
        for line in fh:
            try:
                r = json.loads(line)
            except ValueError:
                continue
            if str(r.get('work', '')).startswith(prefix):
                n_desc += 1
    db = os.path.join(index, 'window_texts.db')
    con = sqlite3.connect(f'file:{db}?mode=ro', uri=True)
    n_win, = con.execute(
        'SELECT COUNT(*) FROM window_texts WHERE work LIKE ?', (prefix + '%',)
    ).fetchone()
    n_lines, = con.execute(
        'SELECT COUNT(*) FROM lines WHERE work LIKE ?', (prefix + '%',)
    ).fetchone()
    con.close()
    return {'ids': n_ids, 'descriptions': n_desc,
            'windows': n_win, 'line rows': n_lines}


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    p.add_argument('--index', required=True, help='the passage_index directory')
    p.add_argument('--from', dest='old', required=True,
                   help='the work prefix to rename, without a trailing dot')
    p.add_argument('--to', dest='new', required=True, help='its new form')
    p.add_argument('--tag', default='rename', help='backup tag')
    add_apply_argument(p, 'write the rename (default: report only)')
    args = p.parse_args(argv)
    index, old, new = args.index, args.old, args.new
    if old == new:
        print('nothing to do: the two names are the same')
        return 0

    before = count_affected(index, old)
    print(f'{old}. -> {new}.')
    for k, v in before.items():
        print(f'  {k:12} {v}')
    if not any(before.values()):
        print('nothing carries that name')
        return 0
    # Renaming onto a name already in use would collide, since the ids are
    # built from the work name and must stay unique. The test is whether a
    # RENAMED id equals an existing one, not whether anything already carries
    # the new prefix: renaming `archimède.arenarius` onto `archimedes` is
    # fine while `archimedes.fragmenta` sits there, because they are
    # different works. Comparing prefixes instead refused that outright.
    existing = set(json.load(open(os.path.join(index, 'ids.json'),
                                  encoding='utf-8')))
    would_be = {renamed(i, old, new) for i in existing
                if i.startswith(old + '.')}
    collisions = sorted(would_be & existing)
    if collisions:
        print(f'REFUSING: {len(collisions)} renamed ids already exist, '
              f'for example {collisions[0]}', file=sys.stderr)
        return 2
    if not args.apply:
        print('\ndry run, nothing written; pass --apply')
        return 0

    stamp = time.strftime('%Y%m%d-%H%M%S')
    for name in ('ids.json', 'descriptions.jsonl', 'window_texts.db'):
        src = os.path.join(index, name)
        shutil.copy2(src, f'{src}.bak-{args.tag}-{stamp}')

    ids_path = os.path.join(index, 'ids.json')
    ids = json.load(open(ids_path, encoding='utf-8'))
    n_before = len(ids)
    ids = [renamed(i, old, new) for i in ids]
    assert len(ids) == n_before, 'the id count must not change'
    tmp = ids_path + '.tmp'
    json.dump(ids, open(tmp, 'w', encoding='utf-8'))
    os.replace(tmp, ids_path)

    desc_path = os.path.join(index, 'descriptions.jsonl')
    tmp = desc_path + '.tmp'
    kept = 0
    with open(tmp, 'w', encoding='utf-8') as out:
        for line in open(desc_path, encoding='utf-8'):
            try:
                r = json.loads(line)
            except ValueError:
                out.write(line)
                kept += 1
                continue
            for field in ('id', 'work', 'ref_start', 'ref_end'):
                if field in r:
                    r[field] = renamed(r[field], old, new)
            out.write(json.dumps(r, ensure_ascii=False) + '\n')
            kept += 1
    os.replace(tmp, desc_path)

    db = os.path.join(index, 'window_texts.db')
    con = sqlite3.connect(db)
    like = old + '.%'
    cut = len(old) + 1
    con.execute(
        'UPDATE window_texts SET work = ? || substr(work, ?), '
        'id = CASE WHEN id LIKE ? THEN ? || substr(id, ?) ELSE id END, '
        'ref_start = CASE WHEN ref_start LIKE ? THEN ? || substr(ref_start, ?) '
        '                 ELSE ref_start END, '
        'ref_end = CASE WHEN ref_end LIKE ? THEN ? || substr(ref_end, ?) '
        '               ELSE ref_end END '
        'WHERE work LIKE ?',
        (new + '.', cut + 1, like, new + '.', cut + 1,
         like, new + '.', cut + 1, like, new + '.', cut + 1, like))
    con.execute(
        'UPDATE lines SET work = ? || substr(work, ?), '
        'ref = CASE WHEN ref LIKE ? THEN ? || substr(ref, ?) ELSE ref END '
        'WHERE work LIKE ?',
        (new + '.', cut + 1, like, new + '.', cut + 1, like))
    con.commit()
    con.close()

    after_old = count_affected(index, old)
    after_new = count_affected(index, new)
    print(f'\ndescriptions rewritten: {kept} rows kept')
    print('left under the old name:', after_old)
    print('now under the new name: ', after_new)
    assert not any(after_old.values()), 'something still carries the old name'
    ids2 = json.load(open(ids_path, encoding='utf-8'))
    assert len(ids2) == n_before, 'the id count changed'
    print(f'ids still {len(ids2):,}; embeddings.npy untouched')
    print(f'backups *.bak-{args.tag}-{stamp}')
    print('\nREMEMBER: descriptions.jsonl changed, so rebuild desc_fts.sqlite '
          '(scripts/build_desc_fts.py), and the Reader margin cache is keyed '
          'on ids.json, so it needs recomputing.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
