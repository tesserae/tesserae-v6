"""Tests for scripts/scholarship/licensed_fetch.py against a local stub server.
No publisher host is ever contacted."""
import csv
import json
import os
import stat
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts', 'scholarship'))
import licensed_fetch as lf  # noqa: E402
import licensed_lists as ll  # noqa: E402

DOIS = [f'10.9999/s{i:02d}' for i in range(1, 11)]
REFUSE_ONCE = {'10.9999/s05': 403, '10.9999/s09': 429}


class Stub(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, refuse=None, captcha=None):
        super().__init__(('127.0.0.1', 0), Handler)
        self.refuse = dict(REFUSE_ONCE if refuse is None else refuse)
        self.captcha = captcha
        self.hits = []
        threading.Thread(target=self.serve_forever, daemon=True).start()

    @property
    def url(self):
        return f'http://127.0.0.1:{self.server_address[1]}'


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def send(self, code, ctype, body):
        self.send_response(code)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        s = self.server
        s.hits.append((time.time(), self.path, self.headers.get('User-Agent')))
        path = self.path.lstrip('/')
        if path.startswith('pdf/'):
            return self.send(200, 'application/pdf', b'%PDF-1.4 fake ' + path.encode())
        if path in s.refuse:
            return self.send(s.refuse.pop(path), 'text/plain', b'no')
        if path == s.captcha:
            return self.send(200, 'text/html', b'<html>Please solve this CAPTCHA</html>')
        n = path.split('/')[-1]
        html = (f'<html><head><meta name="citation_pdf_url" content="/pdf/{n}.pdf">'
                f'</head><body>article {n}</body></html>').encode()
        self.send(200, 'text/html', html)


def make_list(tmp_path, dois=DOIS):
    p = tmp_path / 'list.csv'
    with open(p, 'w', newline='') as f:
        w = csv.DictWriter(f, ['doi', 'journal', 'year', 'title'])
        w.writeheader()
        for d in dois:
            w.writerow({'doi': d, 'journal': 'Stub Journal', 'year': 2020, 'title': 't ' + d})
    return str(p)


def run(stub, tmp_path, **kw):
    kw.setdefault('rate', 0.0)
    kw.setdefault('pause', 0.0)
    return lf.run('muse', make_list(tmp_path), str(tmp_path / 'out'),
                  base_url=stub.url, log=lambda *_: None, **kw)


def log_records(tmp_path):
    with open(tmp_path / 'out' / 'fetched.jsonl') as f:
        return [json.loads(x) for x in f]


def test_stop_on_403_then_resume(tmp_path):
    stub = Stub()
    assert run(stub, tmp_path) == 2
    recs = log_records(tmp_path)
    assert [r['doi'] for r in recs if r['ok']] == DOIS[:4]
    assert recs[-1]['status'] == 403 and recs[-1]['refused']
    stop = json.load(open(tmp_path / 'out' / 'STOPPED.json'))
    assert stop['doi'] == DOIS[4] and stop['status'] == 403
    # No request after the refusal, and the refused DOI was asked for once.
    assert [h[1] for h in stub.hits].count('/' + DOIS[4]) == 1
    assert not any('s06' in h[1] for h in stub.hits)
    # A restart refuses until a person clears the stop.
    assert run(stub, tmp_path) == 3
    # Cleared: resumes past the four done, then meets the 429.
    n_before = len(stub.hits)
    assert run(stub, tmp_path, clear_stop=True) == 2
    assert not any(h[1] == '/' + DOIS[0] for h in stub.hits[n_before:])
    assert [r['doi'] for r in log_records(tmp_path) if r['ok']] == DOIS[:8]
    assert run(stub, tmp_path, clear_stop=True) == 0
    assert [r['doi'] for r in log_records(tmp_path) if r['ok']] == DOIS


def test_stop_on_429_and_captcha(tmp_path):
    stub = Stub(refuse={DOIS[1]: 429})
    assert run(stub, tmp_path) == 2
    assert json.load(open(tmp_path / 'out' / 'STOPPED.json'))['status'] == 429
    t2 = tmp_path / 'c'
    t2.mkdir()
    stub2 = Stub(refuse={}, captcha=DOIS[2])
    assert run(stub2, t2) == 2
    assert 'captcha' in json.load(open(t2 / 'out' / 'STOPPED.json'))['reason']


def test_permissions_and_sidecar(tmp_path):
    stub = Stub(refuse={})
    assert run(stub, tmp_path, limit=2) == 0
    out = tmp_path / 'out'
    assert stat.S_IMODE(os.stat(out).st_mode) == 0o700
    d = out / 'muse' / 'stub_journal'
    assert stat.S_IMODE(os.stat(d).st_mode) == 0o700
    files = sorted(os.listdir(d))
    assert files == ['10.9999_s01.json', '10.9999_s01.pdf',
                     '10.9999_s02.json', '10.9999_s02.pdf']
    for f in files:
        assert stat.S_IMODE(os.stat(d / f).st_mode) == 0o600
    meta = json.load(open(d / '10.9999_s01.json'))
    assert meta['http_status'] == 200 and meta['content_type'] == 'application/pdf'
    assert meta['size_bytes'] == os.path.getsize(d / '10.9999_s01.pdf')
    assert meta['fetched_at'] and meta['journal'] == 'Stub Journal'
    assert stat.S_IMODE(os.stat(out / 'fetched.jsonl').st_mode) == 0o600
    assert all(h[2] == lf.USER_AGENT for h in stub.hits)
    assert 'buffalo.edu' in lf.USER_AGENT


def test_rate_spacing_scales(tmp_path):
    for rate in (1.0, 2.0):
        t = tmp_path / f'r{rate}'
        t.mkdir()
        stub = Stub(refuse={})
        assert run(stub, t, rate=rate, limit=3, pause=0.0) == 0
        starts = [r['started_epoch'] for r in log_records(t)]
        gaps = [b - a for a, b in zip(starts, starts[1:])]
        assert len(gaps) == 2 and all(g >= rate - 0.01 for g in gaps)
        assert all(g < rate + 0.5 for g in gaps)


def test_rate_honoured_across_restart(tmp_path):
    stub = Stub(refuse={})
    run(stub, tmp_path, rate=1.0, limit=1)
    t0 = time.time()
    run(stub, tmp_path, rate=1.0, limit=1)
    recs = log_records(tmp_path)
    assert recs[1]['started_epoch'] - recs[0]['started_epoch'] >= 0.99
    assert time.time() - t0 >= 0.5


def test_address_check(tmp_path):
    msgs = []
    rc = lf.run('muse', make_list(tmp_path), str(tmp_path / 'out'),
                addr_check=lambda: '10.1.2.3', log=msgs.append)
    assert rc == 3 and 'REFUSING' in msgs[0]
    assert not os.path.exists(tmp_path / 'out' / 'fetched.jsonl')
    # Right address: would go on to contact the publisher, so stub the client.
    called = []
    orig = lf.Client.get
    lf.Client.get = lambda self, url: called.append(url) or (404, '', b'', url)
    try:
        lf.run('muse', make_list(tmp_path, DOIS[:1]), str(tmp_path / 'o2'), rate=0,
               addr_check=lambda: lf.ALLOWED_ADDRESS, log=lambda *_: None, pause=0)
    finally:
        lf.Client.get = orig
    assert called == ['https://doi.org/10.9999/s01']


def test_purge_keeps_sidecars_and_log(tmp_path):
    stub = Stub(refuse={})
    run(stub, tmp_path, limit=3)
    out = str(tmp_path / 'out')
    rec = lf.purge(out, 'muse', log=lambda *_: None)
    assert rec['files_deleted'] == 3
    d = tmp_path / 'out' / 'muse' / 'stub_journal'
    assert sorted(os.listdir(d)) == [f'10.9999_s0{i}.json' for i in (1, 2, 3)]
    assert (tmp_path / 'out' / 'fetched.jsonl').exists()
    purges = [f for f in os.listdir(out) if f.startswith('PURGE_muse_')]
    assert len(purges) == 1
    assert len(json.load(open(os.path.join(out, purges[0])))['files']) == 3


def test_redirect_to_other_host_is_refused():
    c = lf.Client({'127.0.0.1'})
    with pytest.raises(lf.Refusal):
        for hd in c.opener.handlers:
            if hasattr(hd, 'redirect_request') and type(hd).__name__ == 'Redirect':
                hd.redirect_request(None, None, 302, '', {}, 'https://evil.example/x')


def test_lists_row_and_key():
    item = {'DOI': '10.1353/x', 'title': ['A  title'], 'issued': {'date-parts': [[2001]]},
            'author': [{'family': 'Smith', 'given': 'J.'}], 'page': '5-9', 'volume': '12',
            'license': [{'URL': 'u', 'content-version': 'vor'}],
            'link': [{'URL': 'l', 'content-type': 'application/pdf',
                      'intended-application': 'text-mining'}]}
    r = ll.article_row(item, 'J')
    assert r['first_author'] == 'Smith, J.' and r['year'] == 2001 and r['title'] == 'A title'
    assert ll.key_of(2001, 12, '5-9', 'Smith, J.') == ('2001', '12', '5', 'smith')
    assert lf.find_fulltext_url('<html></html>', 'http://x/y', r['tdm_links']) == 'l'
