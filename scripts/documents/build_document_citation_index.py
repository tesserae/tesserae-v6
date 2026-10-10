#!/usr/bin/env python3
"""Build data/citation_index/document_citations.db: which journal articles and
commentary notes cite which inscription, papyrus, ostracon or coin.

Input
  --articles-db  the literary citation index (citations.db): its `articles`
                 table gives each article's journal, year, title, authors,
                 first page and JSTOR address.
  --raw-dir      one OCR text file per article, <ia_id>_djvu.txt, pages
                 separated by form feeds (the Early Journal Content files).
  --commentaries directory of commentary json files (units with ref/text).
  --metadata-db  documents metadata.db (opened read-only) whose
                 principal_edition column is what a citation is linked to.

Every sentence is run through backend.document_citations, each recognised
reference is linked to document ids with DocumentEditionIndex, and one row is
written per (citing sentence, document). A reference that matches no document
edition is not stored.

    ~/bin/tess-job --fg doc-cit-index 4 python scripts/documents/build_document_citation_index.py
"""
import argparse
import json
import os
import re
import sqlite3
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from backend.citations import extract_documents  # noqa: E402
from backend.document_citations import DocumentEditionIndex  # noqa: E402

DEFAULT_OUT = os.path.join(ROOT, 'data', 'citation_index', 'document_citations.db')
EXCLUDED_TITLES = {'back matter', 'front matter'}
EXTRACTOR_VERSION = '2026-10-09-doc-citations-v1'
CONTEXT = 400          # characters kept either side of the reference
MAX_DOCS_PER_HIT = 3   # a reference matching more documents than this is too ambiguous to attribute

SCHEMA = """
CREATE TABLE citations (
  id INTEGER PRIMARY KEY,
  doc_id TEXT NOT NULL,
  family_key TEXT NOT NULL,
  surface TEXT,
  source TEXT NOT NULL,           -- 'ejc' or 'commentary'
  article_id INTEGER,             -- articles.id in citations.db (ejc only)
  jstor_id TEXT,
  journal TEXT,
  year INTEGER,
  title TEXT,
  authors TEXT,
  page INTEGER,
  commentary_file TEXT,           -- commentary only
  commentary_ref TEXT,
  sentence TEXT,
  n_docs INTEGER                  -- documents this one reference matched
);
CREATE INDEX idx_doccit_doc ON citations(doc_id);
CREATE INDEX idx_doccit_article ON citations(article_id);
CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT);
"""

# ------------------------------------------------------------- sentences
# Same approach as the literary index's sentences.py: a full stop followed by
# a capital is a boundary unless the word before it is an abbreviation or a
# single letter. Document abbreviations are added to the stoplist so that
# "CIL. VI" or "Inscr. Gr." is not cut.
_BOUNDARY_RE = re.compile(r'[.!?]+(?=\s+["\'(‘“]?[A-Z])')
_PRECEDING_WORD_RE = re.compile(r'([A-Za-z]+)$')
_NO_SPLIT = {
    'p', 'pp', 'v', 'vv', 'l', 'll', 'n', 'nn', 'ch', 'no', 'vol', 'ed', 'cf', 'sec', 'col', 'f', 'ff',
    's', 'sq', 'sqq', 'etc', 'cit', 'op', 'ibid', 'art', 'fr', 'cod', 'ms', 'mss', 'tr', 'cap', 'cc', 'vs',
    'esp', 'resp', 'diss', 'repr', 'rev', 'trans', 'i', 'ii', 'iii', 'iv', 'vi', 'vii', 'viii', 'ix', 'x',
    'xi', 'xii', 'xiii', 'xiv', 'xv', 'xvi', 'xvii', 'xviii', 'xix', 'xx',
    'cil', 'ils', 'ae', 'ig', 'seg', 'illrp', 'cle', 'rib', 'cig', 'syll', 'inscr', 'gr', 'lat', 'ep', 'eph',
    'epigr', 'bull', 'corr', 'hell', 'ric', 'rrc', 'bmc', 'rpc', 'ostr', 'pap', 'pbm', 'poxy', 'oxy',
    'dessau', 'orelli', 'henzen', 'wilm', 'kaibel', 'bücheler', 'mommsen', 'hübner', 'dittenberger',
}
_DIGIT_RE = re.compile(r'\d')


def split_sentences(text):
    """Yield (offset, sentence) spans of `text`; offsets index into it."""
    bounds = [0]
    for m in _BOUNDARY_RE.finditer(text):
        pre = text[max(0, m.start() - 20):m.start()]
        w = _PRECEDING_WORD_RE.search(pre)
        word = w.group(1).lower() if w else ''
        if word and (word in _NO_SPLIT or len(word) == 1):
            continue
        bounds.append(m.end())
    bounds.append(len(text))
    for s, e in zip(bounds, bounds[1:]):
        if s < e:
            yield s, text[s:e]


def _clip(sentence, start, end):
    """The sentence, cut to CONTEXT characters either side of the reference."""
    s = re.sub(r'\s+', ' ', sentence[:start]).lstrip()
    mid = re.sub(r'\s+', ' ', sentence[start:end])
    t = re.sub(r'\s+', ' ', sentence[end:]).rstrip()
    if len(s) > CONTEXT:
        s = '…' + s[-CONTEXT:]
    if len(t) > CONTEXT:
        t = t[:CONTEXT] + '…'
    return (s + (' ' if s and not s.endswith(' ') and not mid.startswith(' ') else '') + mid + t).strip()


def hits_in(text, edition_index):
    """(offset, sentence, citation) for every linked reference in `text`."""
    for off, sent in split_sentences(text):
        if not _DIGIT_RE.search(sent):
            continue
        for c in extract_documents(sent, edition_index):
            yield off, sent, c


def _insert(conn, rows):
    conn.executemany(
        'INSERT INTO citations (doc_id, family_key, surface, source, article_id, jstor_id, journal, year, '
        'title, authors, page, commentary_file, commentary_ref, sentence, n_docs) '
        'VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)', rows)


def key_of(c):
    from backend.document_citations import make_key
    return make_key(c)


def index_articles(conn, edition_index, articles_db, raw_dir, stats, limit=None):
    src = sqlite3.connect('file:%s?mode=ro' % articles_db, uri=True)
    arts = src.execute("SELECT id, ia_id, jstor_id, journal, title, authors, year, first_page FROM articles "
                       "WHERE status='ok' ORDER BY id").fetchall()
    src.close()
    t0 = time.time()
    for n, (aid, ia_id, jstor_id, journal, title, authors, year, first_page) in enumerate(arts):
        if limit and n >= limit:
            break
        if (title or '').strip().lower() in EXCLUDED_TITLES:
            stats['skipped_matter'] += 1
            continue
        path = os.path.join(raw_dir, '%s_djvu.txt' % ia_id)
        if not os.path.exists(path):
            stats['missing_raw'] += 1
            continue
        with open(path, encoding='utf-8', errors='replace') as fh:
            text = fh.read()
        stats['articles_read'] += 1
        seen, rows = set(), []
        for pidx, page in enumerate(text.split('\x0c')):
            page_num = (first_page + pidx) if first_page else pidx
            for _off, sent, c in hits_in(page, edition_index):
                ids = c.get('doc_ids') or []
                if not ids:
                    stats['unlinked'] += 1
                    continue
                if len(ids) > MAX_DOCS_PER_HIT:
                    stats['too_ambiguous'] += 1
                    continue
                clipped = _clip(sent, c['start'], c['end'])
                for d in ids:
                    k = (d, clipped)
                    if k in seen:
                        continue
                    seen.add(k)
                    rows.append((d, key_of(c), c['surface'], 'ejc', aid, jstor_id, journal, year, title, authors,
                                 page_num, None, None, clipped, len(ids)))
        if rows:
            stats['articles_citing'] += 1
            _insert(conn, rows)
        if (n + 1) % 1000 == 0:
            conn.commit()
            print('[%d/%d] rows so far %d (%.0fs)' % (n + 1, len(arts), conn.execute(
                'SELECT COUNT(*) FROM citations').fetchone()[0], time.time() - t0), flush=True)


def index_commentaries(conn, edition_index, directory, stats):
    if not directory or not os.path.isdir(directory):
        return
    for fn in sorted(os.listdir(directory)):
        if not fn.endswith('.json'):
            continue
        try:
            with open(os.path.join(directory, fn), encoding='utf-8') as fh:
                doc = json.load(fh)
        except (OSError, ValueError):
            stats['commentary_unreadable'] += 1
            continue
        stats['commentary_files'] += 1
        title = doc.get('title') or fn
        who = doc.get('commentator')
        seen, rows = set(), []
        for u in doc.get('units') or []:
            for _off, sent, c in hits_in(u.get('text') or '', edition_index):
                ids = c.get('doc_ids') or []
                if not ids:
                    stats['unlinked'] += 1
                    continue
                if len(ids) > MAX_DOCS_PER_HIT:
                    stats['too_ambiguous'] += 1
                    continue
                clipped = _clip(sent, c['start'], c['end'])
                for d in ids:
                    if (d, clipped) in seen:
                        continue
                    seen.add((d, clipped))
                    rows.append((d, key_of(c), c['surface'], 'commentary', None, None, None, None, title, who,
                                 None, fn, u.get('ref'), clipped, len(ids)))
        if rows:
            _insert(conn, rows)


def build(out, metadata_db, articles_db, raw_dir, commentaries, limit=None):
    if os.path.exists(out):
        raise SystemExit('refusing to overwrite %s' % out)
    t0 = time.time()
    edition_index = DocumentEditionIndex.from_metadata_db(metadata_db)
    print('edition index: %d documents, %d with an edition (%.0fs)' % (
        edition_index.n_docs, edition_index.n_with_edition, time.time() - t0), flush=True)
    tmp = out + '.partial'
    if os.path.exists(tmp):
        os.remove(tmp)
    conn = sqlite3.connect(tmp)
    conn.executescript(SCHEMA)
    stats = dict(articles_read=0, articles_citing=0, skipped_matter=0, missing_raw=0, unlinked=0,
                 too_ambiguous=0, commentary_files=0, commentary_unreadable=0)
    if articles_db and raw_dir:
        index_articles(conn, edition_index, articles_db, raw_dir, stats, limit)
    index_commentaries(conn, edition_index, commentaries, stats)
    conn.commit()
    n, nd, na = conn.execute('SELECT COUNT(*), COUNT(DISTINCT doc_id), COUNT(DISTINCT article_id) FROM citations').fetchone()
    meta = dict(stats, extractor_version=EXTRACTOR_VERSION, build_date=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                rows=n, distinct_documents=nd, distinct_articles=na, metadata_db=metadata_db, articles_db=articles_db or '',
                max_docs_per_hit=MAX_DOCS_PER_HIT, seconds=round(time.time() - t0))
    conn.executemany('INSERT INTO meta VALUES (?,?)', [(k, str(v)) for k, v in meta.items()])
    conn.commit()
    conn.execute('VACUUM')
    conn.close()
    os.replace(tmp, out)
    print('DONE', json.dumps(meta), flush=True)
    return meta


def main():
    ejc = os.path.expanduser('~/tesserae-backups/ejc_index_2026-09-14')
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--out', default=DEFAULT_OUT)
    ap.add_argument('--metadata-db', default='/var/www/tesseraev6_flask/data/documents/metadata.db')
    ap.add_argument('--articles-db', default='/var/www/tesseraev6_flask/data/citation_index/citations.db')
    ap.add_argument('--raw-dir', default=os.path.join(ejc, 'raw'))
    ap.add_argument('--commentaries', default='/var/www/tesseraev6_flask/data/commentaries')
    ap.add_argument('--limit', type=int, default=None, help='only the first N articles (trial runs)')
    a = ap.parse_args()
    build(a.out, a.metadata_db, a.articles_db, a.raw_dir, a.commentaries, a.limit)


if __name__ == '__main__':
    main()
