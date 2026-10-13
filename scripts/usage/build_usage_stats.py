#!/usr/bin/env python3
"""Build a small JSON summary of visitors and feature use from the web server's access log.

The admin panel's Analytics tab serves the JSON this script writes. Parsing the
log takes tens of seconds, so it is never done inside a web request.

    python scripts/usage/build_usage_stats.py [--log PATH] [--out PATH]
                                              [--own-ip IP ...] [--force]
"""
import argparse
import glob
import gzip
import json
import os
import re
import socket
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone

# The bot list is shared with the page-view route (backend/usage_bots.py).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from backend.usage_bots import is_bot  # noqa: E402

DEFAULT_LOG = '/var/log/tesserae/tesseraev6_ssl_access.log'
DEFAULT_OUT = 'data/usage/usage_stats.json'
OWN_HOST = 'tesserae.caset.buffalo.edu'
# The server's other names: a visit referred from them is our own page.
OWN_HOSTS = {OWN_HOST, 'marvin.caset.buffalo.edu'}

LINE_RE = re.compile(
    r'^(?P<ip>\S+) \S+ \S+ \[(?P<day>\d{1,2})/(?P<mon>[A-Za-z]{3})/(?P<year>\d{4}):[^\]]*\] '
    r'"(?P<method>[A-Z]+) (?P<path>\S+)[^"]*" (?P<status>\d{3}) (?P<size>\S+) '
    r'"(?P<referer>[^"]*)" "(?P<ua>[^"]*)"'
)
MONTHS = {m: i + 1 for i, m in enumerate(
    ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'])}

ASSET_RE = re.compile(r'\.(js|css|png|jpg|svg|ico|woff2?|map|json|webp|ttf)$', re.I)
APP_BUNDLE_RE = re.compile(r'^/assets/index-[^/?]*\.js$')
# A hostname with letters in it: a bare address such as 128.205.2.231 is the
# server itself or a forged referrer, never a page that links to the site.
HOST_RE = re.compile(r'^(?=.*[A-Za-z])[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)+$')

FEATURES = [
    ('Search page', r'^/api/search'),
    ('Line Search', r'^/api/(line[-_]search|search/line)'),
    ('Rare words and pairs', r'^/api/(hapax|rare)'),
    ('Theme Search', r'^/api/passages/theme-search'),
    ('Similar Passages', r'^/api/passages/similar'),
    ('Reader', r'^/api/passages/(read|work|translation|connections|lines)'),
    ('Tessa', r'^/api/assistant/(ask|guide|analyze)'),
    ('Inscriptions and papyri', r'^/api/documents'),
    ('Scholarship', r'^/api/scholarship'),
    ('Events', r'^/api/events'),
]
FEATURE_RES = [(n, re.compile(p)) for n, p in FEATURES]
CONNECTOR = 'Connector (own AI)'
CONNECTOR_RE = re.compile(r'^/api/mcp')

NOTES = [
    'Counts are of network addresses, not people. One person on several devices counts several times, and many people behind one institutional address count once.',
    'Automated visitors were removed by their user agent, so some robots that do not announce themselves are still counted.',
    "The server's own addresses were removed.",
    "The project's own use from Buffalo is still included.",
    'Connector (own AI) counts addresses of the servers of AI vendors that call the connector for their users, not people.',
]


def own_addresses():
    try:
        out = subprocess.run(['hostname', '-I'], capture_output=True, text=True, timeout=10).stdout.split()
    except Exception:
        out = []
    return set(out) | {'127.0.0.1'}


def summarize(lines, own_ips):
    """Parse an iterable of log lines and return the summary dict."""
    loaders = defaultdict(set)      # month -> addresses that loaded the application
    api_any = defaultdict(set)      # month -> addresses with any /api/ request
    feat = defaultdict(lambda: defaultdict(set))  # month -> feature -> addresses
    connector = defaultdict(set)    # month -> all non-bot addresses calling the connector
    requests = Counter()
    ref_rows = []                   # (month, host, address) of every referred request
    months_seen = set()
    for line in lines:
        m = LINE_RE.match(line)
        if not m:
            continue
        ip = m.group('ip')
        if ip in own_ips:
            continue
        ua = m.group('ua')
        if is_bot(ua):
            continue
        mon = MONTHS.get(m.group('mon'))
        if not mon:
            continue
        month = f"{m.group('year')}-{mon:02d}"
        months_seen.add(month)
        path = m.group('path')
        bare = path.split('?', 1)[0]
        if ASSET_RE.search(bare):
            if m.group('method') == 'GET' and m.group('status') == '200' and APP_BUNDLE_RE.match(bare):
                loaders[month].add(ip)
            continue
        requests[month] += 1
        ref = m.group('referer')
        if ref and ref != '-':
            hm = re.match(r'^https?://([^/:?#]+)', ref)
            if hm:
                host = hm.group(1).lower()
                if host not in OWN_HOSTS and HOST_RE.match(host):
                    ref_rows.append((month, host, ip))
        if bare.startswith('/api/'):
            api_any[month].add(ip)
            if CONNECTOR_RE.match(bare):
                connector[month].add(ip)
            for name, rx in FEATURE_RES:
                if rx.match(bare):
                    feat[month][name].add(ip)
                    break
    # A referrer counts only when the referred address loaded the application
    # that month. Forged referrers (a radiology association, a WordPress page)
    # come from scanners that never do.
    referrers = Counter(host for mo, host, ip in ref_rows if ip in loaders[mo])
    months = []
    for month in sorted(months_seen):
        app = loaders[month]
        months.append({
            'month': month,
            'app_loads': len(app),
            'api_users': len(app & api_any[month]),
            'requests': requests[month],
            'features': {name: len(feat[month][name] & app) for name, _ in FEATURES},
        })
    ordered = sorted(months_seen)
    return {
        'built_at': datetime.now(timezone.utc).isoformat(timespec='seconds'),
        'log_first_month': ordered[0] if ordered else None,
        'log_last_month': ordered[-1] if ordered else None,
        'months': months,
        'connector_addresses_by_month': {
            mo: {'label': 'servers of AI vendors, not people', 'addresses': len(connector[mo])}
            for mo in ordered if connector[mo]},
        'referrers': [{'host': h, 'count': c} for h, c in referrers.most_common(15)],
        'notes': NOTES,
    }


def log_files(path):
    """The rotated copies of the log (oldest first, .gz or plain), then the log itself."""
    rotated = [f for f in glob.glob(path + '.*') if not f.endswith('.tmp')]
    rotated.sort(key=lambda f: os.path.getmtime(f))
    return rotated + [path]


def read_lines(files):
    for f in files:
        opener = gzip.open if f.endswith('.gz') else open
        with opener(f, 'rt', encoding='utf-8', errors='replace') as fh:
            for line in fh:
                yield line


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--log', default=DEFAULT_LOG)
    ap.add_argument('--out', default=DEFAULT_OUT)
    ap.add_argument('--own-ip', action='append', default=None)
    ap.add_argument('--force', action='store_true')
    a = ap.parse_args(argv)
    if os.path.exists(a.out) and not a.force:
        print(f'{a.out} exists, use --force to overwrite', file=sys.stderr)
        return 1
    own = set(a.own_ip) if a.own_ip else own_addresses()
    result = summarize(read_lines(log_files(a.log)), own)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    tmp = a.out + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=1)
    os.replace(tmp, a.out)
    print(f'wrote {a.out}: {len(result["months"])} months')
    return 0


if __name__ == '__main__':
    sys.exit(main())
