#!/usr/bin/env python3
"""Record and check the full Theme Search response, in process.

    THEME_READER_URL=... python scripts/review/theme_search_record.py record --out DIR [--budget 470]
    THEME_READER_URL=... python scripts/review/theme_search_record.py check --against DIR [--budget 470]

The request list is the 57 probe queries of evaluation/probe_sets/
combined_confidence.json in both modes the page offers (all languages, and
languages=la), page 2 (offset=25) for the first ten queries, a page inside the
reader's rows (offset=100) for five, and five searches restricted to an author
or to chosen works. Each response is stored whole (every field, every id and its
order) with floats rounded to 4 places and the fields that change from one run
to the next removed (NORMALIZE below). `record` skips requests already stored,
so a run cut short by --budget is continued by running it again. `check`
compares each stored response with a fresh one and exits 1 on any difference.

The live reader is shared with the site: one request at a time, --pause seconds
apart (default 2).
"""
import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
PROBES = ROOT / 'evaluation' / 'probe_sets' / 'combined_confidence.json'

# Fields removed before storing or comparing. `reader.ms` is the wall time of
# the reader call. Nothing else varies between two runs (see the pull request).
DROP_PATHS = [('reader', 'ms')]

RESTRICTED = [
    ('lucan_storm', 'a storm at sea', {'author': 'lucan'}),
    ('vergil_plague', 'plague', {'author': 'vergil'}),
    ('livy_banquet', 'a banquet', {'works': 'livy.ab_urbe_condita'}),
    ('homer_two', 'a guest is welcomed and fed', {'works': 'homer.iliad,homer.odyssey'}),
    ('ovid_la_shipwreck', 'shipwreck', {'author': 'ovid', 'languages': 'la'}),
]


def request_list():
    qs = [p['query'] for p in json.load(open(PROBES))]
    reqs = []
    for i, q in enumerate(qs):
        reqs.append((f'q{i:02d}_all', {'q': q}))
        reqs.append((f'q{i:02d}_la', {'q': q, 'languages': 'la'}))
    for i, q in enumerate(qs[:10]):
        reqs.append((f'q{i:02d}_all_p2', {'q': q, 'offset': '25'}))
    for i, q in enumerate(qs[:5]):
        reqs.append((f'q{i:02d}_all_off100', {'q': q, 'offset': '100'}))
    for name, q, extra in RESTRICTED:
        reqs.append((f'restricted_{name}', {'q': q, **extra}))
    return reqs


def normalize(obj, path=()):
    if isinstance(obj, dict):
        return {k: normalize(v, path + (k,)) for k, v in obj.items()
                if path + (k,) not in DROP_PATHS}
    if isinstance(obj, list):
        return [normalize(v, path) for v in obj]
    if isinstance(obj, float):
        return round(obj, 4)
    return obj


def fetch(client, params):
    params = dict(params)
    params.setdefault('limit', '25')
    r = client.get('/api/passages/theme-search', query_string=params)
    return normalize(r.get_json())


def make_client():
    from flask import Flask
    from backend.blueprints.passages import passages_bp
    app = Flask(__name__)
    app.register_blueprint(passages_bp, url_prefix='/api')
    from backend import passage_index
    passage_index._ensure_loaded()
    return app.test_client()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('cmd', choices=['record', 'check'])
    ap.add_argument('--out')
    ap.add_argument('--against')
    ap.add_argument('--budget', type=float, default=470.0)
    ap.add_argument('--pause', type=float, default=2.0)
    args = ap.parse_args()
    d = Path(args.out or args.against)
    d.mkdir(parents=True, exist_ok=True)
    client = make_client()
    deadline = time.time() + args.budget
    reqs = request_list()
    done = diff = 0
    marker = d / ('.checked' if args.cmd == 'check' else '.recorded')
    finished = set(marker.read_text().split()) if marker.exists() else set()
    for name, params in reqs:
        f = d / f'{name}.json'
        if args.cmd == 'record' and f.exists():
            continue
        if args.cmd == 'check' and name in finished:
            continue
        if time.time() > deadline:
            print('budget reached; run again to continue')
            return 2
        got = fetch(client, params)
        if args.cmd == 'record':
            f.write_text(json.dumps(got, sort_keys=True, indent=1))
            print('recorded', name, len(got.get('results') or []), flush=True)
        else:
            want = json.loads(f.read_text())
            same = json.dumps(got, sort_keys=True) == json.dumps(want, sort_keys=True)
            print('same     ' if same else 'DIFFERENT', name, flush=True)
            if not same:
                diff += 1
                (d / f'{name}.got.json').write_text(json.dumps(got, sort_keys=True, indent=1))
            with open(marker, 'a') as m:
                m.write(name + ('' if same else '!') + '\n')
            if not same:
                continue
            finished.add(name)
        done += 1
        time.sleep(args.pause)
    if args.cmd == 'check':
        bad = [n for n in marker.read_text().split() if n.endswith('!')] if marker.exists() else []
        print(f'{len(reqs)} requests, {len(bad)} different so far' if bad else 'all checked requests same')
        return 1 if (diff or bad) else 0
    print('recording complete')
    return 0


if __name__ == '__main__':
    sys.exit(main())
