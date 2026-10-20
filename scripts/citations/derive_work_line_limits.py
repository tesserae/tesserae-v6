"""Two tables of where a work ends, from the corpus .tess tags (same tag
parsing as derive_work_depth.py), for backend/citations/extractor.py.

1. data/citations/work_book_line_max.json, {work_id: {"<book>": last_line}}:
the last line of each book of a verse work cited by book and line. It catches
a line past the end of its book ("Juv. III. 463": Juvenal 3 has 322 lines, so
the citation is Juvencus's third book or nothing).

2. data/citations/work_single_level_max.json, {work_id: last_number}: the last
number of a work whose every corpus locus has one level and whose lines run
at most MAX_SINGLE_MEAN_CHARS characters on average. It catches a bare number
past the end of the work ("Vit. 466": the Life of Josephus has 430 sections).
The length limit keeps out works whose corpus unit is a chapter or a chunk
and not the cited section (Cicero's Brutus has 97 corpus chunks of about 1,700
characters, and its printed sections run to 333).

Table 1: a work gets an entry only when
  - at least 95 percent of its tagged lines have exactly two levels (book,
    line), counting the combined file and its .part.N files once each, and
  - it is verse: the mean length of its lines is at most MAX_MEAN_CHARS
    characters. Prose works keep chapter and section numbers that differ from
    edition to edition, so a section beyond the corpus's last one proves
    nothing about the printed citation.
Both thresholds are printed by --report, work by work, so the list can be read.

The leading digits of a level are its number ("433c" is 433), as in
derive_work_max_line.py.

Usage:
  python3 derive_work_line_limits.py [--corpus-root PATH] [--out PATH] [--out-single PATH] [--report]
"""
import argparse
import json
import os
import re
import sys
from collections import defaultdict

WORK = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from derive_work_depth import (  # noqa: E402
    DEFAULT_CORPUS_ROOT, TAG_RE, WS_RE, fold_part, _glued_work_and_locus,
)

OUT_PATH = os.path.join(WORK, "data", "citations", "work_book_line_max.json")
OUT_SINGLE_PATH = os.path.join(WORK, "data", "citations", "work_single_level_max.json")
MAX_SINGLE_MEAN_CHARS = 1000
MAX_MEAN_CHARS = 70
# Latin, Greek and English texts only: the Arabic, Persian, Urdu, Hebrew and Coptic
# texts are cited by sura, psalm or poem and verse, with versifications that differ.
LANGS = {"la", "grc", "en"}
MIN_TWO_LEVEL_SHARE = 0.95
_LEADING_DIGITS_RE = re.compile(r"^\d+")


def process_file(path, stats):
    """Adds to stats[work_id] = {"n": tagged lines, "one": lines with one level,
    "two": lines with two levels, "chars": text characters, "books": {book: last
    line}, "maxone": last number among the one-level lines}."""
    stem = os.path.basename(path)
    if stem.endswith(".tess"):
        stem = stem[:-5]
    file_work_id = fold_part(stem)
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.lstrip()
            if not line.startswith("<"):
                continue
            m = TAG_RE.match(line)
            if not m:
                continue
            tag = m.group(1)
            text = line[m.end():].strip()
            if WS_RE.search(tag):
                locus = tag.split()[-1]
                work_id = file_work_id
            else:
                wid, depth = _glued_work_and_locus(tag)
                if wid is None:
                    continue
                work_id = fold_part(wid)
                locus = ".".join(tag.split(".")[-depth:])
            levels = locus.split(".")
            st = stats[work_id]
            st["n"] += 1
            st["chars"] += len(text)
            if len(levels) == 1:
                one = _LEADING_DIGITS_RE.match(levels[0])
                if one:
                    st["one"] += 1
                    st["maxone"] = max(st["maxone"], int(one.group()))
                continue
            if len(levels) != 2:
                continue
            book, ln = (_LEADING_DIGITS_RE.match(x) for x in levels)
            if not book or not ln:
                continue
            st["two"] += 1
            b, v = str(int(book.group())), int(ln.group())
            if v > st["books"].get(b, 0):
                st["books"][b] = v


def derive(corpus_root):
    stats = defaultdict(lambda: {"n": 0, "one": 0, "two": 0, "chars": 0, "books": {}, "maxone": 0})
    for dirpath, _dirs, files in os.walk(corpus_root):
        rel = os.path.relpath(dirpath, corpus_root).split(os.sep)[0]
        if rel not in LANGS:
            continue
        for fn in sorted(files):
            if fn.endswith(".tess"):
                process_file(os.path.join(dirpath, fn), stats)
    return stats


def select(stats):
    out = {}
    for wid, st in stats.items():
        if not st["n"] or not st["books"]:
            continue
        if st["two"] / st["n"] < MIN_TWO_LEVEL_SHARE:
            continue
        if st["chars"] / st["n"] > MAX_MEAN_CHARS:
            continue
        out[wid] = dict(sorted(st["books"].items(), key=lambda kv: int(kv[0])))
    return dict(sorted(out.items()))


def select_single(stats):
    out = {}
    for wid, st in stats.items():
        if st["n"] and st["one"] == st["n"] and st["maxone"] and st["chars"] / st["n"] <= MAX_SINGLE_MEAN_CHARS:
            out[wid] = st["maxone"]
    return dict(sorted(out.items()))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--corpus-root", default=DEFAULT_CORPUS_ROOT)
    ap.add_argument("--out", default=OUT_PATH)
    ap.add_argument("--out-single", default=OUT_SINGLE_PATH)
    ap.add_argument("--report", action="store_true", help="print every two-level work with its mean line length")
    args = ap.parse_args()
    stats = derive(args.corpus_root)
    table = select(stats)
    single = select_single(stats)
    if args.report:
        for wid, st in sorted(stats.items()):
            if st["n"] and st["two"] / st["n"] >= MIN_TWO_LEVEL_SHARE:
                print("%-6s %-60s lines=%7d mean=%6.1f books=%d" % (
                    "VERSE" if wid in table else "prose", wid, st["n"], st["chars"] / st["n"], len(st["books"])))
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(table, f, indent=1, ensure_ascii=False)
        f.write("\n")
    with open(args.out_single, "w", encoding="utf-8") as f:
        json.dump(single, f, indent=1, ensure_ascii=False)
        f.write("\n")
    print("scanned %d works, wrote %d verse works to %s and %d one-level works to %s" % (
        len(stats), len(table), args.out, len(single), args.out_single), file=sys.stderr)


if __name__ == "__main__":
    main()
