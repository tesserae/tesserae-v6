"""Unit tests for stage 3b-3: restoration marking/exclusion, the stock-
formula count/filter, and GET /api/documents/<doc_id> -- the backend.app
functions and route this stage added on top of stage 3b-2
(backend/documents.py, tested separately in tests/test_documents.py).

Builds a tiny fixture documents index the same way tests/test_documents.py
does (reusing write_document_tess.process_corpus +
build_documents_index.build_one_language, so this exercises the REAL build
path), then drives it through the real Flask app (backend.app.app) exactly
as a browser or the connector would, via /api/line-search and
/api/documents/<doc_id>. No corpus data, no network.
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
from backend.app import (
    app, _restoration_flags, _find_exact_phrase_positions,
    _normalize_token_for_phrase_match, DOCUMENTS_FORMULA_DEFAULT_N,
)


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
def documents_app_env(tmp_path, monkeypatch):
    """Three documents sharing "Dis Manibus" (a formula, by construction:
    formula_count will be 3), one standalone "Rara Avis" document (not a
    formula: formula_count 1), all Latin. F1 has BOTH its tokens ("Dis",
    "Manibus") marked restored (a match on it rests entirely on restored
    text); F2 has only token 1 ("Manibus") marked restored (a PARTIAL
    restoration -- not dropped by exclude_restored, unlike F1's fully-
    restored hit); F3 and RARE1 carry no restoration at all."""
    corpus_path = os.path.join(tmp_path, "merged_corpus.jsonl")
    _write_fixture_corpus(corpus_path, [
        _rec("edh:F1", "edh", [_line(1, "Dis Manibus")]),
        _rec("edh:F2", "edh", [_line(1, "Dis Manibus")]),
        _rec("edh:F3", "edh", [_line(1, "Dis Manibus")]),
        _rec("edh:RARE1", "edh", [_line(1, "Rara Avis")]),
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
        {"id": "edh:F1", "collection": "documents", "source": "edh",
         "principal_edition": "F1 ed.", "region": "Testregio"},
        {"id": "edh:F2", "collection": "documents", "source": "edh",
         "principal_edition": "F2 ed.", "region": "Testregio"},
        {"id": "edh:F3", "collection": "documents", "source": "edh",
         "principal_edition": "F3 ed.", "region": "Testregio"},
        {"id": "edh:RARE1", "collection": "documents", "source": "edh",
         "principal_edition": "Rare ed.", "region": "Testregio"},
    ])

    sidecar_dir = os.path.join(tmp_path, "restored", "la")
    os.makedirs(sidecar_dir, exist_ok=True)
    sidecar_path = os.path.join(sidecar_dir, "edh__testregio.restored_words.jsonl")
    with open(sidecar_path, "w", encoding="utf-8") as f:
        f.write(json.dumps({"ref": "edh:F1", "restored": [0, 1], "fragment": []}) + "\n")
        f.write(json.dumps({"ref": "edh:F2", "restored": [1], "fragment": []}) + "\n")
        f.write(json.dumps({"ref": "edh:F3", "restored": [], "fragment": []}) + "\n")
        f.write(json.dumps({"ref": "edh:RARE1", "restored": [], "fragment": []}) + "\n")

    monkeypatch.setenv("TESSERAE_DOCUMENTS", "1")
    monkeypatch.setenv("TESSERAE_DOCUMENTS_INDEX_DIR", index_dir)
    monkeypatch.setenv("TESSERAE_DOCUMENTS_META", metadata_db)
    monkeypatch.setenv("TESSERAE_DOCUMENTS_RESTORED_DIR", os.path.join(tmp_path, "restored"))
    docs.reset_caches()
    yield
    docs.reset_caches()


def _post(params):
    client = app.test_client()
    body = dict(params)
    body.setdefault('max_results', 50)
    r = client.post('/api/line-search', json=body)
    return r


def _by_doc(results):
    return {r['doc_id']: r for r in results}


# --------------------------------------------------------------------------
# _restoration_flags / _find_exact_phrase_positions (pure helpers)
# --------------------------------------------------------------------------

def test_restoration_flags_all_restored():
    assert _restoration_flags([0, 1], {0, 1}) == (True, False)


def test_restoration_flags_partly_restored():
    assert _restoration_flags([0, 1], {0}) == (False, True)


def test_restoration_flags_none_restored():
    assert _restoration_flags([0, 1], set()) == (False, False)


def test_restoration_flags_no_position_info_is_never_restored():
    assert _restoration_flags([], {0, 1}) == (False, False)
    assert _restoration_flags(None, {0, 1}) == (False, False)


def test_find_exact_phrase_positions_locates_the_run():
    tokens = ["Dis", "Manibus", "Aureliae"]
    assert _find_exact_phrase_positions(tokens, "dis manibus") == [0, 1]


def test_find_exact_phrase_positions_allows_enclitic_on_last_word():
    tokens = ["arma", "virumque", "cano"]
    assert _find_exact_phrase_positions(tokens, "arma virum") == [0, 1]


def test_find_exact_phrase_positions_empty_when_not_found():
    tokens = ["Dis", "Manibus"]
    assert _find_exact_phrase_positions(tokens, "nusquam hic") == []


def test_find_exact_phrase_positions_empty_for_empty_input():
    assert _find_exact_phrase_positions([], "dis manibus") == []
    assert _find_exact_phrase_positions(["Dis", "Manibus"], "") == []


# --------------------------------------------------------------------------
# matched_restored / partly_restored on real document hits
# --------------------------------------------------------------------------

def test_fully_restored_hit_is_flagged(documents_app_env):
    r = _post({'query': 'dis manibus', 'language': 'la', 'collection': 'documents'})
    assert r.status_code == 200
    by_doc = _by_doc(r.get_json()['results'])
    assert by_doc['edh:F1']['matched_restored'] is True
    assert by_doc['edh:F1']['partly_restored'] is False


def test_partly_restored_hit_is_flagged_but_not_fully(documents_app_env):
    r = _post({'query': 'dis manibus', 'language': 'la', 'collection': 'documents'})
    by_doc = _by_doc(r.get_json()['results'])
    assert by_doc['edh:F2']['matched_restored'] is False
    assert by_doc['edh:F2']['partly_restored'] is True


def test_unrestored_hit_is_flagged_neither(documents_app_env):
    r = _post({'query': 'dis manibus', 'language': 'la', 'collection': 'documents'})
    by_doc = _by_doc(r.get_json()['results'])
    assert by_doc['edh:F3']['matched_restored'] is False
    assert by_doc['edh:F3']['partly_restored'] is False


def test_exact_search_also_marks_restoration(documents_app_env):
    r = _post({'query': 'dis manibus', 'language': 'la', 'collection': 'documents',
               'search_type': 'exact'})
    assert r.status_code == 200
    by_doc = _by_doc(r.get_json()['results'])
    assert by_doc['edh:F1']['matched_restored'] is True
    assert by_doc['edh:F3']['matched_restored'] is False


def test_regex_search_never_claims_restoration(documents_app_env):
    r = _post({'query': 'Dis.*', 'language': 'la', 'collection': 'documents',
               'search_type': 'regex'})
    assert r.status_code == 200
    results = r.get_json()['results']
    assert results  # the fixture's own "Dis Manibus" lines all match this pattern
    assert all(row['matched_restored'] is False and row['partly_restored'] is False
               for row in results)


# --------------------------------------------------------------------------
# exclude_restored
# --------------------------------------------------------------------------

def test_exclude_restored_drops_only_the_fully_restored_hit(documents_app_env):
    r = _post({'query': 'dis manibus', 'language': 'la', 'collection': 'documents',
               'exclude_restored': True})
    assert r.status_code == 200
    data = r.get_json()
    doc_ids = {row['doc_id'] for row in data['results']}
    assert doc_ids == {'edh:F2', 'edh:F3'}  # F1 (fully restored) dropped; F2 (partial) kept
    assert data['restored_excluded_count'] == 1


def test_exclude_restored_off_by_default(documents_app_env):
    r = _post({'query': 'dis manibus', 'language': 'la', 'collection': 'documents'})
    data = r.get_json()
    assert 'restored_excluded_count' not in data
    assert {row['doc_id'] for row in data['results']} == {'edh:F1', 'edh:F2', 'edh:F3'}


def test_exclude_restored_also_works_under_collection_both(documents_app_env):
    r = _post({'query': 'dis manibus', 'language': 'la', 'collection': 'both',
               'exclude_restored': True})
    assert r.status_code == 200
    data = r.get_json()
    doc_results = [row for row in data['results'] if row.get('collection') == 'documents']
    assert {row['doc_id'] for row in doc_results} == {'edh:F2', 'edh:F3'}
    assert data['restored_excluded_count'] == 1


# --------------------------------------------------------------------------
# formula_count / formula_summary / hide_formulas
# --------------------------------------------------------------------------

def test_formula_count_counts_distinct_sharing_documents(documents_app_env):
    r = _post({'query': 'dis manibus', 'language': 'la', 'collection': 'documents'})
    by_doc = _by_doc(r.get_json()['results'])
    assert by_doc['edh:F1']['formula_count'] == 3
    assert by_doc['edh:F2']['formula_count'] == 3
    assert by_doc['edh:F3']['formula_count'] == 3


def test_formula_count_is_one_for_a_standalone_phrase(documents_app_env):
    r = _post({'query': 'rara avis', 'language': 'la', 'collection': 'documents'})
    results = r.get_json()['results']
    assert len(results) == 1
    assert results[0]['formula_count'] == 1


def test_formula_summary_reports_the_whole_query(documents_app_env):
    r = _post({'query': 'dis manibus', 'language': 'la', 'collection': 'documents'})
    summary = r.get_json()['formula_summary']
    assert summary['documents_sharing_all'] == 3
    assert set(summary['query_lemmas']) <= set(summary['query_lemmas'])  # present, non-empty
    assert len(summary['query_lemmas']) >= 1


def test_hide_formulas_drops_the_formula_and_keeps_the_rare_phrase(documents_app_env):
    formula = _post({'query': 'dis manibus', 'language': 'la', 'collection': 'documents',
                      'hide_formulas': 2}).get_json()
    assert formula['results'] == []
    assert formula['formulas_hidden_count'] == 3

    rare = _post({'query': 'rara avis', 'language': 'la', 'collection': 'documents',
                   'hide_formulas': 2}).get_json()
    assert len(rare['results']) == 1
    assert rare['formulas_hidden_count'] == 0


def test_hide_formulas_off_by_default(documents_app_env):
    data = _post({'query': 'dis manibus', 'language': 'la', 'collection': 'documents'}).get_json()
    assert 'formulas_hidden_count' not in data
    assert len(data['results']) == 3


def test_hide_formulas_zero_is_a_valid_strict_threshold(documents_app_env):
    # hide_formulas=0 must be honored (not treated as falsy/off): every one
    # of these three hits shares its lemma pair with 2 OTHER documents, so
    # all are hidden at threshold 0.
    data = _post({'query': 'dis manibus', 'language': 'la', 'collection': 'documents',
                  'hide_formulas': 0}).get_json()
    assert data['results'] == []
    assert data['formulas_hidden_count'] == 3


def test_measured_default_n_separates_the_corpus_formula_from_the_rare_phrase(documents_app_env):
    # Sanity check on DOCUMENTS_FORMULA_DEFAULT_N itself (measured against
    # the real dev documents index; see its own comment in backend/app.py):
    # it must sit strictly between this fixture's formula (3 documents) and
    # the fixture's whole corpus size, and 1 (the rare phrase) must survive it.
    assert DOCUMENTS_FORMULA_DEFAULT_N > 3
    rare = _post({'query': 'rara avis', 'language': 'la', 'collection': 'documents',
                   'hide_formulas': DOCUMENTS_FORMULA_DEFAULT_N}).get_json()
    assert len(rare['results']) == 1


# --------------------------------------------------------------------------
# GET /api/documents/<doc_id>
# --------------------------------------------------------------------------

def test_get_document_returns_lines_credit_and_display(documents_app_env):
    client = app.test_client()
    r = client.get('/api/documents/edh:F1?language=la')
    assert r.status_code == 200
    data = r.get_json()
    assert data['doc_id'] == 'edh:F1'
    assert data['language'] == 'la'
    assert [l['text'] for l in data['lines']] == ['Dis Manibus']
    assert data['lines'][0]['restored_indices'] == [0, 1]
    assert data['credit']['principal_edition'] == 'F1 ed.'
    assert data['region'] == 'Testregio'
    assert data['display']['museum'] == 'Test City, Mus. Civico'
    assert data['display']['image_url'] == [
        'https://example.org/f1-a.jpg', 'https://example.org/f1-b.jpg']


def test_get_document_tries_every_language_when_none_given(documents_app_env):
    client = app.test_client()
    r = client.get('/api/documents/edh:F1')  # no ?language=
    assert r.status_code == 200
    assert r.get_json()['language'] == 'la'


def test_get_document_404_for_unknown_doc(documents_app_env):
    client = app.test_client()
    r = client.get('/api/documents/edh:NOPE')
    assert r.status_code == 404


def test_get_document_404_when_switch_is_off(documents_app_env, monkeypatch):
    monkeypatch.setenv('TESSERAE_DOCUMENTS', '0')
    client = app.test_client()
    r = client.get('/api/documents/edh:F1?language=la')
    assert r.status_code == 404


def test_get_document_404_for_wrong_language(documents_app_env):
    client = app.test_client()
    r = client.get('/api/documents/edh:F1?language=grc')  # fixture built Latin only
    assert r.status_code == 404
