"""The documents page's Kind switch (kind=inscriptions|papyri on
/api/line-search) and the case-insensitive text-type/material matching the
page's merged drop-down options rely on. Same fixture style as
tests/test_documents_stage3b3.py: a tiny real documents index, driven
through the real Flask app.
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
from backend.app import app, _document_passes_filters


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
    conn.execute("CREATE TABLE display (id TEXT, field TEXT, value TEXT)")
    for row in rows:
        cols = ", ".join(row.keys())
        placeholders = ", ".join("?" for _ in row)
        conn.execute(f"INSERT INTO documents ({cols}) VALUES ({placeholders})",  # nosec B608
                     list(row.values()))
    conn.execute("INSERT INTO display (id, field, value) VALUES (?, ?, ?)",
                 ("edh:F1", "museum", "Test City, Mus. Civico"))
    conn.execute("INSERT INTO display (id, field, value) VALUES (?, ?, ?)",
                 ("edh:F1", "image_url", "https://example.org/f1-a.jpg"))
    conn.execute("INSERT INTO display (id, field, value) VALUES (?, ?, ?)",
                 ("edh:F1", "image_url", "https://example.org/f1-b.jpg"))
    conn.commit()
    conn.close()




@pytest.fixture
def kind_env(tmp_path, monkeypatch):
    corpus_path = os.path.join(tmp_path, "merged_corpus.jsonl")
    _write_fixture_corpus(corpus_path, [
        _rec("edh:K1", "edh", [_line(1, "Dis Manibus")]),
        _rec("edr:K2", "edr", [_line(1, "Dis Manibus")]),
        _rec("papyri:K3", "papyri", [_line(1, "Dis Manibus")]),
    ])
    texts_root = os.path.join(tmp_path, "texts_documents")
    process_corpus(corpus_path, texts_root)
    index_dir = os.path.join(tmp_path, "inverted_index")
    build_one_language("la", texts_root, index_dir,
                        os.path.join(tmp_path, "cache_lemmas_documents"),
                        os.path.join(tmp_path, "scratch"),
                        fast_greek=True, verbose=False)
    metadata_db = os.path.join(tmp_path, "metadata.db")
    _make_metadata_db(metadata_db, [
        {"id": "edh:K1", "collection": "documents", "source": "edh", "region": "Testregio",
         "text_type_label": "Epitaph"},
        {"id": "edr:K2", "collection": "documents", "source": "edr", "region": "Testregio",
         "text_type_label": "epitaph"},
        {"id": "papyri:K3", "collection": "documents", "source": "papyri", "region": "Testregio",
         "text_type_label": "letter"},
    ])
    monkeypatch.setenv("TESSERAE_DOCUMENTS", "1")
    monkeypatch.setenv("TESSERAE_DOCUMENTS_INDEX_DIR", index_dir)
    monkeypatch.setenv("TESSERAE_DOCUMENTS_META", metadata_db)
    monkeypatch.setenv("TESSERAE_DOCUMENTS_RESTORED_DIR", os.path.join(tmp_path, "restored"))
    docs.reset_caches()
    yield
    docs.reset_caches()


def _ids(params):
    r = app.test_client().post('/api/line-search', json=dict(params, max_results=50))
    assert r.status_code == 200
    return {x['doc_id'] for x in r.get_json()['results'] if x.get('collection') == 'documents'}


BASE = {'query': 'dis manibus', 'language': 'la', 'collection': 'documents'}


def test_kind_omitted_returns_everything(kind_env):
    assert _ids(BASE) == {'edh:K1', 'edr:K2', 'papyri:K3'}


def test_kind_papyri_keeps_only_papyri(kind_env):
    assert _ids(dict(BASE, kind='papyri')) == {'papyri:K3'}


def test_kind_inscriptions_keeps_only_the_rest(kind_env):
    assert _ids(dict(BASE, kind='inscriptions')) == {'edh:K1', 'edr:K2'}


def test_unknown_kind_is_ignored(kind_env):
    assert _ids(dict(BASE, kind='both')) == {'edh:K1', 'edr:K2', 'papyri:K3'}


def test_one_text_type_label_finds_every_case_variant(kind_env):
    assert _ids(dict(BASE, text_type='Epitaph')) == {'edh:K1', 'edr:K2'}
    assert _ids(dict(BASE, text_type='epitaph')) == {'edh:K1', 'edr:K2'}


def test_region_accepts_the_browse_trees_normalized_label():
    papyrus = {'source': 'papyri', 'region': None, 'ancient_place': 'Karanis (Arsinoites)'}
    assert _document_passes_filters(papyrus, None, None, 'Arsinoites', '', '', '')
    assert not _document_passes_filters(papyrus, None, None, 'Oxyrhynchites', '', '', '')
    edh = {'source': 'edh', 'region': 'Latium et Campania cum insulis (Regio I)'}
    assert _document_passes_filters(edh, None, None, 'Latium et Campania (Regio I)', '', '', '')
    assert _document_passes_filters(edh, None, None, 'latium', '', '', '')   # free text still works
    sic = {'source': 'isicily', 'region': None}
    assert _document_passes_filters(sic, None, None, 'Sicilia', '', '', '')


def test_filter_function_kind_and_case():
    m = {'source': 'papyri', 'text_type_label': 'Honorific inscription'}
    assert _document_passes_filters(m, None, None, '', 'honorific inscription', '', '', 'papyri')
    assert not _document_passes_filters(m, None, None, '', '', '', '', 'inscriptions')
    assert _document_passes_filters(None, None, None, '', '', '', '', None)
