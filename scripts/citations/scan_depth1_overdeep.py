"""How many rows in a built citation index are over-deep on a depth-1
work -- i.e. how many rows the depth-1 OCR-digit-join fix
(extractor.py._apply_work_depth, see its own docstring for the "Ar. Ach.
1 1 24" panel fault this fixes) could affect on a rebuild.

"Depth-1 work" here means the work's EFFECTIVE depth as extractor.py
would compute it today: the curated override (work_depth_overrides.json)
if present, else the corpus depth (work_depth.json) unless that work is
flagged inconsistent (work_depth_inconsistent.json), in which case it has
no trusted depth and isn't counted here at all -- matching how the live
rule actually decides whether to touch a locus.

Read-only against the given db; prints a summary and the ten largest
depth-1 works by over-deep row count. Does not write anything.

Usage:
  python3 scan_depth1_overdeep.py --db PATH [--top N]
"""
import argparse
import collections
import json
import os
import sqlite3
import sys

WORK = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CITATIONS_DIR = os.path.join(WORK, "backend", "citations")


def _effective_depth(work_id, corpus_depth, inconsistent, overrides):
    if work_id in overrides:
        return overrides[work_id]
    d = corpus_depth.get(work_id)
    if d is None or work_id in inconsistent:
        return None
    return d


def scan(db_path):
    with open(os.path.join(CITATIONS_DIR, "work_depth.json"), encoding="utf-8") as f:
        corpus_depth = json.load(f)
    with open(os.path.join(CITATIONS_DIR, "work_depth_inconsistent.json"), encoding="utf-8") as f:
        inconsistent = set(json.load(f))
    with open(os.path.join(CITATIONS_DIR, "work_depth_overrides.json"), encoding="utf-8") as f:
        overrides = json.load(f)

    conn = sqlite3.connect(db_path)
    rows = conn.execute(
        "SELECT work_id, locus_start FROM citations WHERE work_id IS NOT NULL AND locus_start IS NOT NULL"
    ).fetchall()
    conn.close()

    total_by_work = collections.Counter()
    overdeep_by_work = collections.Counter()
    depth1_works = set()
    for work_id, locus_start in rows:
        depth = _effective_depth(work_id, corpus_depth, inconsistent, overrides)
        if depth != 1:
            continue
        depth1_works.add(work_id)
        total_by_work[work_id] += 1
        if len(locus_start.split(".")) > 1:
            overdeep_by_work[work_id] += 1

    return depth1_works, total_by_work, overdeep_by_work


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", required=True, help="path to the citations sqlite database")
    ap.add_argument("--top", type=int, default=10)
    args = ap.parse_args()

    if not os.path.exists(args.db):
        print(f"ERROR: db not found at {args.db}", file=sys.stderr)
        sys.exit(1)

    depth1_works, total_by_work, overdeep_by_work = scan(args.db)
    total_rows = sum(total_by_work.values())
    total_overdeep = sum(overdeep_by_work.values())

    print(f"db: {args.db}")
    print(f"distinct depth-1 works with any citations: {len(depth1_works)}")
    print(f"total citations on depth-1 works: {total_rows}")
    print(f"total OVER-DEEP citations on depth-1 works: {total_overdeep}")
    print()
    print(f"top {args.top} depth-1 works by over-deep row count:")
    for work_id, n in overdeep_by_work.most_common(args.top):
        print(f"  {work_id}: {n} over-deep / {total_by_work[work_id]} total")


if __name__ == "__main__":
    main()
