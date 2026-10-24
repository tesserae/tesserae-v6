#!/usr/bin/env python3
"""Prove that a Line Search speed change returns the same results as before.

Sixty queries (twenty exact phrases, twenty lemma phrases that hold a very
common word, twenty single words, across Latin and Greek) are sent to a local
Flask server started from a code folder, each one at least twice (the first answer is
the cold time, the best of the others the warm time). The answers are saved. Run it once
for the old code and once for the new code, on the same data, then compare:

    ~/bin/tess-job --fg ls_old 8 PY scripts/review/line_search_equivalence.py run --code OLD_DIR --out old.json
    ~/bin/tess-job --fg ls_new 8 PY scripts/review/line_search_equivalence.py run --code NEW_DIR --out new.json
    PY scripts/review/line_search_equivalence.py compare old.json new.json

A foreground job must end inside ten minutes, so the sixty queries can be run in
slices (`--slice 0:20`, `20:40`, `40:60`, each into its own file) and `compare`
takes the files of a run joined by commas (`o1.json,o2.json,o3.json`).
`--runs 3` asks each query three times and reports the best of the last two as
the warm time, which steadies the figures on a busy machine.

`compare` checks every field of every answer (loci, order, scores, counts) and
exits 1 on any difference, then prints the median and the worst time per
query kind. Fields that only report how long the request took are left out and
named in the output.
"""
import argparse
import json
import os
import statistics
import subprocess
import sys
import time
import urllib.request

EXACT = [
    ('la', 'sunt lacrimae rerum'), ('la', 'arma virumque'), ('la', 'lacrimae rerum'),
    ('la', 'quo usque tandem'), ('la', 'veni vidi vici'), ('la', 'in nomine'),
    ('la', 'omnis gallia'), ('la', 'o tempora o mores'), ('la', 'carpe diem'),
    ('la', 'si vis pacem'), ('la', 'amor vincit omnia'), ('la', 'habent sua fata libelli'),
    ('la', 'sine ira et studio'), ('la', 'arma virum'), ('la', 'quid est'),
    ('la', 'et in terra'),
    ('grc', 'μῆνιν ἄειδε θεά'), ('grc', 'ἄνδρα μοι ἔννεπε'), ('grc', 'ἐν ἀρχῇ ἦν ὁ λόγος'),
    ('grc', 'γνῶθι σεαυτόν'),
]
LEMMA_PHRASES = [
    ('la', 'sunt lacrimae rerum'), ('la', 'arma virum'), ('la', 'est amor'),
    ('la', 'et bellum'), ('la', 'qui est'), ('la', 'sum homo'), ('la', 'non est'),
    ('la', 'ad urbem'), ('la', 'cum militibus'), ('la', 'in bello'),
    ('la', 'esse videri'), ('la', 'ut sunt'), ('la', 'quod est deus'),
    ('la', 'omnia vincit amor'),
    ('grc', 'ἐστι θεός'), ('grc', 'καὶ λόγος'), ('grc', 'ὁ ἀνήρ'),
    ('grc', 'μῆνιν ἄειδε'), ('grc', 'οὐκ ἔστιν'), ('grc', 'ἄνδρα μοι'),
]
SINGLE = [
    ('la', 'sunt'), ('la', 'amor'), ('la', 'arma'), ('la', 'virum'), ('la', 'lacrimae'),
    ('la', 'bellum'), ('la', 'est'), ('la', 'et'), ('la', 'quod'), ('la', 'deus'),
    ('la', 'rex'), ('la', 'fortuna'),
    ('grc', 'μῆνιν'), ('grc', 'ἄνδρα'), ('grc', 'θεός'), ('grc', 'λόγος'),
    ('grc', 'ἀρχή'), ('grc', 'ἐστί'), ('grc', 'καί'), ('grc', 'ἀνήρ'),
]


def queries():
    out = []
    for kind, search_type, items in (('exact', 'exact', EXACT),
                                     ('lemma-phrase', 'lemma', LEMMA_PHRASES),
                                     ('single-word', 'lemma', SINGLE)):
        for language, q in items:
            out.append({'kind': kind, 'language': language, 'query': q,
                        'search_type': search_type, 'max_results': 500})
    assert len(out) == 60, len(out)
    return out


TIMING_KEYS = ('time', 'elapsed', 'duration', 'took', 'seconds', '_ms', 'cached')


def strip_timing(obj, dropped):
    if isinstance(obj, dict):
        kept = {}
        for k, v in obj.items():
            if any(t in k.lower() for t in TIMING_KEYS):
                dropped.add(k)
                continue
            kept[k] = strip_timing(v, dropped)
        return kept
    if isinstance(obj, list):
        return [strip_timing(v, dropped) for v in obj]
    return obj


# The server main.py starts, without its background cache warm-up, and with the
# corpus frequency caches taken as current. A preview checkout's texts differ in
# size and date from the ones its frequency files were built from, and the first
# search then re-lemmatizes the whole corpus (hours). Old code and new code are
# started the same way, so the frequencies are the same for both.
SERVER_CODE = '''
import json, os, sys
os.environ['TESSERAE_DIRECT_SERVER'] = '1'
sys.path.insert(0, os.path.join(os.getcwd(), 'backend'))
from dotenv import load_dotenv
load_dotenv(override=True)
import backend.frequency_cache as fc
def _stored_checksum(language):
    try:
        with open(fc.get_cache_path(language), encoding='utf-8') as f:
            return json.load(f).get('checksum')
    except Exception:
        return None
fc.get_corpus_checksum = _stored_checksum
from backend.app import app
app.run(host='127.0.0.1', port=int(os.environ['PORT']), threaded=True)
'''


def first_difference(a, b, path=''):
    """The path of the first field where two answers differ, or None."""
    if type(a) is not type(b):
        return f'{path} (type {type(a).__name__} against {type(b).__name__})'
    if isinstance(a, dict):
        for k in sorted(set(a) | set(b)):
            if k not in a or k not in b:
                return f'{path}/{k} (missing on one side)'
            found = first_difference(a[k], b[k], f'{path}/{k}')
            if found:
                return found
        return None
    if isinstance(a, list):
        if len(a) != len(b):
            return f'{path} (length {len(a)} against {len(b)})'
        for i, (x, y) in enumerate(zip(a, b)):
            found = first_difference(x, y, f'{path}[{i}]')
            if found:
                return found
        return None
    return None if a == b else f'{path} ({str(a)[:60]!r} against {str(b)[:60]!r})'


def post(url, payload, timeout=500):
    req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'),
                                 headers={'Content-Type': 'application/json'})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=timeout) as r:
        body = json.loads(r.read().decode('utf-8'))
    return time.time() - t0, body


def run(args):
    code = os.path.abspath(args.code)
    env = dict(os.environ, PORT=str(args.port), PYTHONUNBUFFERED='1')
    py = args.python
    log = open(args.out + '.server.log', 'w')
    proc = subprocess.Popen([py, '-c', SERVER_CODE], cwd=code, env=env, stdout=log, stderr=subprocess.STDOUT)
    base = f'http://127.0.0.1:{args.port}/api'
    try:
        deadline = time.time() + 600
        while True:
            try:
                urllib.request.urlopen(base + '/languages', timeout=10).read()
                break
            except Exception:
                if proc.poll() is not None:
                    raise SystemExit('server exited during start, see ' + args.out + '.server.log')
                if time.time() > deadline:
                    raise SystemExit('server did not start in ten minutes')
                time.sleep(3)
        rows = []
        lo, hi = (int(x) for x in args.slice.split(':'))
        for i, q in enumerate(queries(), 1):
            if not lo < i <= hi:
                continue
            payload = {k: q[k] for k in ('query', 'language', 'search_type', 'max_results')}
            t1, body = post(base + '/line-search', payload)
            warm_times = []
            for _ in range(max(1, args.runs - 1)):
                t2, body2 = post(base + '/line-search', payload)
                warm_times.append(t2)
                dropped = set()
                if json.dumps(strip_timing(body, dropped), sort_keys=True) != json.dumps(strip_timing(body2, dropped), sort_keys=True):
                    print(f'NOTE query {i} {q["query"]!r}: two runs of the same code differ at '
                          f'{first_difference(strip_timing(body, set()), strip_timing(body2, set()))}', flush=True)
            t2 = min(warm_times)
            rows.append(dict(q, cold=t1, warm=t2, body=body))
            print(f'{i:2d} {q["kind"]:12s} {q["language"]:3s} {q["query"]!r:34} cold {t1:6.2f}s warm {t2:6.2f}s', flush=True)
        with open(args.out, 'w', encoding='utf-8') as f:
            json.dump({'code': code, 'rows': rows}, f, ensure_ascii=False)
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=30)
        except subprocess.TimeoutExpired:
            proc.kill()


def compare(args):
    def load(paths):
        return [row for p in paths.split(',') for row in json.load(open(p, encoding='utf-8'))['rows']]
    old, new = load(args.old), load(args.new)
    dropped = set()
    bad = 0
    for o, n in zip(old, new):
        assert (o['query'], o['language'], o['search_type']) == (n['query'], n['language'], n['search_type'])
        a = json.dumps(strip_timing(o['body'], dropped), sort_keys=True, ensure_ascii=False)
        b = json.dumps(strip_timing(n['body'], dropped), sort_keys=True, ensure_ascii=False)
        if a != b:
            bad += 1
            print(f'DIFFERENT: {o["kind"]} {o["language"]} {o["query"]!r} at '
                  f'{first_difference(strip_timing(o["body"], set()), strip_timing(n["body"], set()))}')
    same = len(old) - bad
    print(f'\nIdentical: {same} of {len(old)}')
    if dropped:
        print('Fields left out of the comparison (timing only):', ', '.join(sorted(dropped)))
    print('\nkind          n   old cold med/worst   new cold med/worst   old warm med/worst   new warm med/worst')
    for kind in ('exact', 'lemma-phrase', 'single-word', 'all'):
        sel = [(o, n) for o, n in zip(old, new) if kind == 'all' or o['kind'] == kind]

        def mw(rows, key):
            v = [r[key] for r in rows]
            return f'{statistics.median(v):6.2f}/{max(v):6.2f}'
        print(f'{kind:12s} {len(sel):3d}   {mw([s[0] for s in sel], "cold")}      {mw([s[1] for s in sel], "cold")}'
              f'      {mw([s[0] for s in sel], "warm")}      {mw([s[1] for s in sel], "warm")}')
    sys.exit(1 if bad else 0)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    r = sub.add_parser('run')
    r.add_argument('--code', required=True, help='folder holding main.py (old or new code)')
    r.add_argument('--out', required=True)
    r.add_argument('--port', type=int, default=8123)
    r.add_argument('--slice', default='0:60', help='run queries LO+1 to HI only, e.g. 0:30 (a foreground job must end inside ten minutes)')
    r.add_argument('--runs', type=int, default=2, help='requests per query; the first is the cold time, the best of the others the warm time')
    r.add_argument('--python', default=sys.executable)
    c = sub.add_parser('compare')
    c.add_argument('old', help='result file, or several separated by commas')
    c.add_argument('new')
    args = ap.parse_args()
    run(args) if args.cmd == 'run' else compare(args)


if __name__ == '__main__':
    main()
