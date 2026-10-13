#!/usr/bin/env python3
"""Fetch every allowed object picture into the cache the image route serves.

    python scripts/objects/fetch_object_images.py --db data/objects/objects.sqlite \\
        --out data/objects/images [--rate 2]

Resumable: a picture already in --out is skipped. Uses the route's own rules
(host allow-list, open licence, size and type checks), at most --rate requests
a second. Prints the count fetched, skipped and the failures at the end.
"""
import argparse
import os
import sqlite3
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from backend.blueprints import objects as ob  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--db', default=ob.DEFAULT_DB)
    ap.add_argument('--out', default=os.path.join(ROOT, 'data', 'objects', 'images'))
    ap.add_argument('--rate', type=float, default=2.0, help='requests per second (default 2)')
    a = ap.parse_args()
    os.environ['TESSERAE_OBJECT_IMAGES'] = os.path.abspath(a.out)
    c = sqlite3.connect(f'file:{os.path.abspath(a.db)}?mode=ro', uri=True)
    rows = c.execute('SELECT id, image_url, licence FROM objects '
                     "WHERE image_url IS NOT NULL AND image_url != '' ORDER BY n").fetchall()
    gap = 1.0 / max(a.rate, 0.01)
    fetched = skipped = refused = 0
    failures = []
    last = 0.0
    for oid, url, lic in rows:
        if not ob.image_open_licence(lic) or not ob.image_host_allowed(url):
            refused += 1
            continue
        if ob.find_cached_image(url):
            skipped += 1
            continue
        wait = gap - (time.time() - last)
        if wait > 0:
            time.sleep(wait)
        last = time.time()
        try:
            body, ctype = ob.fetch_image(url)
            ob.store_image(url, body, ctype)
            fetched += 1
        except Exception as e:  # keep going; report at the end
            failures.append((oid, str(e)))
        if (fetched + len(failures)) % 50 == 0:
            print(f'  {fetched} fetched, {len(failures)} failed', flush=True)
    print(f'fetched {fetched}, already cached {skipped}, refused {refused}, failed {len(failures)}')
    for oid, e in failures:
        print(f'FAILED {oid}: {e}')
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main())
