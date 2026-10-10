#!/usr/bin/env python3
"""Embed the object descriptions with the Theme Search encoder and write the two
files the site reads, in the format of the coins vectors.

    python -I scripts/objects/embed_object_descriptions.py --db data/objects/objects.sqlite --out data/objects

One text per object: the title, a full stop, and the museum's catalogue
description. The texts go to the encoder service (services/embed_server.py,
the model and "query: " prefix the passage windows use) in small sequential
batches so the production encoder is never starved. Output:

  <out>/descriptions.npy       float16, L2-normalised, one row per distinct text
  <out>/descriptions_ids.json  a list in row order, each {"text": the text,
                               "types": [object ids that carry it]}

Above 5,000 texts the script stops: that size goes to the campus GPU cluster
(research recipe GPU_JOB_RECIPE.md), not to the server's encoder.
"""
import argparse
import json
import os
import sqlite3
import sys
import time
import urllib.request

import numpy as np

ENDPOINT = os.environ.get("TESSERAE_EMBED_ENDPOINT", "http://127.0.0.1:8090")
PREFIX = "query: "  # same as backend/passage_index.py _E5_PREFIX
MAX_TEXTS = 5000


def text_for(title, description):
    t = (title or "").strip().rstrip(".")
    d = (description or "").strip()
    return f"{t}. {d}" if t else d


def embed(texts):
    payload = json.dumps({"texts": [PREFIX + t for t in texts], "normalize": True}).encode()
    req = urllib.request.Request(ENDPOINT + "/embed", data=payload,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as r:  # nosec B310
        return np.asarray(json.loads(r.read())["vectors"], dtype=np.float32)


def collect(db):
    con = sqlite3.connect(db)
    rows = con.execute("SELECT id, title, description FROM objects WHERE description IS NOT NULL "
                       "ORDER BY n").fetchall()
    con.close()
    index, out = {}, []
    for oid, title, desc in rows:
        t = text_for(title, desc)
        if t not in index:
            index[t] = len(out)
            out.append({"text": t, "types": []})
        out[index[t]]["types"].append(oid)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default="data/objects/objects.sqlite")
    ap.add_argument("--out", default="data/objects")
    ap.add_argument("--batch", type=int, default=16)
    args = ap.parse_args(argv)
    rows = collect(args.db)
    if len(rows) > MAX_TEXTS:
        raise SystemExit(f"{len(rows)} texts is above {MAX_TEXTS}: use the campus GPU recipe instead")
    print(f"{len(rows)} texts to embed", file=sys.stderr)
    t0 = time.time()
    chunks = []
    for i in range(0, len(rows), args.batch):
        chunks.append(embed([r["text"] for r in rows[i:i + args.batch]]))
        if (i // args.batch) % 10 == 0:
            print(f"{i + len(chunks[-1])}/{len(rows)} {time.time() - t0:.0f}s", file=sys.stderr, flush=True)
    vecs = np.concatenate(chunks).astype(np.float16)
    norms = np.linalg.norm(vecs.astype(np.float32), axis=1)
    if vecs.shape[0] != len(rows) or not np.allclose(norms, 1.0, atol=0.01):
        raise SystemExit("vector count or normalisation is wrong")
    os.makedirs(args.out, exist_ok=True)
    np.save(os.path.join(args.out, "descriptions.npy"), vecs)
    tmp = os.path.join(args.out, "descriptions_ids.json.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False)
    os.replace(tmp, os.path.join(args.out, "descriptions_ids.json"))
    print(f"embedded {len(rows)} texts in {time.time() - t0:.1f}s -> {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
