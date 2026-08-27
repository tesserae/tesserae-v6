"""Read the source text of an indexed passage window.

The passage index holds descriptions and embeddings; this holds the passages
themselves. Built by `scripts/build_window_texts.py`, which explains why it has
to exist at all: Persian and Urdu are not in `texts/` in either the dev checkout
or production, so for a third of the index there is no other served route to
its own text.

Read-only, opened per thread. Apache runs three processes of five threads and
an sqlite3 connection cannot be shared across threads, so a module-level
connection would fail intermittently under load rather than cleanly at startup.
"""
import os
import sqlite3
import threading

from backend.logging_config import get_logger

logger = get_logger('window_texts')

DB = os.environ.get(
    'TESSERAE_WINDOW_TEXTS',
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                 'data', 'passage_index', 'window_texts.db'))

_local = threading.local()


def is_available():
    return os.path.exists(DB)


def _conn():
    c = getattr(_local, 'conn', None)
    if c is None:
        if not os.path.exists(DB):
            return None
        c = sqlite3.connect(f'file:{DB}?mode=ro', uri=True, check_same_thread=False)
        _local.conn = c
    return c


def texts_for(ids):
    """{window id: source text} for the ids that resolve. Missing ids are simply
    absent, so a caller can tell "no text" from "empty text"."""
    ids = [i for i in (ids or []) if i]
    if not ids:
        return {}
    c = _conn()
    if c is None:
        logger.warning('[WINDOWTEXTS] no database at %s', DB)
        return {}
    out = {}
    try:
        # Chunked: SQLite's default parameter limit is 999 and an export of a
        # few hundred results would otherwise fail only on the largest requests.
        for i in range(0, len(ids), 500):
            chunk = ids[i:i + 500]
            marks = ','.join('?' * len(chunk))
            for wid, text in c.execute(
                    f'SELECT id, text FROM window_texts WHERE id IN ({marks})',
                    chunk):
                out[wid] = text
    except sqlite3.Error as e:
        logger.error('[WINDOWTEXTS] %s', e)
        return out
    return out
