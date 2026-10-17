#!/usr/bin/env python3
"""Knauer recall tables from the JSON runs of crosslingual_scorer_measure.py.

usage: crosslingual_scorer_analyze.py RUN.json [RUN.json ...]

For each run (Aeneid 1 against the 24 Iliad books that hold a Knauer gold line) prints, at a result
cap of 500 (the run's rows cut to the first 500 per book) and uncapped: rows returned, gold pairs
found anywhere, ranked at 10, 50, 100 and 500 (of 412), and precision at 50. A gold pair is found
when a returned row lies within three lines of the gold line at both loci in the same book pair; it
is ranked at k when such a row sits at position k or better. Precision at 50 is the share of a book
pair's first 50 rows within three lines of some gold pair of that book, averaged over the books.
"""
import collections
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
gold = json.load(open(ROOT / "evaluation" / "benchmarks" / "knauer_aeneid1_iliad.json"))


def nr(r):
    n = re.findall(r"\d+", r)
    return (int(n[-2]), int(n[-1])) if len(n) >= 2 else None


def near(a, b):
    return a and b and a[0] == b[0] and abs(a[1] - b[1]) <= 3


gb = collections.defaultdict(list)
for g in gold:
    b = int(re.search(r"part\.(\d+)", g["source_work"]).group(1))
    gb[b].append((nr(g["source_ref"]), nr(g["target_ref"])))


def analyze(path):
    d = json.load(open(path))
    out = {"setting": d["setting"], "max_results_run": d["max_results"]}
    books = sorted(int(b) for b in d["books"])
    for cap in (500, 0):
        tot = collections.Counter()
        precs = []
        for b in books:
            rows = d["books"][str(b)]["rows"]
            assert all(rows[i]["score"] >= rows[i + 1]["score"] for i in range(len(rows) - 1))
            if cap:
                rows = rows[:cap]
            tot["rows"] += len(rows)
            for r in rows:
                tot["one" if r["lm"] == 1 else "two+" if r["lm"] >= 2 else "none"] += 1
            best = []
            for gs, gt in gb[b]:
                bk = None
                for i, r in enumerate(rows):
                    if near(nr(r["t"]), gs) and near(nr(r["s"]), gt):
                        bk = i + 1
                        break
                best.append(bk)
            tot["gold"] += len(gb[b])
            tot["any"] += sum(x is not None for x in best)
            for k in (10, 50, 100, 500):
                tot[k] += sum(x is not None and x <= k for x in best)
            top = rows[:50]
            hit = sum(any(near(nr(r["t"]), gs) and near(nr(r["s"]), gt) for gs, gt in gb[b]) for r in top)
            precs.append(hit / len(top) if top else 0.0)
            tot["hit50"] += hit
            tot["top50"] += len(top)
        tot["p50"] = sum(precs) / len(precs)
        out[f"cap{cap}"] = dict(tot)
    out["search_secs"] = sum(v["secs"] for v in d["books"].values())
    out["wall_secs"] = d.get("wall_secs")
    out["maxrss_mb"] = d.get("maxrss_mb")
    return out


if __name__ == "__main__":
    for p in sys.argv[1:]:
        print(json.dumps(analyze(p), default=str))
