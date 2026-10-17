#!/usr/bin/env python3
"""Knauer recall of the live Greek-Latin search under a scorer setting.

usage: crosslingual_scorer_measure.py SETTING OUT.json [MAXRES] [books...]
SETTING is live-exclude, live-penalty, live-off, evaluation-off, evaluation-penalty or
evaluation-exclude (scorer, then the two-lemma gate). Aeneid 1 is the source and each Iliad book
that holds a Knauer gold line the target (a Latin query against a Greek text), through the route
the site takes (crosslingual_direct_record). MAXRES 0 is no cap, as the front end sends it.
Every returned row is kept in OUT.json with its score, channels and lemma-match count.
"""
import json
import os
import resource
import sys
import time
from pathlib import Path

os.environ.setdefault("TESSERAE_USE_DIRECT_SEARCH", "1")
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts" / "review"))
import crosslingual_direct_record as R  # noqa: E402

setting, out = sys.argv[1], sys.argv[2]
maxres = int(sys.argv[3]) if len(sys.argv) > 3 else 0
books = [int(b) for b in sys.argv[4:]] or list(range(1, 25))
scorer, gate = setting.split("-")
R.register_language_plugins()
from backend import passage_index  # noqa: E402
passage_index._ensure_loaded()
sm = R.load_search_module()
extra = {"crosslingual_lemma_gate": gate}
if scorer == "evaluation":
    extra["crosslingual_scorer"] = "evaluation"
if gate == "penalty":
    extra["crosslingual_penalty_factor"] = 0.5
res = {"setting": setting, "max_results": maxres, "books": {}}
t_all = time.time()
for b in books:
    params, su, tu = R.build_inputs(sm, "la", "grc", "vergil.aeneid.part.1", f"homer.iliad.part.{b}", extra)
    params["settings"]["max_results"] = maxres
    core, secs = R.run_core(sm, params, su, tu, {})
    if core.get("error"):
        raise SystemExit(f"book {b}: {core['error']}")
    rows = [{"s": r["source"]["ref"], "t": r["target"]["ref"], "score": r["overall_score"],
             "ch": r["channels"], "lm": r["features"]["lemma_match_count"],
             "gt": r["features"]["lemma_gate_triggered"], "mc": r["match_count"]}
            for r in core.get("results", [])]
    res["books"][b] = {"secs": secs, "n_src": len(su), "n_tgt": len(tu), "rows": rows}
    print(f"book {b}: {len(rows)} rows {secs:.1f}s", flush=True)
res["wall_secs"] = time.time() - t_all
res["maxrss_mb"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
json.dump(res, open(out, "w"))
print("maxrss_mb", res["maxrss_mb"], "search secs", sum(v["secs"] for v in res["books"].values()))
