"""Per-work highest first level (book, act, page...) among the corpus .tess
tags of works cited at two or more levels, from the same tag parsing as
derive_work_depth.py.

Used by extractor.py to drop a single-level locus whose number is beyond any
first level the work has ("Aen. 1583": the book number is missing and the
digits are a line, a page or a year).

Output: backend/citations/work_max_book.json, {work_id: max_first_level}.

Usage:
  python3 derive_work_max_book.py [--corpus-root PATH]
"""
import argparse
import json
import os
import re
import sys

WORK = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from derive_work_depth import (  # noqa: E402
    DEFAULT_CORPUS_ROOT, TAG_RE, WS_RE, fold_part, _glued_work_and_locus,
)

OUT_DIR = os.path.join(WORK, "backend", "citations")
_LEADING_DIGITS_RE = re.compile(r"^\d+")


def process_file(path):
    stem = os.path.basename(path)
    if stem.endswith(".tess"):
        stem = stem[:-5]
    file_work_id = fold_part(stem)
    maxima = {}
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.lstrip()
            if not line.startswith("<"):
                continue
            m = TAG_RE.match(line)
            if not m:
                continue
            tag = m.group(1)
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
            if len(levels) < 2:
                continue
            first = _LEADING_DIGITS_RE.match(levels[0])
            if first and int(first.group()) > maxima.get(work_id, -1):
                maxima[work_id] = int(first.group())
    return maxima


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--corpus-root", default=DEFAULT_CORPUS_ROOT)
    ap.add_argument("--out-dir", default=OUT_DIR)
    args = ap.parse_args()
    maxima = {}
    n_files = 0
    for dirpath, _dirs, files in os.walk(args.corpus_root):
        for fn in files:
            if fn.endswith(".tess"):
                n_files += 1
                for wid, v in process_file(os.path.join(dirpath, fn)).items():
                    if v > maxima.get(wid, -1):
                        maxima[wid] = v
    print(f"scanned {n_files} .tess files, {len(maxima)} works with a first level", file=sys.stderr)
    out_path = os.path.join(args.out_dir, "work_max_book.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(maxima, f, indent=1, sort_keys=True, ensure_ascii=False)
        f.write("\n")
    print(f"wrote {out_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
