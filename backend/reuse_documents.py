"""
Tesserae V6 - Documents Reuse Table (cross-collection)

Query layer for cache/reuse_pairs/<lang>_documents.db, built by
scripts/reuse/build_documents_reuse_table.py: which inscriptions and papyri
(the documents collection, backend/documents.py) quote or near-quote a
literary line, using the same word-triple containment logic and strict/
possible tiers as the literary reuse table (backend/reuse_table.py), scored
against the documents collection instead of the rest of the literary corpus.

Gated the same way the rest of the documents trial is: a caller should check
backend.documents.enabled() (TESSERAE_DOCUMENTS=1) before calling anything
here -- this module itself does not re-check that env var, the same
division of responsibility backend/documents.py's own docstring describes
("Everything here is OFF unless the caller checks enabled() first").

Latin and Greek only (backend.documents.SUPPORTED_LANGUAGES) -- a language
with no <lang>_documents.db simply answers available: False, the same
"not built yet, not an error" contract backend/reuse_table.py uses for the
literary table.

Table schema (written by the build script):
    pairs(lit_work, lit_ref, lit_seq, doc_id, doc_bucket, doc_ref, doc_seq,
          shared, jaccard, span_len, doc_restored)
    meta(key, value)
"""
import json
import os
import re
import sqlite3
from collections import defaultdict
from functools import lru_cache

from backend.logging_config import get_logger
from backend.passage_index import _norm_work
from backend.reuse_table import _shared_word_mask, _bold_spans, POSSIBLE_MIN_JACCARD

logger = get_logger('reuse_documents')

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_DIR = os.path.join(BASE_DIR, 'cache', 'reuse_pairs')

_connections = {}


def _db_path(language):
    return os.path.join(DB_DIR, f'{language}_documents.db')


def is_available(language):
    """Same contract as backend.reuse_table.is_available: False for a
    language whose cross-collection table has not been built (a normal
    state -- callers answer 404, not an error) and for a present-but-
    corrupt file (validated by a real read before caching the connection,
    not just by the file existing)."""
    return _get_connection(language) is not None


def _drop_connection(language):
    conn = _connections.pop(language, None)
    if conn is not None:
        try:
            conn.close()
        except Exception:
            pass


def _get_connection(language):
    if language in _connections:
        return _connections[language]
    path = _db_path(language)
    if not os.path.exists(path):
        return None
    conn = None
    try:
        conn = sqlite3.connect(path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("SELECT 1 FROM meta LIMIT 1")
    except sqlite3.DatabaseError as e:
        logger.error(f"Documents reuse table for '{language}' is not a valid database: {e}")
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass
        return None
    except Exception as e:
        logger.error(f"Failed to open documents reuse table for '{language}': {e}")
        return None
    _connections[language] = conn
    return conn


def meta(language):
    conn = _get_connection(language)
    if not conn:
        return {}
    try:
        rows = conn.execute("SELECT key, value FROM meta").fetchall()
        return {r['key']: r['value'] for r in rows}
    except sqlite3.DatabaseError as e:
        logger.error(f"reuse_documents.meta query failed for '{language}': {e}")
        _drop_connection(language)
        return {}
    except Exception:
        return {}


def _work_has_rows(language, work):
    conn = _get_connection(language)
    if not conn:
        return False
    try:
        return conn.execute(
            "SELECT 1 FROM pairs WHERE lit_work = ? LIMIT 1", (work,)
        ).fetchone() is not None
    except Exception:
        return False


def _resolve_work(language, work):
    """Same part-file-collapse resolution as backend.reuse_table._resolve_work,
    but checked against THIS table's own rows (a work can have rows in the
    literary table and none here, or vice versa, so the two must resolve
    independently rather than sharing a cached answer)."""
    w = (work or '')
    if '/' in w:
        w = w.rsplit('/', 1)[-1]
    if w.endswith('.tess'):
        w = w[:-5]
    raw = w
    collapsed = _norm_work(raw)
    if collapsed == raw:
        return raw
    if _work_has_rows(language, collapsed):
        return collapsed
    if _work_has_rows(language, raw):
        return raw
    return collapsed


@lru_cache(maxsize=4096)
def _doc_credit(doc_id):
    """Credit/date/place/label fields for one document, from
    backend.documents.meta() -- None when metadata.db is unavailable or the
    id is unknown (a hit still has its text and locus, simply uncredited)."""
    import backend.documents as docs
    return docs.meta(doc_id)


def _doc_line_data(language, bucket, ref):
    """{'text', 'tokens'} for one document line, via
    backend.documents.get_lines_batch (the same lookup the documents-
    collection search already uses) -- cached per (language, bucket) for
    the life of a single line() call's loop, not across requests."""
    import backend.documents as docs
    data = docs.get_lines_batch(bucket, [ref], language)
    return data.get(ref)


_WORD_RE = re.compile(r"[^\s]+")


def _doc_original_tokens(content, tokens):
    """Case-preserved, in-order words extracted from a document line's raw
    `content` for bolding (see backend/reuse_table.py's _bold_spans) --
    the documents index has no separate original_tokens array the way the
    literary lemma cache does, but `content` and `tokens` are produced by
    the SAME tokenizer run at index time (scripts/documents/
    build_documents_index.py), so splitting content on whitespace and
    stripping the tokenizer's own punctuation set yields the same word
    count and order in practice. Falls back to `tokens` itself (already
    normalized, so bolding may miss original casing) when the counts
    disagree -- the same fallback backend.reuse_table._line_tokens uses
    for a misaligned cache, rather than guessing a wrong alignment."""
    words = [w.strip('.,;:!?()[]{}<>"\'') for w in _WORD_RE.findall(content or '')]
    words = [w for w in words if w]
    if len(words) != len(tokens):
        return list(tokens)
    return words


def line(language, lit_work, lit_ref):
    """Document hits for one literary line: inscriptions/papyri whose own
    lines verbatim- or near-verbatim-repeat it, from `pairs`. Returns
    {'available': False} if no cross-collection table exists for the
    language, else {'available': True, 'documents': [...], 'meta': {...}}.

    Each document hit is {doc_id, ref, language, text, bold_spans, shared,
    jaccard, span_len, tier, restored, date_not_before, date_not_after,
    ancient_place, modern_place, region, text_type_label, object_type_label,
    material_label, collection, source, credit, pleiades_id}. `tier` follows
    the same rule as the literary table (backend.reuse_table.line): shared==1
    is 'possible' (the rare-single-ngram rule, the only rule that can keep a
    shared==1 pair), anything else kept is 'strict'."""
    if not is_available(language):
        return {'available': False, 'documents': []}
    conn = _get_connection(language)
    if not conn:
        return {'available': False, 'documents': []}
    lit_work = _resolve_work(language, lit_work)
    try:
        rows = conn.execute(
            """SELECT doc_id, doc_bucket, doc_ref, shared, jaccard, span_len, doc_restored
                 FROM pairs WHERE lit_work = ? AND lit_ref = ?
                   AND (shared > 1 OR jaccard >= ?)
               ORDER BY shared DESC""",
            (lit_work, lit_ref, POSSIBLE_MIN_JACCARD)
        ).fetchall()
    except sqlite3.DatabaseError as e:
        logger.error(f"reuse_documents.line query failed for {language}/{lit_work}/{lit_ref}: {e}")
        _drop_connection(language)
        return {'available': False, 'documents': []}
    except Exception as e:
        logger.error(f"reuse_documents.line query failed for {language}/{lit_work}/{lit_ref}: {e}")
        return {'available': False, 'documents': []}

    # The literary line's own tokens, for _shared_word_mask -- read via the
    # literary reuse table's own line-cache helper, the exact same source
    # backend.reuse_table.line() uses for the SAME literary line, so the
    # bolding here never drifts from what the literary Reuse tab bolds.
    from backend.reuse_table import _line_tokens as _lit_line_tokens
    source_tokens, _ = _lit_line_tokens(language, lit_work, lit_ref)

    documents = []
    for r in rows:
        doc_id, bucket, doc_ref = r['doc_id'], r['doc_bucket'], r['doc_ref']
        line_data = _doc_line_data(language, bucket, doc_ref)
        text = (line_data or {}).get('text', '')
        quote_tokens = (line_data or {}).get('tokens', [])
        original_tokens = _doc_original_tokens(text, quote_tokens)
        mask = _shared_word_mask(source_tokens, quote_tokens)
        credit = _doc_credit(doc_id) or {}
        documents.append({
            'doc_id': doc_id,
            'ref': doc_ref,
            'language': language,
            'text': text,
            'bold_spans': _bold_spans(text, original_tokens, mask),
            'shared': r['shared'],
            'jaccard': r['jaccard'],
            'span_len': r['span_len'],
            'restored': bool(r['doc_restored']),
            'tier': 'possible' if r['shared'] == 1 else 'strict',
            'collection': credit.get('collection'),
            'source': credit.get('source'),
            'credit': credit.get('credit'),
            'date_not_before': credit.get('date_not_before'),
            'date_not_after': credit.get('date_not_after'),
            'ancient_place': credit.get('ancient_place'),
            'modern_place': credit.get('modern_place'),
            'region': credit.get('region'),
            'pleiades_id': credit.get('pleiades_id'),
            'text_type_label': credit.get('text_type_label'),
            'object_type_label': credit.get('object_type_label'),
            'material_label': credit.get('material_label'),
        })
    return {'available': True, 'documents': documents, 'meta': meta(language)}


def marks(language, lit_work, ref_start=None, ref_end=None):
    """Per-line count of distinct documents repeating each literary line,
    split into the same two tiers as backend.reuse_table.marks:
    `n_documents` (strict, shared>=2 or the containment override) and
    `n_possible_documents` (possible, the rare-single-ngram rule alone).
    Counts DISTINCT DOCUMENTS (doc_id), not document lines -- a long
    inscription quoting the same literary line on two of its own lines
    (span_len>1 territory) still counts once.

    ref_start/ref_end restrict the range by the work's own line order
    (lit_seq, from the build), same convention as the literary table's
    marks(), since a citation label does not sort correctly as a string."""
    if not is_available(language):
        return {'available': False, 'lines': []}
    conn = _get_connection(language)
    if not conn:
        return {'available': False, 'lines': []}
    lit_work = _resolve_work(language, lit_work)
    try:
        rows = conn.execute(
            """SELECT lit_ref AS ref, lit_seq AS seq, doc_id, shared FROM pairs
                 WHERE lit_work = ? AND (shared > 1 OR jaccard >= ?)""",
            (lit_work, POSSIBLE_MIN_JACCARD)
        ).fetchall()
    except sqlite3.DatabaseError as e:
        logger.error(f"reuse_documents.marks query failed for {language}/{lit_work}: {e}")
        _drop_connection(language)
        return {'available': False, 'lines': []}
    except Exception as e:
        logger.error(f"reuse_documents.marks query failed for {language}/{lit_work}: {e}")
        return {'available': False, 'lines': []}

    if not rows:
        return {'available': True, 'lines': []}

    strict_docs = defaultdict(set)
    possible_docs = defaultdict(set)
    seqs = {}
    for r in rows:
        bucket = possible_docs if r['shared'] == 1 else strict_docs
        bucket[r['ref']].add(r['doc_id'])
        seqs[r['ref']] = r['seq']

    seq_start = seq_end = None
    if ref_start or ref_end:
        # Resolve ref_start/ref_end to the literary work's own line order,
        # same convention as backend.reuse_table.marks (a citation label
        # does not sort correctly as a string). Loads the full lemma
        # cache's seq map, not just this table's matched rows, since
        # ref_start/ref_end are often lines with no reuse hit at all.
        from backend.reuse_table import _load_work_lines
        ref_to_seq = _load_work_lines(language, lit_work)['seq']
        if ref_start:
            seq_start = ref_to_seq.get(ref_start)
        if ref_end:
            seq_end = ref_to_seq.get(ref_end)

    out = []
    for ref in set(strict_docs) | set(possible_docs):
        if seq_start is not None or seq_end is not None:
            seq = seqs.get(ref)
            if seq is None:
                continue
            if seq_start is not None and seq < seq_start:
                continue
            if seq_end is not None and seq > seq_end:
                continue
        out.append({
            'ref': ref,
            'n_documents': len(strict_docs.get(ref, ())),
            'n_possible_documents': len(possible_docs.get(ref, ())),
        })
    return {'available': True, 'lines': out}
