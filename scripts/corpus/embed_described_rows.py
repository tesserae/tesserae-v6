#!/usr/bin/env python3
"""Finish a described batch for apply_passage_rows.py: order it, check it, and encode it.

    embed_described_rows.py --windows windows_changed.jsonl --descriptions descriptions.jsonl --out DIR

Reads the windows that were to be described (their order fixes the order of the rows) and the describer's
output, requires one record with a `desc` for every window, and writes to DIR:
  descriptions_final.jsonl  one record per window, in the order of --windows
  ids.json                  the ids in that order
  vectors.npy               float32 vectors of apply_passage_rows.blob_for(desc) from the embed service
                            (TESSERAE_EMBED_URL, default http://127.0.0.1:8090/embed), the same e5 text the
                            index holds, so the rows can go in with `apply_passage_rows.py --mode replace
                            --vectors vectors.npy --vector-ids ids.json`
Meant for a few thousand rows at most; above that use the campus GPU recipe (research/threads/GPU_JOB_RECIPE.md).
"""
import argparse
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import apply_passage_rows as APR   # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--windows', required=True)
    ap.add_argument('--descriptions', required=True)
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    want = [json.loads(line)['id'] for line in open(a.windows, encoding='utf-8')]
    rows = {}
    for line in open(a.descriptions, encoding='utf-8'):
        r = json.loads(line)
        if 'desc' in r:
            rows.setdefault(r['id'], r)
    missing = [i for i in want if i not in rows]
    if missing:
        sys.exit(f'{len(missing)} windows without a description, first {missing[:3]}')
    os.makedirs(a.out, exist_ok=True)
    with open(os.path.join(a.out, 'descriptions_final.jsonl'), 'w', encoding='utf-8') as fh:
        for i in want:
            fh.write(json.dumps(rows[i], ensure_ascii=False) + '\n')
    json.dump(want, open(os.path.join(a.out, 'ids.json'), 'w'))
    vecs = np.asarray(APR.embed_all([APR.blob_for(rows[i]['desc']) for i in want]), dtype=np.float32)
    np.save(os.path.join(a.out, 'vectors.npy'), vecs)
    print(f'{len(want)} rows, vectors {vecs.shape}')


if __name__ == '__main__':
    main()
