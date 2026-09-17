#!/usr/bin/env python3
"""Downstream repair for the 2026-09-16 Paradise Lost renumbering: the corpus
files texts/en/milton.paradise_lost.tess and .part.1.tess .. part.12.tess
used to tag every book's lines starting at ".2", with a duplicated tag a few
lines in absorbing the shift (books 4, 5 and 6 carry a second duplicate
deeper in), and Book 4 carried one whitespace-only row (old tag "4.393")
that scripts/corpus/renumber_paradise_lost.py drops entirely, per a
coordinator decision the same day. scripts/corpus/renumber_paradise_lost.py
fixes the .tess files themselves, by git, dropping that one row and giving
each book's remaining lines consecutive tags 1..n in file order. This
script brings the stores that copied the old, buggy tags (and the deleted
row) into line, on the production root, dry run by default.

    cd /var/www/tesseraev6_flask
    venv/bin/python scripts/corpus/apply_paradise_lost_numbering.py [--apply]

Why this remap can't be a string-to-string function (contrast with
apply_prelude_books.py's remap(), which is exactly that): the OLD tags are
themselves ambiguous. Two different physical lines can carry the identical
old tag (e.g. two different lines both read "Milton P.L. 4.395"), so a bare
"old ref -> new ref" table cannot be built at all -- the same old ref string
has to map to two different new refs depending on WHICH physical line it
was. The fix is positional: the old .tess file and the new one hold the
same lines in the same order (minus the one dropped row), so what
identifies a line is not its old tag but its position -- its book and its
1-based index within that book, in the ORIGINAL (pre-fix, still-live-in-
production) numbering. BOOK_LINE_COUNTS below is that original per-book
count (Book 4 still 1,016: production hasn't been retagged yet when this
script runs, so its `ord` values still span the whitespace-only row). The
`lines` table already carries that original position for every stored
line, as `ord` (0-based, per work), so remap_ref_by_position() below turns
(work, ord) directly into the new ref, applying two corrections in order:
Book 4's DELETED_POSITION (dropping one position out of the run, shifting
every later position in that book down by one) and, only then, whatever
formatting the position into "book.line" needs. window_texts rows and
descriptions.jsonl records don't carry ord, only ref_start/ref_end strings,
so those are resolved by looking the ref string up in the SAME work's rows
in the `lines` table (built once, per work, into an old-ref -> sorted ords
index) and taking the EARLIEST ord among matches -- the documented rule for
a duplicated old tag, both here and in renumber_paradise_lost.py's
docstring. For the rare case where the `lines` table has no row for that
work at all (so a window's boundary can't be resolved from stored lines),
OLD_SEGMENTS below is a hand-built fallback: per book, the (position range,
constant offset) segments of the old, buggy numbering, read off the
pre-fix corpus file at the commit before this fix (old_tag = position +
offset within each segment). Both paths resolve to the same
earliest-occurrence rule when a segment boundary is itself a duplicate.

Book 4's deleted row (original position 393) needs one more rule, since a
window's ref_start or ref_end can land exactly there: coordinator decision,
2026-09-16 -- a ref_start pointing at the deleted row moves to the NEXT
real line (the window's start creeps forward into what is now there), and a
ref_end pointing at it moves to the PREVIOUS real line (the window's end
creeps back to the last real line still inside it). remap_ref_by_position()
takes a `boundary` argument ('start' or 'end') for exactly this; a direct
`lines`-table row that lands on position 393 has no such rule to apply (it
IS the row being deleted, not a boundary pointing near it), so that row is
dropped from the `lines` table outright, the same as from the .tess files,
rather than remapped -- see lines_table() below.

Steps (each reported; --apply writes, with dated backups):
  1. passage index, data/passage_index/:
     a. window_texts.db, table window_texts (id, language, work, ref_start,
        ref_end, text): every row whose work is milton.paradise_lost or
        milton.paradise_lost.part.N (N 1-12) gets ref_start and ref_end
        remapped by position, as described above. No id or work changes:
        the retag does not rename or move any work, so unlike the Prelude
        split, ids.json and embeddings.npy need no attention at all here.
     b. table lines (work, ord, ref, text): rows for the same thirteen
        works get ref remapped in place, directly from ord (no lookup
        needed -- ord to new ref is a pure position formula), EXCEPT the
        one row at Book 4's deleted position, which is deleted outright.
        This pass also builds the old-ref -> ords index that step 1a and
        (2) read, so it runs first.
     c. descriptions.jsonl: one JSON record per window, keyed by id. Same
        ref_start/ref_end remap as window_texts, same no id/work change.
  2. cached fusion results naming any of the thirteen Paradise Lost works
     are deleted, since a cached result may have been computed against the
     old, buggy line numbers.
  3. ids.json and embeddings.npy: untouched. No work is renamed, added, or
     removed, and no window's text changes, so the embedding row for a
     given id is still that window's embedding after the retag. The one
     edge case worth a manual look after deploy: a window whose ref_start
     AND ref_end both pointed at Book 4's deleted row (a window that was
     nothing but that one blank line) would remap to a start after its
     end; this script does not special-case that (window_texts_table()
     prints a warning if it finds one, but does not repair it), since
     fixing it means dropping or resizing a window, which touches
     ids.json and embeddings.npy and was ruled out of scope here.
Not done here (run separately, in this order, before this script):
  scripts/batch_lemma_cache.py en   (rebuilds the stale lemma cache entries
     for the thirteen Paradise Lost files; batch_lemma_cache.py takes a
     language, not a file list, and reprocesses everything under that
     language, which covers these thirteen along with the rest of the
     English corpus)
  scripts/corpus/add_texts_to_index.py --replace <files...> on a COPY of
     data/inverted_index/en_index.db, then swap the copy in. --replace uses
     argparse nargs='*', so it takes every filename listed after ONE
     --replace flag, e.g.:
       --replace milton.paradise_lost.tess milton.paradise_lost.part.1.tess \\
                 milton.paradise_lost.part.2.tess ... milton.paradise_lost.part.12.tess
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

WHOLE = 'milton.paradise_lost'
N_BOOKS = 12
PARTS = {n: f'milton.paradise_lost.part.{n}' for n in range(1, N_BOOKS + 1)}
ALL_WORKS = [WHOLE] + list(PARTS.values())

# Each book's physical line count as it still stands in PRODUCTION at the
# moment this script runs (before the corpus fix is deployed): the ORIGINAL,
# pre-fix count, including Book 4's whitespace-only row. `ord` values in the
# stores this script reads were written against that original layout, so
# this is what decomposes an ord into (book, original 1-based position).
BOOK_LINE_COUNTS = {
    1: 798, 2: 1055, 3: 742, 4: 1016, 5: 907, 6: 912,
    7: 640, 8: 653, 9: 1189, 10: 1104, 11: 901, 12: 649,
}
_CUM_START = {}
_c = 0
for _b in range(1, N_BOOKS + 1):
    _CUM_START[_b] = _c
    _c += BOOK_LINE_COUNTS[_b]
TOTAL_LINES = _c  # 10566, the ORIGINAL (pre-fix) total; see module docstring

# Coordinator decision, 2026-09-16: Book 4's whitespace-only row (a
# digitization artifact, not a line of verse) is dropped, not renumbered.
# Its ORIGINAL 1-based position within Book 4 (before this drop, i.e. the
# same numbering BOOK_LINE_COUNTS uses). Every later position in that book
# shifts down by one; see _apply_book4_deletion().
DELETED_POSITION = {4: 393}

# Fallback only (see module docstring): per book, the old numbering's
# (position_start, position_end, offset) segments, old_tag = position +
# offset within a segment, read off the pre-fix corpus (commit before this
# fix). 1-based positions, inclusive ranges.
OLD_SEGMENTS = {
    1: [(1, 4, 1), (5, 655, 0), (656, 659, 5899), (660, 798, 0)],
    2: [(1, 4, 1), (5, 1055, 0)],
    3: [(1, 4, 1), (5, 364, 0), (365, 369, 3000), (370, 742, 0)],
    4: [(1, 4, 1), (5, 395, 0), (396, 1016, -1)],
    5: [(1, 4, 1), (5, 450, 0), (451, 454, -1), (455, 907, 0)],
    6: [(1, 4, 1), (5, 598, 0), (599, 604, 1), (605, 912, 0)],
    7: [(1, 4, 1), (5, 640, 0)],
    8: [(1, 4, 1), (5, 653, 0)],
    9: [(1, 4, 1), (5, 1189, 0)],
    10: [(1, 4, 1), (5, 1104, 0)],
    11: [(1, 4, 1), (5, 901, 0)],
    12: [(1, 4, 1), (5, 649, 0)],
}

_REF_RE = re.compile(r'^Milton P\.L\. (\d+)\.(\d+)$')


def _book_of_work(work):
    if work == WHOLE:
        return None  # whole work spans all 12 books; book comes from ord
    for n, name in PARTS.items():
        if name == work:
            return n
    return None


def _decompose_position(work, ord_):
    """(work, 0-based ORIGINAL ord) -> (book, ORIGINAL 1-based position
    within that book), before the Book 4 deletion adjustment. Pure position
    formula, no lookup."""
    if work == WHOLE:
        for b in range(1, N_BOOKS + 1):
            start = _CUM_START[b]
            if start <= ord_ < start + BOOK_LINE_COUNTS[b]:
                return b, ord_ - start + 1
        raise ValueError(f'ord {ord_} out of range for {work} (0-{TOTAL_LINES - 1})')
    book = _book_of_work(work)
    if book is None:
        raise ValueError(f'not a Paradise Lost work: {work!r}')
    return book, ord_ + 1


def _apply_book4_deletion(book, line, boundary):
    """ORIGINAL (book, position) -> position after dropping Book 4's
    whitespace-only row. `boundary` is 'start' or 'end' for a window
    ref_start/ref_end that lands exactly on the deleted position (moved to
    the next or previous real line respectively, per the coordinator's
    2026-09-16 decision); None for a `lines`-table row naming an actual
    stored line, which should never be asked to remap the deleted position
    itself -- that row is dropped outright (see lines_table()), not
    remapped, so this raises if it's ever called that way."""
    dp = DELETED_POSITION.get(book)
    if dp is None:
        return line
    if line == dp:
        if boundary == 'start':
            line = dp + 1
        elif boundary == 'end':
            line = dp - 1
        else:
            raise ValueError(
                f'position {dp} in book {book} is the deleted whitespace-only row; '
                'a direct lines-table row there should be dropped, not remapped')
    return line - 1 if line > dp else line


def remap_ref_by_position(work, ord_, boundary=None):
    """(work, 0-based ORIGINAL ord) -> new ref string, applying the Book 4
    deletion adjustment. This is the ground truth every other function in
    this script ultimately answers to."""
    book, line = _decompose_position(work, ord_)
    line = _apply_book4_deletion(book, line, boundary)
    return f'Milton P.L. {book}.{line}'


def _old_ref_to_book_line(ref):
    m = _REF_RE.match(ref or '')
    if not m:
        return None
    return int(m.group(1)), int(m.group(2))


def _fallback_position(work, old_ref):
    """OLD_SEGMENTS-based position lookup, used only when the lines table
    has no row for (work, old_ref) to resolve positionally. Returns a
    0-based ord, or None if old_ref doesn't parse or isn't in range. Where
    more than one segment could produce old_line (a duplicated old tag),
    picks the segment giving the smallest position -- the earliest
    occurrence, same rule as the lines-table path."""
    parsed = _old_ref_to_book_line(old_ref)
    if parsed is None:
        return None
    ref_book, old_line = parsed
    book = _book_of_work(work) if work != WHOLE else ref_book
    if book != ref_book:
        return None
    candidates = []
    for pos_start, pos_end, offset in OLD_SEGMENTS.get(book, []):
        pos = old_line - offset
        if pos_start <= pos <= pos_end:
            candidates.append(pos)
    if not candidates:
        return None
    position = min(candidates)  # earliest occurrence
    if work == WHOLE:
        return _CUM_START[book] + position - 1
    return position - 1


def resolve_ref(work, old_ref, lines_index, boundary):
    """old_ref string -> new_ref string, for one (work, ref) pair, resolving
    a duplicated old tag to its earliest position, and remapping through
    the Book 4 deletion with the given boundary ('start' or 'end', for a
    window's ref_start/ref_end -- see _apply_book4_deletion()). lines_index
    is that work's {old_ref: sorted ords}, from lines_table(); falls back
    to OLD_SEGMENTS if the ref isn't in it."""
    if old_ref in lines_index:
        ord_ = lines_index[old_ref][0]
    else:
        ord_ = _fallback_position(work, old_ref)
    if ord_ is None:
        return old_ref  # not a Paradise Lost ref we recognise; pass through
    return remap_ref_by_position(work, ord_, boundary)


def backup(path):
    if APPLY:
        shutil.copy2(path, f'{path}.bak-milton-{STAMP}')


def lines_table(conn_path):
    """Step 1b (runs first): remap `ref` in the lines table in place, one
    row at a time, straight from that row's own ord -- no ambiguity, no
    lookup needed for this table -- EXCEPT the one row that sits exactly on
    Book 4's deleted position, which is dropped outright rather than
    remapped (it IS the whitespace-only artifact, the same row
    renumber_paradise_lost.py drops from the .tess files). Also returns
    {work: {old_ref: sorted ords}} built from the rows as read (before any
    row is dropped or remapped), for steps 1a and 1c to resolve
    window/description ref_start/ref_end strings against."""
    c = sqlite3.connect(f'file:{conn_path}?mode=ro', uri=True)
    indices = {}
    updates = []  # (new_ref, rowid)
    deletes = []  # rowid
    total = 0
    for work in ALL_WORKS:
        idx = {}
        for rowid, ord_, ref in c.execute(
                'select rowid, ord, ref from lines where work=? order by ord', (work,)):
            idx.setdefault(ref, []).append(ord_)
            book, line = _decompose_position(work, ord_)
            if line == DELETED_POSITION.get(book):
                deletes.append(rowid)
                continue
            new_ref = remap_ref_by_position(work, ord_)
            if new_ref != ref:
                updates.append((new_ref, rowid))
                total += 1
        for refs in idx.values():
            refs.sort()
        indices[work] = idx
    c.close()
    print(f'  window_texts.db lines: {total} refs remapped in place, {len(deletes)} row(s) dropped '
          f'(the whitespace-only Book 4 artifact) across {len(ALL_WORKS)} works')

    if APPLY:
        conn = sqlite3.connect(conn_path)
        if updates:
            conn.executemany('update lines set ref=? where rowid=?', updates)
        if deletes:
            conn.executemany('delete from lines where rowid=?', [(r,) for r in deletes])
        conn.commit()
        conn.close()
    return indices


def window_texts_table(conn_path, indices):
    """Step 1a: remap ref_start/ref_end in window_texts, by looking each up
    in that row's own work's lines-table index (built by lines_table(), on
    the OLD refs, before they were rewritten). ref_start resolves with
    boundary='start' (a ref_start landing on Book 4's deleted row moves
    forward to the next real line), ref_end with boundary='end' (moves back
    to the previous real line) -- see _apply_book4_deletion()."""
    c = sqlite3.connect(f'file:{conn_path}?mode=ro', uri=True)
    rows = c.execute(
        'select rowid, id, work, ref_start, ref_end from window_texts where work in (%s)'
        % ','.join('?' * len(ALL_WORKS)), ALL_WORKS).fetchall()
    c.close()

    updates = []  # (new_rs, new_re, rowid)
    n_remapped = 0
    degenerate = []  # ids where the remapped window collapsed (start past end)
    for rowid, wid, work, rs, re_ in rows:
        idx = indices.get(work, {})
        new_rs = resolve_ref(work, rs, idx, 'start')
        new_re = resolve_ref(work, re_, idx, 'end')
        if new_rs != rs or new_re != re_:
            n_remapped += 1
        start_bl = _old_ref_to_book_line(new_rs)
        end_bl = _old_ref_to_book_line(new_re)
        if start_bl and end_bl and start_bl[0] == end_bl[0] and start_bl[1] > end_bl[1]:
            degenerate.append(wid)
        updates.append((new_rs, new_re, rowid))
    print(f'  window_texts.db window_texts: {n_remapped} of {len(rows)} rows remapped')
    if degenerate:
        print(f'  WARNING: {len(degenerate)} window(s) were nothing but Book 4\'s deleted row '
              f'and were NOT repaired (out of scope here): {degenerate}')

    if APPLY and updates:
        conn = sqlite3.connect(conn_path)
        conn.executemany(
            'update window_texts set ref_start=?, ref_end=? where rowid=?', updates)
        conn.commit()
        conn.close()


def window_texts_db():
    """Steps 1a and 1b together (1b must run first to build the indices).
    Returns {work: {old_ref: sorted ords}} for passage_descriptions() to
    reuse (empty per-work dicts, forcing the OLD_SEGMENTS fallback, if the
    db isn't present)."""
    wdb = os.path.join(ROOT, 'data', 'passage_index', 'window_texts.db')
    if not os.path.exists(wdb):
        print('  window_texts.db: not present, skipping')
        return {w: {} for w in ALL_WORKS}
    if APPLY:
        backup(wdb)
    indices = lines_table(wdb)
    window_texts_table(wdb, indices)
    return indices


def passage_descriptions(indices):
    """Step 1c: descriptions.jsonl, same remap as window_texts, no id/work
    change. indices comes from lines_table() (empty dict per work if
    window_texts.db wasn't present, meaning every ref falls through to the
    OLD_SEGMENTS fallback)."""
    dpath = os.path.join(ROOT, 'data', 'passage_index', 'descriptions.jsonl')
    if not os.path.exists(dpath):
        print('  descriptions.jsonl: not present, skipping')
        return
    out_lines = []
    n_remapped = 0
    n_total = 0
    with open(dpath, encoding='utf-8') as fh:
        for line in fh:
            try:
                r = json.loads(line)
            except ValueError:
                out_lines.append(line)
                continue
            work = r.get('work')
            if work not in ALL_WORKS:
                out_lines.append(line)
                continue
            n_total += 1
            idx = indices.get(work, {})
            rs, re_ = r.get('ref_start'), r.get('ref_end')
            new_rs = resolve_ref(work, rs, idx, 'start')
            new_re = resolve_ref(work, re_, idx, 'end')
            if new_rs != rs or new_re != re_:
                n_remapped += 1
            r['ref_start'], r['ref_end'] = new_rs, new_re
            out_lines.append(json.dumps(r, ensure_ascii=False) + '\n')
    print(f'  descriptions.jsonl: {n_remapped} of {n_total} Paradise Lost records remapped')
    if APPLY:
        backup(dpath)
        tmp = dpath + '.new'
        with open(tmp, 'w', encoding='utf-8') as out:
            out.writelines(out_lines)
        os.replace(tmp, dpath)


def fusion_cache():
    names = set(ALL_WORKS) | {w + '.tess' for w in ALL_WORKS}
    hit = []
    for p in glob.glob(os.path.join(ROOT, 'cache', '*.json')):
        try:
            d = json.load(open(p, encoding='utf-8'))
        except Exception:
            continue
        if isinstance(d, dict) and (d.get('source') in names or d.get('target') in names):
            hit.append(p)
    print(f'  fusion cache: {len(hit)} cached results name one of the thirteen Paradise Lost works')
    if APPLY:
        for p in hit:
            os.remove(p)


def _tess_units(path):
    out = []
    for line in open(path, encoding='utf-8'):
        if line.startswith('<') and '>' in line:
            e = line.index('>')
            out.append((line[1:e].strip(), line[e + 1:].strip()))
    return out


if __name__ == '__main__':
    print(('APPLY' if APPLY else 'DRY RUN') + ' on ' + ROOT)
    whole_path = os.path.join(ROOT, 'texts', 'en', WHOLE + '.tess')
    if os.path.exists(whole_path):
        units = _tess_units(whole_path)
        if not units or units[0][0] != 'Milton P.L. 1.1':
            raise SystemExit('the whole-work file does not start at "Milton P.L. 1.1"; '
                              'pull the retagged texts (renumber_paradise_lost.py) first')
    indices = window_texts_db()
    passage_descriptions(indices)
    fusion_cache()
