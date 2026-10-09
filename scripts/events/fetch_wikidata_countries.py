#!/usr/bin/env python3
"""Mark which of an event's locations came only from country (P17) statements.

Usage: fetch_wikidata_countries.py EVENTS.jsonl OUT_DIR
Writes OUT_DIR/countries.jsonl: {"qid": event, "p17": [location qids], "p276": [location qids]}.
A location that is only a P17 value is a modern or ancient country, too coarse to centre a
100 km search on.
"""
import json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fetch_wikidata_events import sparql  # noqa: E402


def main(events, out):
    ids = [json.loads(l)["qid"] for l in open(events, encoding="utf-8")]
    res = {i: {"qid": i, "p17": [], "p276": []} for i in ids}
    for prop, key in (("P17", "p17"), ("P276", "p276")):
        for n in range(0, len(ids), 300):
            chunk = " ".join("wd:" + i for i in ids[n:n + 300])
            for b in sparql(f"SELECT ?e ?o WHERE {{ VALUES ?e {{ {chunk} }} ?e wdt:{prop} ?o }}"):
                res[b["e"]["value"].rsplit("/", 1)[-1]][key].append(b["o"]["value"].rsplit("/", 1)[-1])
    with open(Path(out) / "countries.jsonl", "w") as f:
        for r in res.values():
            f.write(json.dumps(r) + "\n")


if __name__ == "__main__":
    main(*sys.argv[1:3])
