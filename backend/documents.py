"""Tesserae V6 — documents collection (stage 3b-2).

Lets the corpus-wide phrase search (backend/app.py's `/api/line-search`)
search the documentary corpus (inscriptions, papyri) built dark in stage
3b-1 (PR #678): `la_documents_index.db` / `grc_documents_index.db` (same
`texts`/`postings`/`lines` schema `scripts/build_inverted_index.py` builds
for literature, plus a `doc_meta(doc_id, text_id, first_ref, last_ref)`
table), joined against stage 3a's `metadata.db` (`documents` table) for
credit/date/place/labels, plus a per-bucket-file sidecar for restored-word
positions.

Everything here is OFF unless the caller checks `enabled()` first (reads
`TESSERAE_DOCUMENTS` per call, not memoized, so a running process picks up
the switch without a restart — the same pattern `backend.documents`'s
sibling env-gated features use). With the switch off, `backend/app.py`
never imports past `enabled()`, so a broken or absent documents index
cannot affect a literature-only request.

Paths (all overridable by env, for a worktree whose documents index lives
somewhere other than `data/inverted_index` — e.g. a different stage 3b-1
build):
    TESSERAE_DOCUMENTS_INDEX_DIR   default data/inverted_index
    TESSERAE_DOCUMENTS_META        default data/documents/metadata.db
    TESSERAE_DOCUMENTS_RESTORED_DIR default data/documents/restored/
        (mirrors write_document_tess.py's own output layout:
        <dir>/<language>/<bucket>.restored_words.jsonl)

Connections are lazy, read-only (immutable SQLite URIs — this process never
writes to a documents index) and held one per language for the life of the
process, the same pattern `backend/inverted_index.py` uses for the literary
indexes.
"""
from __future__ import annotations

import json
import os
import sqlite3
from functools import lru_cache

from backend.logging_config import get_logger

logger = get_logger('documents')


def _repo_root():
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _index_dir():
    return os.environ.get('TESSERAE_DOCUMENTS_INDEX_DIR') or os.path.join(
        _repo_root(), 'data', 'inverted_index')


def _metadata_db_path():
    return os.environ.get('TESSERAE_DOCUMENTS_META') or os.path.join(
        _repo_root(), 'data', 'documents', 'metadata.db')


def _sidecar_root():
    return os.environ.get('TESSERAE_DOCUMENTS_RESTORED_DIR') or os.path.join(
        _repo_root(), 'data', 'documents', 'restored')


# Languages the stage 3b-1 build produced an index for. Any other language
# simply has no documents index; callers check `is_index_available` rather
# than hardcoding this list, but it is also the set `backend/app.py` offers
# the documents/both collection for.
SUPPORTED_LANGUAGES = ('la', 'grc')


def enabled():
    """Read TESSERAE_DOCUMENTS per call (not memoized at import time), so a
    long-running dev/preview process picks up the switch without a restart."""
    return os.environ.get('TESSERAE_DOCUMENTS') == '1'


# --------------------------------------------------------------------------
# Index connections (texts / postings / lines / doc_meta)
# --------------------------------------------------------------------------

_connections = {}


def _index_db_path(language):
    return os.path.join(_index_dir(), f'{language}_documents_index.db')


def is_index_available(language):
    return os.path.exists(_index_db_path(language))


def get_connection(language):
    """Lazy read-only connection to <language>_documents_index.db. Returns
    None (not an exception) when the file is absent, matching
    `backend.inverted_index.get_connection`'s contract so callers can treat
    a missing documents index exactly like a missing literary one."""
    if language in _connections:
        return _connections[language]
    path = _index_db_path(language)
    conn = None
    if os.path.exists(path):
        try:
            conn = sqlite3.connect(f'file:{path}?mode=ro&immutable=1', uri=True,
                                    check_same_thread=False)
            conn.row_factory = sqlite3.Row
        except Exception as e:                                     # noqa: BLE001
            logger.error(f"Failed to open documents index for {language}: {e}")
            conn = None
    _connections[language] = conn
    return conn


def find_co_occurring_lemmas(lemmas, language, min_matches=1, max_distance=None,
                              fallback_forms=None):
    """Same contract as backend.inverted_index.find_co_occurring_lemmas, run
    against this module's own documents-index connection for `language`.

    Reuses that module's query/variant-expansion logic directly (passed our
    connection via its `conn=` parameter, added for exactly this reuse —
    see backend/inverted_index.py) rather than re-implementing the SQL and
    the Latin u/v, i/j spelling-variant expansion here. Because `language`
    is passed through unchanged ('la'/'grc', not a pseudo-language), that
    expansion fires for documents exactly as it does for literature — the
    dev-only `query_documents_index.py` tool from stage 3b-1 could not do
    this (it had to pass a pseudo-language to reuse the module at all,
    which left that gate unlit); this is the fix, not a repeat of the
    limitation.
    """
    conn = get_connection(language)
    if conn is None:
        return []
    from backend.inverted_index import find_co_occurring_lemmas as _generic
    return _generic(lemmas, language, min_matches=min_matches,
                     max_distance=max_distance, fallback_forms=fallback_forms,
                     conn=conn)


_corpus_version_cache = {}


def get_corpus_version(language):
    """A date stamp for the documents index's own build state, the same
    `corpus_version` contract `backend.inverted_index.get_corpus_version`
    gives literary responses. The documents index build
    (scripts/documents/build_documents_index.py) stamps no `meta` table of
    its own, so this falls back straight to the index file's own mtime
    (inverted_index.py's own fallback for an unstamped index)."""
    if language in _corpus_version_cache:
        return _corpus_version_cache[language]
    v = None
    path = _index_db_path(language)
    if os.path.exists(path):
        try:
            from datetime import date
            v = date.fromtimestamp(os.path.getmtime(path)).isoformat()
        except Exception:                                          # noqa: BLE001
            v = None
    _corpus_version_cache[language] = v
    return v


def has_lines_data(language):
    conn = get_connection(language)
    if conn is None:
        return False
    from backend.inverted_index import has_lines_data as _generic
    return _generic(language, conn=conn)


def get_lines_batch(filename, refs, language):
    conn = get_connection(language)
    if conn is None:
        return {}
    if not refs:
        return {}
    from backend.inverted_index import get_lines_batch as _generic
    return _generic(filename, refs, language, conn=conn)


# --------------------------------------------------------------------------
# doc_meta (ref -> doc id)
# --------------------------------------------------------------------------

def doc_for(language, filename, ref):
    """The owning document's id for one (bucket filename, ref) pair.

    write_document_tess.py's own convention (confirmed against sample
    records and against build_documents_index.py's doc_meta build): a
    document's id is always the text before the first space in its ref —
    "<ID>" for a short document's one packed line, "<ID LINE>" for a long
    one's own line. So the id is a cheap split, confirmed here against the
    index's own doc_meta table (not merely assumed) so a ref this module
    does not recognize fails loudly (returns None, logged) instead of
    quietly returning a wrong id. `filename` is accepted (and matches the
    spec's doc_for(lang, text filename, ref) signature) but is not needed
    for the lookup itself — doc_meta is keyed on doc_id alone, globally
    unique across a language's bucket files — so it is unused beyond
    documenting which text the caller already knows this ref came from.
    """
    del filename  # see docstring: doc_meta is keyed on doc_id alone
    if not ref:
        return None
    doc_id = ref.split(' ', 1)[0]
    conn = get_connection(language)
    if conn is None:
        return doc_id  # best effort: can't confirm, but still usable
    try:
        row = conn.execute('SELECT doc_id FROM doc_meta WHERE doc_id = ?', (doc_id,)).fetchone()
    except Exception as e:                                         # noqa: BLE001
        logger.error(f"doc_for lookup failed for {language}/{ref!r}: {e}")
        return doc_id
    if row is None:
        logger.warning(f"doc_for: {doc_id!r} (from ref {ref!r}) not in doc_meta for {language}")
        return None
    return doc_id


# --------------------------------------------------------------------------
# metadata.db (credit / date / place / labels)
# --------------------------------------------------------------------------

_meta_conn_state = {'conn': None, 'checked': False}


def get_meta_connection():
    if _meta_conn_state['checked']:
        return _meta_conn_state['conn']
    _meta_conn_state['checked'] = True
    path = _metadata_db_path()
    conn = None
    if os.path.exists(path):
        try:
            conn = sqlite3.connect(f'file:{path}?mode=ro&immutable=1', uri=True,
                                    check_same_thread=False)
            conn.row_factory = sqlite3.Row
        except Exception as e:                                     # noqa: BLE001
            logger.error(f"Failed to open documents metadata db {path}: {e}")
            conn = None
    _meta_conn_state['conn'] = conn
    return conn


def reset_caches():
    """Drop every cached connection/table (index, metadata, sidecars) so a
    changed env var or a swapped-in index/metadata file takes effect
    without a process restart. Also used by tests between fixtures."""
    _connections.clear()
    _meta_conn_state['conn'] = None
    _meta_conn_state['checked'] = False
    _sidecar_cache.clear()
    _corpus_version_cache.clear()
    meta.cache_clear()


_META_FIELDS = (
    "id, collection, source, licence_name, licence_url, source_name, source_url, "
    "licence_name_secondary, licence_url_secondary, source_name_secondary, source_url_secondary, "
    "principal_edition, text_type_label, object_type_label, material_label, "
    "date_not_before, date_not_after, ancient_place, modern_place, region, pleiades_id"
)


@lru_cache(maxsize=8192)
def meta(doc_id):
    """Credit/date/place/label fields for one document id, from
    metadata.db's `documents` table (stage 3a). Cached: a long inscription
    or papyrus's doc id repeats across every one of its lines. Returns None
    when metadata.db is unavailable or the id is unknown — callers must
    handle that (a document hit still has its text and locus with no
    metadata; it is simply uncredited, not dropped)."""
    conn = get_meta_connection()
    if conn is None or not doc_id:
        return None
    try:
        row = conn.execute(f"SELECT {_META_FIELDS} FROM documents WHERE id = ?",
                            (doc_id,)).fetchone()
    except Exception as e:                                         # noqa: BLE001
        logger.error(f"documents metadata lookup failed for {doc_id!r}: {e}")
        return None
    if row is None:
        return None
    d = dict(row)
    return {
        'doc_id': doc_id,
        'collection': d.get('collection'),
        'source': d.get('source'),
        'credit': {
            'licence_name': d.get('licence_name'),
            'licence_url': d.get('licence_url'),
            'source_name': d.get('source_name'),
            'source_url': d.get('source_url'),
            'licence_name_secondary': d.get('licence_name_secondary'),
            'licence_url_secondary': d.get('licence_url_secondary'),
            'source_name_secondary': d.get('source_name_secondary'),
            'source_url_secondary': d.get('source_url_secondary'),
            'principal_edition': d.get('principal_edition'),
        },
        'date_not_before': d.get('date_not_before'),
        'date_not_after': d.get('date_not_after'),
        'ancient_place': d.get('ancient_place'),
        'modern_place': d.get('modern_place'),
        'region': d.get('region'),
        'pleiades_id': d.get('pleiades_id'),
        'text_type_label': d.get('text_type_label'),
        'object_type_label': d.get('object_type_label'),
        'material_label': d.get('material_label'),
    }


# --------------------------------------------------------------------------
# Restored-word sidecars
# --------------------------------------------------------------------------

_sidecar_cache = {}


def _sidecar_path(language, filename):
    bucket = filename[:-5] if filename.endswith('.tess') else filename
    return os.path.join(_sidecar_root(), language, f'{bucket}.restored_words.jsonl')


def _load_sidecar(language, filename):
    key = (language, filename)
    if key in _sidecar_cache:
        return _sidecar_cache[key]
    path = _sidecar_path(language, filename)
    table = {}
    if os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                for raw_line in f:
                    raw_line = raw_line.strip()
                    if not raw_line:
                        continue
                    rec = json.loads(raw_line)
                    ref = rec.get('ref')
                    if ref:
                        table[ref] = rec
        except Exception as e:                                     # noqa: BLE001
            logger.error(f"Failed to load restored-word sidecar {path}: {e}")
            table = {}
    _sidecar_cache[key] = table
    return table


def restored_indices(language, filename, ref):
    """{'restored': [token positions...], 'fragment': [token positions...]}
    for one written .tess line, from its bucket file's own sidecar (see
    write_document_tess.py). Empty lists when the sidecar or this ref is
    unavailable — this is display-only highlighting, never a reason to drop
    a result, so it never raises."""
    rec = _load_sidecar(language, filename).get(ref)
    if not rec:
        return {'restored': [], 'fragment': []}
    return {'restored': list(rec.get('restored') or []), 'fragment': list(rec.get('fragment') or [])}
