"""Per-work maximum line/locus value, from the same corpus .tess tags
derive_work_depth.py reads (same tag-parsing method: see that script's
own docstring for the whitespace-tag vs. glued-dot-joined-tag rules, and
the .part.N folding rule -- this script imports its tag parser directly
rather than re-implementing it).

Used by extractor.py's depth-1 OCR-digit-join guard (_apply_work_depth,
see its own docstring for the fault this fixes: OCR sometimes splits one
multi-digit line number into several short digit runs across whitespace,
e.g. "Ar. Ach. 1 1 24" for line 1124 -- joining the digits back together
is only safe when the result is a plausible line for that work, which
needs this table to check against).

Output: backend/citations/work_max_line.json, {work_id: max_line} -- for
every work_id derive_work_depth.py produced a depth for, the largest
leading-digit run found at the LAST tag level, across every tagged line
in the corpus. (Not restricted to depth-1 works here -- consumers decide
which works this number is meaningful for; extractor.py only ever
consults it for a depth-1 work.)

Usage:
  python3 derive_work_max_line.py [--corpus-root PATH]
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


def _last_level_value(locus_str):
    """The last dot-separated level of a locus string, as an int -- only
    its own leading digit run counts (so '433c' -> 433, matching how a
    trailing subdivision letter is not part of the line number itself),
    or None if that level has no leading digits at all."""
    last = locus_str.rsplit(".", 1)[-1]
    m = _LEADING_DIGITS_RE.match(last)
    return int(m.group()) if m else None


def process_file(path):
    """Returns {work_id: max_last_level_value} for one .tess file."""
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
                last_tok = tag.split()[-1]
                if not last_tok:
                    continue
                work_id = file_work_id
                locus = last_tok
            else:
                wid, _depth = _glued_work_and_locus(tag)
                if wid is None:
                    continue
                work_id = fold_part(wid)
                locus = tag.rsplit(".", 1)[-1]
            value = _last_level_value(locus)
            if value is None:
                continue
            if value > maxima.get(work_id, -1):
                maxima[work_id] = value
    return maxima


def scan_corpus(corpus_root):
    global_maxima = {}
    n_files = 0
    for dirpath, _dirnames, filenames in os.walk(corpus_root):
        for fn in filenames:
            if not fn.endswith(".tess"):
                continue
            n_files += 1
            path = os.path.join(dirpath, fn)
            for work_id, value in process_file(path).items():
                if value > global_maxima.get(work_id, -1):
                    global_maxima[work_id] = value
    return global_maxima, n_files


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--corpus-root", default=DEFAULT_CORPUS_ROOT)
    ap.add_argument("--out-dir", default=OUT_DIR)
    args = ap.parse_args()

    maxima, n_files = scan_corpus(args.corpus_root)
    print(f"scanned {n_files} .tess files under {args.corpus_root}", file=sys.stderr)
    print(f"{len(maxima)} distinct work ids with a max line value", file=sys.stderr)

    os.makedirs(args.out_dir, exist_ok=True)
    out_path = os.path.join(args.out_dir, "work_max_line.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(maxima, f, indent=1, sort_keys=True, ensure_ascii=False)
        f.write("\n")
    print(f"wrote {out_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
