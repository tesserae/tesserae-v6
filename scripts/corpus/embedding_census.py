#!/usr/bin/env python3
"""Census of the per-line semantic vector files against the texts, and a
rebuild of the files that are out of step, into a staging folder.

The semantic channel slices a text's stored vectors from the top, one row
per search unit, so a file with more rows than the text has lines shifts
every later line onto the vector of the line before it. The 2026-10-06
vector fill counted tag lines rather than text lines, and a text with empty
tag lines (an Achilleid line that holds only its tag, say) got one row per
tag line. The 2026-10-18 census found 33 such files among 3,479.

  census  --root /var/www/tesseraev6_flask --out census.csv
      Every .npy under backend/embeddings/{la,grc,en} of the root: rows,
      dimension, tag lines, non-empty lines and cached search units of the
      text. Read-only. Prints the files whose rows differ from the units.

  rebuild --root ROOT --census census.csv --staging DIR [--only NAME ...]
      Re-encodes every text whose rows differ from its cached units with
      the model the site uses for the language (bowphs/SPhilBerta for Latin
      and Greek, all-MiniLM-L6-v2 for English), raw vectors, on the local
      processor, into DIR/<lang>/<name>.npy with a .meta.json beside it,
      and checks that the new row count equals the unit count. Nothing is
      installed: the lead copies the files in with a backup. A few thousand
      lines take seconds; above that the campus GPU recipe applies.

Run from a checkout whose backend/lemma_cache.py matches the root's caches.
"""
import argparse
import csv
import datetime
import json
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))

MODELS = {'la': 'bowphs/SPhilBerta', 'grc': 'bowphs/SPhilBerta', 'en': 'all-MiniLM-L6-v2'}
LANGS = ('la', 'grc', 'en')


def point_caches_at(root):
    from backend import lemma_cache
    lemma_cache.CACHE_DIR = os.path.join(root, 'cache', 'lemmas')
    lemma_cache.TEXTS_DIR = os.path.join(root, 'texts')
    return lemma_cache


def rows_of(path):
    shape = np.load(path, mmap_mode='r').shape
    return shape[0], (shape[1] if len(shape) > 1 else None)


def tag_counts(text_path):
    tag = nonempty = 0
    with open(text_path, encoding='utf-8', errors='replace') as fh:
        for line in fh:
            s = line.strip()
            if not s or s.startswith('#') or '>' not in s:
                continue
            tag += 1
            if s.split('>', 1)[1].strip():
                nonempty += 1
    return tag, nonempty


def cmd_census(args):
    lemma_cache = point_caches_at(args.root)
    rows = []
    for lang in LANGS:
        d = os.path.join(args.root, 'backend', 'embeddings', lang)
        if not os.path.isdir(d):
            continue
        for fn in sorted(os.listdir(d)):
            if not fn.endswith('.npy'):
                continue
            base = fn[:-4]
            n, dim = rows_of(os.path.join(d, fn))
            tp = os.path.join(args.root, 'texts', lang, base + '.tess')
            if not os.path.exists(tp):
                rows.append([lang, base, n, dim, '', '', '', 'no text file'])
                continue
            tag, nonempty = tag_counts(tp)
            cu = lemma_cache.get_cached_units(base + '.tess', lang)
            units = len(cu['units_line']) if cu else ''
            rows.append([lang, base, n, dim, tag, nonempty, units, ''])
    with open(args.out, 'w', newline='') as fh:
        w = csv.writer(fh)
        w.writerow(['lang', 'text', 'rows', 'dim', 'tag_lines', 'nonempty_lines', 'cached_units', 'note'])
        w.writerows(rows)
    bad = [r for r in rows if r[6] != '' and int(r[2]) != int(r[6])]
    print(f'{len(rows)} files, {len(bad)} with rows different from the cached units')
    for r in bad:
        print(f'  {r[0]} {r[1]} rows {r[2]} units {r[6]} tag lines {r[4]} non-empty {r[5]}')
    return 0


def cmd_rebuild(args):
    lemma_cache = point_caches_at(args.root)
    from sentence_transformers import SentenceTransformer
    with open(args.census, newline='') as fh:
        census = list(csv.DictReader(fh))
    todo = [r for r in census if r['cached_units'] and r['rows'] != r['cached_units']]
    if args.only:
        todo = [r for r in todo if r['text'] in set(args.only)]
    print(f'{len(todo)} files to rebuild', flush=True)
    models = {}
    created = datetime.datetime.now().isoformat()
    t0 = time.time()
    failures = 0
    for r in todo:
        lang, base = r['lang'], r['text']
        units = lemma_cache.get_cached_units(base + '.tess', lang)['units_line']
        texts = [u['text'] for u in units]
        name = MODELS[lang]
        if name not in models:
            models[name] = SentenceTransformer(name, device='cpu')
        t1 = time.time()
        vecs = models[name].encode(texts, batch_size=32, normalize_embeddings=False,
                                   convert_to_numpy=True, show_progress_bar=False).astype('float32')
        enc = time.time() - t1
        if vecs.shape[0] != len(units):
            print(f'FAIL {lang} {base}: {vecs.shape[0]} rows for {len(units)} units')
            failures += 1
            continue
        out_dir = os.path.join(args.staging, lang)
        os.makedirs(out_dir, exist_ok=True)
        np.save(os.path.join(out_dir, base + '.npy'), vecs)
        meta = {'text_path': f'texts/{lang}/{base}.tess', 'language': lang, 'n_lines': len(units),
                'embedding_dim': int(vecs.shape[1]), 'created': created,
                'line_refs': [u['ref'] for u in units[:10]]}
        with open(os.path.join(out_dir, base + '.meta.json'), 'w') as fh:
            json.dump(meta, fh)
        print(f'{lang} {base}: old rows {r["rows"]}, new rows {vecs.shape[0]}, {enc:.1f} s', flush=True)
    print(f'done in {time.time() - t0:.0f} s, {failures} failures')
    return 1 if failures else 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    c = sub.add_parser('census')
    c.add_argument('--root', required=True)
    c.add_argument('--out', required=True)
    c.set_defaults(func=cmd_census)
    b = sub.add_parser('rebuild')
    b.add_argument('--root', required=True)
    b.add_argument('--census', required=True)
    b.add_argument('--staging', required=True)
    b.add_argument('--only', nargs='*')
    b.set_defaults(func=cmd_rebuild)
    args = ap.parse_args()
    return args.func(args)


if __name__ == '__main__':
    sys.exit(main())
