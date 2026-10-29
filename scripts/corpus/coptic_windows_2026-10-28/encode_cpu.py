# ruff: noqa: E402, E741  (a run-once script: imports follow its path setup)
"""Encode cpu_blobs.jsonl (restricted works) with multilingual-e5-large on this server's CPU, in-process (not through the live
embed service); the same call the embed server makes (normalize_embeddings=True). usage: encode_cpu.py DIR"""

import json
import sys
import numpy as np
from sentence_transformers import SentenceTransformer

D = sys.argv[1]
rows = [json.loads(l) for l in open(f"{D}/cpu_blobs.jsonl", encoding="utf-8")]
m = SentenceTransformer("intfloat/multilingual-e5-large", device="cpu")
v = m.encode(
    [r["text"] for r in rows],
    batch_size=4,
    normalize_embeddings=True,
    convert_to_numpy=True,
).astype("float32")
np.save(f"{D}/cpu_vectors.npy", v)
json.dump([r["id"] for r in rows], open(f"{D}/cpu_ids.json", "w"))
print(v.shape, np.linalg.norm(v, axis=1))
