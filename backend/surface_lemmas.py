"""Surface form to lemma lookup for the languages whose tagger does not run in
the web process (Persian, Urdu, Arabic).

Tables come from scripts/build_surface_lemma_tables.py, one pass over the lemma
caches: every surface form the tagger saw, with the lemma it gave it most
often. A typed query is looked up here after the language's own normalizer,
so "الديار" reaches the index entry for "دار". A form the table does not know
is searched as it is, which is what happened for every form before.
"""
import json
import os
import threading

from backend.logging_config import get_logger

logger = get_logger('surface_lemmas')

TABLE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                         'data', 'lemma_tables')
_tables = {}
_lock = threading.Lock()


def _load(language):
    path = os.path.join(TABLE_DIR, f'{language}_surface_lemmas.json')
    if not os.path.exists(path):
        return {}
    try:
        with open(path, encoding='utf-8') as fh:
            table = json.load(fh)
        logger.info('[SURFACE] %s: %d forms', language, len(table))
        return table
    except Exception:  # noqa: BLE001
        logger.warning('[SURFACE] %s table unreadable', language, exc_info=True)
        return {}


def lemma_for(form, language):
    """The lemma the tagger usually gave this normalized form, or None."""
    if not form:
        return None
    with _lock:
        if language not in _tables:
            _tables[language] = _load(language)
    return _tables[language].get(form)
