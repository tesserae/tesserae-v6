#!/usr/bin/env python3
"""Recall of the hand-listed primary passages in the ranked literary result of each dossier.

Usage: eval_dossiers.py SAMPLE.json DOSSIER_DIR
For each hand-listed passage, find the best rank at which a ranked window (after overlap
suppression) overlaps it. A passage whose work is not in the result at all is 'absent'.
"""
import json, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_event_dossier import parse_ref, loci_overlap  # noqa: E402


def main(sample, d):
    tot = {"in_corpus": 0, "top20": 0, "top100": 0, "any": 0}
    rows = []
    for s in json.load(open(sample))["events"]:
        ranked = json.load(open(os.path.join(d, s["key"] + ".ranked.json")))
        for work, a, b in s["passages"]:
            lo, hi = parse_ref("x " + a), parse_ref("x " + b)
            best = None
            for i, r in enumerate(ranked, 1):
                if r["work"] == work and loci_overlap(lo, hi, tuple(r["lo"]), tuple(r["hi"])):
                    best = i
                    break
            tot["in_corpus"] += 1
            tot["any"] += best is not None
            tot["top100"] += best is not None and best <= 100
            tot["top20"] += best is not None and best <= 20
            rows.append((s["key"], work, f"{a}-{b}", best, len(ranked)))
    for r in rows:
        print("%-22s %-45s %-12s best_rank=%s of %d" % r)
    print(tot)


if __name__ == "__main__":
    main(*sys.argv[1:3])
