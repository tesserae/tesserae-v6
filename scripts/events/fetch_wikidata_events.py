#!/usr/bin/env python3
"""Fetch ancient events (battle, siege, treaty, military campaign) from Wikidata.

Usage: fetch_wikidata_events.py OUT_DIR
Writes OUT_DIR/events.jsonl. One SPARQL query per type per facet, paced >= 2 s.
"""
import json, sys, time, urllib.parse, urllib.request
from pathlib import Path

ENDPOINT = "https://query.wikidata.org/sparql"
UA = "Tesserae-event-prototype/0.1 (https://tesserae.caset.buffalo.edu; ncoffee@buffalo.edu)"
TYPES = {"battle": "Q178561", "siege": "Q188055", "treaty": "Q131569", "military campaign": "Q831663"}
LO, HI = "-0800-01-01T00:00:00Z", "0600-12-31T23:59:59Z"
_last = [0.0]


def sparql(q):
    wait = 2.2 - (time.time() - _last[0])
    if wait > 0:
        time.sleep(wait)
    req = urllib.request.Request(ENDPOINT, data=urllib.parse.urlencode({"query": q, "format": "json"}).encode(),
                                 headers={"User-Agent": UA, "Accept": "application/sparql-results+json"})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                _last[0] = time.time()
                return json.load(r)["results"]["bindings"]
        except Exception as e:
            print("retry", attempt, e, file=sys.stderr)
            time.sleep(10 * (attempt + 1))
    raise SystemExit("query failed")


def v(b, k):
    return b[k]["value"] if k in b else None


def qid(u):
    return u.rsplit("/", 1)[-1] if u else None


def main(out):
    out = Path(out)
    ev = {}
    for tname, tq in TYPES.items():
        # core: items with dates in range (point in time, or start/end), via subclass closure
        q = f"""
SELECT ?e ?eLabel ?eDescription ?pit ?start ?end ?art WHERE {{
  ?e wdt:P31/wdt:P279* wd:{tq} .
  OPTIONAL {{ ?e wdt:P585 ?pit }} OPTIONAL {{ ?e wdt:P580 ?start }} OPTIONAL {{ ?e wdt:P582 ?end }}
  FILTER(
    (BOUND(?pit) && ?pit >= "{LO}"^^xsd:dateTime && ?pit <= "{HI}"^^xsd:dateTime) ||
    (BOUND(?start) && ?start >= "{LO}"^^xsd:dateTime && ?start <= "{HI}"^^xsd:dateTime) ||
    (BOUND(?end) && ?end >= "{LO}"^^xsd:dateTime && ?end <= "{HI}"^^xsd:dateTime))
  OPTIONAL {{ ?art schema:about ?e ; schema:isPartOf <https://en.wikipedia.org/> }}
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
}}"""
        for b in sparql(q):
            i = qid(v(b, "e"))
            r = ev.setdefault(i, {"qid": i, "types": [], "label": v(b, "eLabel"), "description": v(b, "eDescription"),
                                  "point_in_time": set(), "start": set(), "end": set(), "wikipedia_title": None,
                                  "locations": {}, "participants": {}, "part_of": {}})
            if tname not in r["types"]:
                r["types"].append(tname)
            for k, f in (("point_in_time", "pit"), ("start", "start"), ("end", "end")):
                if v(b, f):
                    r[k].add(v(b, f))
            if v(b, "art"):
                r["wikipedia_title"] = urllib.parse.unquote(v(b, "art").rsplit("/", 1)[-1]).replace("_", " ")
        print(tname, "events so far", len(ev), file=sys.stderr)
    ids = sorted(ev)
    # facets in chunks
    facets = {
        "locations": ("P276|wdt:P17", 'OPTIONAL {{ ?o wdt:P625 ?coord }} OPTIONAL {{ ?o wdt:P1584 ?pl }}'),
        "participants": ("P710", ""),
        "part_of": ("P361", ""),
    }
    for fname, (prop, extra) in facets.items():
        for n in range(0, len(ids), 200):
            chunk = " ".join("wd:" + i for i in ids[n:n + 200])
            q = f"""
SELECT ?e ?o ?oLabel ?coord ?pl WHERE {{
  VALUES ?e {{ {chunk} }}
  ?e wdt:{prop} ?o .
  OPTIONAL {{ ?o wdt:P625 ?coord }}
  {"OPTIONAL { ?o wdt:P1584 ?pl }" if fname == "locations" else ""}
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
}}"""
            for b in sparql(q):
                d = ev[qid(v(b, "e"))][fname].setdefault(qid(v(b, "o")), {"qid": qid(v(b, "o")), "label": v(b, "oLabel")})
                if v(b, "coord"):
                    d["coord"] = v(b, "coord")  # "Point(lon lat)"
                if v(b, "pl"):
                    d["pleiades"] = v(b, "pl")
            print(fname, n, file=sys.stderr)
    with open(out / "events.jsonl", "w") as f:
        for i in ids:
            r = ev[i]
            for k in ("point_in_time", "start", "end"):
                r[k] = sorted(r[k])
            for k in ("locations", "participants", "part_of"):
                r[k] = list(r[k].values())
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print("wrote", len(ids))


if __name__ == "__main__":
    main(sys.argv[1])
