#!/usr/bin/env python3
"""Fix the Paradise Lost line-numbering defect: texts/en/milton.paradise_lost.tess
and its twelve part files (part.1.tess .. part.12.tess) number lines wrongly
near the start of every book. Every book's first tag reads ".2" instead of
".1" ("OF Mans First Disobedience" was tagged 1.2, though every edition
gives it as 1.1), and a duplicated tag a few lines in absorbs that one-line
shift, after which the rest of the book's tags already run correctly. Three
books (4, 5, 6) carry a second duplicate deeper in, and four books (1, 3, 5,
6) also carry a gap (a skipped number) somewhere.

The fix has two parts:

1. Drop the one whitespace-only row. Book 4 carries a line holding a single
   space and no words (old tag "4.393", whole-file line 2988) -- a
   digitization artifact, not a line of verse, and the reason Book 4 had
   1,016 physical rows against the standard 1,015 for that book (confirmed
   by search against multiple independent sources). Coordinator decision,
   2026-09-16: delete that one row, from both the whole file and part.4.
   This is a deliberate, one-line, hand-identified exception to "never
   delete a line" -- every other line in the corpus is untouched. The row
   is found by content (its text is empty once stripped of whitespace),
   not by position, so this step is a no-op if run again after the row is
   already gone.

2. Renumber each remaining book 1..n in file order, n being that book's
   actual line count after step 1. Given the hard constraints (line order
   unchanged, every book strictly consecutive with no duplicate and no
   gap), a simple count of each book's physical rows is the only
   order-preserving bijection onto 1..n, so there is no alternative scheme
   to weigh it against.

Both steps were checked against Verity's commentary
(data/commentaries/verity__milton.paradise_lost.json in the tesserae-preview
checkout, 1,372 lemma-bearing notes) before being adopted; see the commit
body for the numbers and for one thing worth knowing before trusting a raw
agreement-rate figure at face value: Verity's own ref field appears to carry
the same off-by-one as this corpus for the first four or five lines of most
books (e.g. its note on "mortal" in Book 1 is filed at ref 1.3, though "Of
that Forbidden Tree, whose mortal tast" is line 1.2 in every edition,
matching this corpus's pre-fix tag for that row, not the true one). Fifteen
for fifteen sampled head-of-book notes across all twelve books showed the
same pattern. That makes raw agreement a poor judge of the fix at the very
head of a book; the fix there is correct regardless, on the independent,
undisputed fact that "Of Man's first disobedience" opens Book 1 at line 1.
scripts/corpus/rekey_verity_paradise_lost.py re-keys Verity's own numbering
to match, for a fairer check.

Usage:
    venv/bin/python scripts/corpus/renumber_paradise_lost.py [--dry-run]

Run from anywhere; paths are resolved relative to the repository root (two
directories up from this file). With --dry-run, prints the per-book report
and writes nothing. Without it, rewrites the whole-file .tess and all twelve
part files in place.
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
EN_DIR = os.path.join(ROOT, 'texts', 'en')
WHOLE_NAME = 'milton.paradise_lost.tess'
N_BOOKS = 12
TOTAL_LINES = 10565  # after dropping the one whitespace-only row (was 10566)

TAG_RE = re.compile(r'^<Milton P\.L\. (\d+)\.(\d+)>\t(.*)$')

DRY_RUN = '--dry-run' in sys.argv


def load_whole():
    """[(old_book, old_line, text), ...] in file order. Raises on any line
    that doesn't match the expected tag form -- this script does not skip
    or guess at malformed input."""
    path = os.path.join(EN_DIR, WHOLE_NAME)
    units = []
    with open(path, encoding='utf-8') as f:
        for i, raw in enumerate(f):
            line = raw.rstrip('\n')
            m = TAG_RE.match(line)
            if not m:
                raise SystemExit(f'{WHOLE_NAME}:{i + 1}: unexpected line, not a Milton P.L. tag: {line!r}')
            units.append((int(m.group(1)), int(m.group(2)), m.group(3)))
    return units


def drop_blank_rows(units):
    """Remove any row whose text is empty once stripped of whitespace --
    the one digitization artifact this fix deletes (see module docstring).
    Returns (kept_units, dropped) where dropped is [(old_book, old_line,
    text), ...] for reporting. A no-op if the row is already gone."""
    kept, dropped = [], []
    for book, old_line, text in units:
        if text.strip() == '':
            dropped.append((book, old_line, text))
        else:
            kept.append((book, old_line, text))
    return kept, dropped


def renumber(units):
    """Assign each unit a new (book, line) pair: book unchanged, line = that
    book's 1-based position in file order. Returns a new units list and a
    per-book report dict."""
    counters = {}
    out = []
    report = {}
    for book, old_line, text in units:
        counters[book] = counters.get(book, 0) + 1
        new_line = counters[book]
        out.append((book, new_line, text))
        r = report.setdefault(book, {'first_old': old_line, 'count': 0})
        r['count'] = new_line
    return out, report


def format_line(book, line, text):
    return f'<Milton P.L. {book}.{line}>\t{text}\n'


def write_whole(new_units):
    path = os.path.join(EN_DIR, WHOLE_NAME)
    with open(path, 'w', encoding='utf-8') as f:
        for book, line, text in new_units:
            f.write(format_line(book, line, text))


def write_parts(new_units):
    for book in range(1, N_BOOKS + 1):
        path = os.path.join(EN_DIR, f'milton.paradise_lost.part.{book}.tess')
        rows = [(b, l, t) for (b, l, t) in new_units if b == book]
        with open(path, 'w', encoding='utf-8') as f:
            for b, l, t in rows:
                f.write(format_line(b, l, t))


def main():
    raw_units = load_whole()
    if len(raw_units) not in (10565, 10566):
        raise SystemExit(f'expected 10565 or 10566 lines in {WHOLE_NAME}, found {len(raw_units)}; '
                          'stopping, not touching anything')

    books_seen = sorted({b for b, _l, _t in raw_units})
    if books_seen != list(range(1, N_BOOKS + 1)):
        raise SystemExit(f'expected books 1..{N_BOOKS}, found {books_seen}')

    old_units, dropped = drop_blank_rows(raw_units)
    if dropped:
        for book, old_line, text in dropped:
            print(f'dropping whitespace-only row: book {book}, old tag {book}.{old_line}, text={text!r}')
    if len(old_units) != TOTAL_LINES:
        raise SystemExit(f'expected {TOTAL_LINES} lines after dropping blanks, found {len(old_units)}; '
                          'stopping, not touching anything')

    new_units, report = renumber(old_units)

    print(f'{"book":>4}  {"old first tag":>15}  {"new tags":>18}  {"lines":>6}  {"old dup rows":>12}')
    for book in range(1, N_BOOKS + 1):
        r = report[book]
        old_dupes = len([1 for b, l, _t in old_units if b == book]) - len({l for b, l, _t in old_units if b == book})
        old_first = f'{book}.{r["first_old"]}'
        new_range = f'{book}.1 - {book}.{r["count"]}'
        print(f'{book:>4}  {old_first:>15}  {new_range:>18}  {r["count"]:>6}  {old_dupes:>12}')

    if DRY_RUN:
        print('\n--dry-run: nothing written.')
        return

    write_whole(new_units)
    write_parts(new_units)
    print(f'\nWrote {WHOLE_NAME} and {N_BOOKS} part files under {EN_DIR}.')


if __name__ == '__main__':
    main()
