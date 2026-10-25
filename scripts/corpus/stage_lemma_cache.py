#!/usr/bin/env python3
"""Build lemma caches for new .tess files into a STAGING cache folder.

Same analyser as scripts/batch_lemma_cache.py (lookup table, CLTK fallback, no
POS), but the files come from a staging texts folder and the caches go to a
staging cache folder, so nothing under the live cache/ or texts/ changes.

Usage: stage_lemma_cache.py LANG TEXTS_DIR CACHE_DIR [file.tess ...]
Without file names every .tess in TEXTS_DIR is built.
The cache entry records the SHA-256 of the file as get_file_hash computes it,
so after the files are copied into texts/<lang>/ the entries are valid.
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
os.environ['TESSERAE_DIRECT_SERVER'] = '1'

import backend.lemma_cache as LC  # noqa: E402


def main():
    lang, texts_dir, cache_dir = sys.argv[1:4]
    names = sys.argv[4:] or sorted(f for f in os.listdir(texts_dir) if f.endswith('.tess'))
    LC.CACHE_DIR = cache_dir
    os.makedirs(os.path.join(cache_dir, lang), exist_ok=True)
    from scripts.batch_lemma_cache import FastTextProcessor, all_units_empty, register_plugin_languages
    register_plugin_languages()
    tp = FastTextProcessor()
    t0 = time.time()
    for n in names:
        p = os.path.join(texts_dir, n)
        h = LC.get_file_hash(p)
        ul = tp.process_file(p, lang, 'line')
        if all_units_empty(ul):
            raise SystemExit(f'{n}: no tokens in any unit')
        up = tp.process_file(p, lang, 'phrase')
        if not LC.save_cached_units(n, lang, ul, up, h):
            raise SystemExit(f'{n}: cache write failed')
        print(f'{n}: {len(ul)} lines, {len(up)} phrase units, {time.time()-t0:.0f}s', flush=True)


if __name__ == '__main__':
    main()
