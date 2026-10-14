#!/usr/bin/env python3
"""Pack the embedded coin descriptions into the two files the site reads.

Input is the folder embed_descriptions.py writes (vectors.npy, strings.json,
types.json). Output:

  <out>/descriptions.npy       float16, L2-normalised, one row per distinct description
  <out>/descriptions_ids.json  a list in row order, each {"text": the description,
                               "types": [coin type ids that carry it]}

    python -I scripts/coins/pack_descriptions.py --emb DIR --out data/coins
"""
import argparse
import json
import os
import sys

import numpy as np


def pack(emb, out):
    vecs = np.load(os.path.join(emb, "vectors.npy"))
    strings = json.load(open(os.path.join(emb, "strings.json"), encoding="utf-8"))
    types = json.load(open(os.path.join(emb, "types.json"), encoding="utf-8"))
    if vecs.shape[0] != len(strings):
        raise SystemExit(f"{vecs.shape[0]} vectors but {len(strings)} strings")
    rows = [{"text": t, "types": []} for t in strings]
    for tid, row in types.items():
        rows[row]["types"].append(tid)
    empty = sum(1 for r in rows if not r["types"])
    if empty:
        raise SystemExit(f"{empty} descriptions carry no coin type")
    norms = np.linalg.norm(vecs.astype(np.float32), axis=1)
    if not np.allclose(norms, 1.0, atol=0.01):
        raise SystemExit("vectors are not L2-normalised")
    os.makedirs(out, exist_ok=True)
    np.save(os.path.join(out, "descriptions.npy"), vecs.astype(np.float16))
    tmp = os.path.join(out, "descriptions_ids.json.tmp")
    json.dump(rows, open(tmp, "w", encoding="utf-8"), ensure_ascii=False)
    os.replace(tmp, os.path.join(out, "descriptions_ids.json"))
    return vecs.shape[0], len(types)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--emb", required=True)
    ap.add_argument("--out", default="data/coins")
    args = ap.parse_args(argv)
    n, t = pack(args.emb, args.out)
    print(f"packed {n} descriptions for {t} coin types into {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
