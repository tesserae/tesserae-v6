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


_CAP_TTL = 3600
_cap_cache = {'at': 0.0, 'data': None}


def reset_capabilities_cache():
    _cap_cache['at'] = 0.0
    _cap_cache['data'] = None


def _capabilities_inputs():
    """Languages, served cross-language pairs and held pairs, as /api/languages answers them."""
    from backend.blueprints import meta
    body = meta.api_languages().get_json()
    return body['languages'], body.get('crosslingual_pairs', []), body.get('crosslingual_held', [])


def _cap_file():
    return os.path.join(_ROOT, 'cache', 'language_capabilities.json')


def _read_cap_file(now):
    """The answer in cache/language_capabilities.json when it is under an hour old, else None."""
    try:
        with open(_cap_file(), encoding='utf-8') as fh:
            saved = json.load(fh)
        if now - float(saved['computed_epoch']) <= _CAP_TTL and saved.get('data'):
            return saved['data'], float(saved['computed_epoch'])
    except (OSError, ValueError, KeyError, TypeError):
        pass
    return None


def _write_cap_file(data, now):
    """Atomic write (a .tmp beside it, then a rename), mode 664. A failure only costs the next worker a recompute."""
    path = _cap_file()
    tmp = path + '.tmp'
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(tmp, 'w', encoding='utf-8') as fh:
            json.dump({'computed_epoch': now, 'data': data}, fh)
        os.chmod(tmp, 0o664)
        os.replace(tmp, path)
    except OSError:
        logger.warning('[SCOPE] could not write %s', path, exc_info=True)


@scope_bp.route('/scope/capabilities')
def scope_capabilities():
    """Which of twelve capabilities each served language has (backend/language_capabilities.py).
    Cached in the process for an hour and in cache/language_capabilities.json for an hour, so a
    recycled web worker reads the file instead of walking the stores again."""
    from backend import language_capabilities
    now = time.time()
    if _cap_cache['data'] is None or now - _cap_cache['at'] > _CAP_TTL:
        saved = _read_cap_file(now)
        if saved:
            _cap_cache['data'], _cap_cache['at'] = saved
        else:
            langs, pairs, held = _capabilities_inputs()
            data = language_capabilities.build(langs, pairs, held)
            data['computed_at'] = time.strftime('%Y-%m-%d', time.gmtime(now))
            _write_cap_file(data, now)
            _cap_cache['data'] = data
            _cap_cache['at'] = now
    return jsonify(_cap_cache['data'])
