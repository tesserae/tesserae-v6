"""The 2026-09-16 Prelude retag: Wordsworth's Prelude carried Books XII, XIII
and XIV under one tag family, "<wordsworth prelude 12.N>" for N 1-1170.
Checks that the whole file now has 14 distinct books with the right line
counts, that the part files match the whole file line for line, and that
line numbers within each book run consecutively from 1."""
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EN = os.path.join(ROOT, 'texts', 'en')

TAG_RE = re.compile(r'^<wordsworth prelude (\d+)\.(\d+)>\t(.*)$')

EXPECTED_COUNTS = {
    1: 649, 2: 479, 3: 640, 4: 471, 5: 607, 6: 780, 7: 771, 8: 689, 9: 588,
    10: 607, 11: 474, 12: 336, 13: 378, 14: 456,
}


def _whole_units():
    """[(book, line, text), ...] in file order."""
    out = []
    with open(os.path.join(EN, 'wordsworth.prelude.tess'), encoding='utf-8') as f:
        for raw in f:
            m = TAG_RE.match(raw)
            assert m, f'malformed or unexpected tag: {raw!r}'
            out.append((int(m.group(1)), int(m.group(2)), m.group(3)))
    return out


def _part_units(n):
    path = os.path.join(EN, f'wordsworth.prelude.part.{n}.tess')
    out = []
    with open(path, encoding='utf-8') as f:
        for raw in f:
            m = TAG_RE.match(raw)
            assert m, f'malformed or unexpected tag in part.{n}: {raw!r}'
            out.append((int(m.group(1)), int(m.group(2)), m.group(3)))
    return out


def test_fourteen_books():
    units = _whole_units()
    books = sorted({b for b, _l, _t in units})
    assert books == list(range(1, 15)), books


def test_book_line_counts():
    units = _whole_units()
    counts = {}
    for b, _l, _t in units:
        counts[b] = counts.get(b, 0) + 1
    assert counts == EXPECTED_COUNTS


def test_lines_consecutive_within_each_book():
    units = _whole_units()
    by_book = {}
    for b, l, _t in units:
        by_book.setdefault(b, []).append(l)
    for b, lines in by_book.items():
        assert lines == list(range(1, len(lines) + 1)), f'book {b} not consecutive from 1'


def test_part_files_match_whole_file_per_book():
    whole = _whole_units()
    for n in (12, 13, 14):
        want = [(b, l, t) for (b, l, t) in whole if b == n]
        got = _part_units(n)
        assert got == want, f'part.{n}.tess does not match book {n} of the whole file'
        assert len(got) == EXPECTED_COUNTS[n]


def test_part_12_no_longer_carries_books_13_and_14():
    got = _part_units(12)
    assert all(b == 12 for b, _l, _t in got)
