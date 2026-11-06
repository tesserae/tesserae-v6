"""Time every stage of an uncached Theme Search, offline, on production data.

Runs the real route (/passages/theme-search) through a Flask test client, with a
timer around each stage, against its OWN copies of the two services it calls
(the query encoder and the reader), started here on other ports and stopped at
the end. The live services are never contacted.

    tess-job --fg NAME 8 venv/bin/python scripts/profile_theme_search.py \
        --label before --out /path/to/before.json --dump /path/to/before_results.json

Each request starts with every in-process cache emptied (query vector, lexical
rows, reader scores), so each one costs what a fresh search costs live.
`--dump` writes the full result lists (ids, order, scores) so a later run can
be compared byte for byte with `--compare`.
"""
import argparse
import json
import os
import statistics
import subprocess
import sys
import time
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ.setdefault('OPENBLAS_NUM_THREADS', '8')      # as the live wsgi file sets it
os.environ.setdefault('HF_HOME', '/var/www/tesseraev6_flask/models')
os.environ.setdefault('HF_HUB_OFFLINE', '1')
os.environ.setdefault('TRANSFORMERS_OFFLINE', '1')

EMBED_PORT = 8190
READER_PORT = 8191
PROBE = os.path.join(ROOT, 'evaluation', 'probe_sets', 'theme_confidence_2026-10-08.json')
READER_MODEL = '/home/ncoffee/tesserae-models/theme_reader_minilm_2026-09-17'


def pick_queries(n=20):
    """Twenty fixed queries: the present-in-corpus probes, evenly spaced."""
    rows = [r for r in json.load(open(PROBE)) if r.get('present')]
    step = len(rows) / n
    return [rows[int(i * step)]['query'] for i in range(n)]


def wait_health(url, seconds=240):
    end = time.time() + seconds
    while time.time() < end:
        try:
            with urllib.request.urlopen(url, timeout=3) as r:
                if r.status == 200:
                    return True
        except Exception:
            time.sleep(1)
    return False


def start_services(reader_env):
    env = dict(os.environ)
    procs = []
    e = dict(env, TESSERAE_EMBED_PORT=str(EMBED_PORT))
    procs.append(subprocess.Popen(
        [sys.executable, os.path.join(ROOT, 'services', 'embed_server.py')], env=e,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
    r = dict(env, TESSERAE_READER_PORT=str(READER_PORT), READER_MODEL_DIR=READER_MODEL,
             READER_THREADS='16', READER_SORT='1', READER_BATCH_SIZE='8',
             MALLOC_ARENA_MAX='2')
    r.update(reader_env)
    procs.append(subprocess.Popen(
        [sys.executable, os.path.join(ROOT, 'services', 'reader_server.py')], env=r,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
    return procs


def stop(procs):
    for p in procs:
        if p.poll() is None:
            p.terminate()
    for p in procs:
        try:
            p.wait(timeout=20)
        except subprocess.TimeoutExpired:
            p.kill()
            p.wait()


def canonical(resp):
    """The response as stored, without the one field that is a wall-clock time."""
    d = json.loads(json.dumps(resp))
    if isinstance(d.get('reader'), dict):
        d['reader'].pop('ms', None)
    return d


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--label', default='run')
    ap.add_argument('--out', required=True)
    ap.add_argument('--dump')
    ap.add_argument('--runs', type=int, default=3)
    ap.add_argument('--queries', type=int, default=20)
    ap.add_argument('--slice', default='', help='a:b, run only these of the twenty (to fit one call)')
    ap.add_argument('--reader-env', default='{}', help='JSON of env overrides for the reader')
    ap.add_argument('--dump-payloads', help='write the reader payloads (query, passages) here')
    args = ap.parse_args()

    os.environ['TESSERAE_EMBED_ENDPOINT'] = f'http://127.0.0.1:{EMBED_PORT}'
    os.environ['THEME_READER_URL'] = f'http://127.0.0.1:{READER_PORT}'
    procs = start_services(json.loads(args.reader_env))
    try:
        if not wait_health(f'http://127.0.0.1:{READER_PORT}/health'):
            print('reader did not come up', file=sys.stderr)
            return 2
        from flask import Flask
        from backend import passage_index, reader_rerank, reader_client, window_texts
        import backend.blueprints.passages as P

        P._log_passage_search = lambda *a, **k: None          # no database writes
        app = Flask(__name__)
        app.register_blueprint(P.passages_bp)
        client = app.test_client()

        calls = {}

        def wrap(mod, name, label):
            fn = getattr(mod, name)

            def timed(*a, **k):
                t = time.perf_counter()
                try:
                    return fn(*a, **k)
                finally:
                    calls[label] = calls.get(label, 0.0) + (time.perf_counter() - t)
            setattr(mod, name, timed)

        for mod, name, label in [
            (passage_index, 'find_by_text', 'find_by_text (all index work)'),
            (passage_index, 'embed_query', 'encode (embed service)'),
            (passage_index, '_score_all', 'scan (727k dot products)'),
            (passage_index, '_mask_undescribed', 'mask undescribed'),
            (passage_index, '_cluster_coherence', 'coherence'),
            (passage_index, '_lexical_boost', 'lexical (desc_fts + boost)'),
            (passage_index, '_vocab_fields', 'vocab fields'),
            (passage_index, '_rank', 'rank (three passes, with result rows)'),
            (passage_index, '_interleave_languages', 'interleave languages'),
            (reader_rerank, 'apply', 'reader apply (all)'),
            (window_texts, 'texts_for', 'reader: window texts'),
            (reader_rerank, '_translation_for', 'reader: translations lookup'),
            (reader_client, 'score', 'reader: HTTP call (model time + transfer)'),
        ]:
            wrap(mod, name, label)

        def clear_caches():
            passage_index._QUERY_VECTORS.clear()
            passage_index._lex_rows_cache.clear()
            reader_rerank.clear_score_cache()

        queries = pick_queries(args.queries)
        if args.slice:
            a, b = (int(x) for x in args.slice.split(':'))
            queries = queries[a:b]
        # Warm: load the index, the encoder and the reader once, as a live worker is.
        clear_caches()
        client.get('/passages/theme-search', query_string={'q': 'a warm-up query about a storm at sea'})

        results = {}
        per_query = {}
        nondeterministic = []
        payloads = []
        if args.dump_payloads:
            inner = reader_client.score
            seen = set()

            def capture(query, passages, timeout=6.0):
                if query not in seen:
                    seen.add(query)
                    payloads.append({'query': query, 'passages': passages})
                return inner(query, passages, timeout=timeout)
            reader_client.score = capture

        for q in queries:
            runs = []
            first = None
            for i in range(args.runs):
                clear_caches()
                calls.clear()
                t = time.perf_counter()
                resp = client.get('/passages/theme-search', query_string={'q': q})
                total = time.perf_counter() - t
                body = resp.get_json()
                runs.append({'total': total, **dict(calls)})
                canon = canonical(body)
                if not (body.get('reader') or {}).get('applied'):
                    print('READER NOT APPLIED for', q, file=sys.stderr)
                if first is None:
                    first = canon
                elif canon != first:
                    nondeterministic.append(q)
            results[q] = first
            per_query[q] = runs

        stages = ['total'] + sorted({k for r in per_query.values() for run in r for k in run if k != 'total'})
        table = {}
        for st in stages:
            meds = [statistics.median([run.get(st, 0.0) for run in runs]) for runs in per_query.values()]
            table[st] = {'median_of_query_medians_s': round(statistics.median(meds), 4),
                         'mean_of_query_medians_s': round(statistics.mean(meds), 4)}
        out = {'label': args.label, 'queries': queries, 'runs': args.runs, 'table': table,
               'per_query': per_query, 'nondeterministic_between_runs': sorted(set(nondeterministic))}
        json.dump(out, open(args.out, 'w'), indent=1)
        if args.dump_payloads:
            json.dump(payloads, open(args.dump_payloads, 'w'))
        if args.dump:
            json.dump(results, open(args.dump, 'w'), sort_keys=True)
        for st in stages:
            print(f'{table[st]["median_of_query_medians_s"]:8.3f}  {st}')
        print('nondeterministic between runs:', sorted(set(nondeterministic)))
        return 0
    finally:
        stop(procs)


if __name__ == '__main__':
    sys.exit(main())
