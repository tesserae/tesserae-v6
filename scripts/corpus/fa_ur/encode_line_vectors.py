#!/usr/bin/env python3
"""Line vectors for new Persian and Urdu works, from the site's own embedding service.

backend/embeddings/<lang>/<work>.npy holds one multilingual-e5-large vector per line of a
work (float32, unit length, text prefixed "passage: ") beside <work>.meta.json with the
reference of every row. The campus GPU route (research/threads/GPU_JOB_RECIPE.md) needs the
job's input to sit under public_data on the production checkout, which a staging run may not
write, so this encodes through the tesserae-embed service (the same model and call as the GPU
job, port 8090) one batch at a time with a short pause so Theme Search keeps its turn.

    encode_line_vectors.py --tess a.tess b.tess --lang fa --out DIR [--pause 0.3]

Writes DIR/<lang>/<work>.npy and .meta.json, skipping works already done. Prints the rate.
"""

import argparse
import datetime
import json
import os
import re
import sys
import time
import urllib.request

import numpy as np

BATCH = 32


def embed(url, texts):
    body = json.dumps({"texts": texts, "normalize": True}).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    for attempt in range(5):
        try:
            with urllib.request.urlopen(req, timeout=600) as resp:
                v = json.loads(resp.read().decode("utf-8")).get("vectors")
            if isinstance(v, list) and len(v) == len(texts):
                return v
        except Exception as exc:  # service busy: wait and retry
            print("retry", attempt, exc, file=sys.stderr)
        time.sleep(5 * (attempt + 1))
    raise SystemExit("embedding service failed")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tess", nargs="+", required=True)
    ap.add_argument("--lang", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--url", default="http://localhost:8090/embed")
    ap.add_argument("--pause", type=float, default=0.3)
    ap.add_argument("--max-seconds", type=float, default=1e9)
    a = ap.parse_args()
    t_start = time.time()
    os.makedirs(os.path.join(a.out, a.lang), exist_ok=True)
    for path in a.tess:
        work = os.path.basename(path)[: -len(".tess")]
        npy = os.path.join(a.out, a.lang, work + ".npy")
        if os.path.exists(npy):
            continue
        refs, texts = [], []
        for line in open(path, encoding="utf-8"):
            m = re.match(r"<([^>]+)>\t(.*)", line.rstrip("\n"))
            if m:
                refs.append(m.group(1))
                texts.append("passage: " + m.group(2))
        part = npy + ".part.npy"
        rows = []
        done_file = npy + ".rows.json"
        if os.path.exists(part):
            rows = list(np.load(part))
        t0 = time.time()
        for i in range(len(rows), len(texts), BATCH):
            if time.time() - t_start > a.max_seconds:
                np.save(part, np.asarray(rows, dtype=np.float32))
                print(f"time box: {work} {len(rows)}/{len(texts)} saved")
                return 3
            rows.extend(embed(a.url, texts[i : i + BATCH]))
            time.sleep(a.pause)
        arr = np.asarray(rows, dtype=np.float32)
        norms = np.linalg.norm(arr, axis=1)
        assert arr.shape[0] == len(refs) and np.allclose(norms, 1.0, atol=1e-3), (arr.shape, norms.min(), norms.max())
        np.save(npy, arr)
        json.dump(
            {
                "text_path": f"texts/{a.lang}/{work}.tess",
                "language": a.lang,
                "n_lines": len(refs),
                "embedding_dim": int(arr.shape[1]),
                "model": "intfloat/multilingual-e5-large",
                "prefix": "passage: ",
                "precision": "float32 from the tesserae-embed service (CPU)",
                "device": "tesserae-embed service on the application server",
                "created": datetime.datetime.now().isoformat(timespec="seconds"),
                "line_refs": refs,
            },
            open(os.path.join(a.out, a.lang, work + ".meta.json"), "w", encoding="utf-8"),
            ensure_ascii=False,
        )
        for f in (part, done_file):
            if os.path.exists(f):
                os.remove(f)
        print(f"{work}: {len(refs)} lines, {len(refs) / (time.time() - t0):.1f} per second", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
