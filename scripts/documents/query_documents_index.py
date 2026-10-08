#!/usr/bin/env python3
"""Stage 3b-1: dev-only lemma/phrase lookup against a `<lang>_documents_index.db`
built by `build_documents_index.py`.

Reuses `backend.inverted_index.lookup_lemmas`/`find_co_occurring_lemmas`
for the actual postings lookup (by monkeypatching that module's own
`INDEX_DIR` for the duration of the call and passing a language string of
"<lang>_documents" -- `get_connection()` builds its path as
"<language>_index.db", so "la_documents" resolves to exactly
"la_documents_index.db" without forking any of that module's own SQL).
KNOWN LIMITATION from this reuse: `lookup_lemmas`'s Latin u/v and i/j
spelling-variant expansion is gated on `language == 'la'` exactly, so it
does not fire for "la_documents" -- a query lemma's own u/v or i/j variant
spelling will not be auto-expanded here the way a live Latin search does.
Acceptable for a dev-only tool; flagged rather than silently worked around
by widening that gate inside backend/inverted_index.py itself, which this
stage does not touch.

Reuses `TextProcessor._tokenize_and_lemmatize` (the same call
`process_file`'s phrase mode uses internally) to turn a raw query phrase
into lemmas, so a caller can pass surface Latin/Greek text ("dis manibus")
rather than pre-lemmatized forms.

Joins hits against `metadata.db` (stage 3a's own database: `documents`
table, primary key `id`, the SAME id this index's own `doc_meta.doc_id`
and every ref's leading token already carry) for licence, source link,
and other credit fields.

Does not modify any index, cache, or metadata database; read-only.
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO_ROOT)

import backend.inverted_index as inv_index  # noqa: E402
from backend.text_processor import TextProcessor  # noqa: E402


def lemmatize_query(text: str, language: str) -> list[str]:
    tp = TextProcessor()
    _orig_tokens, _tokens, lemmas, _pos, _variants, _hemi = \
        tp._tokenize_and_lemmatize(text, language)  # noqa: SLF001
    seen = []
    for lem in lemmas:
        if lem and lem not in seen:
            seen.append(lem)
    return seen


def query_lemmas(lemmas: list[str], language: str, index_dir: str, min_matches: int = 1):
    """Returns find_co_occurring_lemmas' own result list, against
    "<language>_documents_index.db" under index_dir."""
    orig_index_dir = inv_index.INDEX_DIR
    orig_connections = dict(inv_index._connections)  # noqa: SLF001
    inv_index.INDEX_DIR = index_dir
    inv_index._connections = {}  # noqa: SLF001  (force a fresh connection to the new INDEX_DIR)
    try:
        pseudo_lang = f"{language}_documents"
        return inv_index.find_co_occurring_lemmas(lemmas, pseudo_lang, min_matches=min_matches)
    finally:
        inv_index.INDEX_DIR = orig_index_dir
        inv_index._connections = orig_connections  # noqa: SLF001


def load_metadata_row(metadata_db: str, doc_id: str):
    if not metadata_db or not os.path.exists(metadata_db):
        return None
    conn = sqlite3.connect(metadata_db)
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT id, licence_name, licence_url, source_name, source_url, "
        "principal_edition FROM documents WHERE id = ?", (doc_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def _line_text(index_db_path: str, filename: str, ref: str):
    conn = sqlite3.connect(index_db_path)
    row = conn.execute(
        "SELECT l.content FROM lines l JOIN texts t ON l.text_id = t.text_id "
        "WHERE t.filename = ? AND l.ref = ?", (filename, ref)
    ).fetchone()
    conn.close()
    return row[0] if row else None


def run_query(text: str, language: str, index_dir: str, metadata_db: str | None,
              min_matches: int = 1, limit: int = 20):
    lemmas = lemmatize_query(text, language)
    hits = query_lemmas(lemmas, language, index_dir, min_matches=min_matches)
    index_db_path = os.path.join(index_dir, f"{language}_documents_index.db")
    results = []
    for filename, ref, matching_lemmas, positions in hits[:limit]:
        doc_id = ref.split(" ", 1)[0]
        meta = load_metadata_row(metadata_db, doc_id) if metadata_db else None
        results.append({
            "doc_id": doc_id,
            "ref": ref,
            "bucket_file": filename,
            "text": _line_text(index_db_path, filename, ref),
            "matched_lemmas": sorted(matching_lemmas),
            "licence": meta.get("licence_name") if meta else None,
            "source_url": meta.get("source_url") if meta else None,
            "principal_edition": meta.get("principal_edition") if meta else None,
        })
    return {
        "query_text": text,
        "language": language,
        "query_lemmas": lemmas,
        "hit_count": len(hits),
        "shown": results,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                  formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--text", required=True, help="surface-form query phrase")
    ap.add_argument("--language", required=True, choices=["la", "grc"])
    ap.add_argument("--index-dir", default=os.path.join(REPO_ROOT, "data", "inverted_index"))
    ap.add_argument("--metadata-db", default=os.path.expanduser(
        "~/tesserae-docs/stage3/metadata.db"))
    ap.add_argument("--min-matches", type=int, default=1)
    ap.add_argument("--limit", type=int, default=20)
    args = ap.parse_args(argv)

    result = run_query(args.text, args.language, args.index_dir, args.metadata_db,
                        min_matches=args.min_matches, limit=args.limit)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
