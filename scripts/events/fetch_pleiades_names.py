#!/usr/bin/env python3
"""Fetch the Pleiades JSON of every place an event points to, and the Pleiades time-period vocabulary.

  fetch_pleiades_names.py EVENTS.sqlite RAW_DIR [--delay 1.1] [--max-seconds 540]

For every distinct events.pleiades_id the file RAW_DIR/places/<id>.json is written (the response of
https://pleiades.stoa.org/places/<id>/json, kept as received). RAW_DIR/periods.json maps each Pleiades
time-period key to its [start, end] years, read from https://pleiades.stoa.org/vocabularies/time-periods.
The script is resumable (a file already present is skipped) and makes at most one request per second.
It stops after --max-seconds so that a long fetch is run again until it reports nothing left.
Exit code 0 when everything is fetched, 3 when more remain, 1 on a failure that is not a missing place.
"""
import argparse
import http.client
import json
import os
import re
import sqlite3
import sys
import time
import urllib.error
import urllib.request

UA = 'Tesserae Project, University at Buffalo (tesserae.caset.buffalo.edu)'
VOCAB_URL = 'https://pleiades.stoa.org/vocabularies/time-periods'


def get(url):
    req = urllib.request.Request(url, headers={'User-Agent': UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def parse_periods(html):
    """Return {key: [start, end]} from the vocabulary page (each entry ends with [[start, end]])."""
    out = {}
    for m in re.finditer(r'<a href="time-periods/([a-z0-9-]+)">(.*?)</p>', html, re.S):
        rng = re.search(r'\[\[\s*(-?\d+)\s*,\s*(-?\d+)\s*\]\]', m.group(2))
        if rng:
            out[m.group(1)] = [int(rng.group(1)), int(rng.group(2))]
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('events')
    ap.add_argument('raw_dir')
    ap.add_argument('--delay', type=float, default=1.1)
    ap.add_argument('--max-seconds', type=float, default=540)
    a = ap.parse_args(argv)
    places = os.path.join(a.raw_dir, 'places')
    os.makedirs(places, exist_ok=True)
    started = time.time()
    pj = os.path.join(a.raw_dir, 'periods.json')
    if not os.path.exists(pj):
        html = get(VOCAB_URL).decode('utf-8', 'replace')
        with open(os.path.join(a.raw_dir, 'time-periods.html'), 'w', encoding='utf-8') as f:
            f.write(html)
        with open(pj, 'w') as f:
            json.dump(parse_periods(html), f, indent=0, sort_keys=True)
        time.sleep(a.delay)
    con = sqlite3.connect('file:%s?mode=ro' % a.events, uri=True)
    ids = [r[0] for r in con.execute("SELECT DISTINCT pleiades_id FROM events WHERE pleiades_id IS NOT NULL AND pleiades_id <> '' ORDER BY 1")]
    todo = [i for i in ids if not os.path.exists(os.path.join(places, i + '.json'))]
    print('places %d, to fetch %d' % (len(ids), len(todo)), flush=True)
    missing = []
    for n, pid in enumerate(todo):
        if time.time() - started > a.max_seconds:
            print('stopping after %d fetched, %d remain' % (n, len(todo) - n), flush=True)
            return 3
        try:
            for attempt in range(3):
                try:
                    body = get('https://pleiades.stoa.org/places/%s/json' % pid)
                    json.loads(body)
                    break
                except (http.client.IncompleteRead, json.JSONDecodeError, TimeoutError):
                    if attempt == 2:
                        raise
                    time.sleep(a.delay * 2)
            with open(os.path.join(places, pid + '.json'), 'wb') as f:
                f.write(body)
        except urllib.error.HTTPError as e:
            if e.code in (404, 410):
                with open(os.path.join(places, pid + '.json'), 'w') as f:
                    json.dump({'_error': e.code}, f)
                missing.append(pid)
            else:
                print('HTTP %s on %s' % (e.code, pid), file=sys.stderr)
                return 1
        except Exception as e:  # network trouble: stop, the run is resumable
            print('error on %s: %r' % (pid, e), file=sys.stderr)
            return 1
        time.sleep(a.delay)
    print('done; missing places: %s' % missing)
    return 0


if __name__ == '__main__':
    sys.exit(main())
