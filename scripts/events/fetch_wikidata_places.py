#!/usr/bin/env python3
"""Fetch from Wikidata what each event's place stands for, and the English Wikipedia coordinates of the events.

  fetch_wikidata_places.py EVENTS.sqlite RAW_DIR [--delay 1.1] [--max-seconds 540]

Three stages, each resumable (a stored response is not fetched again), at most one request per second.
  1. wbgetentities (claims, labels, 50 items per request) for every event item: P625 coordinates,
     P276 location, P31 instance of, P17 country. Files RAW_DIR/events_<n>.json.
  2. The same for every P276 and P17 item found, and then for every P31 class of those items (labels
     only matter for the classes). Files RAW_DIR/locations_<n>.json and RAW_DIR/classes_<n>.json.
  3. The MediaWiki API (prop=coordinates, 50 titles per request) for the wikipedia_title of every event.
     Files RAW_DIR/wikipedia_<n>.json.
Exit code 0 when everything is fetched, 3 when more remain, 1 on an error.
"""
import argparse
import hashlib
import json
import os
import sqlite3
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

UA = 'Tesserae Project, University at Buffalo (tesserae.caset.buffalo.edu)'
WD = 'https://www.wikidata.org/w/api.php'
WP = 'https://en.wikipedia.org/w/api.php'


def api(base, params):
    url = base + '?' + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={'User-Agent': UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def chunks(seq, n=50):
    for i in range(0, len(seq), n):
        yield seq[i:i + n]


class Fetcher:
    def __init__(self, raw, delay, max_seconds):
        self.raw, self.delay, self.deadline = raw, delay, time.time() + max_seconds
        self.stopped = False
        os.makedirs(raw, exist_ok=True)

    def run(self, prefix, items, fetch):
        """Fetch each chunk of items; the file name carries a hash of the chunk so a changed list refetches."""
        out = []
        for chunk in chunks(sorted(items)):
            h = hashlib.sha1('|'.join(chunk).encode()).hexdigest()[:10]
            path = os.path.join(self.raw, '%s_%s.json' % (prefix, h))
            if os.path.exists(path):
                out.append(path)
                continue
            if time.time() > self.deadline:
                self.stopped = True
                continue
            for attempt in range(5):
                try:
                    data = fetch(chunk)
                    break
                except Exception as e:  # network trouble or a 429: wait as asked, retry, then give up (resumable)
                    if attempt == 4:
                        raise
                    wait = self.delay * 3
                    if isinstance(e, urllib.error.HTTPError) and e.code == 429:
                        wait = max(float(e.headers.get('Retry-After') or 0), 30)
                    print('retry in %.0fs after %r' % (wait, e), flush=True)
                    time.sleep(wait)
            with open(path, 'w') as f:
                json.dump(data, f)
            out.append(path)
            time.sleep(self.delay)
        return out


def entities(ids):
    return lambda chunk: api(WD, {'action': 'wbgetentities', 'ids': '|'.join(chunk), 'props': 'claims|labels',
                                  'languages': 'en', 'format': 'json'})


def claim_ids(ent, prop):
    out = []
    for c in (ent.get('claims') or {}).get(prop, []):
        v = ((c.get('mainsnak') or {}).get('datavalue') or {}).get('value')
        if isinstance(v, dict) and 'id' in v:
            out.append(v['id'])
    return out


def load_entities(paths):
    ents = {}
    for p in paths:
        ents.update((json.load(open(p)).get('entities') or {}))
    return ents


def titles_query(chunk):
    return api(WP, {'action': 'query', 'prop': 'coordinates', 'titles': '|'.join(chunk), 'colimit': 'max',
                    'redirects': 1, 'format': 'json', 'formatversion': 2})


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('events')
    ap.add_argument('raw_dir')
    ap.add_argument('--delay', type=float, default=2.0)
    ap.add_argument('--max-seconds', type=float, default=540)
    a = ap.parse_args(argv)
    con = sqlite3.connect('file:%s?mode=ro' % a.events, uri=True)
    qids = [r[0] for r in con.execute("SELECT id FROM events WHERE id GLOB 'Q[0-9]*'")]
    titles = sorted({r[0] for r in con.execute("SELECT wikipedia_title FROM events WHERE wikipedia_title IS NOT NULL AND wikipedia_title <> ''")})
    f = Fetcher(a.raw_dir, a.delay, a.max_seconds)
    ev_paths = f.run('events', qids, entities(qids))
    ents = load_entities(ev_paths)
    locs = set()
    for e in ents.values():
        locs.update(claim_ids(e, 'P276'))
        locs.update(claim_ids(e, 'P17'))
    loc_paths = f.run('locations', sorted(locs), entities(locs))
    lents = load_entities(loc_paths)
    classes = set()
    for e in lents.values():
        classes.update(claim_ids(e, 'P31'))
    f.run('classes', sorted(classes), entities(classes))
    f.run('wikipedia', titles, titles_query)
    print('events %d, locations %d, classes %d, titles %d; %s' % (len(qids), len(locs), len(classes), len(titles),
                                                                'more remain' if f.stopped else 'complete'), flush=True)
    return 3 if f.stopped else 0


if __name__ == '__main__':
    sys.exit(main())
