"""Shared helpers for the "Daylight" prototype (topics covered for one work and
not for comparable works), run on the JSTOR Early Journal Content citation
index the site already holds (29,055 articles, 1827 to 1922).

Production data is only read. Article text is read from the cached raw files
the index was built from; nothing read here is written into the repository.
"""
import os
import re
import sqlite3
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB = '/var/www/tesseraev6_flask/data/citation_index/citations.db'
RAW = os.path.expanduser('~/tesserae-backups/ejc_index_2026-09-14/raw')
OUT = os.path.expanduser('~/tesserae-backups/daylight_prototype_2026-10-13')
ENV = '/var/www/tesseraev6_flask/.env'
HOLDINGS = 'JSTOR Early Journal Content, 24 journals, 1827 to 1922 (29,055 articles)'

_BOILER_END = re.compile(r'contact\s+support@jstor\.org\.?', re.I)


def connect():
    return sqlite3.connect('file:%s?mode=ro' % DB, uri=True)


def load_gateway_env():
    """Put the gateway settings in the environment (never printed)."""
    for line in open(ENV, encoding='utf-8'):
        line = line.strip()
        if line.startswith('TESSERAE_LLM') and '=' in line:
            k, v = line.split('=', 1)
            os.environ[k] = v.strip().strip('"\'')
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)


def articles(con=None):
    con = con or connect()
    cols = ['id', 'ia_id', 'journal', 'title', 'authors', 'year']
    return [dict(zip(cols, r)) for r in con.execute(
        'select id, ia_id, journal, title, authors, year from articles order by id')]


def article_text(ia_id, words=1200):
    """The first `words` words of the article body, boilerplate removed."""
    try:
        raw = open(os.path.join(RAW, ia_id + '_djvu.txt'), encoding='utf-8',
                   errors='replace').read()
    except OSError:
        return ''
    m = _BOILER_END.search(raw[:6000])
    if m:
        raw = raw[m.end():]
    return ' '.join(raw.split()[:words])


def citing_sentences(con, article_id, n=6, chars=300):
    out = []
    for (s,) in con.execute('select sentence from citations where article_id=? order by page limit ?',
                            (article_id, n)):
        out.append(' '.join((s or '').split())[:chars])
    return out


def cited_works(con):
    """article id -> sorted list of cited work ids."""
    d = {}
    for a, w in con.execute('select distinct article_id, work_id from citations where work_id is not null'):
        d.setdefault(a, []).append(w)
    return {a: sorted(w) for a, w in d.items()}
