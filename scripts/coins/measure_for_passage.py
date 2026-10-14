#!/usr/bin/env python3
"""Run the ten prototype passages through /api/coins/for-passage and write the
top five of each, for judging precision at 5 by hand.

The passages and the works they live in are those of query_descriptions.py
(Actium on the shield, Odes 1.37, Res Gestae 34, the Fasti on the Ara Pacis,
Eclogue 4, the Carmen Saeculare, Suetonius Aug. 94, Lucan 1, Annals 1.60-62,
Pliny Letters 6.31). Needs the passage index, the lemma cache, the coins
database and vectors, and the query encoder service, so it runs where those
are installed (set TESSERAE_COINS_DB).

    python scripts/coins/measure_for_passage.py --out results.json
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", ".."))
from query_descriptions import PASSAGES, WINDOW_WORK  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--lemma-cache", help="folder holding la/<work>.json lemma caches "
                    "(default: the checkout's cache/lemmas)")
    args = ap.parse_args()
    from backend.app import app
    if args.lemma_cache:
        from backend import lemma_cache
        lemma_cache.CACHE_DIR = args.lemma_cache
    client = app.test_client()
    results = []
    for label, fname, prefix, lo, hi, _para in PASSAGES:
        work = WINDOW_WORK[fname][0]
        ref, ref_end = f"{prefix}{lo}", f"{prefix}{hi}"
        r = client.get("/api/coins/for-passage", query_string={
            "work": work, "lang": "la", "ref": ref, "ref_end": ref_end})
        d = r.get_json()
        results.append({"label": label, "work": work, "ref": ref, "ref_end": ref_end,
                        "status": r.status_code, "window": d.get("window"), "query": d.get("query"),
                        "related": d.get("related"), "name_links": d.get("name_links"),
                        "error": d.get("error")})
        print(label, "->", len(d.get("related") or []), "hits,", len(d.get("name_links") or []),
              "name links", file=sys.stderr)
    json.dump(results, open(args.out, "w"), indent=1, ensure_ascii=False)


if __name__ == "__main__":
    main()
