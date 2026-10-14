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

Campus GPU route (docs/DATA_OPERATIONS.md, research recipe for the cluster):

    --blobs-out DIR     write DIR/blobs.jsonl.gz ({id, text} per distinct
                        description, text already carrying the "query: "
                        prefix, id the row number) for the cluster job, then stop
    --rows-out FILE     write FILE as JSONL, one row per distinct description:
                        {"id": row number, "text": the description, "types":
                        [coin type ids that carry it]}, in the order the
                        vectors must be numbered, then stop
    --from-parts DIR    build <out>/vectors.npy, strings.json and types.json
                        from the job's returned vectors-NNN.npy and
                        ids-NNN.json instead of calling the encoder service

scripts/coins/pack_descriptions.py then writes the two files the site reads.
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


def write_blobs(strings, folder):
    import gzip
    os.makedirs(folder, exist_ok=True)
    with gzip.open(os.path.join(folder, "blobs.jsonl.gz"), "wt", encoding="utf-8") as f:
        for i, t in enumerate(strings):
            f.write(json.dumps({"id": str(i), "text": PREFIX + t}, ensure_ascii=False) + "\n")


def assemble_parts(folder, n_rows):
    """Vectors from the cluster job's parts, in row order, checked against the row count."""
    import glob
    vec_files = sorted(glob.glob(os.path.join(folder, "vectors-*.npy")))
    id_files = sorted(glob.glob(os.path.join(folder, "ids-*.json")))
    if not vec_files or len(vec_files) != len(id_files):
        raise SystemExit(f"parts missing or unpaired in {folder}")
    vecs, ids = [], []
    for vf, idf in zip(vec_files, id_files):
        v = np.load(vf)
        i = json.load(open(idf))
        if len(v) != len(i):
            raise SystemExit(f"{vf}: {len(v)} vectors but {len(i)} ids")
        vecs.append(v)
        ids += [int(x) for x in i]
    if ids != list(range(n_rows)):
        raise SystemExit("the job's ids are not the input order 0..N-1")
    return np.concatenate(vecs).astype(np.float16)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--batch", type=int, default=16)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--blobs-out", help="write the cluster job's input here and stop")
    ap.add_argument("--rows-out", help="write one JSONL row per distinct description and stop")
    ap.add_argument("--from-parts", help="assemble the cluster job's returned parts instead of encoding")
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

    if args.rows_out:
        carriers = [[] for _ in strings]
        for tid, row in types.items():
            if row < len(strings):
                carriers[row].append(tid)
        with open(args.rows_out, "w", encoding="utf-8") as f:
            for i, t in enumerate(strings):
                f.write(json.dumps({"id": i, "text": t, "types": carriers[i]}, ensure_ascii=False) + "\n")
        print(f"wrote {len(strings)} rows to {args.rows_out}", file=sys.stderr)
        return
    if args.blobs_out:
        write_blobs(strings, args.blobs_out)
        print(f"wrote {len(strings)} blobs to {args.blobs_out}", file=sys.stderr)
        return
    if args.from_parts:
        allv = assemble_parts(args.from_parts, len(strings))
        np.save(os.path.join(args.out, "vectors.npy"), allv)
        json.dump(strings, open(os.path.join(args.out, "strings.json"), "w"))
        json.dump(types, open(os.path.join(args.out, "types.json"), "w"))
        print("assembled", allv.shape, file=sys.stderr)
        return

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
