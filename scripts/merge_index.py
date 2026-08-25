"""Merge a finished description run into the served scene index.

The index is three files that must stay in lockstep: ids.json, embeddings.npy
row i belonging to ids[i], and descriptions.jsonl keyed by id. A merge that
desynchronises them does not fail loudly, it silently returns the wrong passage
for every query, so the invariants are checked before anything is written and
the old files are kept until the new ones verify.

Usage: merge_index.py <desc.jsonl> <emb.npy> <emb_ids.json> [more triples...]
"""
import json
import os
import shutil
import sys

import numpy as np

INDEX = '/home/ncoffee/tesserae-scene/data/passage_index'


def load_run(desc_path, emb_path, ids_path):
    ids = json.load(open(ids_path, encoding='utf-8'))
    emb = np.load(emb_path)
    if emb.shape[0] != len(ids):
        raise SystemExit(f'{os.path.basename(emb_path)}: {emb.shape[0]} rows '
                         f'but {len(ids)} ids')
    recs = {}
    with open(desc_path, encoding='utf-8') as fh:
        for line in fh:
            try:
                r = json.loads(line)
            except ValueError:
                continue
            if r.get('id'):
                recs[r['id']] = r
    missing = [i for i in ids if i not in recs]
    if missing:
        raise SystemExit(f'{os.path.basename(desc_path)}: {len(missing)} ids have '
                         f'an embedding but no description, e.g. {missing[:3]}')

    # Drop windows whose description came back empty. Two ways it happens: the
    # model's JSON failed to parse, leaving desc {}, or it returned the schema
    # with every field blank. Either way the blob is empty, so the embedding is
    # of the bare prompt prefix and identical for all of them. Left in, those
    # windows would be each other's nearest neighbours and would surface together
    # as a spurious cluster.
    keep = [n for n, i in enumerate(ids)
            if (recs[i].get('blob') or '').strip()]
    dropped = len(ids) - len(keep)
    if dropped:
        print(f'  {os.path.basename(desc_path)}: dropping {dropped} empty descriptions')
        ids = [ids[n] for n in keep]
        emb = emb[keep]
        recs = {i: recs[i] for i in ids}
    return ids, emb, recs


def main():
    args = sys.argv[1:]
    if not args or len(args) % 3:
        raise SystemExit(__doc__)

    ids = json.load(open(os.path.join(INDEX, 'ids.json'), encoding='utf-8'))
    emb = np.load(os.path.join(INDEX, 'embeddings.npy'))
    recs = {}
    with open(os.path.join(INDEX, 'descriptions.jsonl'), encoding='utf-8') as fh:
        for line in fh:
            try:
                r = json.loads(line)
            except ValueError:
                continue
            if r.get('id'):
                recs[r['id']] = r
    print(f'existing index: {len(ids):,} windows, dim {emb.shape[1]}')
    if emb.shape[0] != len(ids):
        raise SystemExit('existing index is already inconsistent; not touching it')

    have = set(ids)
    new_ids, new_rows = [], []
    for k in range(0, len(args), 3):
        d, e, i = args[k:k + 3]
        r_ids, r_emb, r_recs = load_run(d, e, i)
        if r_emb.shape[1] != emb.shape[1]:
            raise SystemExit(f'{os.path.basename(e)}: dim {r_emb.shape[1]} '
                             f'!= index dim {emb.shape[1]}')
        added = replaced = 0
        for n, wid in enumerate(r_ids):
            rec = r_recs[wid]
            if wid in have:
                # A rerun of the same window supersedes the old description, and
                # its embedding row has to be replaced in place, not appended.
                emb[ids.index(wid)] = r_emb[n]
                recs[wid] = rec
                replaced += 1
            else:
                new_ids.append(wid)
                new_rows.append(r_emb[n])
                recs[wid] = rec
                have.add(wid)
                added += 1
        print(f'  {os.path.basename(d)}: {added:,} new, {replaced:,} replaced')

    if new_rows:
        emb = np.vstack([emb, np.asarray(new_rows, dtype=emb.dtype)])
        ids = ids + new_ids

    if emb.shape[0] != len(ids):
        raise SystemExit('merge produced a row/id mismatch; nothing written')
    if len(set(ids)) != len(ids):
        raise SystemExit('merge produced duplicate ids; nothing written')

    tmp = INDEX + '.new'
    os.makedirs(tmp, exist_ok=True)
    json.dump(ids, open(os.path.join(tmp, 'ids.json'), 'w'), ensure_ascii=False)
    np.save(os.path.join(tmp, 'embeddings.npy'), emb)
    with open(os.path.join(tmp, 'descriptions.jsonl'), 'w', encoding='utf-8') as fh:
        for wid in ids:
            fh.write(json.dumps(recs[wid], ensure_ascii=False) + '\n')

    # Verify the written files independently before they replace anything.
    v_ids = json.load(open(os.path.join(tmp, 'ids.json'), encoding='utf-8'))
    v_emb = np.load(os.path.join(tmp, 'embeddings.npy'), mmap_mode='r')
    if v_emb.shape[0] != len(v_ids):
        raise SystemExit('written index failed verification; original untouched')
    n_desc = sum(1 for _ in open(os.path.join(tmp, 'descriptions.jsonl'), encoding='utf-8'))
    if n_desc != len(v_ids):
        raise SystemExit(f'written index has {n_desc} descriptions for '
                         f'{len(v_ids)} ids; original untouched')

    backup = INDEX + '.prev'
    if os.path.isdir(backup):
        shutil.rmtree(backup)
    os.rename(INDEX, backup)
    os.rename(tmp, INDEX)
    print(f'\nmerged index: {len(v_ids):,} windows, dim {v_emb.shape[1]}')
    print(f'previous index kept at {backup}')

    import collections
    langs = collections.Counter(recs[i].get('language') for i in ids)
    print('by language:', dict(langs))


if __name__ == '__main__':
    main()
