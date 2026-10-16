#!/usr/bin/env python3
"""Change the prefix of a work's line references in every store that holds
references as plain strings.

Why it exists (2026-10-16): the three Libanius part files carried line tags
such as `<libanius. orations_1-11. 1.1>` while the whole file carries
`<libanius. orations. 1.1>`. The part files were corrected in git, and every
production store that copied the tag still holds the old spelling. A
reference is a key into those stores, so each needs the same substitution.

    ./venv/bin/python3 scripts/corpus/fix_ref_prefix.py --root <root> \\
        --fix libanius.orations.part.1 'libanius. orations_1-11.' 'libanius. orations.' \\
        --fix libanius.orations.part.2 'libanius. orations_26-50.' 'libanius. orations.' \\
        --fix libanius.orations.part.3 'libanius. orations_51-64.' 'libanius. orations.'
    ... --apply [--only window_texts,descriptions,reuse,events,embeddings]

Each `--fix WORK OLD NEW` names a work id (the .tess file name without
.tess), the reference prefix it carries now and the one it should carry. A
reference moves when it starts with OLD and the next character is not a
letter or digit (so `x_1-11.` never matches `x_1-110.`); the rest of the
reference is kept. Dry run by default. With --apply, every file the script
writes gets a dated `.bak-<tag>-<timestamp>` copy beside it first
(scripts/corpus/corpus_safety.py), and the big SQLite stores are rewritten on
a copy that is integrity-checked and then renamed over the live file, so a
reader never sees a half-written store.

STORES WRITTEN (all hold references as strings):
  data/passage_index/window_texts.db   window_texts.ref_start, ref_end and
                                       lines.ref, rows of the work
  data/passage_index/descriptions.jsonl  ref_start, ref_end, records of the work
  cache/reuse_pairs/<lang>.db          pairs.line_a_ref, line_b_ref and
                                       line_counts.line_ref (matched on the
                                       prefix alone, because the work column
                                       of the reuse tables can still hold an
                                       older work id)
  data/events/event_dossiers.sqlite    passages.ref_start, ref_end and
                                       scholarship.passage_ref
  backend/embeddings/<lang>/<work>.meta.json  line_refs

STORES ONLY COUNTED (they derive from the .tess files; rebuild them instead):
  data/inverted_index/<lang>_index.db  lines and postings: replace the work's
                                       entries from the corrected file with
                                       scripts/corpus/add_texts_to_index.py
                                       --replace, on a copy, then swap
  cache/lemmas/<lang>/<work>-<hash>.json  the file hash no longer matches the
                                       corrected .tess, so the cache is
                                       ignored: delete it and run
                                       scripts/batch_lemma_cache.py <lang>
  cache/connections_map/*.db           windows.ref_start, ref_end: rebuilt by
                                       scripts/build_connections_map.py

NOT TOUCHED: window ids and work names. If a store still holds an older work
id (the reuse tables and the events store did after the 2026-10-13 rename),
that is a separate rename and is reported by the dry run as an "other work
ids" line.
"""
import argparse
import glob
import json
import os
import re
import shutil
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

from scripts.corpus.corpus_safety import (  # noqa: E402
    add_apply_argument, atomic_write, backup)

_ALNUM = re.compile(r'[A-Za-z0-9]')


class Remapper:
    """Rewrites a reference when it starts with one of the old prefixes."""

    def __init__(self, fixes):
        self.fixes = [(old, new) for _work, old, new in fixes]

    def __call__(self, ref):
        if not isinstance(ref, str):
            return ref
        for old, new in self.fixes:
            if ref.startswith(old):
                rest = ref[len(old):]
                if rest == '' or not _ALNUM.match(rest[0]):
                    return new + rest
        return ref

    def has_old(self, ref):
        return self(ref) != ref

    def old_like_patterns(self):
        """LIKE prefilters (escaped), to keep the SQL scans cheap."""
        out = []
        for old, _new in self.fixes:
            esc = old.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
            out.append(esc + '%')
        return out


def _ro(path):
    return sqlite3.connect(f'file:{path}?mode=ro', uri=True)


def _like_clause(col, patterns):
    return '(' + ' OR '.join(f"{col} LIKE ? ESCAPE '\\'" for _ in patterns) + ')'


def count_rows(con, table, cols, remap, extra_where='', extra_args=()):
    """Rows of `table` in which at least one of `cols` would change."""
    patterns = remap.old_like_patterns()
    where = ' OR '.join(_like_clause(c, patterns) for c in cols)
    args = list(patterns) * len(cols)
    if extra_where:
        where = f'({where}) AND {extra_where}'
        args += list(extra_args)
    n = 0
    sel = ', '.join(cols)
    for row in con.execute(f'SELECT {sel} FROM {table} WHERE {where}', args):
        if any(remap.has_old(v) for v in row):
            n += 1
    return n


def update_rows(con, table, cols, remap, extra_where='', extra_args=()):
    """Rewrite the `cols` of every row of `table` that carries an old prefix."""
    con.create_function('fixref', 1, remap)
    patterns = remap.old_like_patterns()
    where = ' OR '.join(_like_clause(c, patterns) for c in cols)
    args = list(patterns) * len(cols)
    if extra_where:
        where = f'({where}) AND {extra_where}'
        args += list(extra_args)
    sets = ', '.join(f'{c} = fixref({c})' for c in cols)
    con.execute(f'UPDATE {table} SET {sets} WHERE {where}', args)


class Report:
    def __init__(self):
        self.rows = []  # (store, label, before, after, note)

    def add(self, store, label, before, after=None, note=''):
        self.rows.append((store, label, before, after, note))

    def print(self, apply_):
        print()
        print(f'{"store":44} {"rows":28} {"before":>9} {"after":>9}')
        for store, label, before, after, note in self.rows:
            a = '' if after is None else str(after)
            print(f'{store:44} {label:28} {before:>9} {a:>9}  {note}')
        print()
        print('after = rows still carrying an old prefix'
              + ('' if apply_ else ' (dry run: not measured)'))


# ---------------------------------------------------------------- stores

def _swap_sqlite(live, tag, mutate):
    """Back up `live`, apply `mutate(con)` on a copy, check it, rename it in."""
    bak = backup(live, tag=tag)
    work = live + '.fixing'
    shutil.copy2(live, work)
    try:
        con = sqlite3.connect(work)
        mutate(con)
        con.commit()
        ok = con.execute('PRAGMA quick_check').fetchone()[0] == 'ok'
        con.close()
        if not ok:
            raise RuntimeError(f'{live}: the rewritten copy failed quick_check; live file untouched')
    except BaseException:
        if os.path.exists(work):
            os.remove(work)
        raise
    os.replace(work, live)
    return bak


def store_window_texts(root, fixes, remap, apply_, tag, report):
    path = os.path.join(root, 'data', 'passage_index', 'window_texts.db')
    name = 'passage_index/window_texts.db'
    if not os.path.exists(path):
        report.add(name, 'not present', 0)
        return
    works = sorted({w for w, _o, _n in fixes})
    marks = ','.join('?' * len(works))
    where = f'work IN ({marks})'
    con = _ro(path)
    wt = count_rows(con, 'window_texts', ['ref_start', 'ref_end'], remap, where, works)
    ln = count_rows(con, 'lines', ['ref'], remap, where, works)
    con.close()
    after_wt = after_ln = None
    if apply_:
        def mutate(c):
            update_rows(c, 'window_texts', ['ref_start', 'ref_end'], remap, where, works)
            update_rows(c, 'lines', ['ref'], remap, where, works)
        _swap_sqlite(path, tag, mutate)
        con = _ro(path)
        after_wt = count_rows(con, 'window_texts', ['ref_start', 'ref_end'], remap, where, works)
        after_ln = count_rows(con, 'lines', ['ref'], remap, where, works)
        con.close()
    report.add(name, 'window_texts (windows)', wt, after_wt)
    report.add(name, 'lines (line rows)', ln, after_ln)


def store_descriptions(root, fixes, remap, apply_, tag, report):
    path = os.path.join(root, 'data', 'passage_index', 'descriptions.jsonl')
    name = 'passage_index/descriptions.jsonl'
    if not os.path.exists(path):
        report.add(name, 'not present', 0)
        return
    works = {w for w, _o, _n in fixes}
    out, n = [], 0
    with open(path, encoding='utf-8', newline='') as fh:
        for line in fh:
            rec = None
            if any(w in line for w in works):
                try:
                    rec = json.loads(line)
                except ValueError:
                    rec = None
            if rec is not None and rec.get('work') in works:
                new_s, new_e = remap(rec.get('ref_start')), remap(rec.get('ref_end'))
                if (new_s, new_e) != (rec.get('ref_start'), rec.get('ref_end')):
                    rec['ref_start'], rec['ref_end'] = new_s, new_e
                    line = json.dumps(rec, ensure_ascii=False) + '\n'
                    n += 1
            out.append(line)
    after = None
    if apply_ and n:
        backup(path, tag=tag)
        atomic_write(path, out)
        after = 0
        with open(path, encoding='utf-8') as fh:
            for line in fh:
                if any(w in line for w in works):
                    rec = json.loads(line)
                    if rec.get('work') in works and (
                            remap.has_old(rec.get('ref_start')) or remap.has_old(rec.get('ref_end'))):
                        after += 1
    elif apply_:
        after = 0
    report.add(name, 'description records', n, after)


def store_reuse(root, language, remap, apply_, tag, report):
    path = os.path.join(root, 'cache', 'reuse_pairs', f'{language}.db')
    name = f'reuse_pairs/{language}.db'
    if not os.path.exists(path):
        report.add(name, 'not present', 0)
        return
    con = _ro(path)
    pairs = count_rows(con, 'pairs', ['line_a_ref', 'line_b_ref'], remap)
    lc = count_rows(con, 'line_counts', ['line_ref'], remap)
    con.close()
    ap = al = None
    if apply_ and (pairs or lc):
        def mutate(c):
            update_rows(c, 'pairs', ['line_a_ref', 'line_b_ref'], remap)
            update_rows(c, 'line_counts', ['line_ref'], remap)
        _swap_sqlite(path, tag, mutate)
        con = _ro(path)
        ap = count_rows(con, 'pairs', ['line_a_ref', 'line_b_ref'], remap)
        al = count_rows(con, 'line_counts', ['line_ref'], remap)
        con.close()
    elif apply_:
        ap = al = 0
    report.add(name, 'pairs', pairs, ap)
    report.add(name, 'line_counts', lc, al)


def store_events(root, remap, apply_, tag, report):
    path = os.path.join(root, 'data', 'events', 'event_dossiers.sqlite')
    name = 'events/event_dossiers.sqlite'
    if not os.path.exists(path):
        report.add(name, 'not present', 0)
        return
    con = _ro(path)
    p = count_rows(con, 'passages', ['ref_start', 'ref_end'], remap)
    s = count_rows(con, 'scholarship', ['passage_ref'], remap)
    con.close()
    ap = as_ = None
    if apply_ and (p or s):
        # The store is in WAL mode and the pipeline may hold it open, so it is
        # updated in place after a checkpoint (as rename_work.py does), not
        # swapped from a copy.
        con = sqlite3.connect(path, timeout=60)
        con.execute('PRAGMA wal_checkpoint(TRUNCATE)')
        con.close()
        backup(path, tag=tag)
        con = sqlite3.connect(path, timeout=60)
        update_rows(con, 'passages', ['ref_start', 'ref_end'], remap)
        update_rows(con, 'scholarship', ['passage_ref'], remap)
        con.commit()
        con.execute('PRAGMA wal_checkpoint(TRUNCATE)')
        con.close()
        con = _ro(path)
        ap = count_rows(con, 'passages', ['ref_start', 'ref_end'], remap)
        as_ = count_rows(con, 'scholarship', ['passage_ref'], remap)
        con.close()
    elif apply_:
        ap = as_ = 0
    report.add(name, 'passages', p, ap)
    report.add(name, 'scholarship', s, as_)


def store_embeddings_meta(root, language, fixes, remap, apply_, tag, report):
    for work in sorted({w for w, _o, _n in fixes}):
        path = os.path.join(root, 'backend', 'embeddings', language, f'{work}.meta.json')
        name = f'embeddings/{language}/{work}.meta.json'
        if not os.path.exists(path):
            report.add(name, 'not present', 0)
            continue
        with open(path, encoding='utf-8') as fh:
            meta = json.load(fh)
        refs = meta.get('line_refs')
        n = sum(1 for r in refs if remap.has_old(r)) if isinstance(refs, list) else 0
        after = None
        if apply_ and n:
            backup(path, tag=tag)
            meta['line_refs'] = [remap(r) for r in refs]
            atomic_write(path, json.dumps(meta, ensure_ascii=False))
            after = sum(1 for r in meta['line_refs'] if remap.has_old(r))
        elif apply_:
            after = 0
        report.add(name, 'line_refs entries', n, after)


# ----------------------------------------------------- counted, not written

def count_inverted_index(root, language, fixes, remap, report):
    path = os.path.join(root, 'data', 'inverted_index', f'{language}_index.db')
    name = f'inverted_index/{language}_index.db'
    if not os.path.exists(path):
        report.add(name, 'not present', 0)
        return
    con = _ro(path)
    ids = [r[0] for r in con.execute(
        'SELECT text_id FROM texts WHERE filename IN (%s)'
        % ','.join('?' * len(fixes)), [f'{w}.tess' for w, _o, _n in fixes])]
    marks = ','.join('?' * len(ids)) or "''"
    where = f'text_id IN ({marks})'
    lines = count_rows(con, 'lines', ['ref'], remap, where, ids) if ids else 0
    post = count_rows(con, 'postings', ['ref'], remap, where, ids) if ids else 0
    con.close()
    report.add(name, 'lines (REBUILD)', lines, None, 'counted only')
    report.add(name, 'postings (REBUILD)', post, None, 'counted only')


def count_lemma_cache(root, language, fixes, remap, report):
    for work in sorted({w for w, _o, _n in fixes}):
        files = [f for f in glob.glob(os.path.join(
            root, 'cache', 'lemmas', language, f'{work}-*.json')) if '.bak' not in f]
        n = 0
        for f in files:
            with open(f, encoding='utf-8') as fh:
                d = json.load(fh)
            for key in ('units_line', 'units_phrase'):
                n += sum(1 for u in d.get(key) or [] if remap.has_old(u.get('ref')))
        report.add(f'lemma cache {language}/{work}', f'refs in {len(files)} file(s) (REBUILD)',
                   n, None, 'counted only')


def count_connections_map(root, remap, report):
    for path in sorted(glob.glob(os.path.join(root, 'cache', 'connections_map', '*.db'))):
        con = _ro(path)
        try:
            n = count_rows(con, 'windows', ['ref_start', 'ref_end'], remap)
        except sqlite3.Error:
            con.close()
            continue
        con.close()
        report.add('connections_map/' + os.path.basename(path)[:16] + '...',
                   'windows (REBUILD)', n, None, 'counted only')


def report_other_work_ids(root, language, fixes, remap, report):
    """Reuse-table rows that carry the old prefix under a work id other than the current one."""
    path = os.path.join(root, 'cache', 'reuse_pairs', f'{language}.db')
    if not os.path.exists(path):
        return
    current = {w for w, _o, _n in fixes}
    con = _ro(path)
    patterns = remap.old_like_patterns()
    seen = {}
    for col_ref, col_work in (('line_a_ref', 'work_a'), ('line_b_ref', 'work_b')):
        for ref, work in con.execute(
                f'SELECT {col_ref}, {col_work} FROM pairs WHERE ' + _like_clause(col_ref, patterns),
                patterns):
            if remap.has_old(ref) and work not in current:
                seen[work] = seen.get(work, 0) + 1
    con.close()
    for work, n in sorted(seen.items()):
        print(f'note: reuse_pairs/{language}.db has {n} pair row(s) under the older work id '
              f'{work!r}; a work-id rename of that table is a separate step')


# ------------------------------------------------------------------ main

def main(argv=None):
    p = argparse.ArgumentParser(
        description=__doc__.split('\n')[0],
        formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--root', default='.', help='project root (production root or a fixture)')
    p.add_argument('--fix', nargs=3, action='append', required=True,
                   metavar=('WORK', 'OLD', 'NEW'),
                   help='work id, old reference prefix, new reference prefix (repeatable)')
    p.add_argument('--language', default='grc', help='language code of the work (default grc)')
    p.add_argument('--tag', default='fixrefs', help='backup tag (default fixrefs)')
    p.add_argument('--only', default='',
                   help='comma list of stores to write: window_texts, descriptions, reuse, '
                        'events, embeddings (default: all of them)')
    add_apply_argument(p)
    args = p.parse_args(argv)
    names = {'window_texts', 'descriptions', 'reuse', 'events', 'embeddings'}
    only = {x.strip() for x in args.only.split(',') if x.strip()} or names
    if only - names:
        print(f'refusing: unknown store(s) in --only: {sorted(only - names)}', file=sys.stderr)
        return 2

    fixes = [tuple(f) for f in args.fix]
    for _w, old, new in fixes:
        if old == new:
            print(f'refusing: old and new prefix are the same ({old!r})', file=sys.stderr)
            return 2
    remap = Remapper(fixes)
    report = Report()
    root = os.path.abspath(args.root)
    print(('APPLY' if args.apply else 'DRY RUN') + f' against {root}')
    for w, o, n in fixes:
        print(f'  {w}: {o!r} -> {n!r}')

    count_inverted_index(root, args.language, fixes, remap, report)
    count_lemma_cache(root, args.language, fixes, remap, report)
    count_connections_map(root, remap, report)
    if 'window_texts' in only:
        store_window_texts(root, fixes, remap, args.apply, args.tag, report)
    if 'descriptions' in only:
        store_descriptions(root, fixes, remap, args.apply, args.tag, report)
    if 'reuse' in only:
        store_reuse(root, args.language, remap, args.apply, args.tag, report)
    if 'events' in only:
        store_events(root, remap, args.apply, args.tag, report)
    if 'embeddings' in only:
        store_embeddings_meta(root, args.language, fixes, remap, args.apply, args.tag, report)
    report.print(args.apply)
    report_other_work_ids(root, args.language, fixes, remap, report)
    if not args.apply:
        print('dry run, nothing written; pass --apply')
    else:
        print('Stores marked REBUILD were not touched: rebuild them from the corrected '
              '.tess files (see the module docstring).')
    return 0


if __name__ == '__main__':
    sys.exit(main())
