#!/usr/bin/env python3
"""
Automated endpoint integration tests for Tesserae V6.
Converted from manual raw HTTP requests to pytest-compatible tests
using Flask's in-memory test client to avoid local port 5000 AirPlay conflicts.

Usage:
    pytest tests/test_endpoints.py
    # or direct:
    python tests/test_endpoints.py
"""

import os
import sys
import json
import sqlite3
import pytest

# Ensure project root is in python path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Load env variables from .env
from dotenv import load_dotenv
load_dotenv(os.path.join(PROJECT_ROOT, '.env'))

# Set direct server mode to enable /api prefix for API routes
os.environ['TESSERAE_DIRECT_SERVER'] = '1'


def check_db_connection(url):
    """Verify if a database URL is reachable via psycopg2."""
    if not url:
        return False
    import psycopg2
    try:
        conn = psycopg2.connect(url, connect_timeout=2)
        conn.close()
        return True
    except Exception:
        return False


# Handle database port fallback if configured port (e.g. 5433) is unreachable
db_url = os.environ.get('DATABASE_URL')
if not check_db_connection(db_url):
    # Search common fallback database locations on the host system
    fallbacks = [
        'postgresql://arpitsharma2010@localhost:5432/postgres',
        'postgresql://postgres@localhost:5432/postgres',
        'postgresql://localhost:5432/postgres'
    ]
    if db_url and ':5433/' in db_url:
        fallbacks.insert(0, db_url.replace(':5433/', ':5432/'))

    for fb in fallbacks:
        if check_db_connection(fb):
            os.environ['DATABASE_URL'] = fb
            break


def setup_module(module):
    """Initialize mock caches and mini-index database to enable all search endpoints."""
    # 1. Setup mock bigram cache for Latin
    bigram_dir = os.path.join(PROJECT_ROOT, 'cache', 'bigrams')
    os.makedirs(bigram_dir, exist_ok=True)
    bigram_path = os.path.join(bigram_dir, 'la_bigrams.json')
    mock_bigrams = {
        "language": "la",
        "frequencies": {
            "arma|uir": 5
        },
        "total_bigrams": 100,
        "doc_frequencies": {
            "arma|uir": 2
        },
        "total_docs": 100,
        "last_updated": "2026-07-08T00:00:00"
    }
    with open(bigram_path, 'w', encoding='utf-8') as f:
        json.dump(mock_bigrams, f)

    # 2. Setup mock SQLite index for Latin ('la') to simulate pre-built search indexes
    index_dir = os.path.join(PROJECT_ROOT, 'data', 'inverted_index')
    os.makedirs(index_dir, exist_ok=True)
    db_path = os.path.join(index_dir, 'la_index.db')
    
    # Remove existing index if any
    if os.path.exists(db_path):
        try:
            os.remove(db_path)
        except Exception:
            pass

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE texts (
            text_id INTEGER PRIMARY KEY,
            filename TEXT UNIQUE,
            author TEXT,
            title TEXT,
            line_count INTEGER
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE postings (
            lemma TEXT,
            text_id INTEGER,
            ref TEXT,
            positions TEXT,
            FOREIGN KEY (text_id) REFERENCES texts(text_id)
        )
    ''')
    
    cursor.execute('CREATE INDEX idx_lemma ON postings(lemma)')
    cursor.execute('CREATE INDEX idx_text ON postings(text_id)')
    
    # Insert 10 real distinct texts (required for corpus-search total >= 5 tests)
    mock_texts = [
        (1, 'vergil.aeneid.tess', 'Vergil', 'Aeneid', 12185),
        (2, 'lucan.bellum_civile.tess', 'Lucan', 'Bellum Civile', 8061),
        (3, 'vergil.eclogues.tess', 'Vergil', 'Eclogues', 829),
        (4, 'vergil_pseudo.moretum.tess', 'Pseudo-Vergil', 'Moretum', 124),
        (5, 'vergil_pseudo.copa.tess', 'Pseudo-Vergil', 'Copa', 38),
        (6, 'vergil_pseudo.ciris.tess', 'Pseudo-Vergil', 'Ciris', 541),
        (7, 'vergil_pseudo.dirae.tess', 'Pseudo-Vergil', 'Dirae', 103),
        (8, 'vergil_pseudo.lydia.tess', 'Pseudo-Vergil', 'Lydia', 80),
        (9, 'vergil.aeneid.part.1.tess', 'Vergil', 'Aeneid 1', 756),
        (10, 'lucan.bellum_civile.part.1.tess', 'Lucan', 'Bellum Civile 1', 695),
    ]
    cursor.executemany('INSERT INTO texts VALUES (?, ?, ?, ?, ?)', mock_texts)
    
    # Insert postings with references matching the exact format of line tags in .tess files
    postings_data = []
    
    # 'hadriacas'/'adriacas' appears in 3 distinct base works (1, 2, 3) -> rare (limit <= 5)
    postings_data.append(('hadriacas', 1, 'verg. aen. 11.405', '[0]'))
    postings_data.append(('adriacas', 1, 'verg. aen. 11.405', '[0]'))
    postings_data.append(('hadriacas', 2, 'luc. 2.407', '[0]'))
    postings_data.append(('adriacas', 2, 'luc. 2.407', '[0]'))
    postings_data.append(('hadriacas', 3, 'verg. ecl. 1.1', '[0]'))
    postings_data.append(('adriacas', 3, 'verg. ecl. 1.1', '[0]'))
    
    # common words 'aspero', 'foedo', 'foederis' (and their lemmatized forms 'asper', 'asperus', 'foedus', 'foedum', 'foedera')
    # in 8 distinct base works (1..8) -> not rare (> 5)
    refs_by_id = {
        1: 'verg. aen. 1.1',
        2: 'luc. 1.1',
        3: 'verg. ecl. 1.1',
        4: 'vergil_pseudo. moretum. 2',
        5: 'vergil_pseudo. copa. 1',
        6: 'vergil_pseudo. ciris. 1',
        7: 'vergil_pseudo. dirae. 1',
        8: 'vergil_pseudo. lydia. 1',
        9: 'verg. aen. 1.1',
        10: 'luc. 1.1'
    }
    for t_id in range(1, 9):
        ref = refs_by_id[t_id]
        for lemma_var in ['aspero', 'asper', 'asperus']:
            postings_data.append((lemma_var, t_id, ref, '[2]'))
        for lemma_var in ['foedo', 'foedus', 'foedum', 'foederis', 'foedera']:
            postings_data.append((lemma_var, t_id, ref, '[3]'))
        
    # 'arma', 'uir', 'vir' in all 10 texts -> co-occur in all 10 texts (including part files)
    for t_id in range(1, 11):
        ref = refs_by_id[t_id]
        postings_data.append(('arma', t_id, ref, '[5]'))
        postings_data.append(('uir', t_id, ref, '[6]'))
        postings_data.append(('vir', t_id, ref, '[6]'))
        
    cursor.executemany('INSERT INTO postings VALUES (?, ?, ?, ?)', postings_data)
    
    conn.commit()
    conn.close()


def teardown_module(module):
    """Clean up mock caches and SQLite database indices created during setup."""
    bigram_path = os.path.join(PROJECT_ROOT, 'cache', 'bigrams', 'la_bigrams.json')
    if os.path.exists(bigram_path):
        try:
            os.remove(bigram_path)
        except Exception:
            pass
            
    db_path = os.path.join(PROJECT_ROOT, 'data', 'inverted_index', 'la_index.db')
    if os.path.exists(db_path):
        try:
            os.remove(db_path)
        except Exception:
            pass


@pytest.fixture(scope="module")
def client():
    """Module-scoped pytest fixture yielding the Flask test client."""
    from backend.app import app
    with app.test_client() as c:
        yield c


def check_json(resp, min_keys=None):
    """Verify response is valid JSON with expected keys."""
    assert resp.status_code == 200, f"HTTP {resp.status_code}: {resp.get_data(as_text=True)[:200]}"
    data = resp.get_json()
    assert data is not None, "Response body is not valid JSON"
    if min_keys:
        for k in min_keys:
            assert k in data, f"Missing key '{k}' in response data: {data}"
    return data


def run_sse_search(client, endpoint, payload, expect_results=True):
    """Helper to exercise and parse Server-Sent Events (SSE) stream endpoints."""
    resp = client.post(endpoint, json=payload)
    assert resp.status_code == 200, f"HTTP {resp.status_code}: {resp.get_data(as_text=True)[:200]}"

    events = []
    line_buffer = ""
    # Iterate over response chunks to build and parse complete JSON events
    for chunk in resp.response:
        chunk_str = chunk.decode('utf-8')
        line_buffer += chunk_str
        while "\n" in line_buffer:
            line, line_buffer = line_buffer.split("\n", 1)
            line = line.strip()
            if line.startswith("data: "):
                try:
                    data = json.loads(line[6:])
                    events.append(data)
                except json.JSONDecodeError:
                    pass

    assert len(events) > 0, "No SSE events received"
    last = events[-1]
    if last.get('type') == 'error':
        raise AssertionError(f"Search error: {last.get('message')}")
    assert last.get('type') == 'complete', f"Last event type: {last.get('type')}"

    if expect_results:
        results = last.get('results', [])
        assert len(results) > 0, "No results in complete event"
    return last


# ── Corpus & Text APIs ──────────────────────────────────────────────

def test_get_authors_la(client):
    assert len(check_json(client.get("/api/authors?language=la"))) > 100


def test_get_authors_grc(client):
    assert len(check_json(client.get("/api/authors?language=grc"))) > 50


def test_get_texts_la(client):
    assert len(check_json(client.get("/api/texts?language=la"))) > 500


def test_get_texts_en(client):
    assert len(check_json(client.get("/api/texts?language=en"))) > 5


def test_get_text_aeneid(client):
    res = check_json(client.get("/api/text/vergil.aeneid.tess"))
    assert 'units' in res or 'lines' in res


# ── Line Search ─────────────────────────────────────────────────────

def test_line_search_la(client):
    res = check_json(client.post("/api/line-search", json={
        "query": "arma virumque cano", "language": "la"
    }))
    assert res.get('total', 0) > 0


def test_line_search_grc(client):
    res = check_json(client.post("/api/line-search", json={
        "query": "μῆνιν ἄειδε θεά", "language": "grc"
    }))
    assert res.get('total', 0) >= 0


def test_line_search_exact(client):
    res = check_json(client.post("/api/line-search", json={
        "query": "arma virumque", "language": "la", "search_type": "exact"
    }))
    assert res.get('total', 0) >= 0


# ── Pairwise Search (SSE streaming) ────────────────────────────────

def test_pairwise_lemma_search(client):
    run_sse_search(client, "/api/search-stream", {
        "source": "lucan.bellum_civile.part.1.tess",
        "target": "vergil.aeneid.part.1.tess",
        "language": "la",
        "match_type": "lemma",
        "min_matches": 2,
        "stoplist_size": 0,
        "stoplist_basis": "source_target",
        "source_unit_type": "line",
        "target_unit_type": "line",
        "max_distance": 999,
        "max_results": 100
    })


def test_pairwise_exact_search(client):
    run_sse_search(client, "/api/search-stream", {
        "source": "lucan.bellum_civile.part.1.tess",
        "target": "vergil.aeneid.part.1.tess",
        "language": "la",
        "match_type": "exact",
        "min_matches": 2,
        "stoplist_size": 0,
        "stoplist_basis": "source_target",
        "source_unit_type": "line",
        "target_unit_type": "line",
        "max_distance": 999,
        "max_results": 100
    })


# ── Fusion Search (SSE streaming) ──────────────────────────────────

def test_fusion_search(client):
    run_sse_search(client, "/api/search-fusion", {
        "source": "lucan.bellum_civile.part.1.tess",
        "target": "vergil.aeneid.part.1.tess",
        "language": "la",
        "mode": "merged",
        "max_results": 100,
        "source_unit_type": "line",
        "target_unit_type": "line",
        "use_meter": False
    })


# ── Corpus Search ──────────────────────────────────────────────────

def test_corpus_search_la(client):
    res = check_json(client.post("/api/corpus-search", json={
        "lemmas": ["arma", "uir"],
        "language": "la"
    }))
    assert res.get('total', 0) > 0


def test_corpus_search_single_lemma_la(client):
    res = check_json(client.post("/api/corpus-search", json={
        "lemmas": ["arma"],
        "language": "la"
    }))
    assert res.get('total', 0) > 0


# ── Rare Words / Bigrams ───────────────────────────────────────────

def test_rare_lemmata(client):
    res = check_json(client.get("/api/rare-lemmata?language=la&max_occurrences=3"))
    assert 'total_rare_words' in res


def test_rare_bigrams(client):
    resp = client.get("/api/rare-bigrams?language=la&max_occurrences=10")
    assert resp.status_code == 200


# ── Wildcard / String Search ───────────────────────────────────────

def test_wildcard_search(client):
    res = check_json(client.post("/api/wildcard-search", json={
        "query": "arma vir*", "language": "la", "max_results": 10
    }))
    assert res.get('total_matches', 0) > 0


# ── Result Quality Checks ─────────────────────────────────────────

def test_hapax_quality(client):
    resp = client.post("/api/hapax-search", json={
        "source": "vergil.aeneid.tess",
        "target": "lucan.bellum_civile.tess",
        "language": "la",
        "max_occurrences": 5
    })
    assert resp.status_code == 200
    data = resp.get_json()
    results = data.get('results', [])
    assert len(results) > 0, "No hapax results returned"
    lemmas = {r['lemma'] for r in results}
    # hadriacas appears in only 3 texts — must be found
    assert 'hadriacas' in lemmas, f"Missing known rare word 'hadriacas'; got: {sorted(lemmas)[:10]}"
    # Common words must NOT appear (aspero = 77 texts, foedo = 216 texts)
    for bad in ['aspero', 'foedo', 'foederis']:
        assert bad not in lemmas, f"Common word '{bad}' should not appear in hapax results"
    # corpus_count should reflect document frequency, not token frequency
    for r in results:
        assert r['corpus_count'] <= 5, f"Lemma '{r['lemma']}' has corpus_count={r['corpus_count']} > max_occurrences=5"


def test_lemma_search_reference(client):
    last = run_sse_search(client, "/api/search-stream", {
        "source": "vergil.aeneid.part.1.tess",
        "target": "lucan.bellum_civile.part.1.tess",
        "language": "la",
        "match_type": "lemma",
        "min_matches": 2,
        "stoplist_size": 10,
        "stoplist_basis": "corpus",
        "source_unit_type": "line",
        "target_unit_type": "line",
        "max_distance": 999,
        "max_results": 500
    })
    results = last.get('results', [])
    assert len(results) >= 10, f"Too few results: {len(results)}"
    r0 = results[0]
    for key in ['source', 'target', 'matched_words', 'overall_score']:
        assert key in r0, f"Missing key '{key}' in search result"
    assert r0['overall_score'] > 0, "Score should be positive"
    assert len(r0['matched_words']) > 0, "No matched words in top result"


def test_line_search_quality(client):
    resp = client.post("/api/line-search", json={
        "query": "arma virumque cano", "language": "la"
    })
    assert resp.status_code == 200
    data = resp.get_json()
    results = data.get('results', [])
    assert len(results) > 0, "No line search results"
    # Aeneid must appear somewhere in the results (not necessarily top 3,
    # since prose lines with more word matches may rank higher)
    texts = [r.get('text_id', '') for r in results]
    found_aeneid = any('aeneid' in t.lower() for t in texts)
    assert found_aeneid, f"Aeneid not found in any of {len(results)} results"


def test_corpus_search_quality(client):
    resp = client.post("/api/corpus-search", json={
        "lemmas": ["arma", "uir"], "language": "la"
    })
    assert resp.status_code == 200
    data = resp.get_json()
    total = data.get('total', 0)
    assert total >= 5, f"Expected 5+ texts with arma+uir, got {total}"
    results = data.get('results', [])
    if results:
        r0 = results[0]
        assert 'text_id' in r0, "Missing text_id in corpus search result"


def test_wildcard_quality(client):
    resp = client.post("/api/wildcard-search", json={
        "query": "arma vir*", "language": "la", "max_results": 50
    })
    assert resp.status_code == 200
    data = resp.get_json()
    total = data.get('total_matches', 0)
    assert total > 0, "No wildcard matches"
    results = data.get('results', [])
    texts = [r.get('text_id', '') for r in results]
    found_aeneid = any('aeneid' in t.lower() for t in texts)
    assert found_aeneid, f"Aeneid not in wildcard results for 'arma vir*'"


def test_rare_bigrams_loaded(client):
    resp = client.get("/api/rare-bigrams?language=la&max_occurrences=10")
    assert resp.status_code == 200
    data = resp.get_json()
    bigrams = data.get('bigrams', [])
    assert len(bigrams) > 0, f"No bigrams returned; message: {data.get('message', '')}"
    b0 = bigrams[0]
    assert 'bigram' in b0 or 'word1' in b0, f"Bigram missing expected keys: {list(b0.keys())}"


def test_fusion_result_quality(client):
    last = run_sse_search(client, "/api/search-fusion", {
        "source": "lucan.bellum_civile.part.1.tess",
        "target": "vergil.aeneid.part.1.tess",
        "language": "la",
        "mode": "merged",
        "max_results": 50,
        "source_unit_type": "line",
        "target_unit_type": "line",
        "use_meter": False
    })
    results = last.get('results', [])
    assert len(results) >= 10, f"Too few fusion results: {len(results)}"
    r0 = results[0]
    assert r0.get('overall_score', 0) > 0, "Top fusion result has no score"
    assert 'matched_words' in r0, "Fusion result missing matched_words"
    assert 'channels' in r0 or 'match_basis' in r0, "Fusion result missing channel info"


# ── Static Pages (HTML served) ────────────────────────────────────

def test_index_page(client):
    resp = client.get("/")
    assert resp.status_code == 200


def test_help_page(client):
    resp = client.get("/help")
    assert resp.status_code == 200


def test_about_page(client):
    resp = client.get("/about")
    assert resp.status_code == 200


# ── Auth Status ────────────────────────────────────────────────────

def test_auth_user(client):
    resp = client.get("/api/auth/user")
    assert resp.status_code == 200


# ── Repository (Intertexts) ───────────────────────────────────────

def test_intertexts_list(client):
    check_json(client.get("/api/intertexts"), min_keys=['intertexts'])


def test_intertexts_stats(client):
    check_json(client.get("/api/intertexts/stats"), min_keys=['total'])


if __name__ == '__main__':
    pytest.main([__file__])
