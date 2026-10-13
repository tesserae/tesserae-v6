#!/usr/bin/env python3
"""Article and book lists for the licensed journal text project.

Builds, from Crossref's public metadata only, the lists of works for

  muse      American Journal of Philology, Transactions of the American
            Philological Association, The Classical Journal, Arethusa
            (the Project MUSE records in Crossref)
  degruyter Philologus, Mnemosyne, and the classics monograph series of
            De Gruyter Brill

and compares a list with the JSTOR list of 2026-10-09 so that the same
article is not fetched twice.

    licensed_lists.py build --publisher muse|degruyter --out DIR
    licensed_lists.py overlap --dir DIR --jstor CSV

Only api.crossref.org is called, with a mailto parameter, at most one
request a second. No publisher host is contacted.
"""
import argparse
import csv
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

CONTACT = os.environ.get('TESSERAE_CONTACT_EMAIL', 'ncoffee@buffalo.edu')
UA = f'Tesserae V6 licensed-lists (https://tesserae.caset.buffalo.edu; mailto:{CONTACT})'
API = 'https://api.crossref.org'
MIN_INTERVAL = 1.0

# Journals by publisher. ISSNs are those of the publisher's own record in
# Crossref's journal index (checked 2026-10-13); the JSTOR records of the same
# journals are different Crossref records and are the JSTOR list's business.
JOURNALS = {
    'muse': [
        ('American Journal of Philology', ['1086-3168']),
        ('Transactions of the American Philological Association', ['1533-0699']),
        ('Classical Journal', ['2327-5812']),
        ('Arethusa', ['1080-6504']),
    ],
    'degruyter': [
        ('Philologus', ['0031-7985', '2196-7008']),
        ('Mnemosyne', ['0026-7074', '1568-525X']),
    ],
}

# De Gruyter Brill book prefixes and the series-name patterns of the spec.
BOOK_PREFIXES = ['10.1515', '10.1163']
SERIES_TERMS = ['classic', 'antiquity', 'Mnemosyne Supplements',
                'Philologus Supplements', 'Beiträge zur Altertumskunde']
SERIES_RE = re.compile(
    r'classic|antiquit|antik|altertum|mnemosyne|philologus|graecor|teubner', re.I)
SERIES_EXCLUDE_RE = re.compile(r'german|iberoroman|romanisch', re.I)
BOOK_TYPES = ['monograph', 'edited-book', 'book', 'book-series']
MAX_PAGES_PER_QUERY = 5

COLUMNS = ['doi', 'journal', 'year', 'volume', 'issue', 'pages', 'title',
           'first_author', 'authors', 'landing_url', 'resource_url', 'issn',
           'licence', 'tdm_links']
BOOK_COLUMNS = ['doi', 'series', 'year', 'title', 'first_author', 'authors',
                'isbn', 'type', 'landing_url', 'resource_url', 'licence',
                'tdm_links']

SELECT = ('DOI,title,author,editor,issued,published,volume,issue,page,ISSN,'
          'container-title,resource,license,link,type,ISBN')

_last = [0.0]


def get_json(path, params, fetch=None):
    """One polite Crossref request. `fetch` is replaced in tests."""
    params = dict(params)
    params['mailto'] = CONTACT
    url = f'{API}{path}?{urllib.parse.urlencode(params)}'
    if fetch is not None:
        return fetch(url)
    wait = MIN_INTERVAL - (time.monotonic() - _last[0])
    if wait > 0:
        time.sleep(wait)
    req = urllib.request.Request(url, headers={'User-Agent': UA})
    last_err = None
    for attempt in range(4):
        try:
            _last[0] = time.monotonic()
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.load(r)
        except Exception as e:  # network or 5xx: back off, retry
            last_err = e
            time.sleep(5 * (attempt + 1))
    raise RuntimeError(f'Crossref request failed: {url}: {last_err}')


def _year(item):
    for k in ('issued', 'published', 'published-print', 'published-online'):
        parts = (item.get(k) or {}).get('date-parts') or [[None]]
        if parts and parts[0] and parts[0][0]:
            return parts[0][0]
    return ''


def _people(item):
    people = item.get('author') or item.get('editor') or []
    names = []
    for p in people:
        fam, giv = p.get('family', ''), p.get('given', '')
        names.append(f'{fam}, {giv}'.strip(', ') if fam else p.get('name', ''))
    return names


def _licence(item):
    return ' | '.join(
        f"{x.get('URL', '')} [{x.get('content-version', '')}"
        f"{' from ' + str(x['start']['date-time'])[:10] if x.get('start') else ''}]"
        for x in item.get('license') or [])


def _tdm(item):
    return ' | '.join(
        f"{x.get('URL', '')} [{x.get('content-type', '')};"
        f"{x.get('intended-application', '')}]"
        for x in item.get('link') or [])


def article_row(item, journal):
    names = _people(item)
    doi = item['DOI']
    return {
        'doi': doi,
        'journal': journal,
        'year': _year(item),
        'volume': item.get('volume', ''),
        'issue': item.get('issue', ''),
        'pages': item.get('page', ''),
        'title': re.sub(r'\s+', ' ', (item.get('title') or [''])[0]).strip(),
        'first_author': names[0] if names else '',
        'authors': '; '.join(names),
        'landing_url': f'https://doi.org/{doi}',
        'resource_url': ((item.get('resource') or {}).get('primary') or {}).get('URL', ''),
        'issn': ' '.join(item.get('ISSN') or []),
        'licence': _licence(item),
        'tdm_links': _tdm(item),
    }


def book_row(item, series):
    names = _people(item)
    doi = item['DOI']
    return {
        'doi': doi,
        'series': series,
        'year': _year(item),
        'title': re.sub(r'\s+', ' ', (item.get('title') or [''])[0]).strip(),
        'first_author': names[0] if names else '',
        'authors': '; '.join(names),
        'isbn': ' '.join(item.get('ISBN') or []),
        'type': item.get('type', ''),
        'landing_url': f'https://doi.org/{doi}',
        'resource_url': ((item.get('resource') or {}).get('primary') or {}).get('URL', ''),
        'licence': _licence(item),
        'tdm_links': _tdm(item),
    }


def cursor_works(path, params, fetch=None, max_pages=None, log=print):
    """Yield every item of a cursor-paged Crossref works query."""
    cursor = '*'
    pages = 0
    while True:
        p = dict(params, rows=1000, cursor=cursor)
        d = get_json(path, p, fetch)['message']
        items = d.get('items') or []
        for it in items:
            yield it
        pages += 1
        if not items or len(items) < 1000 or (max_pages and pages >= max_pages):
            return
        cursor = d['next-cursor']
        log(f'  page {pages}, {pages * 1000} of {d.get("total-results")}')


def build_journals(publisher, out, fetch=None, log=print):
    summary = []
    for name, issns in JOURNALS[publisher]:
        rows, seen = [], set()
        for issn in issns:
            for it in cursor_works(f'/journals/{issn}/works',
                                   {'select': SELECT}, fetch, log=log):
                if it['DOI'] in seen:
                    continue
                seen.add(it['DOI'])
                rows.append(article_row(it, name))
        rows.sort(key=lambda r: (str(r['year']), r['volume'], r['issue'], r['pages']))
        slug = re.sub(r'[^a-z0-9]+', '_', name.lower()).strip('_')
        path = os.path.join(out, f'{publisher}_{slug}.csv')
        with open(path, 'w', newline='', encoding='utf-8') as f:
            w = csv.DictWriter(f, COLUMNS)
            w.writeheader()
            w.writerows(rows)
        years = [int(r['year']) for r in rows if str(r['year']).isdigit()]
        summary.append({'journal': name, 'issn': ' '.join(issns),
                        'first_year': min(years) if years else '',
                        'last_year': max(years) if years else '',
                        'count': len(rows), 'file': os.path.basename(path)})
        log(f'{name}: {len(rows)} works')
    return summary


def build_books(out, fetch=None, log=print):
    """Books of De Gruyter Brill whose series name matches the spec's terms.

    Crossref carries a series name only in container-title, and only for some
    records. A first pass finds the container titles that match; a second
    lists every book under each found title.
    """
    found = {}  # (prefix, series title) -> n seen in first pass
    for prefix in BOOK_PREFIXES:
        for term in SERIES_TERMS:
            for typ in BOOK_TYPES:
                params = {'query.container-title': term, 'select': SELECT,
                          'filter': f'prefix:{prefix},type:{typ}'}
                for it in cursor_works('/works', params, fetch,
                                       max_pages=MAX_PAGES_PER_QUERY, log=log):
                    for ct in it.get('container-title') or []:
                        if SERIES_RE.search(ct) and not SERIES_EXCLUDE_RE.search(ct):
                            found[(prefix, ct)] = found.get((prefix, ct), 0) + 1
        # Series records themselves
        params = {'select': SELECT, 'filter': f'prefix:{prefix},type:book-series'}
        for it in cursor_works('/works', params, fetch,
                               max_pages=MAX_PAGES_PER_QUERY, log=log):
            t = (it.get('title') or [''])[0]
            if SERIES_RE.search(t) and not SERIES_EXCLUDE_RE.search(t):
                found.setdefault((prefix, t), 0)
    rows, seen, per_series = [], set(), {}
    for (prefix, series) in sorted(found):
        for typ in BOOK_TYPES:
            params = {'query.container-title': series, 'select': SELECT,
                      'filter': f'prefix:{prefix},type:{typ}'}
            for it in cursor_works('/works', params, fetch,
                                   max_pages=MAX_PAGES_PER_QUERY, log=log):
                if series not in (it.get('container-title') or []):
                    continue
                if it['DOI'] in seen:
                    continue
                seen.add(it['DOI'])
                rows.append(book_row(it, series))
                per_series[(prefix, series)] = per_series.get((prefix, series), 0) + 1
    rows.sort(key=lambda r: (r['series'], str(r['year']), r['title']))
    path = os.path.join(out, 'degruyter_classics_monographs.csv')
    with open(path, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, BOOK_COLUMNS)
        w.writeheader()
        w.writerows(rows)
    log(f'monograph series: {len(per_series)}, books: {len(rows)}')
    return [{'prefix': p, 'series': s, 'books': n}
            for (p, s), n in sorted(per_series.items())], len(rows)


def write_summary(out, journals, series=None, nbooks=None):
    path = os.path.join(out, 'summary.csv')
    with open(path, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['kind', 'name', 'issn_or_prefix', 'first_year', 'last_year', 'count'])
        for j in journals:
            w.writerow(['journal', j['journal'], j['issn'], j['first_year'],
                        j['last_year'], j['count']])
        for s in series or []:
            w.writerow(['series', s['series'], s['prefix'], '', '', s['books']])
    return path


def key_of(year, volume, pages, first_author):
    start = re.split(r'[-–]', str(pages or ''))[0].strip()
    fam = re.sub(r'[^a-z]', '', (first_author or '').split(',')[0].lower())
    return (str(year), str(volume or '').strip(), start, fam)


def overlap(directory, jstor_csv):
    """Overlap of each list in `directory` with the JSTOR list.

    By DOI, and by (year, volume, first page, first author's family name),
    the second because the same article carries a different DOI at each
    publisher.
    """
    jdoi, jkey = set(), set()
    with open(jstor_csv, newline='', encoding='utf-8') as f:
        for r in csv.DictReader(f):
            jdoi.add(r['doi'].lower())
            jkey.add(key_of(r['year'], r['volume'], r['pages'], r['first_author']))
    result = []
    for fn in sorted(os.listdir(directory)):
        if not fn.endswith('.csv') or fn in ('summary.csv',) or 'monograph' in fn:
            continue
        n = by_doi = by_key = 0
        with open(os.path.join(directory, fn), newline='', encoding='utf-8') as f:
            for r in csv.DictReader(f):
                n += 1
                by_doi += r['doi'].lower() in jdoi
                by_key += key_of(r['year'], r['volume'], r['pages'],
                                 r['first_author']) in jkey
        result.append({'file': fn, 'count': n, 'same_doi': by_doi,
                       'same_year_volume_page_author': by_key})
    return result


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    sub = ap.add_subparsers(dest='cmd', required=True)
    b = sub.add_parser('build')
    b.add_argument('--publisher', choices=['muse', 'degruyter'], required=True)
    b.add_argument('--out', required=True)
    o = sub.add_parser('overlap')
    o.add_argument('--dir', required=True)
    o.add_argument('--jstor', required=True)
    a = ap.parse_args(argv)
    if a.cmd == 'build':
        os.makedirs(a.out, exist_ok=True)
        journals = build_journals(a.publisher, a.out)
        series = nbooks = None
        if a.publisher == 'degruyter':
            series, nbooks = build_books(a.out)
        print(write_summary(a.out, journals, series, nbooks))
    else:
        print(json.dumps(overlap(a.dir, a.jstor), indent=1))
    return 0


if __name__ == '__main__':
    sys.exit(main())
