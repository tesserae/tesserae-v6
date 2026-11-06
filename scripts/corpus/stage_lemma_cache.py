#!/usr/bin/env python3
"""Build lemma caches for named new files into a STAGING cache folder.

batch_lemma_cache.py writes to cache/lemmas of the checkout it runs in and
visits every uncached text. For an import prepared in a worktree this builds
only the files named, into a folder of your choosing, so nothing under the
production tree is written and the caches can be copied in at install time.

    stage_lemma_cache.py LANG CACHE_ROOT FILE.tess [FILE.tess ...]

Writes CACHE_ROOT/LANG/<hashed name>.json, the same names and contents
batch_lemma_cache.py writes (same FastTextProcessor, same save function).
"""
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
os.environ['TESSERAE_DIRECT_SERVER'] = '1'

import backend.lemma_cache as LC  # noqa: E402
import batch_lemma_cache as B     # noqa: E402


def main():
    lang, cache_root, files = sys.argv[1], sys.argv[2], sys.argv[3:]
    LC.CACHE_DIR = os.path.abspath(cache_root)
    os.makedirs(os.path.join(LC.CACHE_DIR, lang), exist_ok=True)
    # The web app registers the plugin languages (Coptic, Hebrew, Persian, Urdu, Arabic) when it starts;
    # a script that imports the processor directly gets an empty handler table (issue #495).
    B.register_plugin_languages()
    tp = B.FastTextProcessor()
    t0, built, errors = time.time(), 0, []
    for path in files:
        name = os.path.basename(path)
        try:
            h = LC.get_file_hash(path)
            line = tp.process_file(path, lang, 'line')
            if B.all_units_empty(line):
                raise ValueError('no tokens in any unit')
            phrase = tp.process_file(path, lang, 'phrase')
            if not LC.save_cached_units(name, lang, line, phrase, h):
                raise IOError('cache file not written')
            built += 1
        except Exception as e:  # noqa: BLE001
            errors.append(f'{name}: {e}')
            print('ERROR', name, e, flush=True)
    print(f'built {built} of {len(files)} in {time.time() - t0:.0f}s, {len(errors)} errors')
    sys.exit(1 if errors else 0)


if __name__ == '__main__':
    main()
