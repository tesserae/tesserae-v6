#!/usr/bin/env python3
"""Apply described windows to the passage index: append new rows, or
replace rows in place (embedding + description) for ids already indexed.

Latin corpus batch 2 (2026-08-30). Append mode is the hardened lockstep
append from index_missing_windows.py (2026-08-29): the embed server answers
at most 32 texts per request; every batch is retried then FATAL if short;
ids/embeddings/descriptions grow together with count asserts before and
after, and .bak-<tag> copies are made first. Replace mode is the in-place
row replacement from reembed_missing.py: embeddings.npy is edited at the
row indices of the given ids, and descriptions.jsonl is rewritten with the
old records for those ids dropped and the new ones appended.

Usage:
  python apply_passage_rows.py --index /path/passage_index --sidecar d.jsonl \
      --mode append  --tag batch2-20260830
  python apply_passage_rows.py --index ... --sidecar ... --mode replace --tag ...
"""
import argparse
import json
import os
import shutil
import time
import urllib.request

import numpy as np

EMBED = os.environ.get('TESSERAE_EMBED_URL', 'http://127.0.0.1:8090/embed')
E5_PREFIX = 'query: '


def blob_for(desc):
    parts = []
    for k in ('mode', 'setting', 'participants', 'action_steps', 'props',
              'themes', 'imagery_tone', 'gist'):
        v = desc.get(k)
        if isinstance(v, list):
            v = ', '.join(str(x) for x in v)
        if v:
            parts.append(f'{k}: {v}')
    return E5_PREFIX + ' | '.join(parts)


def embed_all(blobs):
    vecs = []
    for i in range(0, len(blobs), 32):
        batch = blobs[i:i + 32]
        got = None
        for _attempt in range(3):
            body = json.dumps({'texts': batch, 'normalize': True}).encode()
            req = urllib.request.Request(
                EMBED, data=body, headers={'Content-Type': 'application/json'})
            try:
                with urllib.request.urlopen(req, timeout=600) as r:
                    got = json.loads(r.read())['vectors']
            except Exception as e:
                print(f'  batch {i}: {e}')
                got = None
            if got and len(got) == len(batch):
                break
            time.sleep(5)
        assert got and len(got) == len(batch), \
            f'embed batch at {i} returned {0 if not got else len(got)} of {len(batch)}'
        vecs.extend(got)
        if (i // 32) % 10 == 0:
            print(f'  embedded {len(vecs)}/{len(blobs)}', flush=True)
    assert len(vecs) == len(blobs), 'embedding count mismatch'
    return vecs


def backup(index, name, tag):
    dst = os.path.join(index, f'{name}.bak-{tag}')
    if not os.path.exists(dst):
        shutil.copy2(os.path.join(index, name), dst)


def load_sidecar(path):
    recs = {}
    for line in open(path, encoding='utf-8'):
        r = json.loads(line)
        recs[r['id']] = r
    return recs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--index', required=True)
    ap.add_argument('--sidecar', required=True)
    ap.add_argument('--mode', choices=('append', 'replace'), required=True)
    ap.add_argument('--tag', required=True)
    args = ap.parse_args()
    index = args.index

    recs = load_sidecar(args.sidecar)
    ids = json.load(open(os.path.join(index, 'ids.json')))
    pos = {i: n for n, i in enumerate(ids)}
    emb = np.load(os.path.join(index, 'embeddings.npy'))
    assert emb.shape[0] == len(ids), 'index out of lockstep BEFORE apply'

    if args.mode == 'append':
        new = [r for i, r in recs.items() if i not in pos]
        print(f'{len(new)} new records to append ({len(recs) - len(new)} '
              'already indexed, skipped)')
        if not new:
            return
        vecs = embed_all([blob_for(r['desc']) for r in new])
        V = np.asarray(vecs, dtype=emb.dtype)
        assert V.shape[1] == emb.shape[1], 'dimension mismatch'
        for name in ('ids.json', 'embeddings.npy', 'descriptions.jsonl'):
            backup(index, name, args.tag)
        np.save(os.path.join(index, 'embeddings.npy'), np.vstack([emb, V]))
        json.dump(ids + [r['id'] for r in new],
                  open(os.path.join(index, 'ids.json'), 'w'))
        with open(os.path.join(index, 'descriptions.jsonl'), 'a',
                  encoding='utf-8') as out:
            for r in new:
                out.write(json.dumps(r, ensure_ascii=False) + '\n')
    else:
        hit = [r for i, r in recs.items() if i in pos]
        miss = len(recs) - len(hit)
        print(f'{len(hit)} records to replace in place'
              + (f' ({miss} sidecar ids NOT in index, skipped)' if miss else ''))
        if not hit:
            return
        vecs = embed_all([blob_for(r['desc']) for r in hit])
        V = np.asarray(vecs, dtype=emb.dtype)
        assert V.shape[1] == emb.shape[1], 'dimension mismatch'
        for name in ('embeddings.npy', 'descriptions.jsonl'):
            backup(index, name, args.tag)
        rows = [pos[r['id']] for r in hit]
        emb[rows, :] = V
        np.save(os.path.join(index, 'embeddings.npy'), emb)
        replaced = {r['id'] for r in hit}
        desc_path = os.path.join(index, 'descriptions.jsonl')
        tmp = desc_path + '.rewriting'
        kept = 0
        with open(tmp, 'w', encoding='utf-8') as out:
            for line in open(desc_path, encoding='utf-8'):
                try:
                    rid = json.loads(line).get('id')
                except ValueError:
                    rid = None
                if rid in replaced:
                    continue
                out.write(line)
                kept += 1
            for r in hit:
                out.write(json.dumps(r, ensure_ascii=False) + '\n')
        os.replace(tmp, desc_path)
        print(f'descriptions.jsonl rewritten: {kept} kept + {len(hit)} replaced')

    emb2 = np.load(os.path.join(index, 'embeddings.npy'), mmap_mode='r')
    ids2 = json.load(open(os.path.join(index, 'ids.json')))
    n_desc = sum(1 for _ in open(os.path.join(index, 'descriptions.jsonl'),
                                 encoding='utf-8'))
    assert emb2.shape[0] == len(ids2), 'index out of lockstep AFTER apply'
    print(f'index now {len(ids2):,} ids / {emb2.shape[0]:,} vectors / '
          f'{n_desc:,} description rows')


if __name__ == '__main__':
    main()
