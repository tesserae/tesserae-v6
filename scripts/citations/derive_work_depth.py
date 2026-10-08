"""Derive per-work locus depth from the live corpus .tess tags.

Reads every .tess file under the corpus root (default: the production
texts directory, /var/www/tesseraev6_flask/texts/), reproducing exactly the
method used in the read-only diagnosis at
/home/ncoffee/tesserae-backups/ejc_index_2026-09-14/COMMA_CHAIN_DIAGNOSIS.md
section 1:

  - Whitespace-tagged files ("<verg. aen. 1.1> ..."): the work id is the
    file's own stem (folded to its base id if it's a .part.N file); the
    locus is the LAST whitespace-separated token inside the tag, and its
    depth is that token's dot-separated segment count.
  - Glued dot-joined tags ("<hebrew_bible.genesis.1.1> ..."): the whole tag
    is one dot-joined token and is NOT keyed by the file name (one file can
    hold many books, each under its own tag prefix). Split the token from
    the RIGHT, peeling off trailing dot-segments that start with a digit as
    locus levels; whatever dot-joined prefix is left is the work id.
  - Part files (e.g. homer.iliad.part.3.tess) are folded into their base
    work id (homer.iliad) before counting, on either tag shape.

Depth for a work is the MODAL number of levels in its locus, taken over
every tagged line found for that work id across the whole corpus (not a
sample). A work whose lines are not all at the same depth is "inconsistent"
-- flagged separately, not trusted for the modal number alone.

Outputs (both committed to git, both consumed by backend/citations/parser.py
and extractor.py):
  - backend/citations/work_depth.json            {work_id: modal_depth}
  - backend/citations/work_depth_inconsistent.json   [work_id, ...]

Run without arguments to use the default corpus root and write both files
into backend/citations/. Pass --corpus-root to point at a different texts/
directory, and --check <path> to diff the freshly-derived table against a
previously saved one (used to confirm this script reproduces the
diagnosis's own seed work_depth.json) without writing anything.
"""
import argparse
import json
import os
import re
import sys
from collections import Counter, defaultdict

DEFAULT_CORPUS_ROOT = "/var/www/tesseraev6_flask/texts/"
OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                        "backend", "citations")

PART_RE = re.compile(r"^(.*)\.part\.\d+$")
TAG_RE = re.compile(r"^<([^>]+)>")
WS_RE = re.compile(r"\s")


def fold_part(stem):
    """'homer.iliad.part.3' -> 'homer.iliad' (a plain numbered part of the
    SAME continuous work, same numbering as the combined base file).

    A part file with an extra descriptive segment after the number
    ('pindar.odes.part.1.isthmeans', 'antiphon.speeches.part.2.
    first_tetralogy') is left UNFOLDED and counted as its own separate work
    id -- confirmed empirically against the diagnosis's seed
    work_depth.json (ejc_index_2026-09-14/COMMA_CHAIN_DIAGNOSIS.md): those
    named parts keep their own depth entry alongside the base file's,
    because their own internal numbering genuinely differs from the base
    file's (e.g. Antiphon's Tetralogies are tagged tetralogy.speech.line
    inside their own part file, but speech.line, numbered straight through
    all six speeches, inside the combined antiphon.speeches.tess)."""
    m = PART_RE.match(stem)
    return m.group(1) if m else stem


def _glued_work_and_locus(tag):
    """Peel trailing digit-leading dot-segments off the right of a glued,
    no-whitespace tag. Returns (work_id, depth) or (None, None) if the tag
    has no locus levels at all (nothing to peel) or no work-id prefix."""
    parts = tag.split(".")
    i = len(parts)
    while i > 0 and parts[i - 1] and parts[i - 1][0].isdigit():
        i -= 1
    work_parts = parts[:i]
    locus_parts = parts[i:]
    if not work_parts or not locus_parts:
        return None, None
    return ".".join(work_parts), len(locus_parts)


def process_file(path):
    """Returns {work_id: Counter(depth -> line_count)} for one .tess file."""
    stem = os.path.basename(path)
    if stem.endswith(".tess"):
        stem = stem[:-5]
    file_work_id = fold_part(stem)

    counts = defaultdict(Counter)
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
                depth = len(last_tok.split("."))
                counts[file_work_id][depth] += 1
            else:
                wid, depth = _glued_work_and_locus(tag)
                if wid is None:
                    continue
                wid = fold_part(wid)
                counts[wid][depth] += 1
    return counts


def scan_corpus(corpus_root):
    """Returns {work_id: Counter(depth -> line_count)} merged over every
    .tess file under corpus_root (recursive)."""
    global_counts = defaultdict(Counter)
    n_files = 0
    for dirpath, _dirnames, filenames in os.walk(corpus_root):
        for fn in filenames:
            if not fn.endswith(".tess"):
                continue
            n_files += 1
            path = os.path.join(dirpath, fn)
            file_counts = process_file(path)
            for wid, ctr in file_counts.items():
                global_counts[wid].update(ctr)
    return global_counts, n_files


def derive(corpus_root):
    global_counts, n_files = scan_corpus(corpus_root)
    depth = {}
    inconsistent = []
    for wid, ctr in global_counts.items():
        if not ctr:
            continue
        modal_depth, _n = ctr.most_common(1)[0]
        depth[wid] = modal_depth
        if len(ctr) > 1:
            inconsistent.append(wid)
    inconsistent.sort()
    return depth, inconsistent, n_files


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--corpus-root", default=DEFAULT_CORPUS_ROOT)
    ap.add_argument("--out-dir", default=OUT_DIR)
    ap.add_argument("--check", metavar="PATH",
                     help="diff the derived depth table against a previously "
                          "saved {work_id: depth} JSON file; write nothing")
    args = ap.parse_args()

    depth, inconsistent, n_files = derive(args.corpus_root)
    print(f"scanned {n_files} .tess files under {args.corpus_root}", file=sys.stderr)
    print(f"{len(depth)} distinct work ids with a depth; "
          f"{len(inconsistent)} flagged inconsistent", file=sys.stderr)

    if args.check:
        with open(args.check) as f:
            seed = json.load(f)
        missing = sorted(set(seed) - set(depth))
        extra = sorted(set(depth) - set(seed))
        mismatched = sorted(
            wid for wid in (set(seed) & set(depth))
            if seed[wid] != depth[wid]
        )
        print(f"seed has {len(seed)} work ids", file=sys.stderr)
        print(f"missing from derived (in seed, not derived): {len(missing)}", file=sys.stderr)
        print(f"extra in derived (not in seed): {len(extra)}", file=sys.stderr)
        print(f"mismatched depth: {len(mismatched)}", file=sys.stderr)
        if mismatched:
            for wid in mismatched[:20]:
                print(f"  {wid}: seed={seed[wid]} derived={depth[wid]}", file=sys.stderr)
        if missing:
            print("  sample missing:", missing[:10], file=sys.stderr)
        if extra:
            print("  sample extra:", extra[:10], file=sys.stderr)
        return

    os.makedirs(args.out_dir, exist_ok=True)
    depth_path = os.path.join(args.out_dir, "work_depth.json")
    inconsistent_path = os.path.join(args.out_dir, "work_depth_inconsistent.json")
    with open(depth_path, "w", encoding="utf-8") as f:
        json.dump(depth, f, indent=1, sort_keys=True, ensure_ascii=False)
        f.write("\n")
    with open(inconsistent_path, "w", encoding="utf-8") as f:
        json.dump(inconsistent, f, indent=1, ensure_ascii=False)
        f.write("\n")
    print(f"wrote {depth_path}", file=sys.stderr)
    print(f"wrote {inconsistent_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
