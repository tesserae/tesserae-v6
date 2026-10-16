#!/usr/bin/env python3
"""Rename a stale work id in the reuse table and the events store.

The 2026-10-13 rename of the three Libanius oration part files
(`libanius.orations_1-11.part.1` to `libanius.orations.part.1`, and the same
for parts 2 and 3) did not reach two stores, which still name the old ids:

  cache/reuse_pairs/<lang>.db      pairs.work_a, pairs.work_b and
                                   line_counts.work
  data/events/event_dossiers.sqlite  passages.window_id and
                                   judgements.window_id (`<id>:<scale>:<n>`),
                                   and the passages.work of those rows

Use `scripts/corpus/rename_work.py` for a whole rename; use this for a store
pair it missed. The events window-id match is the one rename_work.py uses
(`_WINDOW_MATCH`: the id, then a colon), imported from it. The old `work`
value of an events passage can be a shorter name than the window id's work
(`libanius.orations_1-11` for window `libanius.orations_1-11.part.1:fine:444`),
so the work of every row matched by window id is set to the new id, as the
Events page looks the title up by that id.

    ./venv/bin/python3 scripts/corpus/rename_stale_work_ids.py --root <root> \\
        --rename libanius.orations_1-11.part.1 libanius.orations.part.1 \\
        --rename libanius.orations_26-50.part.2 libanius.orations.part.2 \\
        --rename libanius.orations_51-64.part.3 libanius.orations.part.3
    ... --apply

Dry run by default, with before and after counts per store. With --apply each
store gets a dated `.bak-<tag>-<timestamp>` copy beside it first. REFUSES
(exit 2, nothing written) if a new id already has rows in the same store.
The reuse table is rewritten on a copy and renamed in; the events store is
updated in place after a WAL checkpoint, as rename_work.py does.

Line-reference prefixes are a separate step: scripts/corpus/fix_ref_prefix.py.
"""
import argparse
import glob
import os
import shutil
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

from scripts.corpus.corpus_safety import add_apply_argument, backup  # noqa: E402
from scripts.corpus.rename_work import _WINDOW_MATCH, events_db_path  # noqa: E402


def _ro(path):
    return sqlite3.connect(f'file:{path}?mode=ro', uri=True)


def _one(con, sql, args=()):
    return con.execute(sql, args).fetchone()[0]


# ----------------------------------------------------------------- events

def events_counts(con, old):
    b = {'id': old, 'n': len(old)}
    return {
        'passages (window id)': _one(con, f'SELECT COUNT(*) FROM passages WHERE {_WINDOW_MATCH}', b),
        'passages (work = id)': _one(con, 'SELECT COUNT(*) FROM passages WHERE work = ?', (old,)),
        'judgements (window id)': _one(con, f'SELECT COUNT(*) FROM judgements WHERE {_WINDOW_MATCH}', b),
    }


def events_apply(con, old, new):
    b = {'id': old, 'n': len(old), 'new': new}
    # work first: it is chosen by the window id before that id changes
    con.execute(f'UPDATE passages SET work = :new WHERE {_WINDOW_MATCH}', b)
    con.execute('UPDATE passages SET work = :new WHERE work = :id', b)
    con.execute(f'UPDATE passages SET window_id = :new || substr(window_id, :n + 1) '
                f'WHERE {_WINDOW_MATCH}', b)
    con.execute(f'UPDATE judgements SET window_id = :new || substr(window_id, :n + 1) '
                f'WHERE {_WINDOW_MATCH}', b)


def do_events(root, renames, apply_, tag, rows):
    path = events_db_path(root)
    name = 'events/event_dossiers.sqlite'
    if not os.path.exists(path):
        rows.append((name, 'not present', 0, None))
        return True
    con = _ro(path)
    before = {old: events_counts(con, old) for old, _n in renames}
    clash = {new: events_counts(con, new) for _o, new in renames}
    con.close()
    bad = {n: c for n, c in clash.items() if any(c.values())}
    if bad:
        print(f'REFUSING: new id already has rows in {name}: {bad}', file=sys.stderr)
        return False
    after = {}
    if apply_ and any(any(c.values()) for c in before.values()):
        con = sqlite3.connect(path, timeout=60)
        con.execute('PRAGMA wal_checkpoint(TRUNCATE)')
        con.close()
        backup(path, tag=tag)
        con = sqlite3.connect(path, timeout=60)
        for old, new in renames:
            events_apply(con, old, new)
        con.commit()
        con.execute('PRAGMA wal_checkpoint(TRUNCATE)')
        con.close()
        con = _ro(path)
        after = {old: events_counts(con, old) for old, _n in renames}
        con.close()
    elif apply_:
        after = before and {o: {k: 0 for k in c} for o, c in before.items()}
    for old, _new in renames:
        for k, v in before[old].items():
            a = after[old][k] if apply_ else None
            rows.append((name, f'{old}: {k}', v, a))
    return True


# ------------------------------------------------------------------ reuse

def reuse_counts(con, work):
    return {
        'pairs (work_a)': _one(con, 'SELECT COUNT(*) FROM pairs WHERE work_a = ?', (work,)),
        'pairs (work_b)': _one(con, 'SELECT COUNT(*) FROM pairs WHERE work_b = ?', (work,)),
        'line_counts': _one(con, 'SELECT COUNT(*) FROM line_counts WHERE work = ?', (work,)),
    }


def do_reuse(root, renames, apply_, tag, rows):
    ok = True
    for path in sorted(glob.glob(os.path.join(root, 'cache', 'reuse_pairs', '*.db'))):
        name = 'reuse_pairs/' + os.path.basename(path)
        con = _ro(path)
        try:
            before = {old: reuse_counts(con, old) for old, _n in renames}
            clash = {new: reuse_counts(con, new) for _o, new in renames}
        except sqlite3.Error:
            con.close()
            continue
        con.close()
        if not any(any(c.values()) for c in before.values()):
            continue
        bad = {n: c for n, c in clash.items() if any(c.values())}
        if bad:
            print(f'REFUSING: new id already has rows in {name}: {bad}', file=sys.stderr)
            ok = False
            continue
        after = {}
        if apply_:
            backup(path, tag=tag)
            work = path + '.renaming'
            shutil.copy2(path, work)
            try:
                c = sqlite3.connect(work)
                for old, new in renames:
                    c.execute('UPDATE pairs SET work_a = ? WHERE work_a = ?', (new, old))
                    c.execute('UPDATE pairs SET work_b = ? WHERE work_b = ?', (new, old))
                    c.execute('UPDATE line_counts SET work = ? WHERE work = ?', (new, old))
                c.commit()
                good = c.execute('PRAGMA quick_check').fetchone()[0] == 'ok'
                c.close()
                if not good:
                    raise RuntimeError(f'{name}: the copy failed quick_check; live file untouched')
            except BaseException:
                if os.path.exists(work):
                    os.remove(work)
                raise
            os.replace(work, path)
            con = _ro(path)
            after = {old: reuse_counts(con, old) for old, _n in renames}
            con.close()
        for old, _new in renames:
            for k, v in before[old].items():
                rows.append((name, f'{old}: {k}', v, after[old][k] if apply_ else None))
    return ok


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    p.add_argument('--root', default='.')
    p.add_argument('--rename', nargs=2, action='append', required=True, metavar=('OLD', 'NEW'),
                   help='stale work id and its current id (repeatable)')
    p.add_argument('--tag', default='stalework')
    add_apply_argument(p)
    args = p.parse_args(argv)
    renames = [tuple(r) for r in args.rename]
    if any(o == n for o, n in renames):
        print('refusing: old and new id are the same', file=sys.stderr)
        return 2
    root = os.path.abspath(args.root)
    print(('APPLY' if args.apply else 'DRY RUN') + f' against {root}')
    rows = []
    ok = do_events(root, renames, False, args.tag, [])  # clash check before any write
    ok = ok and do_reuse(root, renames, False, args.tag, [])
    if not ok:
        return 2
    do_events(root, renames, args.apply, args.tag, rows)
    do_reuse(root, renames, args.apply, args.tag, rows)
    print(f'\n{"store":34} {"rows":62} {"before":>7} {"after":>7}')
    for store, label, b, a in rows:
        print(f'{store:34} {label:62} {b:>7} {"" if a is None else a:>7}')
    print('\nafter = rows still under the old id' + ('' if args.apply else ' (dry run: not measured)'))
    if not args.apply:
        print('dry run, nothing written; pass --apply')
    return 0


if __name__ == '__main__':
    sys.exit(main())
