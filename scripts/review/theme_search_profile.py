#!/usr/bin/env python3
"""Time each stage of one Theme Search request, in process.

    THEME_READER_URL=http://127.0.0.1:8091 \
        python scripts/review/theme_search_profile.py run --mode all --first 0 --count 57 \
            --out profile_all_warm.jsonl [--pause 2]
    python scripts/review/theme_search_profile.py summarize FILE [FILE...]

`run` loads the passage index in this process, builds a one-blueprint Flask
app around /api/passages/theme-search and sends each probe query through its
test client, so the timings include everything the route does (the encoder
call, the ranking, the lexical boost, composition and confidence, reading the
passage texts, the reader call, building the JSON). Stage wrappers are put
around the module functions; they only start and stop a clock.

The reader call is split into the reader's own compute (the `ms` field its
reply carries) and everything else (network, JSON in and out). Never run this
against the live reader faster than one request per two seconds (--pause).

`--mode all` searches every language, `--mode la` only Latin (languages=la).
`--page2` also times offset=100 for the same query. The queries are the 57 of
evaluation/probe_sets/combined_confidence.json.
"""
import argparse
import json
import os
import statistics
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
PROBES = ROOT / 'evaluation' / 'probe_sets' / 'combined_confidence.json'

STAGES = ['encode', 'score_all', 'mask', 'lexical', 'rank', 'confidence_other',
          'reader_texts', 'reader_http', 'reader_compute', 'reader_overhead',
          'route_other', 'total']

_acc = {}


def _add(name, dt):
    _acc[name] = _acc.get(name, 0.0) + dt


def _wrap(mod, name, label):
    fn = getattr(mod, name)

    def timed(*a, **k):
        t0 = time.perf_counter()
        try:
            return fn(*a, **k)
        finally:
            _add(label, time.perf_counter() - t0)
    setattr(mod, name, timed)


def _install():
    from backend import passage_index as pi, reader_client, reader_rerank
    _wrap(pi, 'embed_query', 'encode')
    _wrap(pi, '_score_all', 'score_all')
    _wrap(pi, '_mask_undescribed', 'mask')
    _wrap(pi, '_lexical_boost', 'lexical')
    _wrap(pi, '_rank', 'rank')
    _wrap(pi, 'find_by_text', 'find_by_text')
    _wrap(reader_rerank, '_reader_texts', 'reader_texts')
    _wrap(reader_rerank, 'apply', 'reader_apply')
    real_score = reader_client.score

    def score(query, passages, timeout=6.0):
        # Same request the client makes, but keep the reader's own `ms`.
        url = (os.environ.get('THEME_READER_URL') or '').strip()
        if not url or not passages:
            return real_score(query, passages, timeout=timeout)
        t0 = time.perf_counter()
        body = json.dumps({'query': query, 'passages': passages}).encode('utf-8')
        req = urllib.request.Request(
            url.rstrip('/') + '/score', data=body, method='POST',
            headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # nosec B310
            payload = json.loads(resp.read().decode('utf-8'))
        dt = time.perf_counter() - t0
        _add('reader_http', dt)
        _add('reader_compute', (payload.get('ms') or 0) / 1000.0)
        _add('reader_bytes', len(body))
        return {k: float(v) for k, v in payload['scores'].items()}
    reader_client.score = score


def _client():
    from flask import Flask
    from backend.blueprints.passages import passages_bp
    app = Flask(__name__)
    app.register_blueprint(passages_bp, url_prefix='/api')
    return app.test_client()


def one(client, q, mode, offset):
    _acc.clear()
    params = {'q': q, 'limit': '25'}
    if mode != 'all':
        params['languages'] = mode
    if offset:
        params['offset'] = str(offset)
    t0 = time.perf_counter()
    r = client.get('/api/passages/theme-search', query_string=params)
    total = time.perf_counter() - t0
    data = r.get_json() or {}
    a = dict(_acc)
    fbt = a.get('find_by_text', 0.0)
    known = sum(a.get(k, 0.0) for k in ('encode', 'score_all', 'mask', 'lexical', 'rank'))
    row = {
        'q': q, 'mode': mode, 'offset': offset, 'status': r.status_code,
        'total': total,
        'encode': a.get('encode', 0.0), 'score_all': a.get('score_all', 0.0),
        'mask': a.get('mask', 0.0), 'lexical': a.get('lexical', 0.0),
        'rank': a.get('rank', 0.0),
        'confidence_other': max(0.0, fbt - known),
        'reader_texts': a.get('reader_texts', 0.0),
        'reader_http': a.get('reader_http', 0.0),
        'reader_compute': a.get('reader_compute', 0.0),
        'reader_overhead': max(0.0, a.get('reader_http', 0.0) - a.get('reader_compute', 0.0)),
        'reader_apply': a.get('reader_apply', 0.0),
        'reader_applied': bool((data.get('reader') or {}).get('applied')),
        'n_results': len(data.get('results') or []),
    }
    row['route_other'] = max(0.0, total - fbt - a.get('reader_apply', 0.0))
    return row


def cmd_run(args):
    probes = json.load(open(PROBES))
    queries = [p['query'] for p in probes][args.first:args.first + args.count]
    _install()
    from backend import passage_index as pi
    t0 = time.perf_counter()
    pi._ensure_loaded()
    print(f'index loaded in {time.perf_counter() - t0:.1f}s', flush=True)
    client = _client()
    out = open(args.out, 'a')
    deadline = time.time() + args.budget
    for i, q in enumerate(queries):
        if time.time() > deadline:
            print(f'budget reached before query {args.first + i}', flush=True)
            break
        runs = [(off, rep) for off in ([0, 100] if args.page2 else [0])
                for rep in range(2 if args.repeat else 1)]
        for off, rep in runs:
            row = one(client, q, args.mode, off)
            row['rep'] = rep
            row['idx'] = args.first + i
            row['seq_in_process'] = i
            out.write(json.dumps(row) + '\n')
            out.flush()
            print(f"{args.first + i:2d} off={off:<3d} rep={rep} total={row['total']:.2f}s "
                  f"enc={row['encode']:.2f} score={row['score_all']:.2f} "
                  f"lex={row['lexical']:.2f} rank={row['rank']:.2f} "
                  f"txt={row['reader_texts']:.2f} rdr={row['reader_http']:.2f} "
                  f"(compute {row['reader_compute']:.2f}) {q[:40]!r}", flush=True)
            time.sleep(args.pause)


def _pct(vals, q):
    vals = sorted(vals)
    if not vals:
        return 0.0
    k = (len(vals) - 1) * q
    lo = int(k)
    hi = min(lo + 1, len(vals) - 1)
    return vals[lo] + (vals[hi] - vals[lo]) * (k - lo)


def cmd_summarize(args):
    rows = []
    for f in args.files:
        rows += [json.loads(line) for line in open(f)]
    if args.offset is not None:
        rows = [r for r in rows if r['offset'] == args.offset]
    if args.rep is not None:
        rows = [r for r in rows if r.get('rep', 0) == args.rep]
    print(f'{len(rows)} requests')
    tot_med = statistics.median([r['total'] for r in rows])
    print(f"{'stage':18s} {'median':>8s} {'p90':>8s} {'share of mean total':>20s}")
    mean_total = statistics.mean([r['total'] for r in rows])
    for s in STAGES:
        v = [r[s] for r in rows if s in r]
        if not v:
            continue
        print(f'{s:18s} {statistics.median(v):8.3f} {_pct(v, .9):8.3f} '
              f'{100 * statistics.mean(v) / mean_total:19.1f}%')
    print(f'median total {tot_med:.3f}s')


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest='cmd', required=True)
    r = sub.add_parser('run')
    r.add_argument('--mode', default='all')
    r.add_argument('--first', type=int, default=0)
    r.add_argument('--count', type=int, default=57)
    r.add_argument('--out', required=True)
    r.add_argument('--pause', type=float, default=2.0)
    r.add_argument('--budget', type=float, default=480.0)
    r.add_argument('--page2', action='store_true')
    r.add_argument('--repeat', action='store_true',
                   help='send every request twice in a row (the second is a repeat)')
    s = sub.add_parser('summarize')
    s.add_argument('files', nargs='+')
    s.add_argument('--offset', type=int, default=None)
    s.add_argument('--rep', type=int, default=None, help='0 first time, 1 repeat')
    args = ap.parse_args()
    if args.cmd == 'run':
        cmd_run(args)
    else:
        cmd_summarize(args)


if __name__ == '__main__':
    main()
