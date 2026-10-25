#!/usr/bin/env python3
"""Rebuild cache/frequencies/<lang>.json from the per-file lemma caches.

The server keeps the word frequencies of a language (backend/frequency_cache.py) keyed on a checksum of
texts/<lang>; when the file is missing or stale, the first Line Search in a worker rebuilds it inside the
request by lemmatizing every text with the live text processor. For languages whose lemmatizer is not
installed in the serving environment (Persian and Urdu run through Stanza, present only in the development
environment) that rebuild yields an empty table, and for the large languages it runs past the request
limit. This script builds the same table offline from cache/lemmas/<lang>/, which every installed text has.

    rebuild_frequency_cache.py --root /var/www/tesseraev6_flask --language fa [--language ur ...]

Run with the root's own interpreter or any interpreter: the root is put first on sys.path so `backend`
resolves to the root's code and the cache and texts folders are the root's. Texts without a valid lemma
cache are listed and left out (exit status 2), never lemmatized here.
"""
import argparse
import os
import sys
from collections import Counter


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', required=True, help='the checkout whose caches are read and written')
    ap.add_argument('--language', '-l', action='append', required=True)
    args = ap.parse_args()
    root = os.path.abspath(args.root)
    sys.path.insert(0, root)
    os.chdir(root)
    from backend.frequency_cache import (TEXTS_DIR, deduplicate_text_files, get_corpus_checksum,
                                         save_frequency_cache, get_cache_path)
    from backend.lemma_cache import get_cached_units
    status = 0
    for lang in args.language:
        lang_dir = os.path.join(TEXTS_DIR, lang)
        files = sorted(f for f in os.listdir(lang_dir) if f.endswith('.tess'))
        files = deduplicate_text_files(files)
        counts = Counter()
        total = 0
        missing = []
        for f in files:
            cached = get_cached_units(f[:-5], lang) or get_cached_units(f, lang)
            if not cached:
                missing.append(f)
                continue
            for u in cached.get('units_line') or []:
                lem = u.get('lemmas') or []
                counts.update(lem)
                total += len(lem)
        if missing:
            status = 2
            print(f'{lang}: {len(missing)} of {len(files)} texts have no valid lemma cache and were left out:')
            for f in missing:
                print('   ', f)
        save_frequency_cache(lang, dict(counts.most_common()), total, get_corpus_checksum(lang))
        path = get_cache_path(lang)
        print(f'{lang}: {len(files) - len(missing)} texts, {len(counts)} unique lemmas, {total} tokens, '
              f'wrote {path} ({os.path.getsize(path)} bytes)')
    return status


if __name__ == '__main__':
    sys.exit(main())
