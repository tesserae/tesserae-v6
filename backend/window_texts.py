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


MAX_LINES = 120


def passage_lines(work, ref_start=None, ref_end=None, context=0,
                  cap=MAX_LINES):
    """The actual lines of a passage, each with its own reference.

    Returns {'lines': [{'ref', 'text'}], 'capped': bool, 'total': int} or an
    'error'. `capped` is honest rather than silent: a request for a whole book
    comes back as a bounded window that says it was bounded, in the same style
    as line_search's own cap, instead of a truncated payload that looks whole.

    `context` widens the window by that many lines on each side, which is what
    a reader wants when a machine-chosen window starts mid-sentence.
    """
    c = _conn()
    if c is None:
        return {'error': 'no passage text database', 'lines': []}
    base = _base_work(work)
    if not base:
        return {'error': 'work is required', 'lines': []}
    try:
        rows = c.execute(
            'SELECT ord, ref FROM lines WHERE work = ? ORDER BY ord',
            (base,)).fetchall()
        if not rows:
            return {'error': f'no text stored for work {work}', 'lines': []}
        at = {ref: o for o, ref in rows}
        lo, hi = rows[0][0], rows[-1][0]
        i = at.get(ref_start, lo) if ref_start else lo
        j = at.get(ref_end, i) if ref_end else i
        if ref_start and ref_start not in at:
            return {'error': f'reference {ref_start} not found in {work}',
                    'lines': []}
        if j < i:
            i, j = j, i
        i = max(lo, i - int(context or 0))
        j = min(hi, j + int(context or 0))
        total = j - i + 1
        capped = total > cap
        if capped:
            j = i + cap - 1
        out = c.execute(
            'SELECT ref, text FROM lines WHERE work = ? AND ord BETWEEN ? AND ? '
            'ORDER BY ord', (base, i, j)).fetchall()
    except sqlite3.Error as e:
        logger.error('[WINDOWTEXTS] %s', e)
        return {'error': str(e), 'lines': []}
    return {'lines': [{'ref': r, 'text': t} for r, t in out],
            'capped': capped, 'total': total, 'returned': len(out)}


def _base_work(work):
    """Strip .tess. Part files are their OWN works here and are NOT collapsed:
    "vergil.aeneid.part.6" has its own line numbering in the index, so folding
    it into "vergil.aeneid" would look up the wrong lines."""
    return str(work or '').strip().replace('.tess', '')


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
            # `marks` is a run of '?' separated by commas and nothing else, so
            # no value reaches the SQL text: the ids go in as bound parameters
            # on the next line. bandit cannot see that and flags any f-string
            # query (B608), so the reason is recorded rather than the warning
            # silenced repo-wide.
            marks = ','.join('?' * len(chunk))
            for wid, text in c.execute(
                    f'SELECT id, text FROM window_texts WHERE id IN ({marks})',  # nosec B608
                    chunk):
                out[wid] = text
    except sqlite3.Error as e:
        logger.error('[WINDOWTEXTS] %s', e)
        return out
    return out


def language_of(work):
    """The language a work is indexed under, or None.

    Read from the window rows rather than guessed from the id: the work ids
    carry no language and the corpus spans three checkouts.
    """
    c = _conn()
    if c is None:
        return None
    try:
        r = c.execute('SELECT language FROM window_texts WHERE work = ? LIMIT 1',
                      (_base_work(work),)).fetchone()
    except sqlite3.Error:
        return None
    return r[0] if r else None
