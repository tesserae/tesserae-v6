"""Live counts for the scope box on each search page.

    GET /api/scope
        { texts: {code: works}, documents: {code: n}, passage_windows: n|null,
          events: n|null, coins: n|null, objects: n|null,
          scholarship_windows: n|null }

`texts` counts the works for every language this server serves (the same list
/api/languages answers, through backend/assistant/site_facts.py). Each other
count is null when its collection is not installed, using the same presence
checks site_facts makes. The answer is cached in the process for ten minutes,
so the box costs a page view nothing.
"""
import json
import os
import sqlite3
import time

from flask import Blueprint, jsonify

from backend import scholarship_theme
from backend.assistant import site_facts
from backend.logging_config import get_logger

logger = get_logger('scope')
scope_bp = Blueprint('scope', __name__)

_TTL = 600
_cache = {'at': 0.0, 'data': None}

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _count_sql(path, sql):
    """One integer from a read-only SQLite file, or None when the file is
    absent or does not have the table."""
    if not path or not os.path.exists(path):
        return None
    try:
        c = sqlite3.connect(f'file:{path}?mode=ro', uri=True)
        try:
            return int(c.execute(sql).fetchone()[0])
        finally:
            c.close()
    except Exception:                                               # noqa: BLE001
        logger.warning('[SCOPE] count failed for %s', path, exc_info=True)
        return None


def _texts():
    out = {}
    for code, _label in site_facts.languages():
        d = os.path.join(_ROOT, 'texts', code)
        try:
            out[code] = sum(1 for f in os.listdir(d) if f.endswith('.tess'))
        except OSError:
            continue
    return out


def _documents():
    try:
        import backend.documents as docs
    except ImportError:
        return {}
    if not docs.enabled():
        return {}
    out = {}
    for lang in docs.SUPPORTED_LANGUAGES:
        if docs.is_index_available(lang):
            n = _count_sql(docs._index_db_path(lang), 'SELECT COUNT(*) FROM doc_meta')
            if n is not None:
                out[lang] = n
    return out


def _passage_windows():
    try:
        from backend import passage_index
        path = os.path.join(passage_index._DATA_DIR, 'ids.json')
        if not os.path.exists(path):
            return None
        with open(path, encoding='utf-8') as fh:
            return len(json.load(fh))
    except Exception:                                               # noqa: BLE001
        logger.warning('[SCOPE] passage count failed', exc_info=True)
        return None


def build():
    from backend.blueprints import events, objects
    coins_path = os.environ.get('TESSERAE_COINS_DB') or os.path.join(_ROOT, 'data', 'coins', 'coins.sqlite')
    return {
        'texts': _texts(),
        'documents': _documents(),
        'passage_windows': _passage_windows(),
        'events': _count_sql(events.db_path(), 'SELECT COUNT(*) FROM events'),
        'coins': _count_sql(coins_path, 'SELECT COUNT(*) FROM coins'),
        'objects': _count_sql(objects.db_path(), 'SELECT COUNT(*) FROM objects'),
        'scholarship_windows': scholarship_theme.count(),
    }


def reset_cache():
    _cache['at'] = 0.0
    _cache['data'] = None


@scope_bp.route('/scope')
def scope_counts():
    now = time.time()
    if _cache['data'] is None or now - _cache['at'] > _TTL:
        _cache['data'] = build()
        _cache['at'] = now
    return jsonify(_cache['data'])
