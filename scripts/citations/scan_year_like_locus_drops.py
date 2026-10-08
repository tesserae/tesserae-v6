"""How many rows in a built citation index the year-like-locus guard
(extractor.py._year_like_locus_should_drop, see its own docstring for the
"Arch. 1888" fault this fixes) would remove on
a rebuild: a single-level, four-digit Arabic locus for a depth-1 work,
in the range a real publication year would plausibly fall in, dropped
unless the work's own line range reaches that number and the surrounding
text isn't otherwise bibliographic.

Re-runs the CURRENT extractor over each stored citation's own saved
`sentence` text (the same local context the original extraction saw) and
checks whether the hit matching that row's surface/locus is now dropped
with reason 'dropped_year_like_locus'. Read-only against the given db;
prints a summary and the ten largest affected works. Does not write
anything.

Usage:
  python3 scan_year_like_locus_drops.py --db PATH [--top N]
"""
import argparse
import collections
import os
import sqlite3
import sys

WORK = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, WORK)

from backend import citations as C


def would_be_dropped(work_id, locus_start, surface, sentence):
    if not sentence or not surface:
        return False
    hits = C.extract(sentence)
    for h in hits:
        if h.get("surface") != surface:
            continue
        if h.get("reason") == "dropped_year_like_locus":
            return True
        if h.get("resolved") and h.get("work_id") == work_id and h.get("locus_start") == locus_start:
            return False
    return False


def scan(db_path):
    conn = sqlite3.connect(db_path)
    rows = conn.execute(
        "SELECT work_id, locus_start, surface, sentence FROM citations "
        "WHERE work_id IS NOT NULL AND locus_start IS NOT NULL "
        "AND locus_start GLOB '[0-9][0-9][0-9][0-9]'"
    ).fetchall()
    conn.close()

    dropped_by_work = collections.Counter()
    total_checked = 0
    total_dropped = 0
    for work_id, locus_start, surface, sentence in rows:
        total_checked += 1
        if would_be_dropped(work_id, locus_start, surface, sentence):
            total_dropped += 1
            dropped_by_work[work_id] += 1
    return total_checked, total_dropped, dropped_by_work


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", required=True, help="path to the citations sqlite database")
    ap.add_argument("--top", type=int, default=10)
    args = ap.parse_args()

    if not os.path.exists(args.db):
        print(f"ERROR: db not found at {args.db}", file=sys.stderr)
        sys.exit(1)

    total_checked, total_dropped, dropped_by_work = scan(args.db)
    print(f"db: {args.db}")
    print(f"candidate rows (single-level, exactly 4 digits): {total_checked}")
    print(f"rows the new guard would drop: {total_dropped}")
    print()
    print(f"top {args.top} affected works:")
    for work_id, n in dropped_by_work.most_common(args.top):
        print(f"  {work_id}: {n}")


if __name__ == "__main__":
    main()
