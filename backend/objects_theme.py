"""Objects for Theme Search: the logic behind /api/objects/theme.

The description of every kept object (title and the museum's catalogue text) is
encoded offline with the Theme Search encoder and stored as
data/objects/descriptions.npy (float16, L2-normalised) with descriptions_ids.json
beside the objects database, in the format of the coins vectors: a list in row
order, each {"text": the encoded text, "types": [object ids]}.

A query is encoded through the query encoder SERVICE (never in this process, as
in backend/coins_passage.py, whose encoder call, error class and ranking this
module reuses) and compared by cosine with those rows. The result is its own
list, never mixed into the passage ranking. With no vectors installed the route
says available=false. Nothing here loads a model.
"""
import json
import os
import threading
from collections import OrderedDict

from backend import coins_passage
from backend.coins_passage import EncoderUnavailable, rank  # noqa: F401  (re-exported)
from backend.logging_config import get_logger

logger = get_logger('objects_theme')

THEME_LABEL = ('Ranked by how close each museum description is in meaning to your words. '
               'These are the museums\' own catalogue texts, so a query that describes what '
               'an object shows or how it was used finds the most. The ranking has not been '
               'measured against known matches yet.')
SNIPPET_CHARS = 420

_lock = threading.Lock()
_vec = {'key': None, 'matrix': None, 'rows': None}


def load_vectors(db_path):
    """(float16 matrix, rows) or (None, None) when the vectors are not installed.
    Re-read when either file changes."""
    d = os.path.dirname(os.path.abspath(db_path))
    npy, ids = os.path.join(d, 'descriptions.npy'), os.path.join(d, 'descriptions_ids.json')
    if not (os.path.exists(npy) and os.path.exists(ids)):
        return None, None
    key = (npy, os.path.getmtime(npy), os.path.getmtime(ids))
    with _lock:
        if _vec['key'] != key:
            import numpy as np
            matrix = np.load(npy, mmap_mode='r')
            with open(ids, encoding='utf-8') as f:
                rows = json.load(f)
            if matrix.shape[0] != len(rows):
                logger.error('objects vectors out of step: %d vectors, %d rows', matrix.shape[0], len(rows))
                return None, None
            _vec.update(key=key, matrix=matrix, rows=rows)
        return _vec['matrix'], _vec['rows']


def snippet(text, n=SNIPPET_CHARS):
    t = ' '.join(str(text or '').split())
    if len(t) <= n:
        return t
    cut = t[:n].rsplit(' ', 1)[0]
    return cut + '...'


def card(conn, row, score):
    """One Theme Search card for a vector row: the object it came from and its score."""
    from backend.blueprints.objects import LIST_COLUMNS, _present
    oid = (row.get('types') or [None])[0]
    r = conn.execute(f'SELECT {LIST_COLUMNS} FROM objects WHERE id = ?', (oid,)).fetchone()  # nosec B608 -- fixed column list
    if r is None:
        return None
    d = _present(r)
    d['score'] = round(score, 4)
    d['snippet'] = snippet(r['description'])
    return d


def theme(conn, db_path, q, k=10):
    """The /api/objects/theme payload: the descriptions nearest the query."""
    matrix, rows = load_vectors(db_path)
    out = {'available': matrix is not None, 'query': q, 'results': [], 'label': THEME_LABEL}
    if matrix is None:
        out['reason'] = 'The object description vectors are not installed.'
        return out
    try:
        qvec = coins_passage.embed(q)
    except Exception as e:
        raise EncoderUnavailable(str(e)) from e
    cards = (card(conn, rows[i], s) for i, s in rank(matrix, qvec, k))
    out['results'] = [c for c in cards if c]
    return out
