#!/usr/bin/env python3
"""Fetch Latin/Greek labels and aliases for the places and participants of the event records.

Usage: fetch_wikidata_labels.py EVENTS.jsonl OUT_DIR
Writes OUT_DIR/labels.jsonl: {"qid":..., "la":[...], "grc":[...], "el":[...]} so event
names can be matched against the corpus's own (Latin and Greek) spellings.
Paced at no more than one query per 2.2 s.
"""
import json, sys, time, urllib.parse, urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fetch_wikidata_events import sparql  # noqa: E402


def main(events, out):
    ids = set()
    for line in open(events, encoding="utf-8"):
        e = json.loads(line)
        for k in ("locations", "participants", "part_of"):
            ids.update(x["qid"] for x in e[k])
    ids = sorted(ids)
    res = {}
    for n in range(0, len(ids), 150):
        chunk = " ".join("wd:" + i for i in ids[n:n + 150])
        q = f"""
SELECT ?e ?l ?lang WHERE {{
  VALUES ?e {{ {chunk} }}
  {{ ?e rdfs:label ?l }} UNION {{ ?e skos:altLabel ?l }}
  BIND(LANG(?l) AS ?lang)
  FILTER(?lang IN ("la","grc","el"))
}}"""
        for b in sparql(q):
            qid = b["e"]["value"].rsplit("/", 1)[-1]
            d = res.setdefault(qid, {"qid": qid, "la": [], "grc": [], "el": []})
            d[b["lang"]["value"]].append(b["l"]["value"])
        print(n, len(ids), file=sys.stderr)
    with open(Path(out) / "labels.jsonl", "w", encoding="utf-8") as f:
        for d in res.values():
            f.write(json.dumps(d, ensure_ascii=False) + "\n")
    print("entities with la/grc/el labels", len(res), "of", len(ids))


if __name__ == "__main__":
    main(*sys.argv[1:3])
