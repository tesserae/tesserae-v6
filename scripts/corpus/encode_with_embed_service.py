#!/usr/bin/env python3
"""Encode described passage windows with the site's own embedding service.

The campus GPU recipe (research/threads/GPU_JOB_RECIPE.md) is for runs above a
few thousand texts. For a small set, the query encoder that already runs as the
`tesserae-embed` service (services/embed_server.py, multilingual-e5-large,
port 8090) does the same encoding in a minute or two, with the same model, the
same normalisation and the same blob text the index build embeds
(apply_passage_rows.blob_for, which carries the "query: " prefix). Used first
on 2026-10-13 for Salutati's 1,450 paragraph units re-cut into prose windows
(#904) and eight one-window poems.

    python scripts/corpus/encode_with_embed_service.py descriptions.jsonl \\
        vectors.npy ids.json [--url http://127.0.0.1:8090/embed]

Rows without a description are skipped; duplicate ids keep their first row.
Writes vectors.npy (float32, one row per id, unit length) and ids.json (the
ids in row order), the pair apply_passage_rows.py --vectors/--vector-ids takes.
"""
import argparse
import json
import os
import sys
import urllib.request

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from apply_passage_rows import blob_for  # noqa: E402

BATCH = 32  # the service's MAX_TEXTS


def embed(url, texts):
    body = json.dumps({'texts': texts, 'normalize': True}).encode('utf-8')
    req = urllib.request.Request(url, data=body, headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=600) as resp:
        data = json.loads(resp.read().decode('utf-8'))
    vectors = data.get('vectors')
    if not isinstance(vectors, list) or len(vectors) != len(texts):
        raise SystemExit(f'service returned {len(vectors) if isinstance(vectors, list) else "no"} '
                         f'vectors for {len(texts)} texts')
    return vectors


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('descriptions')
    ap.add_argument('vectors_out')
    ap.add_argument('ids_out')
    ap.add_argument('--url', default='http://127.0.0.1:8090/embed')
    a = ap.parse_args()

    ids, blobs, seen = [], [], set()
    with open(a.descriptions, encoding='utf-8') as fh:
        for line in fh:
            if not line.strip():
                continue
            r = json.loads(line)
            if 'desc' not in r or r['id'] in seen:
                continue
            seen.add(r['id'])
            ids.append(r['id'])
            blobs.append(blob_for(r['desc']))
    if not ids:
        raise SystemExit('nothing to encode')

    rows = []
    for i in range(0, len(blobs), BATCH):
        rows.extend(embed(a.url, blobs[i:i + BATCH]))
        done = min(i + BATCH, len(blobs))
        if done % (BATCH * 10) == 0 or done == len(blobs):
            print(f'  {done}/{len(blobs)}', flush=True)
    arr = np.asarray(rows, dtype=np.float32)
    assert arr.shape[0] == len(ids), (arr.shape, len(ids))
    norms = np.linalg.norm(arr, axis=1)
    if not np.allclose(norms, 1.0, atol=1e-3):
        raise SystemExit(f'vectors are not unit length (min {norms.min():.4f}, max {norms.max():.4f})')
    np.save(a.vectors_out, arr)
    json.dump(ids, open(a.ids_out, 'w', encoding='utf-8'))
    print(f'wrote {arr.shape[0]} x {arr.shape[1]} vectors to {a.vectors_out} and {len(ids)} ids to {a.ids_out}')


if __name__ == '__main__':
    main()
