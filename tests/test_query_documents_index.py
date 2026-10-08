"""Tests for scripts/documents/query_documents_index.py against a tiny
end-to-end fixture: write_document_tess -> build_documents_index -> a
synthetic metadata.db -> query_documents_index."""
import json
import os
import sqlite3
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scripts.documents.build_documents_index import build_one_language
from scripts.documents.query_documents_index import run_query
from scripts.documents.write_document_tess import process_corpus


def _flags(n):
    return [False] * n


def _line(n, text):
    return {"n": str(n), "text": text, "diplomatic": text,
            "restored_flags": _flags(len(text)), "joins_previous": False}


def _rec(doc_id, source, lines, languages=("la",)):
    return {"id": doc_id, "source": source, "tm_id": 1, "languages": list(languages),
            "findspot": {"region": "dalmatia"}, "date_not_before": None, "lines": lines}


def _make_metadata_db(path, doc_ids):
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE documents (id TEXT PRIMARY KEY, licence_name TEXT, "
                 "licence_url TEXT, source_name TEXT, source_url TEXT, principal_edition TEXT)")
    for doc_id in doc_ids:
        conn.execute("INSERT INTO documents VALUES (?, ?, ?, ?, ?, ?)",
                     (doc_id, "CC BY-SA 4.0", "https://example.org/licence",
                      "EDH", f"https://example.org/{doc_id}", "CIL VI 1234"))
    conn.commit()
    conn.close()


def test_query_finds_a_hit_and_joins_metadata(tmp_path):
    corpus_path = os.path.join(tmp_path, "merged_corpus.jsonl")
    with open(corpus_path, "w", encoding="utf-8") as f:
        f.write(json.dumps(_rec("edh:HD000001", "edh",
                                 [_line(1, "Dis Manibus Sacrum")])) + "\n")

    texts_root = os.path.join(tmp_path, "texts_documents")
    process_corpus(corpus_path, texts_root)

    index_dir = os.path.join(tmp_path, "data_inverted_index")
    build_one_language("la", texts_root, index_dir, os.path.join(tmp_path, "cache"),
                        os.path.join(tmp_path, "scratch"), verbose=False)

    metadata_db = os.path.join(tmp_path, "metadata.db")
    _make_metadata_db(metadata_db, ["edh:HD000001"])

    result = run_query("dis manibus", "la", index_dir, metadata_db, min_matches=1)
    assert result["hit_count"] >= 1
    doc_ids = [r["doc_id"] for r in result["shown"]]
    assert "edh:HD000001" in doc_ids
    hit = next(r for r in result["shown"] if r["doc_id"] == "edh:HD000001")
    assert hit["licence"] == "CC BY-SA 4.0"
    assert hit["source_url"] == "https://example.org/edh:HD000001"
