#!/usr/bin/env python3
"""Record the passage-index answers of THIS checkout through Flask's test client.

Builds the app the way tesseraev6_flask.wsgi does (chdir to the checkout, load its
.env, `from backend.app import app`), then replays every request in
golden_requests.json whose path starts with /api/passages, /api/theme, /api/text/,
/api/reuse or /api/documents, and writes {name: {status, body}} to OUT.json, with
the normalisation golden_api.py applies (volatile keys dropped, scores rounded,
unordered lists sorted). Run it once on main and once on a branch, then diff the
two files: a change that must not alter an answer leaves them identical.

    python scripts/review/passages_testclient_record.py OUT.json [--requests FILE] [--checkout DIR]

It records the checkout this script sits in, or DIR (to record main with the
script from a branch). Theme Search requests call
the live embed and reader services.
"""
import argparse
import importlib.util
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
PREFIXES = ('/api/passages', '/api/theme', '/api/text/', '/api/reuse', '/api/documents')


def _golden_api():
    spec = importlib.util.spec_from_file_location('golden_api', os.path.join(HERE, 'golden_api.py'))
    mod = importlib.util.module_from_spec(spec)
    sys.modules['golden_api'] = mod
    spec.loader.exec_module(mod)
    return mod


def _decode(raw):
    try:
        return json.loads(raw.decode('utf-8'))
    except (ValueError, UnicodeDecodeError):
        return {'_text': raw.decode('utf-8', 'replace')}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('out')
    ap.add_argument('--requests', default=os.path.join(HERE, 'golden_requests.json'))
    ap.add_argument('--checkout', default=ROOT)
    a = ap.parse_args()
    root = os.path.abspath(a.checkout)

    os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
    os.environ.setdefault('OPENBLAS_NUM_THREADS', '8')
    os.environ.setdefault('HF_HUB_OFFLINE', '1')
    os.environ.setdefault('TRANSFORMERS_OFFLINE', '1')
    sys.path.insert(0, root)
    os.chdir(root)
    from dotenv import load_dotenv
    load_dotenv(os.path.join(root, '.env'))
    golden = _golden_api()
    reqs = [r for r in golden.load_requests(a.requests) if r['path'].startswith(PREFIXES)]
    from backend.app import app
    client = app.test_client()

    out = {}
    for r in reqs:
        t = time.time()
        params = r.get('params') or {}
        method = r.get('method', 'GET').upper()
        kwargs = {'query_string': params}
        if 'body' in r:
            kwargs['json'] = r['body']
        resp = client.open(r['path'], method=method, **kwargs)
        if resp.status_code == 404 and r['path'].startswith('/api/'):
            # a preview mounts the app at the root rather than under /api
            resp = client.open(r['path'][4:], method=method, **kwargs)
        doc = json.loads(golden.normalise(r, resp.status_code, _decode(resp.data)))
        out[r['name']] = doc
        print('{:<36} {} {:.1f}s'.format(r['name'], resp.status_code, time.time() - t), flush=True)
    with open(a.out, 'w', encoding='utf-8') as f:
        json.dump(out, f, indent=1, sort_keys=True, ensure_ascii=False)
    print('wrote', a.out, len(out), 'requests')


if __name__ == '__main__':
    main()
