#!/usr/bin/env python3
"""Passage vectors for described windows, resumable, through the site's embedding service.

Same text and model as scripts/corpus/encode_with_embed_service.py (blob_for of the
description, "query: " prefix, multilingual-e5-large, unit length) but it saves its progress
every batch so a run limited to ten minutes can be repeated until done. The campus GPU route
needs a job input under public_data on the production checkout, which a staging run may not
write.

    encode_passage_vectors.py descriptions.jsonl OUT_DIR [--max-seconds 500]

Reads the records that have a description (the last one for each id), writes
OUT_DIR/ids.json and OUT_DIR/embeddings.npy when every id is done, OUT_DIR/progress.npy before.
"""

import argparse
import json
import os
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from apply_passage_rows import blob_for  # noqa: E402

BATCH = 8


def embed(url, texts):
    body = json.dumps({"texts": texts, "normalize": True}).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    for attempt in range(5):
        try:
            with urllib.request.urlopen(req, timeout=600) as resp:
                v = json.loads(resp.read().decode("utf-8")).get("vectors")
            if isinstance(v, list) and len(v) == len(texts):
                return v
        except Exception as exc:
            print("retry", attempt, exc, file=sys.stderr)
        time.sleep(5 * (attempt + 1))
    raise SystemExit("embedding service failed")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("descriptions")
    ap.add_argument("out")
    ap.add_argument("--url", default="http://localhost:8090/embed")
    ap.add_argument("--max-seconds", type=float, default=500)
    ap.add_argument("--pause", type=float, default=0.0)
    ap.add_argument("--clients", type=int, default=4, help="requests in flight (one client gave 1.6 per second, three gave 4.0)")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    recs = {}
    for line in open(a.descriptions, encoding="utf-8"):
        if line.strip():
            r = json.loads(line)
            if "desc" in r:
                recs[r["id"]] = r
    ids = list(recs)
    blobs = [blob_for(recs[i]["desc"]) for i in ids]
    prog = os.path.join(a.out, "progress.npy")
    rows = list(np.load(prog)) if os.path.exists(prog) else []
    t0, start = time.time(), len(rows)
    with ThreadPoolExecutor(a.clients) as ex:
        for i in range(len(rows), len(blobs), BATCH * a.clients):
            if time.time() - t0 > a.max_seconds:
                np.save(prog, np.asarray(rows, dtype=np.float32))
                print(f"time box: {len(rows)}/{len(blobs)}, {(len(rows) - start) / (time.time() - t0):.1f} per second")
                return 3
            chunks = [blobs[j : j + BATCH] for j in range(i, min(i + BATCH * a.clients, len(blobs)), BATCH)]
            for part in ex.map(lambda c: embed(a.url, c), chunks):
                rows.extend(part)
            time.sleep(a.pause)
    arr = np.asarray(rows, dtype=np.float32)
    norms = np.linalg.norm(arr, axis=1)
    assert arr.shape[0] == len(ids) and np.allclose(norms, 1.0, atol=1e-3)
    json.dump(ids, open(os.path.join(a.out, "ids.json"), "w", encoding="utf-8"))
    np.save(os.path.join(a.out, "embeddings.npy"), arr)
    if os.path.exists(prog):
        os.remove(prog)
    print(f"wrote {arr.shape} vectors and {len(ids)} ids; {(len(rows) - start) / (time.time() - t0):.1f} per second")
    return 0


if __name__ == "__main__":
    sys.exit(main())
