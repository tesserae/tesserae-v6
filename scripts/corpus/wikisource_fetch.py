#!/usr/bin/env python3
"""Fetch wikitext of Wikisource pages politely (one request a second).

Usage: wikisource_fetch.py LANG OUTDIR [--html] PAGE [PAGE ...]
       --html saves the rendered HTML (needed where the text sits in the Page namespace and the article only transcludes it)
       wikisource_fetch.py LANG OUTDIR --prefix PREFIX     (every page under a prefix)
Each page is saved as OUTDIR/<title with / replaced by __>.wiki together with a
.rev file holding the revision id, so the exact text fetched is citable.
"""
import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

UA = 'TesseraeProject/6 (https://tesserae.caset.buffalo.edu; text import)'


def api(lang, **params):
    params['format'] = 'json'
    url = f'https://{lang}.wikisource.org/w/api.php?' + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={'User-Agent': UA})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=90) as r:
                data = json.load(r)
            time.sleep(1)
            return data
        except Exception:
            time.sleep(3 * (attempt + 1))
    raise SystemExit(f'failed: {url}')


def main():
    lang, out = sys.argv[1], Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    args = sys.argv[3:]
    html = False
    if args and args[0] == '--html':
        html = True
        args = args[1:]
    if args and args[0] == '--prefix':
        pages = []
        d = api(lang, action='query', list='allpages', apprefix=args[1], aplimit=500)
        pages = [p['title'] for p in d['query']['allpages']]
    else:
        pages = args
    for t in pages:
        if html:
            d = api(lang, action='parse', page=t, prop='text|revid', redirects=1)
            if 'parse' not in d:
                print('MISSING', t)
                continue
            name = t.replace('/', '__').replace(' ', '_')
            (out / f'{name}.html').write_text(d['parse']['text']['*'], encoding='utf-8')
            (out / f'{name}.rev').write_text(str(d['parse']['revid']) + '\n')
            print(f'{t}: {len(d["parse"]["text"]["*"])} chars rev {d["parse"]["revid"]}')
            continue
        d = api(lang, action='query', prop='revisions', rvprop='content|ids', rvslots='main', titles=t, redirects=1)
        pg = next(iter(d['query']['pages'].values()))
        if 'revisions' not in pg:
            print('MISSING', t)
            continue
        rev = pg['revisions'][0]
        txt = rev['slots']['main']['*']
        name = t.replace('/', '__').replace(' ', '_')
        (out / f'{name}.wiki').write_text(txt, encoding='utf-8')
        (out / f'{name}.rev').write_text(str(rev['revid']) + '\n')
        print(f'{t}: {len(txt)} chars rev {rev["revid"]}')


if __name__ == '__main__':
    main()
