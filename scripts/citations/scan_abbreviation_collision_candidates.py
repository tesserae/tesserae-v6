"""Candidate two- and three-letter abbreviation-table collisions, for a
later hand-review pass -- the same shape of problem already fixed for
"Rep." (plato.respublica vs cicero.de_republica), "Her." (Philostratus'
Heroicus, unguarded, mostly wrong), "Ach." (Aristophanes' Acharnians vs
statius.achilleid), "Plut." (Aristophanes' Plutus vs Plutarch), "Cri."
(Plato's Crito vs the Old English poem Christ), and "Dom." (Cicero's De
Domo Sua vs Suetonius' Domitian): a short abbreviation key registered in
data/citations/abbreviations.json to exactly ONE candidate work sails
through the resolver's ambiguity guard unchecked (that guard only fires
when two or more candidates are tied at the same priority for a key --
see backend/citations/resolver.py's _pick_candidate), even when real
running prose uses the same short form for something else entirely.

This script does NOT decide which of these are real collisions or fix
anything -- every one of the six fixes above needed a human to read
actual sampled sentences (REPORT_v3.md through REPORT_v6.md) before
acting; a short, heavily-cited abbreviation key is a lead, not a verdict.

Criterion: every abbreviation key in the table that is (a) two or three
letters (no spaces -- a combined "Author. Work." key is a different,
lower-risk shape, already effectively guarded by needing both tokens to
match), (b) registered to exactly one candidate work, and (c) whose
candidate work has more than MIN_CITATIONS citations in the given
citations db (so a rarely-cited work's key isn't worth chasing). Lists
the ten largest by citation count, each with up to five example surfaces.

Output: writes a Markdown table to
/home/ncoffee/tesserae-backups/ejc_index_2026-09-14/
ABBREVIATION_COLLISION_CANDIDATES.md (read-only against the citations db
and abbreviations.json; writes only that one report file).

Usage:
  python3 scan_abbreviation_collision_candidates.py [--db PATH] [--min-citations N] [--top N]
"""
import argparse
import collections
import os
import sqlite3
import sys

WORK = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, WORK)

from backend.citations.abbrev_index import AbbrevIndex

ABBREV_PATH = os.path.join(WORK, "data", "citations", "abbreviations.json")
DEFAULT_DB = "/home/ncoffee/tesserae-backups/ejc_index_2026-09-14/citations_v6.db"
DEFAULT_OUT = "/home/ncoffee/tesserae-backups/ejc_index_2026-09-14/ABBREVIATION_COLLISION_CANDIDATES.md"
MIN_CITATIONS = 100
MAX_EXAMPLES = 5


def short_single_candidate_keys(index):
    """{key: base_id} for every 2-3 letter, no-space key registered to
    exactly one distinct candidate work."""
    out = {}
    for key, entries in index.index.items():
        if " " in key or not (2 <= len(key) <= 3):
            continue
        candidates = {base_id for base_id, _priority, _src in entries}
        if len(candidates) == 1:
            out[key] = next(iter(candidates))
    return out


def resolved_work_id(index, base_id):
    """The work_id a citation to this base_id actually gets STORED under
    -- the combined tesserae_work_id when there is one, else the base_id
    itself (a part-routed work would show up under one of its own part
    ids in the db, which this script doesn't try to enumerate; it will
    simply show a 0 count for those, which is fine -- they're rare and
    _route_to_part already means the citation's own locus decides which
    part, not the key)."""
    rec = index.works_by_base_id.get(base_id, {})
    return rec.get("tesserae_work_id") or base_id


def scan(db_path, index, min_citations, max_examples):
    keys = short_single_candidate_keys(index)
    conn = sqlite3.connect(db_path)

    results = []
    for key, base_id in keys.items():
        work_id = resolved_work_id(index, base_id)
        rows = conn.execute(
            "SELECT surface FROM citations WHERE work_id = ?", (work_id,)
        ).fetchall()
        n = len(rows)
        if n <= min_citations:
            continue
        examples = []
        seen = set()
        for (surface,) in rows:
            if surface in seen:
                continue
            seen.add(surface)
            examples.append(surface)
            if len(examples) >= max_examples:
                break
        results.append({"key": key, "base_id": base_id, "work_id": work_id,
                        "count": n, "examples": examples})
    conn.close()
    results.sort(key=lambda r: r["count"], reverse=True)
    return results


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", default=DEFAULT_DB)
    ap.add_argument("--min-citations", type=int, default=MIN_CITATIONS)
    ap.add_argument("--top", type=int, default=10)
    ap.add_argument("--out", default=DEFAULT_OUT)
    args = ap.parse_args()

    if not os.path.exists(args.db):
        print(f"ERROR: db not found at {args.db}", file=sys.stderr)
        sys.exit(1)

    index = AbbrevIndex(ABBREV_PATH)
    results = scan(args.db, index, args.min_citations, MAX_EXAMPLES)
    top = results[:args.top]

    lines = []
    lines.append("# Abbreviation-collision candidates")
    lines.append("")
    lines.append(f"Generated by scripts/citations/scan_abbreviation_collision_candidates.py "
                 f"from {args.db} and data/citations/abbreviations.json.")
    lines.append("")
    lines.append(f"Every 2-3 letter abbreviation key registered to exactly ONE candidate work, "
                 f"with more than {args.min_citations} citations for that work in the given db. "
                 f"A lead for a later hand-review pass (the same one that found \"Rep.\", \"Her.\", "
                 f"\"Ach.\", \"Plut.\", \"Cri.\", \"Dom.\"), not a verdict -- read the sample "
                 f"sentences before registering a second candidate or dropping the bare form.")
    lines.append("")
    lines.append(f"{len(results)} candidate keys total (>{args.min_citations} citations, "
                 f"single candidate); top {len(top)} by citation count shown below.")
    lines.append("")
    lines.append("| key | resolves to | citations | example surfaces |")
    lines.append("|---|---|---|---|")
    for r in top:
        ex = "; ".join(repr(e) for e in r["examples"])
        lines.append(f"| {r['key']} | {r['work_id']} | {r['count']} | {ex} |")

    with open(args.out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    print(f"{len(results)} candidates found, top {len(top)} written to {args.out}", file=sys.stderr)


if __name__ == "__main__":
    main()
