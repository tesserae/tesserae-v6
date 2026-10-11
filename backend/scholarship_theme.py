"""Theme Search over scholarship: the logic behind /api/scholarship/theme.

The commentary notes and journal sentences the Scholarship tab draws on are cut
into windows, encoded offline with the Theme Search encoder and packed by
scripts/scholarship/pack_scholarship_theme.py into data/scholarship_theme/
(or the folder named by TESSERAE_SCHOLARSHIP_THEME_DIR):

    embeddings.npy   float16 unit rows        ids.json   window ids, row order
    windows.jsonl    one window per line      windows_fts.db   FTS5 keyword index

A query is ranked two ways, by cosine against the vectors (the query is encoded
through the encoder SERVICE, never in this process, as in backend/coins_passage.py
whose encoder call, error class and ranking this module reuses) and by an FTS5
keyword search, and the two lists are merged by reciprocal rank fusion with
k = 60. The result is its own list, never mixed into the passage ranking. With no
files installed the route says available=false. Nothing here loads a model.
"""
import json
import os
import re
import sqlite3
import threading

from backend import coins_passage
from backend.coins_passage import EncoderUnavailable, rank  # noqa: F401  (re-exported)
from backend.logging_config import get_logger

logger = get_logger('scholarship_theme')

DEEP = 50              # depth of each list before fusion
RRF_K = 60
DEFAULT_K = 10
MAX_K = 30
SNIPPET_CHARS = 300
FILES = ('embeddings.npy', 'ids.json', 'windows.jsonl', 'windows_fts.db')
STOP = set('a an the of in on and or to for with as by at from is are was be its it their his her'.split())

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_lock = threading.Lock()
_state = {'key': None, 'matrix': None, 'ids': None, 'offsets': None}


def data_dir():
    return os.environ.get('TESSERAE_SCHOLARSHIP_THEME_DIR') or os.path.join(_ROOT, 'data', 'scholarship_theme')


def label(n):
    return (f'Ranked by a blend of meaning and keyword search over {n:,} commentary notes and article '
            'sentences. On fifteen test questions, thirteen had a strongly relevant note in the first ten.')


def installed(d=None):
    d = d or data_dir()
    return all(os.path.exists(os.path.join(d, f)) for f in FILES)


def _offsets(path):
    import numpy as np
    out, pos = [], 0
    with open(path, 'rb') as fh:
        for line in fh:
            out.append(pos)
            pos += len(line)
    return np.asarray(out, dtype=np.int64)


def load(d=None):
    """(float16 matrix, ids, line offsets) or (None, None, None) when the files are
    not installed or out of step. Re-read when any file changes."""
    d = d or data_dir()
    if not installed(d):
        return None, None, None
    paths = [os.path.join(d, f) for f in FILES]
    key = (d,) + tuple(os.path.getmtime(p) for p in paths)
    with _lock:
        if _state['key'] != key:
            import numpy as np
            matrix = np.load(paths[0], mmap_mode='r')
            with open(paths[1], encoding='utf-8') as fh:
                ids = json.load(fh)
            offsets = _offsets(paths[2])
            if not (matrix.shape[0] == len(ids) == len(offsets)):
                logger.error('scholarship theme files out of step: %d vectors, %d ids, %d windows',
                             matrix.shape[0], len(ids), len(offsets))
                _state.update(key=None, matrix=None, ids=None, offsets=None)
                return None, None, None
            _state.update(key=key, matrix=matrix, ids=ids, offsets=offsets)
        return _state['matrix'], _state['ids'], _state['offsets']


def count(d=None):
    """Number of windows installed, or None. Reads the array header only."""
    d = d or data_dir()
    p = os.path.join(d, 'embeddings.npy')
    if not installed(d):
        return None
    try:
        import numpy as np
        return int(np.load(p, mmap_mode='r').shape[0])
    except Exception:                                               # noqa: BLE001
        return None


def rrf(rank_lists, k=RRF_K):
    """Reciprocal rank fusion: score(d) = sum over lists of 1/(k + rank), rank from 1.
    Ties go to the document seen first (the meaning list is read first). Returns
    [(doc, score)] best first."""
    sc, first = {}, {}
    for lst in rank_lists:
        for r, d in enumerate(lst, 1):
            sc[d] = sc.get(d, 0.0) + 1.0 / (k + r)
            first.setdefault(d, len(first))
    return sorted(sc.items(), key=lambda kv: (-kv[1], first[kv[0]]))


def fts_query(q):
    """OR of the words of the query (stop words dropped), each quoted so that a
    word such as NEAR or NOT is read as a word and not as an FTS5 operator."""
    toks = [t for t in re.findall(r'\w+', q.lower()) if t not in STOP]
    return ' OR '.join(f'"{t}"' for t in dict.fromkeys(toks))


def keyword_rank(d, q, depth=DEEP):
    """Row numbers of the best keyword matches, best first (FTS5 bm25)."""
    match = fts_query(q)
    if not match:
        return []
    con = sqlite3.connect(f'file:{os.path.join(d, "windows_fts.db")}?mode=ro', uri=True)
    try:
        rows = con.execute('SELECT rowid FROM f WHERE f MATCH ? ORDER BY bm25(f) LIMIT ?', (match, depth)).fetchall()
    finally:
        con.close()
    return [r[0] for r in rows]


def snippet(text, n=SNIPPET_CHARS):
    t = ' '.join(str(text or '').split())
    if len(t) <= n:
        return t
    return t[:n].rstrip() + '...'


def reader_ref(ref):
    """The Reader's reference from a commentary reference such as 'verg. aen. 1.1'."""
    parts = str(ref or '').split()
    for tok in reversed(parts):
        if re.search(r'\d', tok):
            return tok.rstrip('.,;')
    return str(ref or '')


def reader_link(w):
    """A Reader path to the passage a commentary note is on, or None when the
    work's language is unknown."""
    if not w.get('work') or not w.get('work_language'):
        return None
    from urllib.parse import urlencode
    p = {'work': f"{w['work']}.tess", 'lang': w['work_language'], 'ref': reader_ref(w.get('ref_start'))}
    end = reader_ref(w.get('ref_end'))
    if end and end != p['ref']:
        p['refEnd'] = end
    return '/read?' + urlencode(p)


def read_window(d, offsets, row):
    with open(os.path.join(d, 'windows.jsonl'), 'rb') as fh:
        fh.seek(int(offsets[row]))
        return json.loads(fh.readline().decode('utf-8'))


def card(w, row, fused, dense_rank, kw_rank, position):
    article = w.get('source') == 'ejc'
    link = None
    if article and w.get('url'):
        link = {'kind': 'jstor', 'url': w['url']}
    elif not article:
        path = reader_link(w)
        if path:
            link = {'kind': 'reader', 'url': path}
    return {
        'id': w['id'], 'rank': position, 'score': round(fused, 5),
        'meaning_rank': dense_rank, 'keyword_rank': kw_rank,
        'kind': 'article' if article else 'commentary',
        'commentator': None if article else w.get('commentator'),
        'work': w.get('work') or None, 'ref_start': w.get('ref_start'), 'ref_end': w.get('ref_end'),
        'journal': w.get('journal') if article else None,
        'title': w.get('title') if article else None,
        'authors': w.get('authors') if article else None,
        'year': w.get('year') if article else None,
        'snippet': snippet(w.get('text')), 'link': link,
    }


def theme(q, k=DEFAULT_K, d=None):
    """The /api/scholarship/theme payload."""
    d = d or data_dir()
    k = min(max(int(k or DEFAULT_K), 1), MAX_K)
    matrix, ids, offsets = load(d)
    out = {'available': matrix is not None, 'query': q, 'results': []}
    if matrix is None:
        out['reason'] = 'The scholarship search files are not installed on this server.'
        return out
    out['label'] = label(len(ids))
    try:
        qvec = coins_passage.embed(q)
    except Exception as e:
        raise EncoderUnavailable(str(e)) from e
    dense = [i for i, _ in rank(matrix, qvec, DEEP)]
    kw = keyword_rank(d, q, DEEP)
    dense_pos = {r: p for p, r in enumerate(dense, 1)}
    kw_pos = {r: p for p, r in enumerate(kw, 1)}
    fused = rrf([dense, kw])[:k]
    out['results'] = [card(read_window(d, offsets, r), r, s, dense_pos.get(r), kw_pos.get(r), n)
                      for n, (r, s) in enumerate(fused, 1)]
    return out
