"""The 2026-09-16 Paradise Lost renumbering: every book of
texts/en/milton.paradise_lost.tess used to start its tags at ".2" (an
off-by-one at the head of the book, absorbed a few lines in by a duplicated
tag), which scripts/corpus/renumber_paradise_lost.py fixes by giving each
book's lines consecutive tags 1..n in file order. Checks that the whole
file now has twelve books each running 1..n with no duplicate and no gap,
that the total line count is 10,565 (10,566 minus the one whitespace-only
digitization artifact in Book 4 the coordinator had dropped, 2026-09-16),
that the part files match the whole file line for line, and spot-checks the
poem's famous first and last lines."""
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EN = os.path.join(ROOT, 'texts', 'en')

TAG_RE = re.compile(r'^<Milton P\.L\. (\d+)\.(\d+)>\t(.*)$')
N_BOOKS = 12
TOTAL_LINES = 10565
BOOK_4_LINES = 1015


def _whole_units():
    """[(book, line, text), ...] in file order."""
    out = []
    with open(os.path.join(EN, 'milton.paradise_lost.tess'), encoding='utf-8') as f:
        for raw in f:
            line = raw.rstrip('\n')
            m = TAG_RE.match(line)
            assert m, f'malformed or unexpected tag: {line!r}'
            out.append((int(m.group(1)), int(m.group(2)), m.group(3)))
    return out


def _part_units(n):
    path = os.path.join(EN, f'milton.paradise_lost.part.{n}.tess')
    out = []
    with open(path, encoding='utf-8') as f:
        for raw in f:
            line = raw.rstrip('\n')
            m = TAG_RE.match(line)
            assert m, f'malformed or unexpected tag in part.{n}: {line!r}'
            out.append((int(m.group(1)), int(m.group(2)), m.group(3)))
    return out


def test_twelve_books():
    units = _whole_units()
    books = sorted({b for b, _l, _t in units})
    assert books == list(range(1, N_BOOKS + 1)), books


def test_whole_file_line_count():
    units = _whole_units()
    assert len(units) == TOTAL_LINES


def test_book_four_line_count():
    units = _whole_units()
    book4 = [1 for b, _l, _t in units if b == 4]
    assert len(book4) == BOOK_4_LINES


def test_no_whitespace_only_lines_remain():
    units = _whole_units()
    blanks = [(b, l) for b, l, t in units if t.strip() == '']
    assert not blanks, f'whitespace-only rows should have been dropped: {blanks}'


def test_lines_consecutive_within_each_book_no_dup_no_gap():
    units = _whole_units()
    by_book = {}
    for b, l, _t in units:
        by_book.setdefault(b, []).append(l)
    for b, lines in by_book.items():
        assert lines == list(range(1, len(lines) + 1)), f'book {b} not consecutive from 1 with no dup/gap'


def test_part_files_match_whole_file_per_book():
    whole = _whole_units()
    for n in range(1, N_BOOKS + 1):
        want = [(b, l, t) for (b, l, t) in whole if b == n]
        got = _part_units(n)
        assert got == want, f'part.{n}.tess does not match book {n} of the whole file'


def test_first_line_of_book_one():
    units = _whole_units()
    book, line, text = units[0]
    assert (book, line) == (1, 1)
    assert 'OF Mans First Disobedience' in text


def test_last_line_of_book_twelve():
    units = _whole_units()
    book, line, text = units[-1]
    assert (book, line) == (12, 649)
    assert 'Through Eden took thir solitarie way' in text
