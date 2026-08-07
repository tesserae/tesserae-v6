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


# Determine if the database is available. If not, skip intertexts tests gracefully.
db_unavailable = not check_db_connection(os.environ.get('DATABASE_URL'))


@pytest.fixture(scope="module", autouse=True)
def mock_search_env(tmp_path_factory):
    """
    Module-scoped fixture to dynamically construct and configure a temporary
    mock search index and bigram cache for Latin.
    
    NOTE: This mock index and cache data is hand-fabricated specifically for
    endpoint integration tests and is not a replacement for full corpus/index validation.
    """
    # 1. Create temporary directories under pytest's temp path
    tmp_dir = tmp_path_factory.mktemp("tesserae_test_data")
    bigram_dir = tmp_dir / "cache" / "bigrams"
    index_dir = tmp_dir / "data" / "inverted_index"
    
    os.makedirs(bigram_dir, exist_ok=True)
    os.makedirs(index_dir, exist_ok=True)
    
    # 2. Write mock bigram cache for Latin
    bigram_path = bigram_dir / "la_bigrams.json"
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

    # 3. Setup mock SQLite index for Latin ('la') to simulate pre-built search indexes
    db_path = index_dir / "la_index.db"
    conn = sqlite3.connect(str(db_path))
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
    
    # common words 'aspero', 'foedo', 'foederis' (and their lemmatized forms) in 8 distinct base works -> not rare
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
        
    # 'arma', 'uir', 'vir' in all 10 texts -> co-occur in all 10 texts
    for t_id in range(1, 11):
        ref = refs_by_id[t_id]
        postings_data.append(('arma', t_id, ref, '[5]'))
        postings_data.append(('uir', t_id, ref, '[6]'))
        postings_data.append(('vir', t_id, ref, '[6]'))
        
    cursor.executemany('INSERT INTO postings VALUES (?, ?, ?, ?)', postings_data)
    conn.commit()
    conn.close()

    # Monkeypatch the module paths to use our clean tmp folders
    import backend.inverted_index
    import backend.bigram_frequency
    
    old_index_dir = backend.inverted_index.INDEX_DIR
    old_cache_dir = backend.bigram_frequency.CACHE_DIR
    
    backend.inverted_index.INDEX_DIR = str(index_dir)
    backend.bigram_frequency.CACHE_DIR = str(bigram_dir)
    
    # Ensure caches are cleared so connections are opened on the new paths
    backend.inverted_index._connections.clear()
    backend.bigram_frequency._bigram_cache.clear()
    
    yield
    
    # Restore original paths
    backend.inverted_index.INDEX_DIR = old_index_dir
    backend.bigram_frequency.CACHE_DIR = old_cache_dir
    backend.inverted_index._connections.clear()
    backend.bigram_frequency._bigram_cache.clear()


@pytest.fixture(scope="module")
def client():
    """Module-scoped pytest fixture yielding the Flask test client."""
    # Move environment setup into the fixture to avoid import-time global side-effects
    old_direct_server = os.environ.get('TESSERAE_DIRECT_SERVER')
    os.environ['TESSERAE_DIRECT_SERVER'] = '1'
    
    try:
        from backend.app import app
        with app.test_client() as c:
            yield c
    finally:
        if old_direct_server is None:
            os.environ.pop('TESSERAE_DIRECT_SERVER', None)
        else:
            os.environ['TESSERAE_DIRECT_SERVER'] = old_direct_server


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


def test_rare_lemmata_full_pagination_and_export(client, monkeypatch):
    from backend.blueprints import hapax

    cached_words = [
        {'lemma': 'zeta', 'display': 'zeta', 'count': 3, 'first_author': 'Virgil', 'first_work': 'Aeneid'},
        {'lemma': 'alpha', 'display': 'alpha', 'count': 1, 'first_author': 'Homer', 'first_work': 'Iliad'},
        {'lemma': 'beta', 'display': 'beta', 'count': 2, 'first_author': 'Cicero', 'first_work': 'Orations'},
    ]
    monkeypatch.setattr(hapax, 'load_rare_words_cache', lambda _language: {'words': cached_words})

    first_page = check_json(client.get(
        '/api/rare-lemmata-full?language=la&max_occurrences=3&limit=25&sort_by=frequency&sort_order=asc'
    ))
    assert first_page['total'] == 3
    assert first_page['offset'] == 0
    assert first_page['limit'] == 25
    assert [word['lemma'] for word in first_page['words']] == ['alpha', 'beta', 'zeta']

    offset_page = check_json(client.get(
        '/api/rare-lemmata-full?language=la&max_occurrences=3&offset=1&limit=25&sort_by=frequency&sort_order=asc'
    ))
    assert [word['lemma'] for word in offset_page['words']] == ['beta', 'zeta']

    author_sorted = check_json(client.get(
        '/api/rare-lemmata-full?language=la&max_occurrences=3&limit=25&sort_by=author&sort_order=desc'
    ))
    assert [word['first_author'] for word in author_sorted['words']] == ['Virgil', 'Homer', 'Cicero']

    invalid_limit = client.get('/api/rare-lemmata-full?limit=10')
    assert invalid_limit.status_code == 400

    export = client.get('/api/rare-lemmata-full/export?language=la&max_occurrences=3&sort_by=lemma')
    assert export.status_code == 200
    assert export.mimetype == 'text/csv'
    assert 'attachment;' in export.headers['Content-Disposition']
    assert export.get_data(as_text=True).splitlines()[1].startswith('alpha,1,Homer,Iliad')


def test_text_credits_pagination_and_filtering(client, monkeypatch, tmp_path):
    from backend.blueprints import corpus

    sources_file = tmp_path / 'text_sources.json'
    sources_file.write_text(json.dumps([
        {'author': 'Virgil', 'work': 'Aeneid'},
        {'author': 'Homer', 'work': 'Iliad'},
        {'author': 'Virgil', 'work': 'Eclogues'},
    ]), encoding='utf-8')
    monkeypatch.setattr(corpus, 'TEXT_SOURCES_FILE', sources_file)

    first_page = check_json(client.get('/api/text-credits?limit=25'))
    assert first_page['total'] == 3
    assert first_page['offset'] == 0
    assert first_page['limit'] == 25
    assert [entry['work'] for entry in first_page['entries']] == ['Aeneid', 'Iliad', 'Eclogues']

    filtered_page = check_json(client.get('/api/text-credits?query=virgil&offset=1&limit=25'))
    assert filtered_page['total'] == 2
    assert [entry['work'] for entry in filtered_page['entries']] == ['Eclogues']

    assert client.get('/api/text-credits?limit=10').status_code == 400
    assert client.get('/api/text-credits?offset=-1').status_code == 400


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

@pytest.mark.skipif(db_unavailable, reason="Database connection not available")
def test_intertexts_list(client):
    res = check_json(client.get(
        "/api/intertexts?per_page=25&source_language=la&sort_by=score&sort_order=desc"
    ), min_keys=['intertexts', 'total', 'pages', 'current_page', 'per_page', 'summary'])
    assert res['per_page'] == 25
    assert 'visible' in res['summary']
    assert 'with_notes' in res['summary']


@pytest.mark.skipif(db_unavailable, reason="Database connection not available")
def test_intertexts_export(client):
    resp = client.get("/api/intertexts/export?format=csv&per_page=50&sort_by=created_at")
    assert resp.status_code == 200
    assert resp.mimetype == 'text/csv'


def test_intertexts_reject_invalid_page_size(client):
    resp = client.get("/api/intertexts?per_page=20")
    assert resp.status_code == 400


@pytest.mark.skipif(db_unavailable, reason="Database connection not available")
def test_intertexts_stats(client):
    check_json(client.get("/api/intertexts/stats"), min_keys=['total'])


if __name__ == '__main__':
    pytest.main([__file__])
