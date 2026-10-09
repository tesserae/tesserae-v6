#!/usr/bin/env python3
"""Embed coin-type descriptions with the Theme Search encoder (prototype).

Reads the converter's JSONL, builds one description string per type
("Obverse: <obverse description> Reverse: <reverse description>"), embeds the
DISTINCT strings through the encoder service (services/embed_server.py, same
model and the same "query: " prefix the passage windows use), and writes:

  <out>/vectors.npy   float16, L2-normalised, one row per distinct string
  <out>/strings.json  the distinct strings, same order
  <out>/types.json    {type id: row index}

Resumable: rows already written to <out>/partial.* are reused. Requests are
sequential and small so the production encoder is never starved.

    python scripts/coins/embed_descriptions.py --input coins.jsonl --out DIR
"""
import argparse
import json
import os
import sys
import time
import urllib.request

import numpy as np

ENDPOINT = os.environ.get("TESSERAE_EMBED_ENDPOINT", "http://127.0.0.1:8090")
PREFIX = "query: "  # same as backend/passage_index.py _E5_PREFIX


def describe(rec):
    o, r = rec.get("obverse_description"), rec.get("reverse_description")
    parts = []
    if o:
        parts.append("Obverse: " + o.rstrip(". ") + ".")
    if r:
        parts.append("Reverse: " + r.rstrip(". ") + ".")
    return " ".join(parts)


def embed(texts):
    payload = json.dumps({"texts": [PREFIX + t for t in texts], "normalize": True}).encode()
    req = urllib.request.Request(ENDPOINT + "/embed", data=payload,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as r:  # nosec B310
        return np.asarray(json.loads(r.read())["vectors"], dtype=np.float32)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--batch", type=int, default=16)
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)

    strings, index, types = [], {}, {}
    with open(args.input, encoding="utf-8") as f:
        for line in f:
            rec = json.loads(line)
            d = describe(rec)
            if not d:
                continue
            if d not in index:
                index[d] = len(strings)
                strings.append(d)
            types[rec["id"]] = index[d]
    if args.limit:
        strings = strings[:args.limit]
    print(f"{len(types)} types with a description, {len(strings)} distinct strings", file=sys.stderr)

    part = os.path.join(args.out, "partial.npy")
    done = np.load(part) if os.path.exists(part) else np.zeros((0, 1024), np.float32)
    chunks = [done] if len(done) else []
    n = len(done)
    t0 = time.time()
    while n < len(strings):
        vec = embed(strings[n:n + args.batch])
        chunks.append(vec)
        n += len(vec)
        if (n // args.batch) % 50 == 0:
            np.save(part, np.concatenate(chunks))
            chunks = [np.load(part)]
            print(f"{n}/{len(strings)} {n / (time.time() - t0 + 1e-9):.1f}/s", file=sys.stderr, flush=True)
    allv = np.concatenate(chunks).astype(np.float16)
    np.save(os.path.join(args.out, "vectors.npy"), allv)
    json.dump(strings, open(os.path.join(args.out, "strings.json"), "w"))
    json.dump(types, open(os.path.join(args.out, "types.json"), "w"))
    print("done", allv.shape, file=sys.stderr)


if __name__ == "__main__":
    main()
