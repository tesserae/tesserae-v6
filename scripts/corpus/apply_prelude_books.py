#!/usr/bin/env python3
"""Downstream repair for the 2026-09-16 Prelude book split: the corpus file
texts/en/wordsworth.prelude.tess carried Books XII, XIII and XIV under one
tag family "<wordsworth prelude 12.N>" (1,170 lines run together). That is
now fixed in the .tess files (the whole file and the per-book part files
part.12/13/14), by git. This script brings the stores that copied the old
tags or the old part.12/13/14 split into line, on the production root, dry
run by default.

    cd /var/www/tesseraev6_flask
    venv/bin/python scripts/corpus/apply_prelude_books.py [--apply]

The mapping (also the source of the .tess retag, restated here so this file
is a complete record of the change): old tag "wordsworth prelude 12.N" for
N 1-336 keeps book 12; N 337-714 becomes book 13, lines 1-378; N 715-1170
becomes book 14, lines 1-456. remap() below is the one function that applies
this, and every ref touched by this script goes through it.

Steps (each reported; --apply writes, with dated backups):
  1. passage index, data/passage_index/:
     a. window_texts.db, table window_texts (id, language, work, ref_start,
        ref_end, text): every row of work "wordsworth.prelude" or
        "wordsworth.prelude.part.12" gets ref_start and ref_end remapped.
        A window is a stretch of text, not a single line, so ref_start and
        ref_end can remap to different books: such a window keeps its row
        (its text is unchanged, still a contiguous stretch of the poem) and
        is counted as straddling. For part.12 rows, the new work is decided
        by ref_start's book alone: a straddling 12/13 window is left in
        part.12, a straddling 13/14 window moves to part.13. When a row's
        work changes, its id changes too, keeping the ":scale:ordinal"
        suffix and only replacing the work prefix (ids look like
        "wordsworth.prelude.part.12:fine:400"; nothing in the backend
        parses that suffix as a line offset, so leaving it as-is is safe
        and matches how apply_lucretius_lucan_editions.py treats ids).
     b. table lines (work, ord, ref, text), which backend/window_texts.py
        reads by work and by ord range for the Reader's line view: rows for
        "wordsworth.prelude" get ref remapped in place (still one work, one
        ord sequence). Rows for "wordsworth.prelude.part.12" are dropped
        and rebuilt from scratch, split across part.12/13/14, by reading
        the three current .tess files directly and renumbering ord from 0
        within each. Re-reading the files rather than remapping row by row
        avoids having to also recompute per-work ord ranges by hand.
     c. descriptions.jsonl: one JSON record per window, keyed by "id". The
        same ref remap and, for part.12 records, the same work/id move as
        window_texts. This file is not itself ordered to match ids.json
        (the loader in backend/passage_index.py builds a dict from it and
        looks records up by id), so rows can be rewritten in place without
        touching file order.
     d. ids.json: the embedding row order backend/passage_index.py depends
        on (ids.json[i] names the window at embeddings.npy row i). This
        script never reorders or drops entries, only renames the ones that
        moved from part.12 to part.13/14, using the exact same id -> new_id
        mapping computed for window_texts.db in step 1a (the id rename
        decision needs each row's ref_start, which window_texts.db carries
        for every window including ones with no description; deciding from
        descriptions.jsonl alone would miss the 2026-08-23 batch of
        undescribed windows noted in passage_index.py). embeddings.npy is
        never touched: no rows are added, dropped, or reordered, so the
        vectors stay valid for their (possibly renamed) id.
  2. cached fusion results naming any of the four post-split Prelude works
     (wordsworth.prelude, .part.12, .part.13, .part.14) are deleted, since a
     part.12 result may have been computed and cached back when part.12
     covered books XII-XIV.
Not done here (run separately, in this order, before this script):
  scripts/batch_lemma_cache.py en   (rebuilds the four stale caches: the
     whole file and part.12/13/14; batch_lemma_cache.py takes a language,
     not a file list, and reprocesses everything under that language, which
     covers these four along with the rest of the English corpus)
  scripts/corpus/add_texts_to_index.py --replace <files...> on a COPY of
     data/inverted_index/en_index.db, then swap the copy in. --replace uses
     argparse nargs='*', so it takes every filename listed after ONE
     --replace flag, e.g.:
       --replace wordsworth.prelude.tess wordsworth.prelude.part.12.tess \\
                 wordsworth.prelude.part.13.tess wordsworth.prelude.part.14.tess
After this script: the reference checks in tests/search_reference_tests.md.
"""
import glob
import json
import os
import re
import shutil
import sqlite3
import sys
import time

ROOT = os.getcwd()
APPLY = '--apply' in sys.argv
STAMP = time.strftime('%Y%m%d-%H%M%S')

WHOLE = 'wordsworth.prelude'
OLD_PART = 'wordsworth.prelude.part.12'
NEW_PARTS = {13: 'wordsworth.prelude.part.13', 14: 'wordsworth.prelude.part.14'}
ALL_PART_WORKS = [OLD_PART, NEW_PARTS[13], NEW_PARTS[14]]
TEXTS = [WHOLE] + ALL_PART_WORKS

_REF_RE = re.compile(r'^(wordsworth prelude) 12\.(\d+)$')
_BOOK_LINE_RE = re.compile(r'^wordsworth prelude (\d+)\.(\d+)$')


def remap(ref):
    """Old "wordsworth prelude 12.N" (the merged book 12/13/14 family, N from
    1 to 1170) to its correct book.line form. Any other ref, including an
    already-correct one, passes through unchanged."""
    m = _REF_RE.match(ref or '')
    if not m:
        return ref
    n = int(m.group(2))
    if 1 <= n <= 336:
        book, line = 12, n
    elif 337 <= n <= 714:
        book, line = 13, n - 336
    elif 715 <= n <= 1170:
        book, line = 14, n - 714
    else:
        return ref
    return f'{m.group(1)} {book}.{line}'


def _book_of(ref):
    """The book number of a "wordsworth prelude B.L" ref, or None."""
    m = _BOOK_LINE_RE.match(ref or '')
    return int(m.group(1)) if m else None


def _new_part_work(remapped_ref_start):
    """Which part.N work a part.12 row belongs to after the split, decided
    by its own (already remapped) ref_start's book. Book 12 (or a ref this
    script does not recognise) stays in part.12."""
    book = _book_of(remapped_ref_start)
    return NEW_PARTS.get(book, OLD_PART)


def _new_id(old_id, new_work):
    """Replace an id's work prefix, keeping ":scale:ordinal" unchanged."""
    if ':' not in old_id:
        return old_id
    _, suffix = old_id.split(':', 1)
    return f'{new_work}:{suffix}'


def backup(path):
    if APPLY:
        shutil.copy2(path, f'{path}.bak-prelude-{STAMP}')


def tess_units(path):
    """[(ref, text), ...] for a .tess file, in file order."""
    out = []
    for line in open(path, encoding='utf-8'):
        if line.startswith('<') and '>' in line:
            e = line.index('>')
            out.append((line[1:e].strip(), line[e + 1:].strip()))
    return out


def _straddles(new_rs, new_re):
    bs, be = _book_of(new_rs), _book_of(new_re)
    return bs is not None and be is not None and bs != be


def window_texts_db():
    """Step 1a/1b: remap and, for part.12, rename rows in window_texts.db.

    Returns the id -> new_id map for rows that moved to part.13/14, which
    is also the map applied to descriptions.jsonl and ids.json, so all three
    stores agree on the same renames.
    """
    wdb = os.path.join(ROOT, 'data', 'passage_index', 'window_texts.db')
    if not os.path.exists(wdb):
        print('  window_texts.db: not present, skipping')
        return {}
    c = sqlite3.connect(f'file:{wdb}?mode=ro', uri=True)
    w_rows = c.execute(
        'select rowid, id, work, ref_start, ref_end from window_texts '
        'where work in (?, ?)', (WHOLE, OLD_PART)).fetchall()
    c.close()

    id_rename = {}
    w_updates = []  # (new_id, new_work, new_ref_start, new_ref_end, rowid)
    n_whole, n_moved, n_straddle = 0, {13: 0, 14: 0}, 0
    for rowid, wid, work, rs, re_ in w_rows:
        new_rs, new_re = remap(rs), remap(re_)
        if (new_rs != rs or new_re != re_) and _straddles(new_rs, new_re):
            n_straddle += 1
        if work == WHOLE:
            if new_rs != rs or new_re != re_:
                n_whole += 1
            w_updates.append((wid, work, new_rs, new_re, rowid))
        else:  # OLD_PART
            new_work = _new_part_work(new_rs)
            new_id = wid
            if new_work != OLD_PART:
                new_id = _new_id(wid, new_work)
                id_rename[wid] = new_id
                book = 13 if new_work == NEW_PARTS[13] else 14
                n_moved[book] += 1
            w_updates.append((new_id, new_work, new_rs, new_re, rowid))
    print(f'  window_texts.db window_texts: whole-work rows remapped: {n_whole}; '
          f'part.12 windows moved to part.13: {n_moved[13]}, to part.14: {n_moved[14]}; '
          f'windows straddling the new 12/13 or 13/14 boundary (refs remapped independently): {n_straddle}')

    # lines table: whole work updated in place; part.12 dropped and rebuilt
    # from the three current .tess files.
    conn_ro = sqlite3.connect(f'file:{wdb}?mode=ro', uri=True)
    l_whole = conn_ro.execute(
        'select rowid, ref from lines where work=?', (WHOLE,)).fetchall()
    part_count_before = conn_ro.execute(
        'select count(*) from lines where work=?', (OLD_PART,)).fetchone()[0]
    conn_ro.close()
    l_updates = [(remap(ref), rowid) for rowid, ref in l_whole if remap(ref) != ref]
    print(f'  window_texts.db lines: {WHOLE}: {len(l_updates)} refs remapped in place')

    new_part_lines = {}
    for work_name, fname in ((OLD_PART, 'wordsworth.prelude.part.12.tess'),
                              (NEW_PARTS[13], 'wordsworth.prelude.part.13.tess'),
                              (NEW_PARTS[14], 'wordsworth.prelude.part.14.tess')):
        path = os.path.join(ROOT, 'texts', 'en', fname)
        new_part_lines[work_name] = tess_units(path) if os.path.exists(path) else None

    for work_name, units in new_part_lines.items():
        n = len(units) if units is not None else 'FILE MISSING'
        print(f'  window_texts.db lines: {work_name}: {part_count_before if work_name == OLD_PART else 0} '
              f'stored (old) -> {n} from the current file')

    if not APPLY:
        return id_rename

    new = wdb + '.new'
    shutil.copy2(wdb, new)
    c = sqlite3.connect(new)
    c.executemany(
        'update window_texts set id=?, work=?, ref_start=?, ref_end=? where rowid=?',
        w_updates)
    c.executemany('update lines set ref=? where rowid=?', l_updates)
    c.execute('delete from lines where work=?', (OLD_PART,))
    for work_name, units in new_part_lines.items():
        if units is None:
            continue
        c.execute('delete from lines where work=?', (work_name,))
        c.executemany(
            'insert into lines (work, ord, ref, text) values (?,?,?,?)',
            [(work_name, i, ref, text) for i, (ref, text) in enumerate(units)])
    c.commit(); c.close()
    backup(wdb)
    os.replace(new, wdb)
    return id_rename


def passage_descriptions(id_rename):
    """Step 1c: descriptions.jsonl. Falls back to a ref-derived rename for
    any part.12 id window_texts.db did not have a row for (an undescribed
    window can still carry a description record, or vice versa), so the
    file agrees with window_texts.db even if the two stores disagree on
    which ids they cover."""
    dpath = os.path.join(ROOT, 'data', 'passage_index', 'descriptions.jsonl')
    if not os.path.exists(dpath):
        print('  descriptions.jsonl: not present, skipping')
        return id_rename
    out_lines = []
    n_whole, n_moved, n_straddle = 0, {13: 0, 14: 0}, 0
    id_rename = dict(id_rename)
    with open(dpath, encoding='utf-8') as fh:
        for line in fh:
            try:
                r = json.loads(line)
            except ValueError:
                out_lines.append(line)
                continue
            work = r.get('work')
            if work not in (WHOLE, OLD_PART):
                out_lines.append(line)
                continue
            rs, re_ = r.get('ref_start'), r.get('ref_end')
            new_rs, new_re = remap(rs), remap(re_)
            if (new_rs != rs or new_re != re_) and _straddles(new_rs, new_re):
                n_straddle += 1
            r['ref_start'], r['ref_end'] = new_rs, new_re
            if work == WHOLE:
                if new_rs != rs or new_re != re_:
                    n_whole += 1
            else:
                old_id = r.get('id')
                new_work = _new_part_work(new_rs)
                new_id = id_rename.get(old_id)
                if new_id is None and new_work != OLD_PART:
                    new_id = _new_id(old_id, new_work)
                    id_rename[old_id] = new_id
                if new_id is not None:
                    r['work'] = new_work
                    r['id'] = new_id
                    book = 13 if new_work == NEW_PARTS[13] else 14
                    n_moved[book] += 1
            out_lines.append(json.dumps(r, ensure_ascii=False) + '\n')
    print(f'  descriptions.jsonl: whole-work rows remapped: {n_whole}; '
          f'part.12 windows moved to part.13: {n_moved[13]}, to part.14: {n_moved[14]}; '
          f'straddling windows: {n_straddle}')
    if APPLY:
        backup(dpath)
        tmp = dpath + '.new'
        with open(tmp, 'w', encoding='utf-8') as out:
            out.writelines(out_lines)
        os.replace(tmp, dpath)
    return id_rename


def ids_json(id_rename):
    """Step 1d: rename entries in place, same order, same count."""
    ipath = os.path.join(ROOT, 'data', 'passage_index', 'ids.json')
    if not os.path.exists(ipath):
        print('  ids.json: not present, skipping')
        return
    ids = json.load(open(ipath, encoding='utf-8'))
    new_ids = [id_rename.get(i, i) for i in ids]
    n_renamed = sum(1 for a, b in zip(ids, new_ids) if a != b)
    print(f'  ids.json: {n_renamed} ids renamed, order and count unchanged ({len(ids)})')
    if APPLY:
        backup(ipath)
        tmp = ipath + '.new'
        json.dump(new_ids, open(tmp, 'w', encoding='utf-8'), ensure_ascii=False)
        os.replace(tmp, ipath)


def fusion_cache():
    names = set(TEXTS) | {t + '.tess' for t in TEXTS}
    hit = []
    for p in glob.glob(os.path.join(ROOT, 'cache', '*.json')):
        try:
            d = json.load(open(p, encoding='utf-8'))
        except Exception:
            continue
        if isinstance(d, dict) and (d.get('source') in names or d.get('target') in names):
            hit.append(p)
    print(f'  fusion cache: {len(hit)} cached results name one of the four Prelude works')
    if APPLY:
        for p in hit:
            os.remove(p)


if __name__ == '__main__':
    print(('APPLY' if APPLY else 'DRY RUN') + ' on ' + ROOT)
    whole_path = os.path.join(ROOT, 'texts', 'en', WHOLE + '.tess')
    if os.path.exists(whole_path):
        first14 = [ref for ref, _ in tess_units(whole_path) if ref.startswith('wordsworth prelude 14.')]
        if not first14:
            raise SystemExit('the whole-work file has no book 14 tags yet; pull the retagged texts first')
    id_rename = window_texts_db()
    id_rename = passage_descriptions(id_rename)
    ids_json(id_rename)
    fusion_cache()
