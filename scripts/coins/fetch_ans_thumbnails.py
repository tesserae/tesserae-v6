#!/usr/bin/env python3
"""Store one small thumbnail per OCRE type from the American Numismatic Society's own photographs.

Step 1 (--specimens): ask the Nomisma SPARQL endpoint (GET only) for every ANS specimen of an
OCRE type, with its obverse and reverse thumbnail URLs. Written to ans_specimens.jsonl.
Step 2 (default): for each type pick one ANS specimen (both sides preferred), download the
obverse (and reverse) image, scale to 160 px wide, join side by side, save as JPEG.
Photographs of other museums' coins are never taken: only specimens whose collection is
http://nomisma.org/id/ans are asked for.

One request a second at most. Stops on any 403 or 429 (exit 3) or three 5xx in a row (exit 4).
Resumable: types already in thumbnails.sqlite (stored or failed) are skipped.
Slices: --max-seconds N stops cleanly after N seconds (exit 0 with "MORE" if work remains).

Usage:
  fetch_ans_thumbnails.py --out DIR --specimens
  fetch_ans_thumbnails.py --out DIR [--max-seconds 470] [--limit N]
DIR holds ans_specimens.jsonl, thumbs/ and thumbnails.sqlite.
"""
import argparse
import hashlib
import io
import json
import os
import re
import sqlite3
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

from PIL import Image

UA = 'Tesserae Project, University at Buffalo (tesserae.caset.buffalo.edu)'
NOMISMA = 'https://nomisma.org/query'
WIDTH = 160
MAX_BYTES = 12 * 1024
QUERY = '''PREFIX nmo: <http://nomisma.org/ontology#>
PREFIX nm: <http://nomisma.org/id/>
PREFIX foaf: <http://xmlns.com/foaf/0.1/>
SELECT ?type ?obj ?obv ?rev WHERE {
 ?obj nmo:hasCollection nm:ans ; nmo:hasTypeSeriesItem ?type .
 FILTER(STRSTARTS(STR(?type),"http://numismatics.org/ocre/id/"))
 OPTIONAL { ?obj nmo:hasObverse/foaf:thumbnail ?obv }
 OPTIONAL { ?obj nmo:hasReverse/foaf:thumbnail ?rev } } ORDER BY ?type ?obj LIMIT 8000 OFFSET %d'''


class Stop(Exception):
    def __init__(self, code, msg):
        super().__init__(msg)
        self.code = code


_last = [0.0]
_5xx = [0]


def get(url, accept=None):
    """One polite GET: at most one request a second, stop rules applied."""
    wait = 1.05 - (time.time() - _last[0])
    if wait > 0:
        time.sleep(wait)
    headers = {'User-Agent': UA}
    if accept:
        headers['Accept'] = accept
    try:
        _last[0] = time.time()
        with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=60) as r:
            _5xx[0] = 0
            return r.read()
    except urllib.error.HTTPError as e:
        if e.code in (403, 429):
            raise Stop(3, 'HTTP %d from %s: stop for the day' % (e.code, url))
        if e.code >= 500:
            _5xx[0] += 1
            if _5xx[0] >= 3:
                raise Stop(4, 'three 5xx in a row, last %d' % e.code)
        else:
            _5xx[0] = 0
        raise


def safe_name(type_uri):
    tid = type_uri.rsplit('/id/', 1)[-1]
    return re.sub(r'[^A-Za-z0-9._-]', '_', tid)


def fetch_specimens(out):
    path = os.path.join(out, 'ans_specimens.jsonl')
    rows, off = 0, 0
    with open(path + '.tmp', 'w') as f:
        while True:
            url = NOMISMA + '?' + urllib.parse.urlencode({'query': QUERY % off, 'output': 'json'})
            d = json.loads(get(url))
            b = d['results']['bindings']
            for r in b:
                f.write(json.dumps({k: v['value'] for k, v in r.items()}) + '\n')
            rows += len(b)
            if len(b) < 8000:
                break
            off += 8000
    os.replace(path + '.tmp', path)
    print('specimen rows', rows)


def choose(specs):
    """Per type: first specimen with both sides, else first with an obverse."""
    best = {}
    for s in specs:
        t = s['type']
        score = 2 if ('obv' in s and 'rev' in s) else (1 if 'obv' in s else 0)
        if score and (t not in best or score > best[t][0]):
            best[t] = (score, s)
    return {t: v[1] for t, v in best.items()}


def thumb_bytes(images):
    ims = []
    for raw in images:
        im = Image.open(io.BytesIO(raw)).convert('RGB')
        h = max(1, round(im.height * WIDTH / im.width))
        ims.append(im.resize((WIDTH, h), Image.LANCZOS))
    H = max(i.height for i in ims)
    sheet = Image.new('RGB', (WIDTH * len(ims), H), (255, 255, 255))
    for n, im in enumerate(ims):
        sheet.paste(im, (n * WIDTH, (H - im.height) // 2))
    for q in (80, 70, 60, 50, 40, 30):
        buf = io.BytesIO()
        sheet.save(buf, 'JPEG', quality=q, optimize=True)
        if buf.tell() <= MAX_BYTES:
            break
    return buf.getvalue(), sheet.width, sheet.height


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', required=True)
    ap.add_argument('--specimens', action='store_true')
    ap.add_argument('--max-seconds', type=float, default=470)
    ap.add_argument('--limit', type=int, default=0)
    a = ap.parse_args()
    os.makedirs(os.path.join(a.out, 'thumbs'), exist_ok=True)
    try:
        if a.specimens:
            fetch_specimens(a.out)
            return 0
        specs = [json.loads(line) for line in open(os.path.join(a.out, 'ans_specimens.jsonl'))]
        chosen = choose(specs)
        none_img = sorted({s['type'] for s in specs} - set(chosen))
        db = sqlite3.connect(os.path.join(a.out, 'thumbnails.sqlite'))
        db.execute('CREATE TABLE IF NOT EXISTS thumbnails (type_id TEXT PRIMARY KEY, specimen_uri TEXT, '
                   'collection TEXT, image_url TEXT, fetched_at TEXT, width INT, height INT, bytes INT, sha256 TEXT)')
        db.execute('CREATE TABLE IF NOT EXISTS failures (type_id TEXT PRIMARY KEY, reason TEXT, fetched_at TEXT)')
        def now():
            return datetime.now(timezone.utc).isoformat(timespec='seconds')
        for t in none_img:
            db.execute('INSERT OR IGNORE INTO failures VALUES (?,?,?)', (t, 'ANS specimen without image', now()))
        db.commit()
        done = {r[0] for r in db.execute('SELECT type_id FROM thumbnails UNION SELECT type_id FROM failures')}
        todo = [t for t in sorted(chosen) if t not in done]
        start, n = time.time(), 0
        for t in todo:
            if time.time() - start > a.max_seconds or (a.limit and n >= a.limit):
                print('MORE', len(todo) - n, 'types remain')
                break
            s = chosen[t]
            urls = [s['obv']] + ([s['rev']] if 'rev' in s else [])
            try:
                imgs = [get(u) for u in urls]
                data, w, h = thumb_bytes(imgs)
            except (urllib.error.HTTPError, urllib.error.URLError, OSError) as e:
                db.execute('INSERT OR REPLACE INTO failures VALUES (?,?,?)', (t, 'fetch error: %s' % e, now()))
                db.commit()
                n += 1
                continue
            name = safe_name(t) + '.jpg'
            with open(os.path.join(a.out, 'thumbs', name), 'wb') as f:
                f.write(data)
            db.execute('INSERT OR REPLACE INTO thumbnails VALUES (?,?,?,?,?,?,?,?,?)',
                       (t, s['obj'], 'http://nomisma.org/id/ans', ' '.join(urls), now(), w, h, len(data),
                        hashlib.sha256(data).hexdigest()))
            db.commit()
            n += 1
        else:
            print('DONE')
        print('processed %d in %.0f s' % (n, time.time() - start))
        return 0
    except Stop as e:
        print('STOP:', e)
        return e.code


if __name__ == '__main__':
    sys.exit(main())
