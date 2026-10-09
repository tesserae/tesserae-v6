#!/usr/bin/env python3
"""Fetch the first paragraph of the English Wikipedia article of each sample event.

Usage: fetch_wikipedia_intros.py SAMPLE.json EVENTS.jsonl OUT_DIR
Writes OUT_DIR/intros.json: {key: {"title","description","paragraph","query"}}. One request per
event, 2.2 s apart, polite user agent. The Theme Search query is description + paragraph.
"""
import json, sys, time, urllib.parse, urllib.request
from pathlib import Path

UA = "Tesserae-event-prototype/0.1 (https://tesserae.caset.buffalo.edu; ncoffee@buffalo.edu)"


def main(sample, events, out):
    ev = {}
    for line in open(events, encoding="utf-8"):
        d = json.loads(line)
        ev[d["qid"]] = d
    res = {}
    for s in json.load(open(sample))["events"]:
        e = ev[s["qid"]]
        url = "https://en.wikipedia.org/w/api.php?" + urllib.parse.urlencode({
            "action": "query", "prop": "extracts", "exintro": 1, "explaintext": 1, "redirects": 1,
            "titles": e["wikipedia_title"], "format": "json"})
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=60) as r:
            pages = json.load(r)["query"]["pages"]
        text = next(iter(pages.values())).get("extract", "")
        para = next((p.strip() for p in text.split("\n") if len(p.strip()) > 80), text.strip())
        res[s["key"]] = {"title": e["wikipedia_title"], "description": e["description"], "paragraph": para,
                         "query": (e["description"] + ". " + para)[:1500]}
        time.sleep(2.2)
    json.dump(res, open(Path(out) / "intros.json", "w"), ensure_ascii=False, indent=1)
    for k, v in res.items():
        print(k, len(v["paragraph"]), v["paragraph"][:90])


if __name__ == "__main__":
    main(*sys.argv[1:4])
