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
import re
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


def _label_map_path():
    return os.environ.get('TESSERAE_DOCUMENTS_LABEL_MAP') or os.path.join(
        _repo_root(), 'data', 'documents', 'german_label_translations.json')


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


def get_document_lines(language, doc_id):
    """Every line of one document (stage 3b-1's own `lines` table, via
    `doc_meta`), in original order, each carrying its own restored/
    fragment token positions from the sidecar -- the data the Reader's
    document view (stage 3b-3) needs. Returns None (not an exception, not
    an empty dict) when the documents index for `language` is unavailable
    or `doc_id` is not in its doc_meta table, so a caller trying several
    languages in turn (a doc id alone does not say which) can tell "wrong
    language, try the next one" apart from "this really is empty" --
    which never happens, since doc_meta is only ever built from a
    document that had at least one line (build_documents_index.py's
    build_doc_meta loop only ever writes a doc_id it just saw a line
    for).

    `doc_meta.text_id` is the index's own INTEGER id (the `texts` table's
    primary key, not the bucket filename) -- resolved here to the
    filename the sidecar is keyed on. first_ref/last_ref bound a
    CONTIGUOUS run of rows in `lines` (true by construction: doc_meta was
    built by walking `lines` in rowid order and starting a new doc_id
    exactly when the ref's own doc id changed -- see build_doc_meta), so
    the two rowids of those two refs bound every line of the document;
    MIN/MAX guards against a single-line document, where first_ref ==
    last_ref and the two queries legitimately return the same rowid."""
    conn = get_connection(language)
    if conn is None or not doc_id:
        return None
    try:
        row = conn.execute(
            'SELECT text_id, first_ref, last_ref FROM doc_meta WHERE doc_id = ?',
            (doc_id,)).fetchone()
    except Exception as e:                                         # noqa: BLE001
        logger.error(f"get_document_lines: doc_meta lookup failed for {language}/{doc_id!r}: {e}")
        return None
    if row is None:
        return None
    text_id, first_ref, last_ref = row['text_id'], row['first_ref'], row['last_ref']
    try:
        trow = conn.execute('SELECT filename FROM texts WHERE text_id = ?', (text_id,)).fetchone()
    except Exception as e:                                         # noqa: BLE001
        logger.error(f"get_document_lines: texts lookup failed for {language}/{doc_id!r}: {e}")
        return None
    if trow is None:
        return None
    filename = trow['filename']
    try:
        bounds = conn.execute(
            'SELECT MIN(rowid), MAX(rowid) FROM lines WHERE text_id = ? AND ref IN (?, ?)',
            (text_id, first_ref, last_ref)).fetchone()
    except Exception as e:                                         # noqa: BLE001
        logger.error(f"get_document_lines: bounds lookup failed for {language}/{doc_id!r}: {e}")
        return None
    if bounds is None or bounds[0] is None:
        return None
    lo, hi = min(bounds[0], bounds[1]), max(bounds[0], bounds[1])
    try:
        rows = conn.execute(
            'SELECT ref, content, tokens FROM lines WHERE text_id = ? '
            'AND rowid BETWEEN ? AND ? ORDER BY rowid',
            (text_id, lo, hi)).fetchall()
    except Exception as e:                                         # noqa: BLE001
        logger.error(f"get_document_lines: lines lookup failed for {language}/{doc_id!r}: {e}")
        return None
    lines = []
    for r in rows:
        try:
            tokens = json.loads(r['tokens']) if r['tokens'] else []
        except Exception:                                           # noqa: BLE001
            tokens = []
        restored = restored_indices(language, filename, r['ref'])
        lines.append({
            'ref': r['ref'],
            'text': r['content'] or '',
            'tokens': tokens,
            'restored_indices': restored.get('restored'),
            'fragment_indices': restored.get('fragment'),
        })
    return {'filename': filename, 'lines': lines}


# --------------------------------------------------------------------------
# German label translation (stage 4 polish)
# --------------------------------------------------------------------------
# metadata.db's region/ancient_place/modern_place/material_label/
# object_type_label/text_type_label fields come from EDH, EDCS, Trismegistos
# and Papyri.info, whose own working language is German for EDH's "no data"
# placeholders and connector words ("unbekannt", "bei", "oder" -- see
# data/documents/german_label_translations.json, built 2026-10-08 by
# counting every distinct value of those six fields that contains one of
# these words, against the production metadata.db; counts are in
# docs/DECISIONS.md). A real place name spelled in German (Koeln, Mainz,
# Wien) is NOT in the table and is never touched -- that is the place's own
# name, the same reason 'Roma' is not translated to 'Rome' anywhere else on
# the site. The underlying metadata.db value is never modified; translation
# happens only on the way out, in _document_hit (backend/app.py).

_label_map_cache = {'map': None, 'checked': False}


def _label_map():
    if _label_map_cache['checked']:
        return _label_map_cache['map']
    _label_map_cache['checked'] = True
    path = _label_map_path()
    table = {}
    if os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                raw = json.load(f)
            table = {k.lower(): v for k, v in raw.items() if not k.startswith('_')}
        except Exception as e:                                     # noqa: BLE001
            logger.error(f"Failed to load German label translations {path}: {e}")
            table = {}
    _label_map_cache['map'] = table
    return table


_LABEL_WORD_RE = re.compile(r"[^\W\d_]+(?:['’][^\W\d_]+)*", re.UNICODE)
# "bzw." (an abbreviation of "beziehungsweise", always written with the
# period) needs the period consumed along with the word, or the general
# substitution below leaves a stray "." behind ("Alexandria or. Arsinoites").
_LABEL_ABBREV_RE = re.compile(r'\bbzw\.', re.IGNORECASE)


def translate_label(value):
    """`value` with every whole word the German->English table recognizes
    replaced by its English equivalent, word boundaries and surrounding
    punctuation/spacing left exactly as metadata.db wrote them (so "Kostolac,
    bei" becomes "Kostolac, near", not a different string shape), case
    carried over per-word (an initial capital on the German word keeps an
    initial capital on the English one). Returns `value` unchanged when it
    is empty/None or no table word is found -- the overwhelming majority of
    values, which are not German at all."""
    if not value:
        return value
    table = _label_map()
    if not table:
        return value
    value = _LABEL_ABBREV_RE.sub(
        lambda m: 'Or' if m.group(0)[:1].isupper() else 'or', value)

    def _sub(m):
        word = m.group(0)
        english = table.get(word.lower())
        if english is None:
            return word
        if word[:1].isupper():
            return english[:1].upper() + english[1:]
        return english

    return _LABEL_WORD_RE.sub(_sub, value)


# Markers meaning "this document's place is not known", across the
# languages metadata.db's own sources use for that (EDH's German
# 'unbekannt', EDCS/Trismegistos' English 'unknown'/'unknown location', and
# the Latin 'ignoratur' a number of principal editions still use) --
# checked on the RAW value (before translate_label runs), case-insensitive,
# with a trailing editorial '?' ignored. A place hit this recognizes is
# hidden rather than shown translated as the word "unknown": printing that
# word is no information for a reader, per the stage 4 spec.
UNKNOWN_PLACE_MARKERS = frozenset({
    'unbekannt', 'unknown', 'unknown location', 'ignoratur', 'incertum',
})


def is_unknown_place(value):
    if not value:
        return False
    v = value.strip().rstrip('?').strip().lower()
    return v in UNKNOWN_PLACE_MARKERS


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
    _label_map_cache['map'] = None
    _label_map_cache['checked'] = False
    meta.cache_clear()
    display_fields.cache_clear()


_META_FIELDS = (
    "id, collection, source, licence_name, licence_url, source_name, source_url, "
    "licence_name_secondary, licence_url_secondary, source_name_secondary, source_url_secondary, "
    "principal_edition, text_type_label, object_type_label, material_label, "
    "date_not_before, date_not_after, ancient_place, modern_place, region, pleiades_id"
)


def _meta_row_to_dict(doc_id, d):
    """Shared shape-builder for one `documents` table row (as a plain dict),
    used by both `meta` (one id, cached) and `bulk_meta` (many ids, one
    query) so the two never drift apart."""
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
        row = conn.execute(f"SELECT {_META_FIELDS} FROM documents WHERE id = ?",  # nosec B608
                            (doc_id,)).fetchone()
    except Exception as e:                                         # noqa: BLE001
        logger.error(f"documents metadata lookup failed for {doc_id!r}: {e}")
        return None
    if row is None:
        return None
    return _meta_row_to_dict(doc_id, dict(row))


# How many doc ids go in one `WHERE id IN (...)` query in bulk_meta. SQLite's
# default compile-time limit on bound parameters is 999; comfortably under
# that leaves room for drivers with a lower limit.
_BULK_META_CHUNK = 500


def bulk_meta(doc_ids):
    """meta() for many ids in one pass (stage 4 ranking/totals: sorting and
    counting a documents search by date/region needs every matching
    document's metadata, and a stock phrase like "dis manibus" touches tens
    of thousands of them -- one query per id, even lru_cache'd on repeat
    calls, is the first time through every one of them, which measured over
    a second on its own against the production metadata.db; chunked IN
    queries measured under 50ms for the same ids). Returns {doc_id: meta
    dict} for every id metadata.db actually has a row for; an id this does
    not recognize is simply absent from the returned dict (same "uncredited,
    not dropped" contract as `meta`, just without a None entry per miss).
    Does not populate `meta`'s own lru_cache -- the two caches are kept
    deliberately separate so this bulk path can never evict a hot single
    lookup, and a caller that already has the dict from here has no reason
    to call `meta` again for the same id."""
    ids = sorted({d for d in doc_ids if d})
    if not ids:
        return {}
    conn = get_meta_connection()
    if conn is None:
        return {}
    out = {}
    for i in range(0, len(ids), _BULK_META_CHUNK):
        chunk = ids[i:i + _BULK_META_CHUNK]
        placeholders = ', '.join('?' for _ in chunk)
        try:
            rows = conn.execute(
                f"SELECT {_META_FIELDS} FROM documents WHERE id IN ({placeholders})",  # nosec B608
                chunk).fetchall()
        except Exception as e:                                     # noqa: BLE001
            logger.error(f"bulk_meta lookup failed for a chunk of {len(chunk)} ids: {e}")
            continue
        for row in rows:
            d = dict(row)
            out[d['id']] = _meta_row_to_dict(d['id'], d)
    return out


# Every field name extract_metadata.py (stage 3a) writes to the `display`
# EAV table's `field` column; see that script's own module docstring.
# `image_url` is the one field a document can carry more than once.
_DISPLAY_MULTI_FIELDS = ('image_url',)


@lru_cache(maxsize=4096)
def display_fields(doc_id):
    """Stage 3a's `display` table (id, field, value -- an EAV layout,
    since a document can have more than one image_url) for one document
    id, as {field: value} for every field, except `image_url`, which
    comes back as {field: [value, ...]} even when there is exactly one.
    None when metadata.db (or its `display` table) is unavailable; an
    empty dict when the db is reachable but this document simply has no
    display rows (every field here is optional -- see
    extract_metadata.py). A first-wins rule covers the never-expected case
    of a duplicate single-valued field."""
    conn = get_meta_connection()
    if conn is None or not doc_id:
        return None
    try:
        rows = conn.execute('SELECT field, value FROM display WHERE id = ?', (doc_id,)).fetchall()
    except Exception as e:                                         # noqa: BLE001
        logger.error(f"display_fields lookup failed for {doc_id!r}: {e}")
        return None
    out = {}
    for r in rows:
        field, value = r['field'], r['value']
        if field in _DISPLAY_MULTI_FIELDS:
            out.setdefault(field, []).append(value)
        else:
            out.setdefault(field, value)
    return out


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
