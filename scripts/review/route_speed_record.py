#!/usr/bin/env python3
"""Record and compare the answers of the browse, rare-word, rare-pair, search
and cached-fusion routes, and time them (route-speed work, 2026-10-14).

    python3 scripts/review/route_speed_record.py run BASE OUTDIR [--reps N] [--only SUBSTR]
    python3 scripts/review/route_speed_record.py cmp OUTDIR_A OUTDIR_B
    python3 scripts/review/route_speed_record.py sum OUTDIR/timings.jsonl

`run` sends the requests of scripts/review/route_speed_requests.json to a
server one at a time, writes each answer (timings and cache flags removed, keys
sorted, the two rare-pair lists sorted) to OUTDIR/NAME.json, and appends one
line per request to OUTDIR/timings.jsonl. With --reps 2 the second request is
the warm one, and an answer that differs from the first is printed as
REP_DIFFERS. `cmp` lists every request whose answer differs between two
recordings and exits 1 if any does. Record on main, record on the branch with
the same PYTHONHASHSEED, compare.

The fusion requests read cached results: copy the cache files for the pairs
named in the file into the preview's cache folder first, or they start a
computation. The encoder and the reader are not needed.
"""
import argparse
import json
import os
import statistics
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

REQUESTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'route_speed_requests.json')
IGNORE = {"elapsed", "elapsed_time", "took", "time", "timing", "duration", "timestamp",
          "generated", "generated_at", "cache", "cached", "cache_hit", "request_id",
          "server_version", "build", "search_time", "last_updated", "last_updated_raw",
          "bundle", "result_id", "search_id"}


def scrub(obj):
    if isinstance(obj, dict):
        return {k: scrub(v) for k, v in sorted(obj.items()) if k not in IGNORE}
    if isinstance(obj, list):
        return [scrub(x) for x in obj]
    return obj


def sort_lists(obj, keys):
    if isinstance(obj, dict):
        return {k: (sorted(v, key=lambda x: json.dumps(x, sort_keys=True))
                    if k in keys and isinstance(v, list) else sort_lists(v, keys))
                for k, v in obj.items()}
    if isinstance(obj, list):
        return [sort_lists(x, keys) for x in obj]
    return obj


def send(base, req):
    url = base.rstrip('/') + req['path']
    data = None
    headers = {}
    if req['method'] == 'GET':
        if req.get('params'):
            url += '?' + urllib.parse.urlencode(req['params'])
    else:
        data = json.dumps(req['body']).encode()
        headers = {'Content-Type': 'application/json'}
    request = urllib.request.Request(url, data=data, method=req['method'], headers=headers)
    start = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=900) as resp:  # nosec B310 - a preview on this machine
            status, raw = resp.status, resp.read()
    except urllib.error.HTTPError as e:
        status, raw = e.code, e.read()
    return status, raw, time.perf_counter() - start


def percentile(values, q):
    values = sorted(values)
    k = (len(values) - 1) * q
    lo = int(k)
    hi = min(lo + 1, len(values) - 1)
    return values[lo] + (values[hi] - values[lo]) * (k - lo)


def cmd_run(args):
    base, out = args.args
    os.makedirs(out, exist_ok=True)
    with open(REQUESTS, encoding='utf-8') as f:
        requests = json.load(f)['requests']
    rows = []
    for req in requests:
        if args.only and args.only not in req['name']:
            continue
        for rep in range(args.reps):
            status, raw, dt = send(base, req)
            rows.append({'name': req['name'], 'rep': rep, 'status': status, 't': dt, 'size': len(raw)})
            try:
                body = json.loads(raw)
            except ValueError:
                body = raw.decode('utf-8', 'replace')
            unordered = {'results', 'matched_words'} if 'rare_pairs' in req['name'] else set()
            text = json.dumps({'status': status, 'body': sort_lists(scrub(body), unordered)}, sort_keys=True)
            path = os.path.join(out, req['name'] + '.json')
            if rep == 0:
                with open(path, 'w', encoding='utf-8') as f:
                    f.write(text)
            else:
                with open(path, encoding='utf-8') as f:
                    if f.read() != text:
                        print('REP_DIFFERS', req['name'], rep, flush=True)
            print(f"{req['name']:45s} rep{rep} {status} {dt:7.2f}s {len(raw)}", flush=True)
    with open(os.path.join(out, 'timings.jsonl'), 'a', encoding='utf-8') as f:
        for row in rows:
            f.write(json.dumps(row) + '\n')


def cmd_cmp(args):
    a_dir, b_dir = args.args
    same = diff = 0
    for name in sorted(os.listdir(a_dir)):
        if name == 'timings.jsonl' or not name.endswith('.json'):
            continue
        other = os.path.join(b_dir, name)
        if not os.path.exists(other):
            print('MISSING', name)
            diff += 1
            continue
        with open(os.path.join(a_dir, name), encoding='utf-8') as fa, open(other, encoding='utf-8') as fb:
            if fa.read() == fb.read():
                same += 1
            else:
                diff += 1
                print('DIFFERENT', name)
    print(f'same {same} different {diff}')
    return 1 if diff else 0


def cmd_sum(args):
    rows = []
    for path in args.args:
        with open(path, encoding='utf-8') as f:
            rows += [json.loads(line) for line in f]
    groups = {}
    for row in rows:
        route = row['name'].split('_')[0]
        if route == 'rare':
            route = 'rare_pairs' if 'pairs' in row['name'] else 'rare_words'
        groups.setdefault((route, row['rep']), []).append(row['t'])
    for (route, rep), values in sorted(groups.items()):
        print(f'{route:12s} rep{rep} n={len(values):3d} median {statistics.median(values):7.3f} '
              f'p90 {percentile(values, .9):7.3f} max {max(values):7.2f}')
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('cmd', choices=['run', 'cmp', 'sum'])
    ap.add_argument('args', nargs='+')
    ap.add_argument('--reps', type=int, default=1)
    ap.add_argument('--only')
    args = ap.parse_args()
    sys.exit({'run': cmd_run, 'cmp': cmd_cmp, 'sum': cmd_sum}[args.cmd](args) or 0)


if __name__ == '__main__':
    main()
