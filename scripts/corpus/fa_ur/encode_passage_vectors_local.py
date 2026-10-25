#!/usr/bin/env python3
"""Passage vectors in a process of its own (no call to the production embedding service).

Same text and call as encode_passage_vectors.py and services/embed_server.py
(multilingual-e5-large through sentence-transformers, normalize_embeddings=True, input
truncated to 2000 characters as the service does), but the model is loaded here, so a run
cannot push the live encoder over its memory limit (a six-client run did on 2026-10-25 00:26).
Resumable like the service version.

    encode_passage_vectors_local.py descriptions.jsonl OUT_DIR [--max-seconds 500] [--threads 8]
"""

import argparse
import json
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from apply_passage_rows import blob_for  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("descriptions")
    ap.add_argument("out")
    ap.add_argument("--max-seconds", type=float, default=500)
    ap.add_argument("--threads", type=int, default=8)
    ap.add_argument("--batch", type=int, default=16)
    a = ap.parse_args()
    import torch
    from sentence_transformers import SentenceTransformer

    torch.set_num_threads(a.threads)
    os.makedirs(a.out, exist_ok=True)
    recs = {}
    for line in open(a.descriptions, encoding="utf-8"):
        if line.strip():
            r = json.loads(line)
            if "desc" in r:
                recs[r["id"]] = r
    ids = list(recs)
    blobs = [blob_for(recs[i]["desc"])[:2000] for i in ids]
    prog = os.path.join(a.out, "progress.npy")
    rows = list(np.load(prog)) if os.path.exists(prog) else []
    model = SentenceTransformer("intfloat/multilingual-e5-large")
    t0, start = time.time(), len(rows)
    while len(rows) < len(blobs):
        if time.time() - t0 > a.max_seconds:
            np.save(prog, np.asarray(rows, dtype=np.float32))
            print(f"time box: {len(rows)}/{len(blobs)}, {(len(rows) - start) / (time.time() - t0):.1f} per second")
            return 3
        i = len(rows)
        v = model.encode(blobs[i : i + a.batch], normalize_embeddings=True, batch_size=a.batch)
        rows.extend(list(v))
        if (i // a.batch) % 20 == 0:
            print(f"  {len(rows)}/{len(blobs)}", flush=True)
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
