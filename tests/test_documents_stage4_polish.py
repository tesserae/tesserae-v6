"""Unit tests for stage 4 (the owner's review of the live documents trial,
2026-10-08): relevance ranking and the sort control, uncapped totals and
50-row server-side paging, and the German label translation table.

Builds its own tiny fixture documents index the same way
tests/test_documents_stage3b3.py does (reusing write_document_tess.
process_corpus + build_documents_index.build_one_language, so this
exercises the REAL build path), then drives it through the real Flask app
exactly as a browser or the connector would, via /api/line-search. No
corpus data, no network.

NOTE on collection='both': a query that also runs the LITERARY search
(every test below uses collection='documents', not 'both') hits a
pre-existing slow path in this test sandbox's literary branch, unrelated
to this stage -- confirmed by reproducing it against an unmodified
backend/app.py/documents.py (git stash). Not exercised here; see the PR
description.
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
from backend.app import app, DOCUMENTS_FORMULA_DEFAULT_N  # noqa: F401 (kept for parity with sibling test files)


def _write_fixture_corpus(path, records):
    with open(path, "w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def _flags(n):
    return [False] * n


def _rec(doc_id, source, lines, region="testregio"):
    return {"id": doc_id, "source": source, "tm_id": 1, "languages": ["la"],
            "findspot": {"region": region}, "date_not_before": None, "lines": lines}


def _line(n, text):
    return {"n": str(n), "text": text, "diplomatic": text,
            "restored_flags": _flags(len(text)), "joins_previous": False}


_META_COLUMNS = (
    "id TEXT PRIMARY KEY, collection TEXT, source TEXT, "
    "licence_name TEXT, licence_url TEXT, source_name TEXT, source_url TEXT, "
    "licence_name_secondary TEXT, licence_url_secondary TEXT, "
    "source_name_secondary TEXT, source_url_secondary TEXT, "
    "principal_edition TEXT, text_type_label TEXT, object_type_label TEXT, "
    "material_label TEXT, date_not_before INTEGER, date_not_after INTEGER, "
    "ancient_place TEXT, modern_place TEXT, region TEXT, pleiades_id TEXT"
)


def _make_metadata_db(path, rows):
    conn = sqlite3.connect(path)
    conn.execute(f"CREATE TABLE documents ({_META_COLUMNS})")  # nosec B608
    conn.execute("CREATE TABLE display (id TEXT, field TEXT, value TEXT)")
    for row in rows:
        cols = ", ".join(row.keys())
        placeholders = ", ".join("?" for _ in row)
        conn.execute(f"INSERT INTO documents ({cols}) VALUES ({placeholders})",  # nosec B608
                     list(row.values()))
    conn.commit()
    conn.close()


def _build_index(tmp_path, records):
    corpus_path = os.path.join(tmp_path, "merged_corpus.jsonl")
    _write_fixture_corpus(corpus_path, records)
    texts_root = os.path.join(tmp_path, "texts_documents")
    process_corpus(corpus_path, texts_root)
    index_dir = os.path.join(tmp_path, "inverted_index")
    build_one_language("la", texts_root, index_dir,
                        os.path.join(tmp_path, "cache_lemmas_documents"),
                        os.path.join(tmp_path, "scratch"),
                        fast_greek=True, verbose=False)
    return index_dir


def _point_env(monkeypatch, tmp_path, index_dir, metadata_db, sidecar_root=None):
    monkeypatch.setenv("TESSERAE_DOCUMENTS", "1")
    monkeypatch.setenv("TESSERAE_DOCUMENTS_INDEX_DIR", index_dir)
    monkeypatch.setenv("TESSERAE_DOCUMENTS_META", metadata_db)
    monkeypatch.setenv("TESSERAE_DOCUMENTS_RESTORED_DIR", sidecar_root or os.path.join(tmp_path, "restored"))
    docs.reset_caches()


def _post(params):
    client = app.test_client()
    body = dict(params)
    body.setdefault('collection', 'documents')
    body.setdefault('language', 'la')
    return client.post('/api/line-search', json=body)


# --------------------------------------------------------------------------
# Relevance ranking (default sort)
# --------------------------------------------------------------------------

@pytest.fixture
def ranking_env(tmp_path, monkeypatch):
    """Four "Dis Manibus" hits built to disagree on every ranking tier:
    A -- adjacent, unrestored (the best possible hit);
    D -- adjacent, partly restored (one of its two matched tokens);
    C -- adjacent, fully restored (both matched tokens);
    B -- SCATTERED ("Dis" ... "Manibus" with a word between), unrestored.
    Adjacency outranks restoration per the spec, so B (scattered but
    otherwise clean) must sort LAST, behind even C (adjacent but fully
    restored)."""
    index_dir = _build_index(tmp_path, [
        _rec("edh:A", "edh", [_line(1, "Dis Manibus")]),
        _rec("edh:B", "edh", [_line(1, "Dis magno Manibus")]),
        _rec("edh:C", "edh", [_line(1, "Dis Manibus")]),
        _rec("edh:D", "edh", [_line(1, "Dis Manibus")]),
    ])
    metadata_db = os.path.join(tmp_path, "metadata.db")
    _make_metadata_db(metadata_db, [
        {"id": "edh:A", "collection": "documents", "source": "edh", "principal_edition": "A"},
        {"id": "edh:B", "collection": "documents", "source": "edh", "principal_edition": "B"},
        {"id": "edh:C", "collection": "documents", "source": "edh", "principal_edition": "C"},
        {"id": "edh:D", "collection": "documents", "source": "edh", "principal_edition": "D"},
    ])
    sidecar_dir = os.path.join(tmp_path, "restored", "la")
    os.makedirs(sidecar_dir, exist_ok=True)
    with open(os.path.join(sidecar_dir, "edh__testregio.restored_words.jsonl"), "w", encoding="utf-8") as f:
        f.write(json.dumps({"ref": "edh:C", "restored": [0, 1], "fragment": []}) + "\n")
        f.write(json.dumps({"ref": "edh:D", "restored": [1], "fragment": []}) + "\n")
    _point_env(monkeypatch, tmp_path, index_dir, metadata_db)
    yield
    docs.reset_caches()


def test_relevance_ranks_adjacent_over_scattered_and_unrestored_over_restored(ranking_env):
    r = _post({'query': 'dis manibus'})
    assert r.status_code == 200
    data = r.get_json()
    order = [row['doc_id'] for row in data['results']]
    assert order == ['edh:A', 'edh:D', 'edh:C', 'edh:B']
    assert data['sort'] == 'relevance'


def test_relevance_is_the_default_sort(ranking_env):
    with_sort = _post({'query': 'dis manibus', 'sort': 'relevance'}).get_json()
    without_sort = _post({'query': 'dis manibus'}).get_json()
    assert [r['doc_id'] for r in with_sort['results']] == [r['doc_id'] for r in without_sort['results']]


def test_an_unrecognized_sort_value_falls_back_to_relevance(ranking_env):
    r = _post({'query': 'dis manibus', 'sort': 'nonsense'})
    data = r.get_json()
    assert data['sort'] == 'relevance'
    assert [row['doc_id'] for row in data['results']] == ['edh:A', 'edh:D', 'edh:C', 'edh:B']


# --------------------------------------------------------------------------
# oldest / newest / region sort
# --------------------------------------------------------------------------

@pytest.fixture
def dated_env(tmp_path, monkeypatch):
    """Three documents, same phrase, three different dates and regions."""
    index_dir = _build_index(tmp_path, [
        _rec("edh:OLD", "edh", [_line(1, "Dis Manibus")]),
        _rec("edh:MID", "edh", [_line(1, "Dis Manibus")]),
        _rec("edh:NEW", "edh", [_line(1, "Dis Manibus")]),
    ])
    metadata_db = os.path.join(tmp_path, "metadata.db")
    _make_metadata_db(metadata_db, [
        {"id": "edh:OLD", "collection": "documents", "source": "edh",
         "date_not_before": -100, "region": "Zeta"},
        {"id": "edh:MID", "collection": "documents", "source": "edh",
         "date_not_before": 50, "region": "Alpha"},
        {"id": "edh:NEW", "collection": "documents", "source": "edh",
         "date_not_before": 300, "region": "Mu"},
    ])
    _point_env(monkeypatch, tmp_path, index_dir, metadata_db)
    yield
    docs.reset_caches()


def test_sort_oldest_first(dated_env):
    r = _post({'query': 'dis manibus', 'sort': 'oldest'})
    assert [row['doc_id'] for row in r.get_json()['results']] == ['edh:OLD', 'edh:MID', 'edh:NEW']


def test_sort_newest_first(dated_env):
    r = _post({'query': 'dis manibus', 'sort': 'newest'})
    assert [row['doc_id'] for row in r.get_json()['results']] == ['edh:NEW', 'edh:MID', 'edh:OLD']


def test_sort_region_alphabetical(dated_env):
    r = _post({'query': 'dis manibus', 'sort': 'region'})
    assert [row['doc_id'] for row in r.get_json()['results']] == ['edh:MID', 'edh:NEW', 'edh:OLD']


def test_an_undated_hit_sorts_last_under_oldest_and_newest(tmp_path, monkeypatch):
    index_dir = _build_index(tmp_path, [
        _rec("edh:DATED", "edh", [_line(1, "Dis Manibus")]),
        _rec("edh:UNDATED", "edh", [_line(1, "Dis Manibus")]),
    ])
    metadata_db = os.path.join(tmp_path, "metadata.db")
    _make_metadata_db(metadata_db, [
        {"id": "edh:DATED", "collection": "documents", "source": "edh", "date_not_before": 1},
        {"id": "edh:UNDATED", "collection": "documents", "source": "edh"},
    ])
    _point_env(monkeypatch, tmp_path, index_dir, metadata_db)
    for sort in ('oldest', 'newest'):
        r = _post({'query': 'dis manibus', 'sort': sort})
        assert [row['doc_id'] for row in r.get_json()['results']] == ['edh:DATED', 'edh:UNDATED']
    docs.reset_caches()


# --------------------------------------------------------------------------
# Uncapped totals + 50-row server-side paging
# --------------------------------------------------------------------------

@pytest.fixture
def many_docs_env(tmp_path, monkeypatch):
    """62 distinct documents sharing "Dis Manibus" -- more than one page
    (50) and more than the old 500-row response could ever have needed to
    demonstrate the ceiling is gone, while staying fast to build."""
    n = 62
    records = [_rec(f"edh:P{i:03d}", "edh", [_line(1, "Dis Manibus")]) for i in range(n)]
    index_dir = _build_index(tmp_path, records)
    metadata_db = os.path.join(tmp_path, "metadata.db")
    _make_metadata_db(metadata_db, [
        {"id": f"edh:P{i:03d}", "collection": "documents", "source": "edh",
         "date_not_before": i} for i in range(n)
    ])
    _point_env(monkeypatch, tmp_path, index_dir, metadata_db)
    yield n
    docs.reset_caches()


def test_total_is_not_capped_at_500_or_at_the_page_size(many_docs_env):
    n = many_docs_env
    r = _post({'query': 'dis manibus'})
    data = r.get_json()
    assert data['total'] == n
    assert data['distinct_loci'] == n
    assert data['capped'] is False
    assert 'total_at_least' not in data
    assert len(data['results']) == 50          # default page size


def test_offset_and_limit_page_through_every_match(many_docs_env):
    n = many_docs_env
    page1 = _post({'query': 'dis manibus', 'offset': 0, 'limit': 50}).get_json()
    page2 = _post({'query': 'dis manibus', 'offset': 50, 'limit': 50}).get_json()
    assert len(page1['results']) == 50
    assert len(page2['results']) == n - 50
    ids1 = {row['doc_id'] for row in page1['results']}
    ids2 = {row['doc_id'] for row in page2['results']}
    assert not (ids1 & ids2)                     # no overlap
    assert len(ids1 | ids2) == n                 # every document covered exactly once
    assert page1['total'] == page2['total'] == n


def test_limit_is_clamped_to_fifty(many_docs_env):
    r = _post({'query': 'dis manibus', 'limit': 10000})
    assert len(r.get_json()['results']) == 50


def test_pagination_block_reports_offset_limit_and_total(many_docs_env):
    n = many_docs_env
    data = _post({'query': 'dis manibus', 'offset': 10, 'limit': 20}).get_json()
    assert data['pagination'] == {'offset': 10, 'limit': 20, 'total': n}


def test_distribution_by_century_sums_to_the_true_total(many_docs_env):
    n = many_docs_env
    data = _post({'query': 'dis manibus'}).get_json()
    by_century = data['documents_by_century']
    assert sum(c['count'] for c in by_century) == n
    # All 62 fixture dates (0..61) fall in the 1st century AD.
    assert by_century == [{'century': '1st c. AD', 'count': n}]


# --------------------------------------------------------------------------
# German label translation
# --------------------------------------------------------------------------

@pytest.fixture
def german_labels_env(tmp_path, monkeypatch):
    index_dir = _build_index(tmp_path, [
        _rec("edh:G1", "edh", [_line(1, "Dis Manibus")]),
        _rec("edh:G2", "edh", [_line(1, "Dis Manibus")]),
    ])
    metadata_db = os.path.join(tmp_path, "metadata.db")
    _make_metadata_db(metadata_db, [
        {"id": "edh:G1", "collection": "documents", "source": "edh",
         "region": "unbekannt", "ancient_place": "Theben (Ägypten)",
         "modern_place": "Kostolac, bei", "material_label": "szienit",
         "text_type_label": "unbekannt"},
        {"id": "edh:G2", "collection": "documents", "source": "edh",
         "region": "Roma", "ancient_place": "unbekannt", "modern_place": "unknown location"},
    ])
    _point_env(monkeypatch, tmp_path, index_dir, metadata_db)
    yield
    docs.reset_caches()


def test_german_words_are_translated_for_display(german_labels_env):
    data = _post({'query': 'dis manibus'}).get_json()
    by_doc = {row['doc_id']: row for row in data['results']}
    g1 = by_doc['edh:G1']
    assert g1['region'] == 'unknown'
    assert g1['ancient_place'] == 'Theben (Egypt)'
    assert g1['modern_place'] == 'Kostolac, near'
    assert g1['material_label'] == 'syenite'
    assert g1['text_type_label'] == 'unknown'


def test_an_unknown_place_marker_is_hidden_not_shown_translated(german_labels_env):
    data = _post({'query': 'dis manibus'}).get_json()
    by_doc = {row['doc_id']: row for row in data['results']}
    assert by_doc['edh:G2']['ancient_place'] is None   # raw value was 'unbekannt'
    assert by_doc['edh:G2']['modern_place'] is None    # raw value was 'unknown location'
    assert by_doc['edh:G2']['region'] == 'Roma'        # a real region is untouched


def test_the_original_metadata_db_value_is_never_modified(german_labels_env, tmp_path):
    # translate_label only ever touches the OUTGOING row; the database
    # file on disk keeps the raw German value.
    conn = sqlite3.connect(os.environ['TESSERAE_DOCUMENTS_META'])
    row = conn.execute("SELECT region FROM documents WHERE id = ?", ("edh:G1",)).fetchone()
    assert row[0] == 'unbekannt'
    conn.close()


def test_translate_label_leaves_a_real_german_place_name_alone():
    # Koeln/Mainz/Wien etc. are the place's own name, not a label to
    # translate -- see data/documents/german_label_translations.json.
    assert docs.translate_label('Köln') == 'Köln'
    assert docs.translate_label('Mainz') == 'Mainz'
    assert docs.translate_label('Roma') == 'Roma'


def test_translate_label_handles_the_bzw_abbreviation_without_a_stray_period():
    assert docs.translate_label('Alexandria bzw. Arsinoites') == 'Alexandria or Arsinoites'


def test_is_unknown_place_recognizes_german_english_and_latin_markers():
    assert docs.is_unknown_place('unbekannt') is True
    assert docs.is_unknown_place('unbekannt?') is True
    assert docs.is_unknown_place('unknown') is True
    assert docs.is_unknown_place('unknown location') is True
    assert docs.is_unknown_place('ignoratur') is True
    assert docs.is_unknown_place('Roma') is False
    assert docs.is_unknown_place(None) is False
