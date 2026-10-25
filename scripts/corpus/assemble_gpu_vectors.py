#!/usr/bin/env python3
"""Assemble the output of a campus GPU encoding job into staging files.

  lines  --parts-dir D --works works.json --out OUT
      D holds vectors-la-NNN.npy and ids-la-NNN.json (encode_fill.py output).
      The ids are "la|<whole file>|<i>". Writes OUT/la/<file>.npy and
      <file>.meta.json for every whole file (all rows, in unit order) and for
      every part file, sliced from its whole work by reference (the part's
      line_refs must be one consecutive run of the whole work's refs, else
      the script stops). Rows are raw float32, as the existing files are.

  descs  --parts-dir D --descriptions descriptions.jsonl --vectors-out V.npy --ids-out I.json
      D holds vectors-NNN.npy and ids-NNN.json (encode_job.py output). Writes
      the vectors in the order of the descriptions file (rows that have a
      description) and the ids beside them, and stops if any id is missing or
      doubled.

Checks printed: rows against units, no NaN, mean norm.
"""
import argparse
import datetime
import glob
import json
import os

import numpy as np


def load_parts(d, pat_v, pat_i):
    vs, ids = [], []
    for pv, pi in zip(sorted(glob.glob(os.path.join(d, pat_v))), sorted(glob.glob(os.path.join(d, pat_i)))):
        v = np.load(pv)
        i = json.load(open(pi, encoding='utf-8'))
        if len(v) != len(i):
            raise SystemExit(f'{pv}: {len(v)} rows but {len(i)} ids')
        vs.append(v)
        ids += i
    if not vs:
        raise SystemExit('no parts found')
    return np.concatenate(vs).astype('float32'), ids


def lines(a):
    vec, ids = load_parts(a.parts_dir, 'vectors-la-*.npy', 'ids-la-*.json')
    if np.isnan(vec).any():
        raise SystemExit('NaN in vectors')
    works = json.load(open(a.works, encoding='utf-8'))['works']
    by_file = {}
    for k, i in enumerate(ids):
        _lang, f, n = i.split('|')
        by_file.setdefault(f, {})[int(n)] = k
    outdir = os.path.join(a.out, 'la')
    os.makedirs(outdir, exist_ok=True)
    whole = {}
    for w in works:
        if '.part.' in w['file']:
            continue
        rows = by_file.get(w['file'])
        if rows is None or sorted(rows) != list(range(w['n_lines'])):
            raise SystemExit(f"{w['file']}: rows do not cover its {w['n_lines']} units")
        m = vec[[rows[i] for i in range(w['n_lines'])]]
        whole[w['file']] = (w, m)
        write(outdir, w, m)
    for w in works:
        if '.part.' not in w['file']:
            continue
        base = w['file'].split('.part.')[0] + '.tess'
        bw, bm = whole[base]
        refs = bw['line_refs']
        start = refs.index(w['line_refs'][0])
        if refs[start:start + w['n_lines']] != w['line_refs']:
            raise SystemExit(f"{w['file']}: not a consecutive run of {base}")
        write(outdir, w, bm[start:start + w['n_lines']])
    print(f'wrote {len(works)} files to {outdir}')


def write(outdir, w, m):
    stem = w['file'][:-5]
    np.save(os.path.join(outdir, stem + '.npy'), m.astype('float32'))
    meta = {'text_path': f"texts/la/{w['file']}", 'language': 'la', 'n_lines': int(m.shape[0]),
            'embedding_dim': int(m.shape[1]), 'created': datetime.datetime.now().isoformat(),
            'line_refs': w['line_refs']}
    json.dump(meta, open(os.path.join(outdir, stem + '.meta.json'), 'w', encoding='utf-8'), ensure_ascii=False)
    print(f"  {w['file']}: {m.shape[0]} x {m.shape[1]}, mean norm {np.linalg.norm(m, axis=1).mean():.3f}")


def descs(a):
    vec, ids = load_parts(a.parts_dir, 'vectors-[0-9]*.npy', 'ids-[0-9]*.json')
    pos = {}
    for k, i in enumerate(ids):
        if i in pos:
            raise SystemExit(f'id twice: {i}')
        pos[i] = k
    want = []
    for line in open(a.descriptions, encoding='utf-8'):
        r = json.loads(line)
        if 'desc' in r:
            want.append(r['id'])
    seen = set()
    order = []
    for i in want:
        if i in seen:
            continue
        seen.add(i)
        order.append(i)
    missing = [i for i in order if i not in pos]
    if missing:
        raise SystemExit(f'{len(missing)} described ids have no vector, first {missing[:3]}')
    m = vec[[pos[i] for i in order]]
    np.save(a.vectors_out, m)
    json.dump(order, open(a.ids_out, 'w', encoding='utf-8'))
    print(f'{len(order)} x {m.shape[1]}, mean norm {np.linalg.norm(m, axis=1).mean():.4f}')


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest='mode', required=True)
    pl = sub.add_parser('lines')
    pl.add_argument('--parts-dir', required=True)
    pl.add_argument('--works', required=True)
    pl.add_argument('--out', required=True)
    pd = sub.add_parser('descs')
    pd.add_argument('--parts-dir', required=True)
    pd.add_argument('--descriptions', required=True)
    pd.add_argument('--vectors-out', required=True)
    pd.add_argument('--ids-out', required=True)
    a = ap.parse_args()
    {'lines': lines, 'descs': descs}[a.mode](a)


if __name__ == '__main__':
    main()
