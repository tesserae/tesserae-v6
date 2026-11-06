#!/usr/bin/env python3
"""Preview check of Part G (2026-10-25): a Flask copy of the app on port 8104 whose data/translations folder is a
copy of production plus the staged files, asked through /api/translation for two references per work. For the
two merged or two-source files (Isocrates speeches, the Republic) one reference is drawn from each source, and the
`license` field of each answer is printed, so a merged file is seen to show each source's own license.

    g_preview_check.py WORKTREE STAGING_ROOT
Run it as: ~/bin/tess-job --fg preview 8 python -I g_preview_check.py WORKTREE STAGING_ROOT
"""
import glob
import json
import os
import random
import subprocess
import sys
import time
import urllib.parse
import urllib.request

wt, S = sys.argv[1], sys.argv[2]
sys.path.insert(0, os.path.join(wt, 'scripts/translations'))
from g_common import load_work   # noqa: E402

PORT = '8104'
env = dict(os.environ, SESSION_SECRET='preview-only', DEPLOYMENT_ENV='test', TESSERAE_DIRECT_SERVER='1',
           DATABASE_URL=f'sqlite:///{S}/logs/preview.db', PORT=PORT, TESSERAE_MAX_WORKERS='1')
log = open(f'{S}/logs/preview_server.log', 'w')
srv = subprocess.Popen([sys.executable, 'main.py'], cwd=wt, env=env, stdout=log, stderr=subprocess.STDOUT)
base = f'http://127.0.0.1:{PORT}'


def get(path, **q):
    url = base + path + ('?' + urllib.parse.urlencode(q) if q else '')
    with urllib.request.urlopen(url, timeout=90) as r:
        return json.loads(r.read().decode())


try:
    up = False
    for i in range(120):
        try:
            get('/api/languages')
            up = True
            break
        except Exception:
            time.sleep(3)
    print('preview up:', up)
    results, bad = [], []
    files = sorted(glob.glob(f'{S}/out/demosthenes/*.json') + glob.glob(f'{S}/out/republic/*.json') +
                   glob.glob(f'{S}/out/plato/*.json') + glob.glob(f'{S}/out/isocrates/merged/*.json') +
                   glob.glob(f'{S}/out/isocrates/standalone/*.json') + glob.glob(f'{S}/out/plato/review/*.json'))
    for path in files:
        d = json.load(open(path))
        lang, stem = d['tess_work'].split('/')
        refs, src, _ = load_work(lang, stem)
        cov = [r for r in refs if r in d['ref_to_unit']]
        rnd = random.Random(8104)
        picks = rnd.sample(cov, 2)
        us = d.get('unit_sources')
        if us and len(d['sources']) > 1:
            picks = []
            for si in range(len(d['sources'])):
                pool = [r for r in cov if us[d['ref_to_unit'][r]] == si]
                picks.append(rnd.choice(pool))
        for r in picks:
            try:
                a = get('/api/translation', work=d['tess_work'], refs=r)
            except Exception as e:
                a = {'error': str(e)}
            row = {'work': d['tess_work'], 'ref': r, 'available': a.get('available'), 'translator': a.get('translator'),
                   'year': a.get('year'), 'license': a.get('license'), 'text': (a.get('text') or '')[:110],
                   'approximate': a.get('approximate'), 'unit_source': (us[d['ref_to_unit'][r]] if us else None)}
            results.append(row)
            if not a.get('available') or not a.get('license'):
                bad.append(row)
    print(f'{sum(1 for x in results if x["available"])} of {len(results)} answers available; with a license: '
          f'{sum(1 for x in results if x["license"])}')
    for x in bad:
        print('PROBLEM', x)
    for x in results:
        if x['unit_source'] is not None:
            print('TWO-SOURCE', x['work'], x['ref'], 'source', x['unit_source'], x['translator'], x['year'], '|', x['license'])
    json.dump(results, open(f'{S}/logs/preview_results.json', 'w'), ensure_ascii=False, indent=1)
finally:
    srv.terminate()
    try:
        srv.wait(timeout=20)
    except Exception:
        srv.kill()
