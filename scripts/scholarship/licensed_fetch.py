#!/usr/bin/env python3
"""Polite fetcher for licensed journal text (Project MUSE, De Gruyter Brill).

    licensed_fetch.py run   --publisher P --list CSV --out DIR
                            [--rate 60] [--limit N] [--base-url URL]
                            [--clear-stop]
    licensed_fetch.py purge --out DIR --publisher P

One item (one article) per --rate seconds, 60 by default. It refuses to run
unless this machine's outgoing address is the web server's registered
address, 128.205.2.231 (a stub server given by --base-url is exempt, for
tests). It stops at the first 401, 403, 429 or captcha-like page, writes
STOPPED.json and does nothing further until a person has read it and re-run
with --clear-stop. Nothing is retried around a refusal.

Files go to DIR/<publisher>/<journal>/<doi-safe-name>.<ext> with a sidecar
<doi-safe-name>.json; DIR is mode 700 and files are mode 600. fetched.jsonl
is the resumable log: a restart skips every DOI already saved.
"""
import argparse
import csv
import datetime
import json
import os
import re
import socket
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser

ALLOWED_ADDRESS = '128.205.2.231'
CONTACT = 'ncoffee@buffalo.edu'
USER_AGENT = ('TesseraeResearchFetcher/1.0 (Tesserae V6, University at Buffalo; '
              f'licensed text-mining; contact {CONTACT})')
REFUSAL_STATUS = {401, 403, 429}
CAPTCHA_RE = re.compile(
    r'captcha|are you a robot|unusual traffic|verify you are (a )?human|'
    r'cf-chk-|challenge-platform|access denied|too many requests', re.I)
# Hosts a redirect may lead to, besides the starting host.
PUBLISHER_HOSTS = {
    'muse': ('doi.org', 'muse.jhu.edu'),
    'degruyter': ('doi.org', 'degruyterbrill.com', 'www.degruyterbrill.com',
                  'degruyter.com', 'www.degruyter.com', 'brill.com',
                  'www.brill.com', 'brill.com'),
}
INTRA_ITEM_PAUSE = 5.0  # seconds between the landing page and the full text
MAX_CONSECUTIVE_FAILURES = 3


class Refusal(Exception):
    def __init__(self, doi, status, why):
        super().__init__(f'{doi}: {why}')
        self.doi, self.status, self.why = doi, status, why


def outgoing_address():
    """The address this machine would use to reach the internet.

    A UDP connect sends no packet; it only asks the routing table.
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('192.0.2.1', 9))
        return s.getsockname()[0]
    finally:
        s.close()


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds')


def safe_name(doi):
    return re.sub(r'[^A-Za-z0-9._-]+', '_', doi)


def slug(text):
    return re.sub(r'[^a-z0-9]+', '_', text.lower()).strip('_') or 'unknown'


def ensure_dir(path):
    os.makedirs(path, mode=0o700, exist_ok=True)
    os.chmod(path, 0o700)


def write_private(path, data, mode='wb'):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, mode) as f:
        f.write(data)
    os.chmod(path, 0o600)


class _Meta(HTMLParser):
    def __init__(self):
        super().__init__()
        self.meta = {}
        self.links = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == 'meta' and a.get('name') and a.get('content'):
            self.meta.setdefault(a['name'].lower(), a['content'])
        elif tag == 'link' and a.get('href') and (a.get('rel') or '') == 'alternate':
            self.links.append((a.get('type', ''), a['href']))


def find_fulltext_url(html, page_url, tdm_links=''):
    """Best full-text link on a landing page: PDF, then XML, then HTML."""
    p = _Meta()
    p.feed(html)
    for key in ('citation_pdf_url', 'citation_xml_url', 'citation_fulltext_html_url'):
        if p.meta.get(key):
            return urllib.parse.urljoin(page_url, p.meta[key])
    for typ, href in p.links:
        if 'pdf' in typ or 'xml' in typ:
            return urllib.parse.urljoin(page_url, href)
    for part in filter(None, (x.strip() for x in tdm_links.split('|'))):
        m = re.match(r'(\S+) \[(\S*?);', part)
        if m and ('pdf' in m.group(2) or 'xml' in m.group(2)):
            return m.group(1)
    return None


def ext_for(content_type, body):
    ct = (content_type or '').lower()
    if 'pdf' in ct or body[:5] == b'%PDF-':
        return 'pdf'
    if 'xml' in ct:
        return 'xml'
    return 'html'


class Client:
    """urllib with a fixed User-Agent and redirects limited to known hosts."""

    def __init__(self, allowed_hosts):
        self.allowed = set(allowed_hosts)
        client = self

        class Redirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, headers, newurl):
                host = urllib.parse.urlparse(newurl).hostname or ''
                if host not in client.allowed:
                    raise Refusal('', code, f'redirect to unexpected host {host}')
                return super().redirect_request(req, fp, code, msg, headers, newurl)

        self.opener = urllib.request.build_opener(Redirect)

    def get(self, url):
        req = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
        try:
            with self.opener.open(req, timeout=90) as r:
                return r.status, r.headers.get('Content-Type', ''), r.read(), r.geturl()
        except urllib.error.HTTPError as e:
            return e.code, e.headers.get('Content-Type', '') if e.headers else '', b'', url


def read_list(path):
    with open(path, newline='', encoding='utf-8') as f:
        return list(csv.DictReader(f))


def done_dois(log_path):
    done, last_start = set(), 0.0
    if os.path.exists(log_path):
        with open(log_path, encoding='utf-8') as f:
            for line in f:
                try:
                    rec = json.loads(line)
                except ValueError:
                    continue
                if rec.get('ok'):
                    done.add(rec['doi'])
                last_start = max(last_start, rec.get('started_epoch', 0.0))
    return done, last_start


def check_item(doi, status, ctype, body):
    """Raise Refusal on a refusal status or a challenge page."""
    if status in REFUSAL_STATUS:
        raise Refusal(doi, status, f'HTTP {status}')
    if 'html' in (ctype or '').lower() and CAPTCHA_RE.search(
            body[:300000].decode('utf-8', 'replace')):
        raise Refusal(doi, status, 'captcha-like page')


def fetch_item(client, row, publisher, out, base_url, pause, started_epoch):
    """Fetch one article. Returns the log record. Raises Refusal."""
    doi = row['doi']
    landing = (f"{base_url.rstrip('/')}/{doi}" if base_url
               else row.get('landing_url') or f'https://doi.org/{doi}')
    rec = {'doi': doi, 'started': now(), 'started_epoch': started_epoch,
           'landing_url': landing, 'ok': False}
    status, ctype, body, final = client.get(landing)
    check_item(doi, status, ctype, body)
    rec['landing_status'] = status
    rec['landing_final_url'] = final
    if status != 200:
        rec['status'] = status
        rec['error'] = f'landing page HTTP {status}'
        return rec
    html = body.decode('utf-8', 'replace')
    ft = find_fulltext_url(html, final, row.get('tdm_links', ''))
    if ft:
        time.sleep(pause)
        status, ctype, body, final = client.get(ft)
        check_item(doi, status, ctype, body)
        kind = 'fulltext'
    else:
        kind = 'landing-only'
    rec['status'] = status
    rec['content_type'] = ctype
    rec['fulltext_url'] = ft
    rec['kind'] = kind
    if status != 200 or not body:
        rec['error'] = f'full text HTTP {status}'
        return rec
    ext = ext_for(ctype, body)
    d = os.path.join(out, publisher, slug(row.get('journal', '')))
    ensure_dir(d)
    name = safe_name(doi)
    path = os.path.join(d, f'{name}.{ext}')
    write_private(path, body)
    meta = {k: row.get(k, '') for k in
            ('doi', 'journal', 'year', 'volume', 'issue', 'pages', 'title',
             'first_author', 'authors')}
    meta.update({'file': os.path.basename(path), 'http_status': status,
                 'content_type': ctype, 'size_bytes': len(body),
                 'kind': kind, 'fetched_at': now(), 'source_url': ft or landing})
    write_private(os.path.join(d, f'{name}.json'),
                  json.dumps(meta, ensure_ascii=False, indent=1).encode('utf-8'))
    rec.update({'ok': True, 'file': os.path.relpath(path, out),
                'size_bytes': len(body), 'finished': now()})
    return rec


def run(publisher, list_csv, out, rate=60.0, limit=None, base_url=None,
        clear_stop=False, addr_check=outgoing_address, sleep=time.sleep,
        pause=None, log=print):
    """Returns 0 on completion or limit, 2 when stopped by a refusal, 3 on
    refusing to start."""
    if not base_url:
        addr = addr_check()
        if addr != ALLOWED_ADDRESS:
            log(f'REFUSING TO START: outgoing address is {addr}, not {ALLOWED_ADDRESS}. '
                'This job runs from the web server only.')
            return 3
    ensure_dir(out)
    stop_path = os.path.join(out, 'STOPPED.json')
    if os.path.exists(stop_path):
        if not clear_stop:
            log(f'REFUSING TO START: {stop_path} exists. Read it, then re-run '
                'with --clear-stop.')
            return 3
        os.rename(stop_path, os.path.join(out, f'STOPPED.{int(time.time())}.cleared.json'))
    if pause is None:  # keeps an item well inside its own time slot
        pause = min(INTRA_ITEM_PAUSE, rate / 4)
    hosts = set(PUBLISHER_HOSTS[publisher])
    if base_url:
        hosts.add(urllib.parse.urlparse(base_url).hostname)
    client = Client(hosts)
    log_path = os.path.join(out, 'fetched.jsonl')
    done, last_start = done_dois(log_path)
    rows = [r for r in read_list(list_csv) if r['doi'] not in done]
    log(f'{len(done)} already done, {len(rows)} to go, rate {rate:g} s per item')
    saved = failures = 0
    for row in rows:
        if limit is not None and saved >= limit:
            break
        wait = last_start + rate - time.time()
        if wait > 0:
            sleep(wait)
        started = time.time()
        last_start = started
        try:
            rec = fetch_item(client, row, publisher, out, base_url, pause, started)
        except Refusal as r:
            r.doi = r.doi or row['doi']
            rec = {'doi': row['doi'], 'started': now(), 'started_epoch': started,
                   'ok': False, 'refused': True, 'status': r.status, 'error': r.why}
            with open(log_path, 'a', encoding='utf-8') as f:
                f.write(json.dumps(rec) + '\n')
            os.chmod(log_path, 0o600)
            write_private(stop_path, json.dumps(
                {'stopped_at': now(), 'doi': row['doi'], 'status': r.status,
                 'reason': r.why, 'saved_this_run': saved,
                 'note': 'Not retried. Read, tell the licensor if appropriate, '
                         're-run with --clear-stop.'}, indent=1).encode())
            log(f'STOPPED on {row["doi"]}: {r.why}. Saved {saved} this run. '
                f'Nothing further requested.')
            return 2
        except Exception as e:  # network trouble: record, continue, bounded
            rec = {'doi': row['doi'], 'started': now(), 'started_epoch': started,
                   'ok': False, 'error': f'{type(e).__name__}: {e}'}
        with open(log_path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(rec, ensure_ascii=False) + '\n')
        os.chmod(log_path, 0o600)
        if rec['ok']:
            saved += 1
            failures = 0
            log(f'saved {row["doi"]} ({rec["size_bytes"]} bytes)')
        else:
            failures += 1
            log(f'not saved {row["doi"]}: {rec.get("error")}')
            if failures >= MAX_CONSECUTIVE_FAILURES:
                write_private(stop_path, json.dumps(
                    {'stopped_at': now(), 'reason': f'{failures} failures in a row',
                     'last_doi': row['doi']}, indent=1).encode())
                log(f'STOPPED after {failures} failures in a row.')
                return 2
    log(f'finished: {saved} saved this run')
    return 0


def purge(out, publisher, log=print):
    """Delete the text files of one publisher; keep sidecars and the log."""
    root = os.path.join(out, publisher)
    removed = nbytes = 0
    files = []
    for dirpath, _, names in os.walk(root):
        for n in names:
            if n.endswith('.json'):
                continue
            p = os.path.join(dirpath, n)
            nbytes += os.path.getsize(p)
            files.append(os.path.relpath(p, out))
            os.remove(p)
            removed += 1
    record = {'purged_at': now(), 'publisher': publisher, 'files_deleted': removed,
              'bytes_deleted': nbytes, 'kept': 'metadata sidecars (.json) and fetched.jsonl',
              'note': 'Backups drop a deleted file after thirty days.'}
    stamp = datetime.date.today().isoformat()
    path = os.path.join(out, f'PURGE_{publisher}_{stamp}.json')
    write_private(path, json.dumps(dict(record, files=files), indent=1).encode())
    log(f'purged {removed} files ({nbytes} bytes); record {path}')
    return record


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    sub = ap.add_subparsers(dest='cmd', required=True)
    r = sub.add_parser('run')
    r.add_argument('--publisher', choices=sorted(PUBLISHER_HOSTS), required=True)
    r.add_argument('--list', required=True)
    r.add_argument('--out', required=True)
    r.add_argument('--rate', type=float, default=60.0)
    r.add_argument('--limit', type=int)
    r.add_argument('--base-url')
    r.add_argument('--clear-stop', action='store_true')
    p = sub.add_parser('purge')
    p.add_argument('--out', required=True)
    p.add_argument('--publisher', choices=sorted(PUBLISHER_HOSTS), required=True)
    a = ap.parse_args(argv)
    if a.cmd == 'run':
        return run(a.publisher, a.list, a.out, a.rate, a.limit, a.base_url,
                   a.clear_stop)
    purge(a.out, a.publisher)
    return 0


if __name__ == '__main__':
    sys.exit(main())
