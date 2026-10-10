"""Scholarship that cites one inscription, papyrus, ostracon or coin: the
citing sentences from data/citation_index/document_citations.db, built offline
by scripts/documents/build_document_citation_index.py.

Shown as citation, one excerpt and a link, never summarised (docs/DECISIONS.md,
licensed scholarship policy). A missing index file means an empty section.
"""
import os
import re
import sqlite3

from backend.logging_config import get_logger

logger = get_logger(__name__)

DOCUMENT_CITATIONS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                  'data', 'citation_index', 'document_citations.db')
EXCERPT_CHARS = 420
MAX_RESULTS = 100


def _excerpt(sentence, surface):
    """One sentence-sized excerpt, cut around the reference when long."""
    s = re.sub(r'\s+', ' ', sentence or '').strip()
    if len(s) <= EXCERPT_CHARS:
        return s
    i = s.find(re.sub(r'\s+', ' ', surface or '').strip()) if surface else -1
    if i < 0:
        return s[:EXCERPT_CHARS].rstrip() + '…'
    lo = max(0, i - EXCERPT_CHARS // 2)
    hi = min(len(s), lo + EXCERPT_CHARS)
    return ('…' if lo else '') + s[lo:hi].strip() + ('…' if hi < len(s) else '')


def _citation_line(r):
    authors = [a for a in (r['authors'] or '').split('; ') if a]
    who = ', '.join(authors[:3]) + (' and others' if len(authors) > 3 else '') if authors else ''
    if r['source'] == 'commentary':
        return '%s, %s' % (who, r['title']) if who and r['title'] else (r['title'] or who or '')
    head = '%s%s' % (who or 'Unknown author', ' (%s)' % r['year'] if r['year'] else '')
    tail = ', '.join(x for x in (r['title'], r['journal'], 'p. %s' % r['page'] if r['page'] else None) if x)
    return '%s. %s.' % (head, tail)


def scholarship_for(doc_id, path=None):
    """{'available', 'count', 'results': [...]} for one document id, newest first."""
    path = path or DOCUMENT_CITATIONS
    if not os.path.exists(path):
        return {'available': False, 'count': 0, 'results': []}
    try:
        con = sqlite3.connect('file:%s?mode=ro' % path, uri=True)
        con.row_factory = sqlite3.Row
        rows = con.execute(
            'SELECT source, surface, jstor_id, journal, year, title, authors, page, commentary_file, '
            'commentary_ref, sentence FROM citations WHERE doc_id = ? '
            'ORDER BY year IS NULL, year DESC, title, page LIMIT ?', (doc_id, MAX_RESULTS)).fetchall()
        con.close()
    except sqlite3.Error as e:
        logger.warning('document citation index unreadable: %s', e)
        return {'available': False, 'count': 0, 'results': []}
    out = []
    for r in rows:
        item = {
            'source': r['source'],
            'citation': _citation_line(r),
            'title': r['title'], 'journal': r['journal'], 'year': r['year'], 'page': r['page'],
            'cites': r['surface'],
            'excerpt': _excerpt(r['sentence'], r['surface']),
        }
        if r['source'] == 'ejc' and r['jstor_id']:
            item['url'] = 'https://www.jstor.org/stable/%s' % r['jstor_id']
        elif r['source'] == 'commentary':
            item['commentary_file'] = r['commentary_file']
            item['commentary_ref'] = r['commentary_ref']
        out.append(item)
    return {'available': True, 'count': len(out), 'results': out}
