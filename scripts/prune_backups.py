#!/usr/bin/env python3
"""Delete old data backups, keeping the recent ones.

Every data operation on production leaves a dated copy beside the file it
replaces, which is why nothing has been lost this year, and nothing has ever
removed one. By 2026-09-22 that had grown to 343 copies and 222 GB across
the passage index, the inverted indexes and the caches, with the oldest from
January, on a filesystem that had reached 90% full.

A backup exists to undo the operation that made it. Once that operation has
been verified -- the reference tests pass, the site answers, the figures in
docs/DATA_OPERATIONS.md check out -- an older copy earns nothing, and the
underlying data is rebuildable from the texts and the scripts in any case.
So the rule is: keep the most recent copy of each file and delete the rest.
While an operation is still being watched, `--keep 2` or `--keep-days N`
holds the copy underneath it, and neither is on by default.

    keep the --keep newest copies of each file (default 1)
    keep any further copy only while it is younger than --keep-days
        (default 0, which is off: no grace period unless you ask for one)
    delete everything else

The defaults keep one copy per file and nothing else, which is the rule NC
approved on 2026-09-22. A second copy buys little: an operation is verified
the same day it runs, and the copy underneath it is a backup of a state
that was already superseded once.

NEVER leaves a file with no backup at all. The newest copy of each file is
kept whatever its age, which is the difference between this and the
by-hand cull of 2026-09-22 that would have removed the last copy of five
files. If a group's newest copy is ancient, that is a sign the live file
has not changed in months, not a reason to drop its only fallback.

Dry run by default, in line with every other script that writes under
data/. Pass --apply to delete. It prints every path it will remove, with
its age and size, before removing anything.

    ./venv/bin/python3 scripts/prune_backups.py                  # report
    ./venv/bin/python3 scripts/prune_backups.py --apply          # delete

Grouping: a backup is any file whose name contains `.bak` or `.pre-`, and
its group is the name with the backup suffix removed, so
`la_index.db.bak-canonical-20260921-231348`, `la_index.db.pre-stage1a.bak`
and a plain `la_index.db.bak` all belong to `la_index.db`. Getting that
last case wrong is what made the by-hand run look like it would strip a
file's only copy, so it is covered by a test.
"""
import argparse
import datetime
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.corpus.corpus_safety import add_apply_argument  # noqa: E402

# Where backups accumulate. Relative to the repository root.
DEFAULT_ROOTS = ('data/passage_index', 'data/inverted_index', 'cache')
DEFAULT_KEEP = 1
DEFAULT_KEEP_DAYS = 0
DAY = 86400

# A backup suffix is `.bak` or `.pre-...`, with whatever tag follows, to the
# end of the name. `(?:\.bak)?$` catches `foo.db.pre-rebuild-20260808.bak`,
# where the name carries both markers.
_SUFFIX = re.compile(r'\.(?:bak|pre)(?:[-.].*?)?(?:\.bak)?$')


def is_backup(name):
    return '.bak' in name or '.pre-' in name


def group_of(name):
    """The live file a backup belongs to, by name."""
    prev = None
    out = name
    while out != prev:
        prev = out
        out = _SUFFIX.sub('', out)
    return out


def collect(roots):
    """{(directory, live name): [(mtime, size, path), ...]}, newest first."""
    groups = {}
    for root in roots:
        if not os.path.isdir(root):
            continue
        for dirpath, _dirs, files in os.walk(root):
            for f in files:
                if not is_backup(f):
                    continue
                path = os.path.join(dirpath, f)
                try:
                    st = os.stat(path)
                except OSError:
                    continue
                groups.setdefault((dirpath, group_of(f)), []).append(
                    (st.st_mtime, st.st_size, path))
    for v in groups.values():
        v.sort(reverse=True)
    return groups


def plan(groups, keep_days=DEFAULT_KEEP_DAYS, keep=DEFAULT_KEEP, now=None):
    """(keep, drop), each a list of (mtime, size, path).

    The newest copy is always kept, whatever its age and whatever `keep` is,
    so no file is ever left without a fallback.
    """
    now = time.time() if now is None else now
    kept, drop = [], []
    for copies in groups.values():
        for i, rec in enumerate(copies):
            if i == 0 or i < keep:
                kept.append(rec)
            elif keep_days and (now - rec[0]) < keep_days * DAY:
                kept.append(rec)
            else:
                drop.append(rec)
    return kept, drop


def gb(n):
    return n / float(1 << 30)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    p.add_argument('--root', default='.', help='repository root (default: .)')
    p.add_argument('--roots', nargs='*', default=list(DEFAULT_ROOTS),
                   help='directories to walk, relative to --root')
    p.add_argument('--keep', type=int, default=DEFAULT_KEEP,
                   help=f'copies of each file to keep regardless of age '
                        f'(default: {DEFAULT_KEEP}; the newest is always kept)')
    p.add_argument('--keep-days', type=int, default=DEFAULT_KEEP_DAYS,
                   help=f'also keep further copies while they are younger '
                        f'than this many days (default: {DEFAULT_KEEP_DAYS}, off)')
    add_apply_argument(p, 'delete the backups listed (default: report only)')
    args = p.parse_args(argv)

    # The working directory is process-wide and this is called from tests as
    # well as from the command line, so it is restored before returning. The
    # paths collected are relative to --root, so the whole of the work has to
    # happen inside the chdir, not just the walk.
    was = os.getcwd()
    try:
        os.chdir(args.root)
        return _run(args)
    finally:
        os.chdir(was)


def _run(args):
    groups = collect(args.roots)
    keep, drop = plan(groups, args.keep_days, args.keep)

    total = sum(s for v in groups.values() for _t, s, _p in v)
    print(f'{sum(len(v) for v in groups.values())} backup copies of '
          f'{len(groups)} files, {gb(total):.1f} GB')
    rule = f'keep the newest {args.keep} of each file'
    if args.keep_days:
        rule += f', and any further copy under {args.keep_days} days old'
    print('rule: ' + rule)
    print()
    if not drop:
        print('nothing to delete')
        return 0
    for t, s, path in sorted(drop, key=lambda r: -r[1]):
        age = (time.time() - t) / DAY
        print(f'  {"DELETE" if args.apply else "would delete"}  '
              f'{datetime.date.fromtimestamp(t)}  {age:5.0f}d  '
              f'{gb(s):6.2f} GB  {path}')
    print()
    print(f'{len(drop)} copies, {gb(sum(s for _t, s, _p in drop)):.1f} GB; '
          f'{len(keep)} copies, {gb(sum(s for _t, s, _p in keep)):.1f} GB kept')

    # No group may end up empty. This cannot happen under the rule above, so
    # a failure here means the grouping is wrong, which is the one bug this
    # script has already had.
    dropped = {p for _t, _s, p in drop}
    for (dirpath, name), copies in groups.items():
        if all(p in dropped for _t, _s, p in copies):
            print(f'REFUSING: every copy of {os.path.join(dirpath, name)} '
                  f'is in the delete list', file=sys.stderr)
            return 2

    if not args.apply:
        print('\ndry run, nothing deleted; pass --apply')
        return 0
    freed = 0
    for _t, s, path in drop:
        try:
            os.remove(path)
            freed += s
        except OSError as e:
            print(f'  could not delete {path}: {e}', file=sys.stderr)
    print(f'\ndeleted, {gb(freed):.1f} GB freed')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
