#!/usr/bin/env python3
"""Fetch coin-type records of nomisma.org datasets from the public SPARQL
endpoint into the triple format ``convert_ocre.py`` reads.

Two commands.

  types  Download every type of one dataset. One JSON object per line:
         ``{"t": type URI, "p": predicate, "o": {"v": value, "l": lang}}``
         for the type's own triples, plus ``"side": "obverse"|"reverse"``
         for the triples of its obverse and reverse nodes. The list of type
         URIs is fetched first (ordered), then the triples in batches of
         ``--batch`` types, so a failed batch is retried on its own.

  refs   Labels for the nomisma ids a types file uses (mints, denominations,
         materials, authorities, portraits, regions). Appends to the three
         reference files ``convert_ocre.py`` reads (``labels.jsonl``,
         ``mints.jsonl`` with a Pleiades match where nomisma has one,
         ``people.jsonl``), skipping ids the files already hold.

Usage
-----
    python -I scripts/coins/fetch_nomisma.py types \\
        --dataset http://numismatics.org/pella/ --out DIR/pella_types.jsonl
    python -I scripts/coins/fetch_nomisma.py refs \\
        --types DIR/pella_types.jsonl --refs REFS_DIR

The endpoint answers a GET with a curl-style agent (a Python agent string
is refused). English labels only. Licences are the datasets' own and are
recorded in ``data/sources_credits.json``.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.parse
import urllib.request

ENDPOINT = "https://nomisma.org/query"
AGENT = "curl/8.5.0"
PREFIXES = (
    "PREFIX nmo: <http://nomisma.org/ontology#> "
    "PREFIX dcterms: <http://purl.org/dc/terms/> "
    "PREFIX skos: <http://www.w3.org/2004/02/skos/core#> "
    "PREFIX void: <http://rdfs.org/ns/void#> "
    "PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> "
)
NMO = "http://nomisma.org/ontology#"
SKOS = "http://www.w3.org/2004/02/skos/core#"
SKIP_PRED = ("http://www.w3.org/1999/02/22-rdf-syntax-ns#type",)


def sparql(query, retries=5):
    url = ENDPOINT + "?" + urllib.parse.urlencode({"query": PREFIXES + query})
    req = urllib.request.Request(url, headers={
        "User-Agent": AGENT, "Accept": "application/sparql-results+json"})
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=180) as r:
                return json.loads(r.read().decode("utf-8"))["results"]["bindings"]
        except Exception as e:  # noqa: BLE001 -- retry on any transport or parse error
            if attempt == retries - 1:
                raise
            print(f"retry {attempt + 1}: {e}", file=sys.stderr)
            time.sleep(5 * (attempt + 1))


def _o(b):
    """The object of a binding. Some datasets (Ptolemaic Coins Online) wrap an
    uncertain authority or denomination in a blank node holding ``rdf:value``;
    the wrapped value is used and a blank node with none is dropped (None)."""
    if b["o"]["type"] == "bnode":
        return {"v": b["v"]["value"], "l": None} if "v" in b else None
    return {"v": b["o"]["value"], "l": b["o"].get("xml:lang")}


def fetch_types(dataset, out, batch):
    rows = sparql(f"SELECT ?t WHERE {{ ?t a nmo:TypeSeriesItem ; void:inDataset <{dataset}> }} ORDER BY ?t")
    uris = [b["t"]["value"] for b in rows]
    print(f"{dataset}: {len(uris)} types", file=sys.stderr)
    n = 0
    with open(out, "w", encoding="utf-8") as f:
        for i in range(0, len(uris), batch):
            vals = " ".join(f"<{u}>" for u in uris[i:i + batch])
            own = sparql(f"SELECT ?t ?p ?o ?v WHERE {{ VALUES ?t {{ {vals} }} ?t ?p ?o OPTIONAL {{ ?o rdf:value ?v }} }}")
            for b in own:
                p = b["p"]["value"]
                o = _o(b)
                if p in SKIP_PRED or o is None:
                    continue
                f.write(json.dumps({"t": b["t"]["value"], "p": p, "o": o},
                                   ensure_ascii=False) + "\n")
            for side, pred in (("obverse", "hasObverse"), ("reverse", "hasReverse")):
                rows = sparql(f"SELECT ?t ?p ?o ?v WHERE {{ VALUES ?t {{ {vals} }} "
                              f"?t nmo:{pred} ?s . ?s ?p ?o OPTIONAL {{ ?o rdf:value ?v }} }}")
                for b in rows:
                    p = b["p"]["value"]
                    o = _o(b)
                    if p in SKIP_PRED or o is None:
                        continue
                    f.write(json.dumps({"t": b["t"]["value"], "p": p, "o": o,
                                        "side": side}, ensure_ascii=False) + "\n")
            n += len(uris[i:i + batch])
            print(f"  {n}/{len(uris)}", file=sys.stderr)
            time.sleep(0.5)
    return len(uris)


def used_ids(types_path):
    preds = {NMO + x for x in ("hasMint", "hasAuthority", "hasStatedAuthority",
                              "hasIssuer", "hasDenomination", "hasMaterial",
                              "hasRegion", "hasPortrait")}
    ids = {}
    with open(types_path, encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            if d["p"] in preds:
                v = d["o"]["v"]
                if v.startswith("http://nomisma.org/id/"):
                    ids[v] = "mint" if d["p"] == NMO + "hasMint" else (
                        "people" if d["p"] in (NMO + "hasAuthority", NMO + "hasStatedAuthority",
                                               NMO + "hasIssuer", NMO + "hasPortrait") else "label")
    return ids


def fetch_refs(types_path, refs_dir):
    os.makedirs(refs_dir, exist_ok=True)
    files = {"label": "labels.jsonl", "mint": "mints.jsonl", "people": "people.jsonl"}
    known = set()
    for name in files.values():
        p = os.path.join(refs_dir, name)
        if os.path.exists(p):
            with open(p, encoding="utf-8") as f:
                known.update(json.loads(line)["u"] for line in f)
    ids = {u: k for u, k in used_ids(types_path).items() if u not in known}
    print(f"{len(ids)} new ids", file=sys.stderr)
    uris = sorted(ids)
    outs = {k: open(os.path.join(refs_dir, v), "a", encoding="utf-8") for k, v in files.items()}
    try:
        for i in range(0, len(uris), 40):
            chunk = uris[i:i + 40]
            vals = " ".join(f"<{u}>" for u in chunk)
            labs, match = {}, {}
            for b in sparql(f"SELECT ?s ?o WHERE {{ VALUES ?s {{ {vals} }} ?s skos:prefLabel ?o "
                            f"FILTER(lang(?o)='en') }}"):
                labs.setdefault(b["s"]["value"], b["o"]["value"])
            for b in sparql(f"SELECT ?s ?o WHERE {{ VALUES ?s {{ {vals} }} ?s skos:closeMatch ?o "
                            f"FILTER(CONTAINS(STR(?o),'pleiades.stoa.org/places/')) }}"):
                match.setdefault(b["s"]["value"], b["o"]["value"])
            for u in chunk:
                if u not in labs:
                    continue
                rec = {"u": u, "label": labs[u]}
                if ids[u] == "mint" and u in match:
                    rec["match"] = match[u]
                outs[ids[u]].write(json.dumps(rec, ensure_ascii=False) + "\n")
            time.sleep(0.5)
    finally:
        for f in outs.values():
            f.close()


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    t = sub.add_parser("types")
    t.add_argument("--dataset", required=True, help="nomisma dataset URI, e.g. http://numismatics.org/pella/")
    t.add_argument("--out", required=True)
    t.add_argument("--batch", type=int, default=25)
    r = sub.add_parser("refs")
    r.add_argument("--types", required=True)
    r.add_argument("--refs", required=True)
    args = ap.parse_args(argv)
    if args.cmd == "types":
        fetch_types(args.dataset, args.out, args.batch)
    else:
        fetch_refs(args.types, args.refs)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
