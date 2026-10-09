#!/usr/bin/env python3
"""First paragraph of the English Wikipedia article of every event that has one.

Usage: fetch_wikipedia_intros_all.py EVENTS.jsonl OUT_DIR
Batches of 20 titles per request, 2.2 s apart, polite user agent. Writes OUT_DIR/intros_all.json:
{qid: {"title", "description", "paragraph", "query"}} where query = description + paragraph.
"""
import json, sys, time, urllib.parse, urllib.request
from pathlib import Path

UA = "Tesserae-event-prototype/0.1 (https://tesserae.caset.buffalo.edu; ncoffee@buffalo.edu)"


def main(events, out):
    ev = [json.loads(l) for l in open(events, encoding="utf-8")]
    withwp = [e for e in ev if e.get("wikipedia_title")]
    res = {}
    for i in range(0, len(withwp), 20):
        chunk = withwp[i:i + 20]
        url = "https://en.wikipedia.org/w/api.php?" + urllib.parse.urlencode({
            "action": "query", "prop": "extracts", "exintro": 1, "explaintext": 1, "exlimit": 20, "redirects": 1,
            "titles": "|".join(e["wikipedia_title"] for e in chunk), "format": "json"})
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=90) as r:
            q = json.load(r)["query"]
        alias = {}
        for m in q.get("normalized", []) + q.get("redirects", []):
            alias[m["from"]] = m["to"]
        by_title = {p["title"]: p.get("extract", "") for p in q["pages"].values()}
        for e in chunk:
            t = e["wikipedia_title"]
            for _ in range(3):
                t = alias.get(t, t)
            text = by_title.get(t, "")
            para = next((p.strip() for p in text.split("\n") if len(p.strip()) > 80), text.strip())
            res[e["qid"]] = {"title": e["wikipedia_title"], "description": e["description"], "paragraph": para,
                             "query": ((e["description"] or "") + ". " + para)[:1500]}
        print(i, len(withwp), file=sys.stderr, flush=True)
        time.sleep(2.2)
    json.dump(res, open(Path(out) / "intros_all.json", "w"), ensure_ascii=False)
    print("events with an article", len(withwp), "with a paragraph", sum(1 for v in res.values() if v["paragraph"]))


if __name__ == "__main__":
    main(*sys.argv[1:3])
