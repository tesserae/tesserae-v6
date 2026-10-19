#!/usr/bin/env python3
"""Tie each scholarship article on an event page to the passage that brings it in.

  relink_scholarship.py INPUT.sqlite OUTPUT.sqlite [--citation-index PATH] [--extra-index PATH]

The loader that wrote `scholarship` dropped the link between an article and the
passage it cites. This rebuilds the table with two more columns, passage_rank
and passage_ref. For every event it asks the citation index, through
backend.scholarship (the lookup behind the Reader's Scholarship tab), which
articles cite each passage with rank <= 10 or llm_label = 'yes'. One row per
(event, article, passage). Commentary rows are kept, with the lowest-ranked
passage whose range holds the commentary's reference, else rank NULL.

The citation indexes are opened read-only. Default: the production EJC file
/var/www/tesseraev6_flask/data/citation_index/citations.db and, when it exists
beside it, the Project MUSE file citations_muse.db (--extra-index PATH names
another, --extra-index '' reads the EJC file alone). The backend reads the MUSE
index only through the environment variable TESSERAE_CITATIONS_EXTRA, which this
script sets before it asks, so one run joins both. The summary prints how many
distinct articles, and how many rows, come from each index.

Each row also carries `scope`. 'passage' is an article that cites one of the event's
leading passages itself (as before). 'span' is an article that cites anywhere within the
span the event's leading passages cover in a work, from the lowest to the highest locus
of those passages (per work and per citation abbreviation), at the book or chapter level
the citation index resolves. Such a row has no passage rank, and its passage_ref names
the span. An article already listed in the first group for the event is not repeated in
the second. Commentary rows have scope 'passage'. The module also
reads the texts' metadata from the repository it is run in (TESSERAE_ROOT is
not needed). Run from the repository root.
"""
import argparse
import os
import re
import shutil
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

DEFAULT_INDEX = '/var/www/tesseraev6_flask/data/citation_index/citations.db'
MAX_ARTICLES = 100000
EXTRA_NAME = 'citations_muse.db'


def default_extra(citation_index):
    p = os.path.join(os.path.dirname(os.path.abspath(citation_index)), EXTRA_NAME)
    return p if os.path.exists(p) else ''


def article_row(r):
    """(title, page_ref) in the form the loader wrote: authors, venue, year, page, then what it cites."""
    who = '; '.join(r.get('authors') or [])
    venue = r.get('venue') or ''
    year = r.get('year') or ''
    head = ' '.join(x for x in (who, venue, str(year)) if x)
    page = (r.get('pages') or [None])[0]
    if page not in (None, ''):
        head += f', p. {page}'
    cites = r.get('cites') or ''
    return r.get('title') or '', (head + ('; cites ' + cites if cites else '')).strip() or None


def _coords(ref):
    tail = re.search(r'(\d+(?:\.\d+)*)\s*$', ref or '')
    return tuple(int(x) for x in tail.group(1).split('.')) if tail else ()


def _prefix(ref):
    return re.sub(r'\s*\d+(?:\.\d+)*\s*$', '', (ref or '').strip().lower())


def commentary_passage(ref, passages):
    """The lowest-ranked passage (rank, ref_start, ref_end) whose range holds the commentary reference, or None."""
    pre, c = _prefix(ref), _coords(ref)
    if not c:
        return None
    for p in sorted(passages, key=lambda p: (p['rank'] is None, p['rank'])):
        if _prefix(p['ref_start']) != pre:
            continue
        lo, hi = _coords(p['ref_start']), _coords(p['ref_end'] or p['ref_start'])
        n = min(len(c), len(lo), len(hi))
        if n and lo[:n] <= c[:n] <= hi[:n]:
            return p
    return None


def span_of(plist):
    """[(work, lo_ref, hi_ref)] for each work and citation prefix among the passages
    (dicts with work, ref_start, ref_end), from the lowest start to the highest end.
    A group whose span is one passage, or has no numeric locus, is left out."""
    groups = {}
    for p in plist:
        if not _coords(p['ref_start']):
            continue
        groups.setdefault((p['work'], _prefix(p['ref_start'])), []).append(p)
    out = []
    for (work, _pre), ps in groups.items():
        if len(ps) < 2:
            continue
        lo = min(ps, key=lambda p: _coords(p['ref_start']))
        hi = max(ps, key=lambda p: _coords(p['ref_end'] or p['ref_start']))
        out.append((work, lo['ref_start'], hi['ref_end'] or hi['ref_start']))
    return out


def passage_ref(p):
    a, b = p['ref_start'], p['ref_end']
    if not b or b == a:
        return a
    pre = _prefix(a)
    if pre and _prefix(b) == pre:
        b = b[len(pre):].strip()
    return f'{a}-{b}'


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('input')
    ap.add_argument('output')
    ap.add_argument('--citation-index', default=DEFAULT_INDEX)
    ap.add_argument('--extra-index', default=None)
    a = ap.parse_args(argv)
    from backend import scholarship as S
    S.CITATION_INDEX = a.citation_index
    if not os.path.exists(S.CITATION_INDEX):
        sys.exit(f'citation index not found: {S.CITATION_INDEX}')
    extra = default_extra(a.citation_index) if a.extra_index is None else a.extra_index
    if extra and not os.path.exists(extra):
        sys.exit(f'extra citation index not found: {extra}')
    if extra:
        os.environ[S.CITATIONS_EXTRA_ENV] = extra
    else:
        os.environ.pop(S.CITATIONS_EXTRA_ENV, None)
    print(f'EJC index {S.CITATION_INDEX}; extra index {extra or "none"}')
    per_source = {}

    shutil.copyfile(a.input, a.output)
    c = sqlite3.connect(a.output)
    c.row_factory = sqlite3.Row
    before = c.execute('SELECT COUNT(*) FROM scholarship').fetchone()[0]
    old_commentary = c.execute("SELECT * FROM scholarship WHERE kind = 'commentary'").fetchall()
    c.executescript('''
        DROP TABLE scholarship;
        CREATE TABLE scholarship (event_id TEXT, kind TEXT, title TEXT, page_ref TEXT, url TEXT,
                                  passage_rank INTEGER, passage_ref TEXT, scope TEXT);
        CREATE INDEX scholarship_event ON scholarship(event_id);''')
    cache = {}
    n_article = 0
    n_span = 0

    def tally(r, title, scope):
        src = 'muse' if r.get('source') == 'muse' else 'ejc'
        d = per_source.setdefault((src, scope), {'rows': 0, 'articles': set()})
        d['rows'] += 1
        d['articles'].add((r.get('url') or '', title))
    events = [r[0] for r in c.execute('SELECT id FROM events')]
    for eid in events:
        first = set()
        plist = [dict(r) for r in c.execute(
            'SELECT rank, work, ref_start, ref_end FROM passages WHERE event_id = ? '
            "AND (rank <= 10 OR llm_label = 'yes') ORDER BY rank", (eid,))]
        for p in plist:
            key = (p['work'], p['ref_start'], p['ref_end'])
            if key not in cache:
                try:
                    pn = S.passage_names(p['work'], p['ref_start'], p['ref_end'])
                    cache[key] = S.citation_index(pn, limit=MAX_ARTICLES).get('results', [])
                except Exception as e:  # a passage the lookup cannot place has no articles
                    print(f'  {eid} {p["work"]} {p["ref_start"]}: {type(e).__name__}: {e}', file=sys.stderr)
                    cache[key] = []
            for r in cache[key]:
                title, page_ref = article_row(r)
                c.execute('INSERT INTO scholarship VALUES (?,?,?,?,?,?,?,?)',
                          (eid, 'article', title, page_ref, r.get('url'), p['rank'], passage_ref(p), 'passage'))
                n_article += 1
                first.add((r.get('url') or '', title))
                tally(r, title, 'passage')
        for work, lo, hi in span_of(plist):
            key = ('span', work, lo, hi)
            if key not in cache:
                try:
                    cache[key] = S.citation_index(S.passage_names(work, lo, hi), limit=MAX_ARTICLES).get('results', [])
                except Exception as e:
                    print(f'  {eid} span {work} {lo}-{hi}: {type(e).__name__}: {e}', file=sys.stderr)
                    cache[key] = []
            ref = passage_ref({'ref_start': lo, 'ref_end': hi})
            for r in cache[key]:
                title, page_ref = article_row(r)
                if (r.get('url') or '', title) in first:
                    continue
                first.add((r.get('url') or '', title))
                c.execute('INSERT INTO scholarship VALUES (?,?,?,?,?,?,?,?)',
                          (eid, 'article', title, page_ref, r.get('url'), None, ref, 'span'))
                n_span += 1
                tally(r, title, 'span')
    allp = {}
    for r in c.execute('SELECT event_id, rank, ref_start, ref_end FROM passages'):
        allp.setdefault(r['event_id'], []).append(dict(r))
    n_comm = 0
    for r in old_commentary:
        p = commentary_passage(r['page_ref'], allp.get(r['event_id'], []))
        c.execute('INSERT INTO scholarship VALUES (?,?,?,?,?,?,?,?)',
                  (r['event_id'], 'commentary', r['title'], r['page_ref'], r['url'],
                   p['rank'] if p else None, passage_ref(p) if p else None, 'passage'))
        n_comm += 1
    c.commit()
    after = c.execute('SELECT COUNT(*) FROM scholarship').fetchone()[0]
    print(f'scholarship rows before {before}, after {after} ({n_article} article, {n_span} article within the span, {n_comm} commentary)')
    for src in ('ejc', 'muse'):
        for scope in ('passage', 'span'):
            d = per_source.get((src, scope), {'rows': 0, 'articles': ()})
            print(f'  {src} {scope}: {len(d["articles"])} distinct articles, {d["rows"]} rows')
    with_sch = c.execute('SELECT COUNT(DISTINCT event_id) FROM scholarship').fetchone()[0]
    print(f'events with any scholarship row: {with_sch} of {len(events)}')
    rows = c.execute("SELECT kind, passage_rank, passage_ref, title FROM scholarship WHERE event_id = 'Q18001862' "
                     'ORDER BY passage_rank').fetchall()
    print(f'Q18001862 (Siege of Corfinium): {len(rows)} rows')
    for r in rows:
        print('  ', tuple(r))
    c.execute('VACUUM')
    c.close()


if __name__ == '__main__':
    main()
