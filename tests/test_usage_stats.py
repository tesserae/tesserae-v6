"""build_usage_stats.summarize on a small synthetic access log."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'scripts', 'usage'))

import build_usage_stats as b  # noqa: E402

UA = 'Mozilla/5.0 (X11; Linux x86_64) Firefox/120.0'


def line(ip, day, path, status=200, ua=UA, ref='-', method='GET'):
    return f'{ip} - - [{day}:10:00:00 -0400] "{method} {path} HTTP/1.1" {status} 512 "{ref}" "{ua}"'


LOG = [
    line('1.1.1.1', '05/Sep/2026', '/assets/index-abc123.js'),
    line('1.1.1.1', '05/Sep/2026', '/api/search?q=arma', ref='https://www.google.com/'),
    line('1.1.1.1', '06/Sep/2026', '/api/passages/theme-search'),
    line('2.2.2.2', '07/Sep/2026', '/assets/index-abc123.js'),
    line('2.2.2.2', '07/Sep/2026', '/'),
    line('3.3.3.3', '08/Sep/2026', '/api/search?q=x', ua='Googlebot/2.1 bot'),
    line('10.0.0.5', '08/Sep/2026', '/assets/index-abc123.js'),
    line('4.4.4.4', '08/Sep/2026', '/api/mcp', method='POST'),
    line('5.5.5.5', '02/Oct/2026', '/assets/index-abc123.js'),
    line('5.5.5.5', '02/Oct/2026', '/api/search?q=y'),
    line('5.5.5.5', '02/Oct/2026', '/static/logo.png'),
    line('6.6.6.6', '03/Oct/2026', '/api/search?q=z'),
    # A forged referrer from an address that never loaded the application.
    line('7.7.7.7', '03/Oct/2026', '/', ref='https://www.aocr.org/'),
]


def test_counts():
    r = b.summarize(LOG, {'10.0.0.5'})
    assert r['log_first_month'] == '2026-09' and r['log_last_month'] == '2026-10'
    sep, octo = r['months']
    assert sep['month'] == '2026-09'
    assert sep['app_loads'] == 2
    assert sep['api_users'] == 1
    assert sep['requests'] == 4
    assert sep['features']['Search page'] == 1
    assert sep['features']['Theme Search'] == 1
    assert sep['features']['Reader'] == 0
    assert octo['app_loads'] == 1 and octo['api_users'] == 1
    assert octo['requests'] == 3
    assert octo['features']['Search page'] == 1
    assert r['connector_addresses_by_month']['2026-09']['addresses'] == 1
    assert r['referrers'] == [{'host': 'www.google.com', 'count': 1}]
    assert r['notes']


def test_refuses_overwrite(tmp_path):
    log = tmp_path / 'a.log'
    log.write_text('\n'.join(LOG) + '\n')
    out = tmp_path / 'o.json'
    assert b.main(['--log', str(log), '--out', str(out), '--own-ip', '10.0.0.5']) == 0
    assert b.main(['--log', str(log), '--out', str(out), '--own-ip', '10.0.0.5']) == 1
    assert b.main(['--log', str(log), '--out', str(out), '--own-ip', '10.0.0.5', '--force']) == 0


def test_rotated_copies_are_read_oldest_first(tmp_path):
    import gzip
    log = tmp_path / 'access.log'
    log.write_text(LOG[-1] + '\n', encoding='utf-8')
    with gzip.open(str(log) + '.2.gz', 'wt', encoding='utf-8') as f:
        f.write('\n'.join(LOG[:2]) + '\n')
    files = b.log_files(str(log))
    assert files[-1] == str(log) and len(files) == 2
    lines = list(b.read_lines(files))
    assert len(lines) == 3 and lines[-1].startswith('7.7.7.7')
