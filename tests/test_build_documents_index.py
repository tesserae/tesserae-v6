"""Tests for scripts/documents/build_documents_index.py, against tiny
fixtures written through write_document_tess.py itself (no corpus data,
no network, no CLTK model files beyond what's already vendored for the
repo's own Latin/Greek lemma tables)."""
import json
import os
import sqlite3
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scripts.documents.build_documents_index import (
    FORBIDDEN_DB_BASENAMES,
    _assert_not_literary_index,
    _assert_safe_dir,
    build_doc_meta,
    build_one_language,
)
from scripts.documents.write_document_tess import process_corpus


def _write_fixture_corpus(path, records):
    with open(path, "w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def _flags(n):
    return [False] * n


def _rec(doc_id, source, lines, languages=("la",), region="dalmatia"):
    return {"id": doc_id, "source": source, "tm_id": 1, "languages": list(languages),
            "findspot": {"region": region}, "date_not_before": None, "lines": lines}


def _line(n, text):
    return {"n": str(n), "text": text, "diplomatic": text,
            "restored_flags": _flags(len(text)), "joins_previous": False}


def test_assert_not_literary_index_rejects_exact_literary_basenames():
    assert "la_index.db" in FORBIDDEN_DB_BASENAMES
    assert "grc_index.db" in FORBIDDEN_DB_BASENAMES
    with pytest.raises(RuntimeError):
        _assert_not_literary_index("/some/dir/la_index.db")
    _assert_not_literary_index("/some/dir/la_documents_index.db")  # does not raise


def test_assert_safe_dir_refuses_var_www():
    with pytest.raises(RuntimeError):
        _assert_safe_dir("/var/www/tesseraev6_flask/data/inverted_index", "--index-dir")
    _assert_safe_dir("/tmp/somewhere/data/inverted_index", "--index-dir")  # does not raise


@pytest.fixture
def built_la_index(tmp_path):
    """A tiny documents index built end to end from fixture records: one
    short document and one long (13-line) document, so doc_meta has both
    a single-ref and a multi-ref document to check."""
    corpus_path = os.path.join(tmp_path, "merged_corpus.jsonl")
    short_lines = [_line(1, "Dis Manibus"), _line(2, "Euhodia")]
    long_lines = [_line(i, f"verse number {i}") for i in range(1, 14)]
    _write_fixture_corpus(corpus_path, [
        _rec("edh:SHORT1", "edh", short_lines),
        _rec("edh:LONG1", "edh", long_lines),
    ])
    texts_root = os.path.join(tmp_path, "texts_documents")
    process_corpus(corpus_path, texts_root)

    index_dir = os.path.join(tmp_path, "data_inverted_index")
    cache_root = os.path.join(tmp_path, "cache_lemmas_documents")
    scratch_root = os.path.join(tmp_path, "scratch")
    result = build_one_language("la", texts_root, index_dir, cache_root,
                                 scratch_root, fast_greek=True, verbose=False)
    return result, index_dir, cache_root


def test_build_writes_documents_suffixed_db_not_the_literary_name(built_la_index):
    result, index_dir, _ = built_la_index
    assert os.path.basename(result["final_db"]) == "la_documents_index.db"
    assert os.path.exists(result["final_db"])
    assert not os.path.exists(os.path.join(index_dir, "la_index.db"))


def test_doc_meta_rows_correct_for_short_and_long_documents(built_la_index):
    result, _, _ = built_la_index
    conn = sqlite3.connect(result["final_db"])
    rows = {r[0]: r for r in conn.execute(
        "SELECT doc_id, text_id, first_ref, last_ref FROM doc_meta")}
    conn.close()
    assert rows["edh:SHORT1"][2] == "edh:SHORT1"
    assert rows["edh:SHORT1"][3] == "edh:SHORT1"
    assert rows["edh:LONG1"][2] == "edh:LONG1 1"
    assert rows["edh:LONG1"][3] == "edh:LONG1 13"


def test_lemma_cache_written_under_separate_documents_cache_root(built_la_index):
    _, _, cache_root = built_la_index
    la_cache_dir = os.path.join(cache_root, "la")
    assert os.path.isdir(la_cache_dir)
    assert any(f.endswith(".json") for f in os.listdir(la_cache_dir))


def test_build_never_opens_an_existing_literary_index_file_for_writing(tmp_path):
    """Put a fake 'la_index.db' with known content in the SAME index_dir
    the documents build will use, then confirm the build leaves it
    byte-for-byte unchanged (the production file this stands in for is
    never touched, even though it shares a directory with the new
    la_documents_index.db)."""
    corpus_path = os.path.join(tmp_path, "merged_corpus.jsonl")
    _write_fixture_corpus(corpus_path, [
        _rec("edh:SHORT1", "edh", [_line(1, "Dis Manibus")]),
    ])
    texts_root = os.path.join(tmp_path, "texts_documents")
    process_corpus(corpus_path, texts_root)

    index_dir = os.path.join(tmp_path, "data_inverted_index")
    os.makedirs(index_dir, exist_ok=True)
    fake_literary_db = os.path.join(index_dir, "la_index.db")
    fake_content = b"NOT A REAL INDEX -- SENTINEL CONTENT\x00\x01"
    with open(fake_literary_db, "wb") as f:
        f.write(fake_content)
    before_mtime = os.path.getmtime(fake_literary_db)

    build_one_language("la", texts_root, index_dir,
                        os.path.join(tmp_path, "cache"),
                        os.path.join(tmp_path, "scratch"),
                        fast_greek=True, verbose=False)

    with open(fake_literary_db, "rb") as f:
        after_content = f.read()
    assert after_content == fake_content
    assert os.path.getmtime(fake_literary_db) == before_mtime
    # And the real deliverable landed beside it under its own name.
    assert os.path.exists(os.path.join(index_dir, "la_documents_index.db"))


def test_build_refuses_a_var_www_index_dir(tmp_path):
    corpus_path = os.path.join(tmp_path, "merged_corpus.jsonl")
    _write_fixture_corpus(corpus_path, [_rec("edh:SHORT1", "edh", [_line(1, "x")])])
    texts_root = os.path.join(tmp_path, "texts_documents")
    process_corpus(corpus_path, texts_root)
    with pytest.raises(RuntimeError):
        build_one_language("la", texts_root, "/var/www/tesseraev6_flask/data/inverted_index",
                            os.path.join(tmp_path, "cache"), os.path.join(tmp_path, "scratch"),
                            verbose=False)
