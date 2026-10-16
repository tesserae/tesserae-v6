"""The documents findspot (place) filter: doc_place on /api/line-search and
/api/documents/browse, and the place list at /api/documents/places. Same
fixture style as tests/test_documents_kind_filter.py."""
import json
import os
import sqlite3
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scripts.documents.build_documents_index import build_one_language
from scripts.documents.write_document_tess import process_corpus

import backend.documents as docs
import backend.documents_browse as browse_mod
from backend.app import app


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





ROWS = [
    # id, source, ancient, modern, region, date_not_before, date_not_after
    ("edh:R1", "edh", "Rusellae", "Roselle", "Etruria (Regio VII)", 50, 100),
    ("edh:R2", "edh", "Rusellae, bei", "Grosseto", "Etruria (Regio VII)", 150, 200),
    ("edr:R3", "edr", "Rusellae?", "Roselle", "Etruria (Regio VII)", 150, 200),
    ("edh:C1", "edh", "Cosa", "Orbetello", "Etruria (Regio VII)", 50, 100),
    ("edh:T1", "edh", "Torviscosa", "Torviscosa", "Aquileia (Regio X)", 50, 100),
    ("edh:M1", "edh", None, "Roselle (Grosseto)", "Etruria (Regio VII)", 50, 100),
    ("papyri:K1", "papyri", "Karanis (Arsinoites)", None, None, 50, 100),
]


@pytest.fixture
def place_env(tmp_path, monkeypatch):
    corpus_path = os.path.join(tmp_path, "merged_corpus.jsonl")
    _write_fixture_corpus(corpus_path, [
        _rec(r[0], r[1], [_line(1, "Dis Manibus")], region="x") for r in ROWS])
    texts_root = os.path.join(tmp_path, "texts_documents")
    process_corpus(corpus_path, texts_root)
    index_dir = os.path.join(tmp_path, "inverted_index")
    build_one_language("la", texts_root, index_dir,
                        os.path.join(tmp_path, "cache_lemmas_documents"),
                        os.path.join(tmp_path, "scratch"),
                        fast_greek=True, verbose=False)
    metadata_db = os.path.join(tmp_path, "metadata.db")
    _make_metadata_db(metadata_db, [
        {"id": r[0], "collection": "documents", "source": r[1], "ancient_place": r[2],
         "modern_place": r[3], "region": r[4], "date_not_before": r[5], "date_not_after": r[6]}
        for r in ROWS])
    conn = sqlite3.connect(metadata_db)
    conn.execute("ALTER TABLE documents ADD COLUMN languages TEXT")
    conn.execute("UPDATE documents SET languages = 'la'")
    conn.commit()
    conn.close()
    monkeypatch.setenv("TESSERAE_DOCUMENTS", "1")
    monkeypatch.setenv("TESSERAE_DOCUMENTS_INDEX_DIR", index_dir)
    monkeypatch.setenv("TESSERAE_DOCUMENTS_META", metadata_db)
    monkeypatch.setenv("TESSERAE_DOCUMENTS_RESTORED_DIR", os.path.join(tmp_path, "restored"))
    docs.reset_caches()
    browse_mod.reset_cache()
    yield
    docs.reset_caches()
    browse_mod.reset_cache()


def _ids(params):
    r = app.test_client().post('/api/line-search', json=dict(params, max_results=50))
    assert r.status_code == 200
    return {x['doc_id'] for x in r.get_json()['results'] if x.get('collection') == 'documents'}


BASE = {'query': 'dis manibus', 'language': 'la', 'collection': 'documents'}
RUSELLAE = {'edh:R1', 'edh:R2', 'edr:R3'}


def test_place_matches_the_town_its_variants_and_the_modern_name():
    assert docs.place_matches('Rusellae', 'Rusellae, bei', None)
    assert docs.place_matches('rusellae', 'Rusellae?', None)
    assert docs.place_matches('Roselle', None, 'Roselle (Grosseto)')
    assert docs.place_matches('Karanis', 'Karanis (Arsinoites)', None)
    assert not docs.place_matches('Cosa', 'Torviscosa', 'Torviscosa')
    assert not docs.place_matches('Cos', 'Cosa', None)
    assert docs.place_matches('', 'Anything', None)


def test_search_without_a_place_returns_everything(place_env):
    assert len(_ids(BASE)) == len(ROWS)


def test_search_place_finds_documents_found_there(place_env):
    # R1/R2/R3 by ancient name, M1 by its modern name only when asked for it.
    assert _ids(dict(BASE, doc_place='Rusellae')) == RUSELLAE
    assert _ids(dict(BASE, doc_place='rusellae')) == RUSELLAE


def test_search_place_matches_either_column(place_env):
    assert _ids(dict(BASE, doc_place='Roselle')) == {'edh:R1', 'edr:R3', 'edh:M1'}


def test_search_place_cosa_leaves_out_torviscosa(place_env):
    assert _ids(dict(BASE, doc_place='Cosa')) == {'edh:C1'}


def test_search_place_combines_with_region_and_date(place_env):
    assert _ids(dict(BASE, doc_place='Rusellae', region='Etruria')) == RUSELLAE
    assert _ids(dict(BASE, doc_place='Rusellae', region='Aquileia')) == set()
    assert _ids(dict(BASE, doc_place='Rusellae', date_from=140)) == {'edh:R2', 'edr:R3'}
    assert _ids(dict(BASE, doc_place='Rusellae', date_to=120)) == {'edh:R1'}


def test_search_place_works_for_both_collections_and_is_ignored_without_documents(place_env):
    assert _ids(dict(BASE, collection='both', doc_place='Cosa')) == {'edh:C1'}
    r = app.test_client().post('/api/line-search', json={
        'query': 'arma virum', 'language': 'la', 'doc_place': 'Cosa'})
    assert r.status_code == 200


def test_browse_place_narrows_every_count(place_env):
    r = app.test_client().get('/api/documents/browse?doc_place=Rusellae')
    d = r.get_json()
    assert d['total'] == 3
    assert {e['value']: e['count'] for e in d['kind_counts']} == {'inscriptions': 3}
    assert {x['doc_id'] for x in d['documents']} == RUSELLAE
    assert app.test_client().get('/api/documents/browse?doc_place=Cosa').get_json()['total'] == 1
    assert app.test_client().get('/api/documents/browse').get_json()['total'] == len(ROWS)


def test_browse_place_narrows_papyri_findspot_counts(place_env):
    d = app.test_client().get('/api/documents/browse?kind=papyri&region=Arsinoites&doc_place=Karanis').get_json()
    assert d['total'] == 1
    assert {e['value']: e['count'] for e in d['findspot_counts']} == {'Karanis': 1}


def test_place_list_merges_variants_and_gives_modern_names(place_env):
    d = app.test_client().get('/api/documents/places?language=la').get_json()
    by_value = {p['value']: p for p in d['places']}
    assert by_value['Rusellae']['count'] == 3
    assert by_value['Rusellae']['label'] == 'Rusellae (Roselle)'
    assert by_value['Cosa']['label'] == 'Cosa (Orbetello)'
    # A document with no ancient name is listed under its modern one.
    assert 'Roselle' in by_value
    counts = [p['count'] for p in d['places']]
    assert counts == sorted(counts, reverse=True)
    assert d['total'] == len(d['places'])


def test_place_list_search_and_limit(place_env):
    d = app.test_client().get('/api/documents/places?q=ROSE&limit=1').get_json()
    assert d['total'] == 2          # Rusellae (Roselle) and Roselle
    assert len(d['places']) == 1
    # the name that begins with the text comes before one that merely contains it
    assert d['places'][0]['value'] == 'Roselle'
    d = app.test_client().get('/api/documents/places?q=ROSE').get_json()
    assert [p['value'] for p in d['places']] == ['Roselle', 'Rusellae']
    assert app.test_client().get('/api/documents/places?q=zzzz').get_json()['places'] == []


def test_place_list_follows_the_language(place_env):
    d = app.test_client().get('/api/documents/places?language=grc').get_json()
    assert d['places'] == []


def test_place_list_is_404_with_documents_off(place_env, monkeypatch):
    monkeypatch.setenv("TESSERAE_DOCUMENTS", "0")
    assert app.test_client().get('/api/documents/places').status_code == 404
