"""Unit tests for backend/documents.py (stage 3b-2), against a tiny fixture
documents index + metadata db + sidecar, built the same way
tests/test_build_documents_index.py builds its own fixture index (reusing
write_document_tess.process_corpus + build_documents_index.build_one_language
so this exercises the REAL build path, not a hand-rolled schema).

No corpus data, no network; the only "heavy" dependency is the repo's own
vendored Latin lemma table (the same one test_build_documents_index.py
already relies on).
"""
import json
import os
import sqlite3
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scripts.documents.build_documents_index import build_one_language
from scripts.documents.write_document_tess import process_corpus

import backend.documents as docs


def _write_fixture_corpus(path, records):
    with open(path, "w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def _flags(n):
    return [False] * n


def _rec(doc_id, source, lines, languages=("la",), region="testregio"):
    return {"id": doc_id, "source": source, "tm_id": 1, "languages": list(languages),
            "findspot": {"region": region}, "date_not_before": None, "lines": lines}


def _line(n, text):
    return {"n": str(n), "text": text, "diplomatic": text,
            "restored_flags": _flags(len(text)), "joins_previous": False}


def _make_metadata_db(path, rows):
    """A tiny metadata.db with just the columns backend.documents.meta reads.
    One dict per row; `id` is required."""
    conn = sqlite3.connect(path)
    conn.execute(
        "CREATE TABLE documents ("
        "id TEXT PRIMARY KEY, collection TEXT, source TEXT, "
        "licence_name TEXT, licence_url TEXT, source_name TEXT, source_url TEXT, "
        "licence_name_secondary TEXT, licence_url_secondary TEXT, "
        "source_name_secondary TEXT, source_url_secondary TEXT, "
        "principal_edition TEXT, text_type_label TEXT, object_type_label TEXT, "
        "material_label TEXT, date_not_before INTEGER, date_not_after INTEGER, "
        "ancient_place TEXT, modern_place TEXT, region TEXT, pleiades_id TEXT)"
    )
    for row in rows:
        cols = ", ".join(row.keys())
        placeholders = ", ".join("?" for _ in row)
        conn.execute(f"INSERT INTO documents ({cols}) VALUES ({placeholders})",  # nosec B608
                     list(row.values()))
    conn.commit()
    conn.close()


@pytest.fixture
def fixture_env(tmp_path, monkeypatch):
    """Builds a tiny la_documents_index.db (one short doc, one 3-line long
    doc), a matching metadata.db row for the short doc only (the long doc
    is deliberately left uncredited, to exercise the "no metadata" path),
    and a hand-written sidecar marking one restored token on the short
    doc's own line. Points backend.documents at all three via env vars and
    resets its caches before and after, so no state leaks between tests or
    into any other test module that imports backend.documents."""
    corpus_path = os.path.join(tmp_path, "merged_corpus.jsonl")
    _write_fixture_corpus(corpus_path, [
        _rec("edh:SHORT1", "edh", [_line(1, "Dis Manibus")]),
        _rec("edh:LONG1", "edh", [_line(i, f"verbum numero {i}") for i in range(1, 4)]),
    ])
    texts_root = os.path.join(tmp_path, "texts_documents")
    process_corpus(corpus_path, texts_root)

    index_dir = os.path.join(tmp_path, "inverted_index")
    build_one_language("la", texts_root, index_dir,
                        os.path.join(tmp_path, "cache_lemmas_documents"),
                        os.path.join(tmp_path, "scratch"),
                        fast_greek=True, verbose=False)

    metadata_db = os.path.join(tmp_path, "metadata.db")
    _make_metadata_db(metadata_db, [{
        "id": "edh:SHORT1", "collection": "documents", "source": "edh",
        "licence_name": "CC BY-SA 4.0", "licence_url": "https://example.org/by-sa",
        "source_name": "Epigraphic Database Heidelberg",
        "source_url": "https://edh.example.org/HD000001",
        "licence_name_secondary": None, "licence_url_secondary": None,
        "source_name_secondary": None, "source_url_secondary": None,
        "principal_edition": "CIL 00, 0000", "text_type_label": "dedicatory inscription",
        "object_type_label": "altar", "material_label": "marble",
        "date_not_before": 101, "date_not_after": 200,
        "ancient_place": "Testopolis", "modern_place": "Test City",
        "region": "Testregio", "pleiades_id": "123456",
    }])

    sidecar_dir = os.path.join(tmp_path, "restored", "la")
    os.makedirs(sidecar_dir, exist_ok=True)
    sidecar_path = os.path.join(sidecar_dir, "edh__testregio.restored_words.jsonl")
    with open(sidecar_path, "w", encoding="utf-8") as f:
        f.write(json.dumps({"ref": "edh:SHORT1", "restored": [0], "fragment": []}) + "\n")
        f.write(json.dumps({"ref": "edh:LONG1 1", "restored": [], "fragment": [2]}) + "\n")

    monkeypatch.setenv("TESSERAE_DOCUMENTS", "1")
    monkeypatch.setenv("TESSERAE_DOCUMENTS_INDEX_DIR", index_dir)
    monkeypatch.setenv("TESSERAE_DOCUMENTS_META", metadata_db)
    monkeypatch.setenv("TESSERAE_DOCUMENTS_RESTORED_DIR", os.path.join(tmp_path, "restored"))
    docs.reset_caches()
    yield index_dir, metadata_db
    docs.reset_caches()


def test_enabled_reads_env_var_live(monkeypatch):
    monkeypatch.delenv("TESSERAE_DOCUMENTS", raising=False)
    assert docs.enabled() is False
    monkeypatch.setenv("TESSERAE_DOCUMENTS", "1")
    assert docs.enabled() is True
    monkeypatch.setenv("TESSERAE_DOCUMENTS", "0")
    assert docs.enabled() is False


def test_is_index_available(fixture_env):
    assert docs.is_index_available("la") is True
    assert docs.is_index_available("grc") is False  # fixture built Latin only


def test_doc_for_short_and_long_document(fixture_env):
    bucket = "edh__testregio.tess"
    assert docs.doc_for("la", bucket, "edh:SHORT1") == "edh:SHORT1"
    assert docs.doc_for("la", bucket, "edh:LONG1 1") == "edh:LONG1"
    assert docs.doc_for("la", bucket, "edh:LONG1 3") == "edh:LONG1"


def test_doc_for_unknown_ref_returns_none(fixture_env):
    bucket = "edh__testregio.tess"
    assert docs.doc_for("la", bucket, "edh:NOPE 1") is None


def test_meta_returns_credit_date_place_labels_for_known_doc(fixture_env):
    m = docs.meta("edh:SHORT1")
    assert m is not None
    assert m["credit"]["source_name"] == "Epigraphic Database Heidelberg"
    assert m["credit"]["licence_name"] == "CC BY-SA 4.0"
    assert m["credit"]["principal_edition"] == "CIL 00, 0000"
    assert m["date_not_before"] == 101
    assert m["date_not_after"] == 200
    assert m["region"] == "Testregio"
    assert m["text_type_label"] == "dedicatory inscription"
    assert m["material_label"] == "marble"


def test_meta_returns_none_for_doc_with_no_metadata_row(fixture_env):
    # edh:LONG1 is in the index's own doc_meta but has NO row in metadata.db
    # -- the uncredited-hit path a document result must still handle.
    assert docs.meta("edh:LONG1") is None


def test_meta_returns_none_when_metadata_db_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("TESSERAE_DOCUMENTS_META", os.path.join(tmp_path, "does_not_exist.db"))
    docs.reset_caches()
    assert docs.meta("anything") is None
    docs.reset_caches()


def test_restored_indices_from_sidecar(fixture_env):
    bucket = "edh__testregio.tess"
    r = docs.restored_indices("la", bucket, "edh:SHORT1")
    assert r == {"restored": [0], "fragment": []}
    r2 = docs.restored_indices("la", bucket, "edh:LONG1 1")
    assert r2 == {"restored": [], "fragment": [2]}


def test_restored_indices_empty_for_ref_with_no_sidecar_entry(fixture_env):
    bucket = "edh__testregio.tess"
    r = docs.restored_indices("la", bucket, "edh:LONG1 2")
    assert r == {"restored": [], "fragment": []}


def test_restored_indices_empty_when_sidecar_file_missing(fixture_env):
    r = docs.restored_indices("la", "no_such_bucket.tess", "edh:SHORT1")
    assert r == {"restored": [], "fragment": []}


def test_find_co_occurring_lemmas_finds_the_short_document(fixture_env):
    # Discover the real lemmas the fixture build assigned "Dis Manibus" to,
    # from the index's own postings table, rather than hardcoding a guess
    # at what the Latin lemmatizer does with this phrase.
    conn = sqlite3.connect(os.path.join(fixture_env[0], "la_documents_index.db"))
    lemmas = [r[0] for r in conn.execute(
        "SELECT DISTINCT lemma FROM postings p JOIN lines l "
        "ON p.text_id = l.text_id AND p.ref = l.ref WHERE l.ref = ?",
        ("edh:SHORT1",)).fetchall()]
    conn.close()
    assert len(lemmas) >= 2, "fixture line should index at least two lemmas"

    candidates = docs.find_co_occurring_lemmas(lemmas[:2], "la", min_matches=2)
    refs = {(fn, ref) for fn, ref, _lem, _pos in candidates}
    assert ("edh__testregio.tess", "edh:SHORT1") in refs


def test_find_co_occurring_lemmas_returns_empty_without_index(tmp_path, monkeypatch):
    monkeypatch.setenv("TESSERAE_DOCUMENTS_INDEX_DIR", str(tmp_path))
    docs.reset_caches()
    assert docs.find_co_occurring_lemmas(["anything"], "la", min_matches=1) == []
    docs.reset_caches()


def test_get_lines_batch_and_has_lines_data(fixture_env):
    bucket = "edh__testregio.tess"
    assert docs.has_lines_data("la") is True
    batch = docs.get_lines_batch(bucket, ["edh:SHORT1"], "la")
    assert "edh:SHORT1" in batch
    assert batch["edh:SHORT1"]["text"] == "Dis Manibus"


def test_get_corpus_version_is_a_date_string(fixture_env):
    v = docs.get_corpus_version("la")
    assert v is not None
    assert len(v) == 10 and v[4] == "-" and v[7] == "-"


def test_get_connection_returns_none_for_unbuilt_language(fixture_env):
    assert docs.get_connection("grc") is None


# --------------------------------------------------------------------------
# get_document_lines (stage 3b-3): the document Reader view's own data
# --------------------------------------------------------------------------

def test_get_document_lines_returns_the_single_line_short_document(fixture_env):
    r = docs.get_document_lines("la", "edh:SHORT1")
    assert r is not None
    assert r["filename"] == "edh__testregio.tess"
    assert [l["ref"] for l in r["lines"]] == ["edh:SHORT1"]
    assert r["lines"][0]["text"] == "Dis Manibus"
    # The sidecar (fixture_env) marks token 0 restored on this exact ref.
    assert r["lines"][0]["restored_indices"] == [0]
    assert r["lines"][0]["fragment_indices"] == []


def test_get_document_lines_returns_the_packed_short_doc_as_one_slash_joined_line(fixture_env):
    # edh:LONG1 has 3 source lines, still <= SHORT_LINE_THRESHOLD (10): the
    # real build packs every "short" document into ONE .tess line (source
    # lines joined with " / "), not one .tess line per source line -- see
    # write_document_tess.build_short_doc_unit. This is the behavior the
    # fixture's OWN name ("LONG1") suggested but the real pipeline does not
    # give until a document exceeds the threshold (next test).
    r = docs.get_document_lines("la", "edh:LONG1")
    assert r is not None
    assert [l["ref"] for l in r["lines"]] == ["edh:LONG1"]
    assert r["lines"][0]["text"] == "verbum numero 1 / verbum numero 2 / verbum numero 3"


@pytest.fixture
def long_doc_env(tmp_path, monkeypatch):
    """A document with 12 source lines -- one more than
    write_document_tess.SHORT_LINE_THRESHOLD (10) -- so the real build
    classifies it "long" and writes one .tess row per source line, each
    its own ref ("<doc id> <1-based line number>"), exercising
    get_document_lines' multi-row rowid-bounded fetch for real instead of
    the single-row short-doc case every other fixture in this file covers."""
    corpus_path = os.path.join(tmp_path, "merged_corpus.jsonl")
    _write_fixture_corpus(corpus_path, [
        _rec("edh:LONGDOC", "edh", [_line(i, f"verbumnumero{i}") for i in range(1, 13)]),
    ])
    texts_root = os.path.join(tmp_path, "texts_documents")
    process_corpus(corpus_path, texts_root)

    index_dir = os.path.join(tmp_path, "inverted_index")
    build_one_language("la", texts_root, index_dir,
                        os.path.join(tmp_path, "cache_lemmas_documents"),
                        os.path.join(tmp_path, "scratch"),
                        fast_greek=True, verbose=False)

    monkeypatch.setenv("TESSERAE_DOCUMENTS", "1")
    monkeypatch.setenv("TESSERAE_DOCUMENTS_INDEX_DIR", index_dir)
    monkeypatch.setenv("TESSERAE_DOCUMENTS_META", os.path.join(tmp_path, "no_metadata.db"))
    monkeypatch.setenv("TESSERAE_DOCUMENTS_RESTORED_DIR", os.path.join(tmp_path, "restored"))
    docs.reset_caches()
    yield index_dir
    docs.reset_caches()


def test_get_document_lines_returns_every_row_of_a_true_long_document_in_order(long_doc_env):
    r = docs.get_document_lines("la", "edh:LONGDOC")
    assert r is not None
    assert [l["ref"] for l in r["lines"]] == [f"edh:LONGDOC {i}" for i in range(1, 13)]
    assert [l["text"] for l in r["lines"]] == [f"verbumnumero{i}" for i in range(1, 13)]
    # No restoration marked anywhere in this fixture (every restored_flags
    # entry is False) -- every line comes back with empty lists, not an
    # error, even though a per-bucket sidecar file does exist.
    assert all(l["restored_indices"] == [] and l["fragment_indices"] == [] for l in r["lines"])


def test_get_document_lines_returns_none_for_unknown_doc_id(fixture_env):
    assert docs.get_document_lines("la", "edh:NOPE") is None


def test_get_document_lines_returns_none_without_index(tmp_path, monkeypatch):
    monkeypatch.setenv("TESSERAE_DOCUMENTS_INDEX_DIR", str(tmp_path))
    docs.reset_caches()
    assert docs.get_document_lines("la", "edh:SHORT1") is None
    docs.reset_caches()


def test_get_document_lines_returns_none_for_empty_doc_id(fixture_env):
    assert docs.get_document_lines("la", "") is None


# --------------------------------------------------------------------------
# display_fields (stage 3b-3): the display Reader panel's own data
# --------------------------------------------------------------------------

def test_display_fields_returns_none_when_display_table_missing(fixture_env):
    # fixture_env's own _make_metadata_db builds only `documents`, matching
    # every OTHER test in this file -- the display table is new in 3b-3 and
    # deliberately exercised by its own metadata db below instead, so this
    # confirms the graceful-miss path a metadata.db built before stage 3a's
    # display table existed would hit.
    assert docs.display_fields("edh:SHORT1") is None


def test_display_fields_returns_none_when_metadata_db_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("TESSERAE_DOCUMENTS_META", os.path.join(tmp_path, "does_not_exist.db"))
    docs.reset_caches()
    assert docs.display_fields("anything") is None
    docs.reset_caches()


def _make_metadata_db_with_display(path, display_rows):
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE documents (id TEXT PRIMARY KEY)")
    conn.execute("CREATE TABLE display (id TEXT, field TEXT, value TEXT)")
    for doc_id, field, value in display_rows:
        conn.execute("INSERT INTO display (id, field, value) VALUES (?, ?, ?)",
                     (doc_id, field, value))
    conn.commit()
    conn.close()


def test_display_fields_groups_image_url_as_a_list_and_others_as_scalars(tmp_path, monkeypatch):
    db_path = os.path.join(tmp_path, "metadata.db")
    _make_metadata_db_with_display(db_path, [
        ("edh:SHORT1", "museum", "Test City, Mus. Civico"),
        ("edh:SHORT1", "inventory", "inv. 42"),
        ("edh:SHORT1", "image_url", "https://example.org/a.jpg"),
        ("edh:SHORT1", "image_url", "https://example.org/b.jpg"),
        ("edh:LONG1", "museum", "Other Museum"),
    ])
    monkeypatch.setenv("TESSERAE_DOCUMENTS_META", db_path)
    docs.reset_caches()
    d = docs.display_fields("edh:SHORT1")
    assert d["museum"] == "Test City, Mus. Civico"
    assert d["inventory"] == "inv. 42"
    assert d["image_url"] == ["https://example.org/a.jpg", "https://example.org/b.jpg"]
    assert "layout_note" not in d
    docs.reset_caches()


def test_display_fields_returns_empty_dict_for_doc_with_no_display_rows(tmp_path, monkeypatch):
    db_path = os.path.join(tmp_path, "metadata.db")
    _make_metadata_db_with_display(db_path, [("edh:LONG1", "museum", "Other Museum")])
    monkeypatch.setenv("TESSERAE_DOCUMENTS_META", db_path)
    docs.reset_caches()
    assert docs.display_fields("edh:SHORT1") == {}
    docs.reset_caches()
