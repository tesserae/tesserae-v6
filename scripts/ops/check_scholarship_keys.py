#!/usr/bin/env python3
"""Check that the CORE and Semantic Scholar keys behind the Scholarship tab
are still accepted. One tiny request to each; prints "core: OK" or
"core: HTTP <status>" per service and exits 1 if any key is refused.
Key values are never printed.

Usage:  check_scholarship_keys.py [/var/www/tesseraev6_flask/.env]
The env file is read only; a variable already in the environment wins.

Weekly run: install the two templates in scripts/ops/systemd/ as user units
(~/.config/systemd/user/), then
    systemctl --user daemon-reload && systemctl --user enable --now tess-key-check.timer
The service writes the result to ~/tesserae-backups/jobs/key_check.last.
"""
import os
import sys

import requests

UA = 'Tesserae key check (tesserae.caset.buffalo.edu)'


def load_env(path):
    env = {}
    try:
        with open(path, encoding='utf-8') as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith('#') or '=' not in line:
                    continue
                k, v = line.split('=', 1)
                k = k.strip()
                if k.startswith('export '):
                    k = k[7:].strip()
                env[k] = v.strip().strip('"').strip("'")
    except OSError as e:
        print(f'cannot read {path}: {type(e).__name__}', file=sys.stderr)
    return env


def check(name, url, params, headers):
    try:
        r = requests.get(url, params=params, headers=dict(headers, **{'User-Agent': UA}), timeout=30)
    except requests.RequestException as e:
        print(f'{name}: error {type(e).__name__}')
        return False
    if r.status_code in (401, 403):
        print(f'{name}: HTTP {r.status_code} (key refused)')
        return False
    if r.status_code == 200:
        print(f'{name}: OK')
        return True
    # 429 and the like say nothing about the key
    print(f'{name}: HTTP {r.status_code} (key not judged)')
    return True


def main(argv):
    env = load_env(argv[1]) if len(argv) > 1 else {}
    get = lambda k: os.environ.get(k) or env.get(k, '')
    ok = True
    core, s2 = get('CORE_API_KEY'), get('S2_API_KEY')
    if core:
        ok &= check('core', 'https://api.core.ac.uk/v3/search/works/', {'q': '"Aeneid"', 'limit': 1},
                    {'Authorization': f'Bearer {core}'})
    else:
        print('core: no key set')
        ok = False
    if s2:
        ok &= check('semantic_scholar', 'https://api.semanticscholar.org/graph/v1/snippet/search',
                    {'query': 'Aeneid', 'limit': 1}, {'x-api-key': s2})
    else:
        print('semantic_scholar: no key set')
        ok = False
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv))
