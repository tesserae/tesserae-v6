#!/usr/bin/env python3
"""Downstream repair for the 2026-09-20 whole-vs-parts corpus fix (see
CHANGELOG.md "Corpus" entry the same date and docs/DATA_OPERATIONS.md). Four
works had a whole .tess file whose refs (or line content) disagreed with its
book/part .tess files; scripts/corpus/check_whole_vs_parts.py caught them and
the .tess files themselves are already fixed, by git. Two of those fixes
change line REFS -- refs are keys into every production store, so those
stores need the same rename. This script does that, on the production root,
dry run by default. (The other two fixes -- Dionysius Halicarnassensis'
missing 16.1.0 line, and Confucius Sinarum Philosophus' missing lines
overall -- add or change TEXT, not refs already stored under some other
name, so they need no remap here; they need only the reindex and lemma-cache
rebuild already covered in DATA_OPERATIONS.md.)

The three ref renames, each a plain string substitution with no positional
ambiguity (unlike scripts/corpus/apply_paradise_lost_numbering.py's Book 4
deletion, every old ref here maps to exactly one new ref regardless of which
physical line carried it):

  1. texts/grc/isocrates.letters.part.2.tess and .part.3.tess: every line's
     tag carried a doubled leading bracket, "<<isoc. letters 2.1>" instead
     of "<isoc. letters 2.1>". The .tess fix (scripts/corpus's one-off text
     edit, already applied) removed the extra "<". The GREEK inverted index
     (data/inverted_index/grc_index.db) built from the old text stored the
     ref with the bracket embedded literally IN the ref string, e.g.
     "<isoc. letters 2.1" (a leading "<", no trailing ">" -- confirmed by
     reading production's grc_index.db read-only, 2026-09-20: see
     docs/DATA_OPERATIONS.md for the exact rows). The passage index
     (data/passage_index/window_texts.db, descriptions.jsonl) copied the
     same doubled-bracket ref into its own ref_start/ref/ref_end fields.
     Fix: strip exactly one leading "<" from a ref that starts with "<<" in
     the raw line (i.e. from a stored ref that itself starts with "<").
  2. texts/grc/hyperides.speeches.tess (the WHOLE file only -- its six part
     files already use the correct form): tags were "<hyp. 1.1>" instead of
     "<hyp. speeches. 1.1>". Fix (already applied to the .tess file):
     "<hyp. LOCUS>" -> "<hyp. speeches. LOCUS>". The stores for the WHOLE
     file's own rows (never the parts, which were already correct and are
     left untouched) need the same "hyp. " -> "hyp. speeches. " insertion.
  3. texts/la/couplet_et_alii.confucius_sinarum_philosophus.part.1.tess:
     tags were "<Couplet. Confucius. X>" instead of the "Couplet et alii."
     prefix the whole file and parts 2-3 use. Fix (already applied):
     "Couplet. Confucius." -> "Couplet et alii. Confucius.".

Stores touched, each read-only inspected against production before writing
this script (counts in docs/DATA_OPERATIONS.md):
  - data/inverted_index/grc_index.db: tables `lines` (PK text_id, ref) and
    `postings` (no PK; many rows per ref, one per lemma occurrence), for the
    text_id of isocrates.letters.part.2.tess, .part.3.tess, and
    hyperides.speeches.tess (looked up from the `texts` table by filename,
    once per db -- text_id numbering is NOT assumed stable across a rebuilt
    copy, so this script always re-resolves it).
  - data/inverted_index/la_index.db: same two tables, for the text_id of
    couplet_et_alii.confucius_sinarum_philosophus.part.1.tess.
    lemma_doc_freq is untouched: it aggregates by lemma only, no ref column.
  - data/passage_index/window_texts.db: table `window_texts` (ref_start,
    ref_end; id and work never change, since no work is renamed here,
    unlike the Prelude split) and table `lines` (work, ord, ref, text; ref
    updated in place, ord and text untouched).
  - data/passage_index/descriptions.jsonl: same ref_start/ref_end remap,
    keyed by the "work" field, id unchanged.
  - cache/reuse_pairs/{grc,la}.db (backend/reuse_table.py; schema in its
    module docstring): tables `pairs` (work_a/line_a_ref, work_b/
    line_b_ref) and `line_counts` (work, line_ref). Read-only inspection
    2026-09-20 found zero rows for isocrates.letters.part.2/.part.3 or for
    couplet_et_alii.confucius_sinarum_philosophus.part.1 (too short to have
    registered a reuse candidate), but 68 `pairs` rows (13 as work_a, 55 as
    work_b) and 38 `line_counts` rows for hyperides.speeches under the old
    "hyp. LOCUS" naming -- these DO need the rename and this script
    includes them. lemma_doc_freq-style aggregate tables aside, `meta` is
    untouched (build provenance, not per-line data).
  - Cached fusion/theme-search results naming any of the four touched
    files (cache/*.json) are deleted, since a cached result may have been
    computed against the old refs.

Not done here (run separately -- see docs/DATA_OPERATIONS.md for the exact
production sequence and order):
  scripts/batch_lemma_cache.py grc and la (after deleting the stale cache
     entries for the six changed files -- rebuilds the lemma cache from the
     now-fixed .tess files, which also picks up the two TEXT-only fixes,
     Confucius' missing lines and Dionysius' 16.1.0);
  scripts/corpus/add_texts_to_index.py --replace <files...> on a COPY of
     grc_index.db and la_index.db, then swap the copy in (this reindex
     naturally applies the same ref rename this script applies directly --
     run one or the other for the inverted index, not both; this script
     exists for the stores add_texts_to_index.py does NOT touch: the
     passage index and the reuse tables);
  tests/search_reference_tests.md's reference checks, after everything
     above.

Usage:
    python apply_whole_vs_parts_refs.py [--root ROOT] [--apply] [--tag TAG]

ROOT defaults to "." and should contain data/inverted_index/, data/
passage_index/ and cache/reuse_pairs/ (production root, or a test fixture
laid out the same way -- see tests/test_apply_whole_vs_parts_refs.py and
the dry run against a copy under ~/tesserae-backups/whole_vs_parts_2026-09-20/
test/, recorded in docs/DATA_OPERATIONS.md). Dry run by default; --apply
writes, after making a stamped `.bak-<tag>` copy of every file it modifies.
--tag sets the backup suffix (default: a timestamp). Refuses to apply (exits
1, no writes) if any target ref already exists for the same file/text_id --
a collision this script has not been taught to resolve.
"""
import argparse
import glob
import json
import os
import shutil
import sqlite3
import sys
import time


# --- The three renames, as (language, filename, remap_function) ---------

def _strip_doubled_bracket(ref):
    """"<isoc. letters 2.1" (stored WITH the leading "<" baked into the ref
    string, from the doubled-bracket source tag) -> "isoc. letters 2.1".
    A ref that doesn't start with "<" passes through unchanged (defensive;
    every row for these two files is expected to match)."""
    return ref[1:] if ref.startswith('<') else ref


def _hyp_prefix(ref):
    """"hyp. 1.1" -> "hyp. speeches. 1.1". A ref already carrying the
    "speeches." segment (shouldn't occur for the whole file's own rows,
    which is all this is ever applied to) passes through unchanged."""
    if ref.startswith('hyp. speeches. '):
        return ref
    if ref.startswith('hyp. '):
        return 'hyp. speeches. ' + ref[len('hyp. '):]
    return ref


def _couplet_prefix(ref):
    """"Couplet. Confucius. X" -> "Couplet et alii. Confucius. X"."""
    old = 'Couplet. Confucius.'
    new = 'Couplet et alii. Confucius.'
    return new + ref[len(old):] if ref.startswith(old) else ref


# Each entry: key used in reports, language, the .tess filename (index
# lookup) / work name (passage index + reuse table lookup), and the remap
# function applied to every ref belonging to that file/work.
TARGETS = [
    {
        'name': 'isocrates.letters.part.2',
        'language': 'grc',
        'filename': 'isocrates.letters.part.2.tess',
        'work': 'isocrates.letters.part.2',
        'remap': _strip_doubled_bracket,
    },
    {
        'name': 'isocrates.letters.part.3',
        'language': 'grc',
        'filename': 'isocrates.letters.part.3.tess',
        'work': 'isocrates.letters.part.3',
        'remap': _strip_doubled_bracket,
    },
    {
        'name': 'hyperides.speeches',
        'language': 'grc',
        'filename': 'hyperides.speeches.tess',
        'work': 'hyperides.speeches',
        'remap': _hyp_prefix,
    },
    {
        'name': 'couplet_et_alii.confucius_sinarum_philosophus.part.1',
        'language': 'la',
        'filename': 'couplet_et_alii.confucius_sinarum_philosophus.part.1.tess',
        'work': 'couplet_et_alii.confucius_sinarum_philosophus.part.1',
        'remap': _couplet_prefix,
    },
]


def backup(path, apply_, tag):
    if apply_ and os.path.exists(path):
        shutil.copy2(path, f'{path}.bak-{tag}')


# --- Inverted index: data/inverted_index/<lang>_index.db -----------------

def inverted_index(root, apply_, tag, report):
    by_lang = {}
    for t in TARGETS:
        by_lang.setdefault(t['language'], []).append(t)

    for lang, targets in by_lang.items():
        db_path = os.path.join(root, 'data', 'inverted_index', f'{lang}_index.db')
        if not os.path.exists(db_path):
            report.append(f'  {lang}_index.db: not present, skipping')
            continue

        conn_ro = sqlite3.connect(f'file:{db_path}?mode=ro', uri=True)
        collisions = []
        lines_updates = []    # (new_ref, text_id, old_ref)
        postings_updates = []  # (new_ref, text_id, old_ref)
        n_lines = n_postings = 0
        for t in targets:
            row = conn_ro.execute(
                'select text_id from texts where filename=?', (t['filename'],)).fetchone()
            if row is None:
                report.append(f'  {lang}_index.db: {t["filename"]} not found in texts table, skipping')
                continue
            text_id = row[0]

            existing_refs = {r for (r,) in conn_ro.execute(
                'select ref from lines where text_id=?', (text_id,))}
            for (old_ref,) in conn_ro.execute(
                    'select ref from lines where text_id=?', (text_id,)):
                new_ref = t['remap'](old_ref)
                if new_ref == old_ref:
                    continue
                if new_ref in existing_refs:
                    collisions.append((lang, 'lines', t['name'], old_ref, new_ref))
                    continue
                lines_updates.append((new_ref, text_id, old_ref))
                n_lines += 1

            for (old_ref,) in conn_ro.execute(
                    'select distinct ref from postings where text_id=?', (text_id,)):
                new_ref = t['remap'](old_ref)
                if new_ref == old_ref:
                    continue
                postings_updates.append((new_ref, text_id, old_ref))
                n_postings += conn_ro.execute(
                    'select count(*) from postings where text_id=? and ref=?',
                    (text_id, old_ref)).fetchone()[0]
        conn_ro.close()

        report.append(f'  {lang}_index.db lines: {n_lines} ref(s) to remap')
        report.append(f'  {lang}_index.db postings: {n_postings} row(s) to remap '
                       f'({len(postings_updates)} distinct ref(s))')
        if collisions:
            report.append(f'  {lang}_index.db: {len(collisions)} COLLISION(S), see below')
            for c in collisions:
                report.append(f'    COLLISION: {c}')

        if apply_:
            if collisions:
                raise SystemExit(f'{lang}_index.db: refusing to apply, {len(collisions)} '
                                  f'collision(s) found (see report above)')
            backup(db_path, apply_, tag)
            conn = sqlite3.connect(db_path)
            conn.executemany('update lines set ref=? where text_id=? and ref=?', lines_updates)
            conn.executemany('update postings set ref=? where text_id=? and ref=?', postings_updates)
            conn.commit()
            conn.close()


# --- Passage index: data/passage_index/{window_texts.db,descriptions.jsonl}

def passage_index(root, apply_, tag, report):
    wdb = os.path.join(root, 'data', 'passage_index', 'window_texts.db')
    remap_by_work = {t['work']: t['remap'] for t in TARGETS}

    if os.path.exists(wdb):
        conn_ro = sqlite3.connect(f'file:{wdb}?mode=ro', uri=True)

        # table `lines` (work, ord, ref, text) -- ref updated in place.
        lines_updates = []  # (new_ref, work, ord)  -- ord is the row key
        pi_collisions = []
        n_lines = 0
        for work, remap in remap_by_work.items():
            existing = {r for (r,) in conn_ro.execute(
                'select ref from lines where work=?', (work,))}
            for ord_, old_ref in conn_ro.execute(
                    'select ord, ref from lines where work=?', (work,)):
                new_ref = remap(old_ref)
                if new_ref == old_ref:
                    continue
                if new_ref in existing:
                    # Same rule as the inverted index: a target ref already
                    # present for the work is a collision, and the apply
                    # refuses rather than overwrite (review of PR #432).
                    pi_collisions.append((work, ord_, old_ref, new_ref))
                    continue
                lines_updates.append((new_ref, work, ord_))
                n_lines += 1
        report.append(f'  window_texts.db lines: {n_lines} ref(s) to remap')
        if pi_collisions:
            report.append(f'  window_texts.db lines: {len(pi_collisions)} COLLISION(S), see below')
            for c in pi_collisions:
                report.append(f'    COLLISION: {c}')

        # table `window_texts` (id, language, work, ref_start, ref_end, text)
        wt_updates = []  # (new_rs, new_re, rowid)
        n_wt = 0
        rows = conn_ro.execute(
            'select rowid, work, ref_start, ref_end from window_texts '
            'where work in (%s)' % ','.join('?' * len(remap_by_work)),
            list(remap_by_work)).fetchall()
        conn_ro.close()
        for rowid, work, rs, re_ in rows:
            remap = remap_by_work[work]
            new_rs, new_re = remap(rs), remap(re_)
            if new_rs != rs or new_re != re_:
                wt_updates.append((new_rs, new_re, rowid))
                n_wt += 1
        report.append(f'  window_texts.db window_texts: {n_wt} of {len(rows)} row(s) to remap')

        if apply_:
            if pi_collisions:
                raise SystemExit(f'window_texts.db: refusing to apply, {len(pi_collisions)} '
                                  f'collision(s) found (see report above)')
            backup(wdb, apply_, tag)
            conn = sqlite3.connect(wdb)
            conn.executemany('update lines set ref=? where work=? and ord=?', lines_updates)
            conn.executemany(
                'update window_texts set ref_start=?, ref_end=? where rowid=?', wt_updates)
            conn.commit()
            conn.close()
    else:
        report.append('  window_texts.db: not present, skipping')

    dpath = os.path.join(root, 'data', 'passage_index', 'descriptions.jsonl')
    if os.path.exists(dpath):
        n_remapped = 0
        n_total = 0
        out_lines = []
        with open(dpath, encoding='utf-8') as fh:
            for line in fh:
                try:
                    r = json.loads(line)
                except ValueError:
                    out_lines.append(line)
                    continue
                work = r.get('work')
                remap = remap_by_work.get(work)
                if remap is None:
                    out_lines.append(line)
                    continue
                n_total += 1
                rs, re_ = r.get('ref_start'), r.get('ref_end')
                new_rs, new_re = remap(rs), remap(re_)
                if new_rs != rs or new_re != re_:
                    n_remapped += 1
                r['ref_start'], r['ref_end'] = new_rs, new_re
                out_lines.append(json.dumps(r, ensure_ascii=False) + '\n')
        report.append(f'  descriptions.jsonl: {n_remapped} of {n_total} record(s) to remap')
        if apply_:
            backup(dpath, apply_, tag)
            tmp = dpath + '.new'
            with open(tmp, 'w', encoding='utf-8') as out:
                out.writelines(out_lines)
            os.replace(tmp, dpath)
    else:
        report.append('  descriptions.jsonl: not present, skipping')


# --- Reuse tables: cache/reuse_pairs/<lang>.db ----------------------------

def reuse_tables(root, apply_, tag, report):
    by_lang = {}
    for t in TARGETS:
        by_lang.setdefault(t['language'], []).append(t)

    for lang, targets in by_lang.items():
        db_path = os.path.join(root, 'cache', 'reuse_pairs', f'{lang}.db')
        if not os.path.exists(db_path):
            report.append(f'  reuse_pairs/{lang}.db: not present, skipping')
            continue

        conn_ro = sqlite3.connect(f'file:{db_path}?mode=ro', uri=True)
        pairs_a = []  # (new_ref, work, old_ref) for line_a_ref where work_a=work
        pairs_b = []  # (new_ref, work, old_ref) for line_b_ref where work_b=work
        lc_updates = []  # (new_ref, work, old_ref)
        n_pairs_a = n_pairs_b = n_lc = 0
        for t in targets:
            work = t['work']
            remap = t['remap']
            for (old_ref,) in conn_ro.execute(
                    'select distinct line_a_ref from pairs where work_a=?', (work,)):
                new_ref = remap(old_ref)
                if new_ref != old_ref:
                    pairs_a.append((new_ref, work, old_ref))
                    n_pairs_a += conn_ro.execute(
                        'select count(*) from pairs where work_a=? and line_a_ref=?',
                        (work, old_ref)).fetchone()[0]
            for (old_ref,) in conn_ro.execute(
                    'select distinct line_b_ref from pairs where work_b=?', (work,)):
                new_ref = remap(old_ref)
                if new_ref != old_ref:
                    pairs_b.append((new_ref, work, old_ref))
                    n_pairs_b += conn_ro.execute(
                        'select count(*) from pairs where work_b=? and line_b_ref=?',
                        (work, old_ref)).fetchone()[0]
            for (old_ref,) in conn_ro.execute(
                    'select distinct line_ref from line_counts where work=?', (work,)):
                new_ref = remap(old_ref)
                if new_ref != old_ref:
                    lc_updates.append((new_ref, work, old_ref))
                    n_lc += conn_ro.execute(
                        'select count(*) from line_counts where work=? and line_ref=?',
                        (work, old_ref)).fetchone()[0]
        conn_ro.close()

        report.append(f'  reuse_pairs/{lang}.db pairs: {n_pairs_a} row(s) as work_a, '
                       f'{n_pairs_b} row(s) as work_b to remap')
        report.append(f'  reuse_pairs/{lang}.db line_counts: {n_lc} row(s) to remap')

        if apply_:
            backup(db_path, apply_, tag)
            conn = sqlite3.connect(db_path)
            conn.executemany(
                'update pairs set line_a_ref=? where work_a=? and line_a_ref=?', pairs_a)
            conn.executemany(
                'update pairs set line_b_ref=? where work_b=? and line_b_ref=?', pairs_b)
            conn.executemany(
                'update line_counts set line_ref=? where work=? and line_ref=?', lc_updates)
            conn.commit()
            conn.close()


# --- Cached fusion / theme-search results ---------------------------------

def fusion_cache(root, apply_, report):
    names = set()
    for t in TARGETS:
        names.add(t['filename'])
        names.add(t['work'])
    hits = []
    for p in glob.glob(os.path.join(root, 'cache', '*.json')):
        try:
            d = json.load(open(p, encoding='utf-8'))
        except Exception:
            continue
        if isinstance(d, dict) and (d.get('source') in names or d.get('target') in names):
            hits.append(p)
    report.append(f'  fusion cache: {len(hits)} cached result(s) name one of the four touched works')
    if apply_:
        for p in hits:
            os.remove(p)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                  formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--root', default='.', help='production root, or a test fixture root (default: .)')
    ap.add_argument('--apply', action='store_true', help='write changes (default: dry run, report only)')
    ap.add_argument('--tag', default=None, help='backup suffix (default: a timestamp)')
    args = ap.parse_args()

    tag = args.tag or time.strftime('%Y%m%d-%H%M%S')
    print(('APPLY' if args.apply else 'DRY RUN') + f' on {os.path.abspath(args.root)}' +
          (f' (backup tag: {tag})' if args.apply else ''))

    report = []
    print('Inverted index:')
    inverted_index(args.root, args.apply, tag, report)
    print('\n'.join(report)); report.clear()

    print('Passage index:')
    passage_index(args.root, args.apply, tag, report)
    print('\n'.join(report)); report.clear()

    print('Reuse tables:')
    reuse_tables(args.root, args.apply, tag, report)
    print('\n'.join(report)); report.clear()

    print('Fusion cache:')
    fusion_cache(args.root, args.apply, report)
    print('\n'.join(report)); report.clear()


if __name__ == '__main__':
    main()
