"""GET /api/reuse/line and GET /api/reuse/marks, documentary reuse side
(backend/reuse_documents.py, cache/reuse_pairs/<lang>_documents.db) --
inscriptions and papyri that quote or near-quote a literary line, added to
the existing literary reuse response behind TESSERAE_DOCUMENTS=1.

Builds tiny fixtures for all three pieces this needs: a literary lemma
cache + cache/reuse_pairs/<lang>.db (so the existing literary endpoint has
something to answer -- these routes 404 with no literary table regardless
of the documents side), a cache/reuse_pairs/<lang>_documents.db, and a
documents index + metadata db for backend/documents.py (the same minimal
fixture shape tests/test_documents.py hand-rolls, without the heavier
build_one_language/process_corpus pipeline that test uses, since this test
only exercises backend/documents.py's read path, not its own build).
"""
import json
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import backend.documents as docs  # noqa: E402
from backend.app import app  # noqa: E402
from backend import reuse_table, reuse_documents  # noqa: E402


def _route(suffix):
    return next(str(r) for r in app.url_map.iter_rules() if str(r).endswith(suffix))


def _get(client, route, **params):
    qs = '&'.join(f'{k}={v}' for k, v in params.items() if v not in (None, ''))
    return client.get(f'{route}?{qs}')


def _write_literary_cache(lemmas_dir, language, work, refs_and_texts):
    lang_dir = os.path.join(lemmas_dir, language)
    os.makedirs(lang_dir, exist_ok=True)
    units = [{'ref': ref, 'text': text, 'tokens': text.lower().split(),
              'original_tokens': text.replace(',', '').split()}
             for ref, text in refs_and_texts]
    data = {'text_id': work, 'language': language, 'units_line': units}
    with open(os.path.join(lang_dir, work + '.json'), 'w', encoding='utf-8') as f:
        json.dump(data, f)


def _write_literary_reuse_db(reuse_dir, language, pairs_rows):
    """An empty-but-valid literary table: these tests are about the
    DOCUMENTS side, but /reuse/line and /reuse/marks both 404 with no
    literary table at all regardless of what the documents table has, so
    one must exist (even with zero matching pairs for the fixture's own
    line)."""
    os.makedirs(reuse_dir, exist_ok=True)
    db_path = os.path.join(reuse_dir, f'{language}.db')
    if os.path.exists(db_path):
        os.remove(db_path)
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE pairs (work_a TEXT, line_a_ref TEXT, work_b TEXT, "
                 "line_b_ref TEXT, shared INTEGER, jaccard REAL, span_len INTEGER)")
    conn.executemany("INSERT INTO pairs VALUES (?,?,?,?,?,?,?)", pairs_rows)
    conn.execute("CREATE TABLE line_counts (work TEXT, line_ref TEXT, n_works INTEGER)")
    conn.execute("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT)")
    conn.commit()
    conn.close()


def _write_documents_reuse_db(reuse_dir, language, pairs_rows, with_rule=False):
    """pairs_rows: (lit_work, lit_ref, lit_seq, doc_id, doc_bucket, doc_ref,
    doc_seq, shared, jaccard, span_len, doc_restored[, rule]). with_rule
    adds the `rule` column that tables built since 2026-10-09 carry."""
    os.makedirs(reuse_dir, exist_ok=True)
    db_path = os.path.join(reuse_dir, f'{language}_documents.db')
    if os.path.exists(db_path):
        os.remove(db_path)
    conn = sqlite3.connect(db_path)
    conn.execute("""CREATE TABLE pairs (
        lit_work TEXT, lit_ref TEXT, lit_seq INTEGER,
        doc_id TEXT, doc_bucket TEXT, doc_ref TEXT, doc_seq INTEGER,
        shared INTEGER, jaccard REAL, span_len INTEGER, doc_restored INTEGER"""
                 + (", rule TEXT" if with_rule else "") + "\n    )")
    conn.executemany("INSERT INTO pairs VALUES (" + ','.join('?' * (12 if with_rule else 11)) + ")", pairs_rows)
    conn.execute("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT)")
    conn.executemany("INSERT INTO meta VALUES (?,?)", [('corpus_version', '2026-10-08')])
    conn.commit()
    conn.close()


def _make_documents_index(path, rows):
    """rows: [(bucket_filename, ref, content, tokens)]. Just enough of the
    real schema (texts + lines) for backend.documents.get_lines_batch."""
    if os.path.exists(path):
        os.remove(path)
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE texts (text_id INTEGER PRIMARY KEY, filename TEXT UNIQUE, "
                 "author TEXT, title TEXT, line_count INTEGER)")
    conn.execute("CREATE TABLE lines (text_id INTEGER, ref TEXT, content TEXT, lemmas TEXT, "
                 "tokens TEXT, PRIMARY KEY (text_id, ref))")
    buckets = {}
    for bucket, ref, content, tokens in rows:
        if bucket not in buckets:
            buckets[bucket] = len(buckets) + 1
            conn.execute("INSERT INTO texts VALUES (?,?,?,?,?)", (buckets[bucket], bucket, '', '', 0))
        conn.execute("INSERT INTO lines VALUES (?,?,?,?,?)",
                     (buckets[bucket], ref, content, '[]', json.dumps(tokens)))
    conn.commit()
    conn.close()


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
    for row in rows:
        cols = ', '.join(row.keys())
        placeholders = ', '.join('?' for _ in row)
        conn.execute(f"INSERT INTO documents ({cols}) VALUES ({placeholders})",  # nosec B608
                     list(row.values()))
    conn.commit()
    conn.close()


def _reset_reuse_state(monkeypatch, tmp_path):
    monkeypatch.setattr(reuse_table, 'DB_DIR', str(tmp_path / 'reuse_pairs'))
    monkeypatch.setattr(reuse_table, 'CACHE_LEMMAS_DIR', str(tmp_path / 'lemmas'))
    monkeypatch.setattr(reuse_table, '_connections', {})
    reuse_table._load_work_lines.cache_clear()
    monkeypatch.setattr(reuse_documents, 'DB_DIR', str(tmp_path / 'reuse_pairs'))
    monkeypatch.setattr(reuse_documents, '_connections', {})
    monkeypatch.setattr(reuse_documents, '_KEEP_CLAUSE', {})
    reuse_documents._doc_credit.cache_clear()


def _build_fixture(tmp_path):
    _write_literary_cache(str(tmp_path / 'lemmas'), 'la', 'vergil.aeneid', [
        ('verg. aen. 1.1', 'Arma virumque cano, Troiae qui primus ab oris'),
        ('verg. aen. 2.1', 'Conticuere omnes intentique ora tenebant'),
    ])
    _write_literary_reuse_db(str(tmp_path / 'reuse_pairs'), 'la', pairs_rows=[])
    _write_documents_reuse_db(str(tmp_path / 'reuse_pairs'), 'la', pairs_rows=[
        ('vergil.aeneid', 'verg. aen. 1.1', 0, 'edr:GRAFFITO1', 'edr__pompeii.tess',
         'edr:GRAFFITO1', 0, 16, 1.0, 1, 0),
        # shared==1 -> tier 'possible'
        ('vergil.aeneid', 'verg. aen. 2.1', 1, 'edh:FRAG1', 'edh__pompeii.tess',
         'edh:FRAG1', 0, 1, 0.05, 1, 1),
    ])
    index_dir = str(tmp_path / 'documents_index')
    os.makedirs(index_dir, exist_ok=True)
    _make_documents_index(os.path.join(index_dir, 'la_documents_index.db'), [
        ('edr__pompeii.tess', 'edr:GRAFFITO1', 'Arma virumque cano Troiae qui primus ab oris',
         ['arma', 'uirumque', 'cano', 'troiae', 'qui', 'primus', 'ab', 'oris']),
        ('edh__pompeii.tess', 'edh:FRAG1', 'Conticuere omnes',
         ['conticuere', 'omnes']),
    ])
    metadata_db = str(tmp_path / 'metadata.db')
    _make_metadata_db(metadata_db, [{
        'id': 'edr:GRAFFITO1', 'collection': 'documents', 'source': 'edr',
        'licence_name': 'CC BY-SA', 'licence_url': 'https://example.org',
        'source_name': 'EDR', 'source_url': 'https://edr.example.org',
        'licence_name_secondary': None, 'licence_url_secondary': None,
        'source_name_secondary': None, 'source_url_secondary': None,
        'principal_edition': 'CIL IV 9131', 'text_type_label': 'graffito',
        'object_type_label': 'wall', 'material_label': 'plaster',
        'date_not_before': 1, 'date_not_after': 79,
        'ancient_place': 'Pompeii', 'modern_place': 'Pompei', 'region': 'Campania',
        'pleiades_id': '000001',
    }])
    return index_dir, metadata_db


def test_documents_field_absent_without_the_env_switch(monkeypatch, tmp_path):
    _reset_reuse_state(monkeypatch, tmp_path)
    index_dir, metadata_db = _build_fixture(tmp_path)
    monkeypatch.delenv('TESSERAE_DOCUMENTS', raising=False)
    monkeypatch.setenv('TESSERAE_DOCUMENTS_INDEX_DIR', index_dir)
    monkeypatch.setenv('TESSERAE_DOCUMENTS_META', metadata_db)
    docs.reset_caches()
    client = app.test_client()
    r = _get(client, _route('/reuse/line'), work='vergil.aeneid', ref='verg. aen. 1.1', language='la')
    out = json.loads(r.get_data())
    assert 'documents' not in out
    docs.reset_caches()


def test_line_carries_document_hits_when_the_switch_is_on(monkeypatch, tmp_path):
    _reset_reuse_state(monkeypatch, tmp_path)
    index_dir, metadata_db = _build_fixture(tmp_path)
    monkeypatch.setenv('TESSERAE_DOCUMENTS', '1')
    monkeypatch.setenv('TESSERAE_DOCUMENTS_INDEX_DIR', index_dir)
    monkeypatch.setenv('TESSERAE_DOCUMENTS_META', metadata_db)
    docs.reset_caches()
    client = app.test_client()
    r = _get(client, _route('/reuse/line'), work='vergil.aeneid', ref='verg. aen. 1.1', language='la')
    assert r.status_code == 200
    out = json.loads(r.get_data())
    assert out['available'] is True
    assert len(out['documents']) == 1
    hit = out['documents'][0]
    assert hit['doc_id'] == 'edr:GRAFFITO1'
    assert hit['tier'] == 'strict'
    assert hit['text'] == 'Arma virumque cano Troiae qui primus ab oris'
    assert hit['credit']['principal_edition'] == 'CIL IV 9131'
    assert hit['text_type_label'] == 'graffito'
    assert hit['ancient_place'] == 'Pompeii'
    assert hit['date_not_before'] == 1 and hit['date_not_after'] == 79
    assert hit['restored'] is False
    # The whole line is shared -- bold_spans should cover (at least) a span
    # over the line's text, not come back empty.
    assert hit['bold_spans']
    docs.reset_caches()


def test_line_tier_possible_and_restored_flag(monkeypatch, tmp_path):
    _reset_reuse_state(monkeypatch, tmp_path)
    index_dir, metadata_db = _build_fixture(tmp_path)
    monkeypatch.setenv('TESSERAE_DOCUMENTS', '1')
    monkeypatch.setenv('TESSERAE_DOCUMENTS_INDEX_DIR', index_dir)
    monkeypatch.setenv('TESSERAE_DOCUMENTS_META', metadata_db)
    docs.reset_caches()
    client = app.test_client()
    r = _get(client, _route('/reuse/line'), work='vergil.aeneid', ref='verg. aen. 2.1', language='la')
    out = json.loads(r.get_data())
    hit = out['documents'][0]
    assert hit['doc_id'] == 'edh:FRAG1'
    assert hit['tier'] == 'possible'
    assert hit['restored'] is True
    # No metadata.db row for edh:FRAG1 -- credit fields come back None, not
    # an error, and the hit is still present with its text and locus.
    assert hit['credit'] is None
    docs.reset_caches()


def test_marks_carries_document_counts_including_a_literary_only_miss(monkeypatch, tmp_path):
    """verg. aen. 1.1 has both a literary-table entry (none, here) and a
    documents hit; verg. aen. 2.1 has ONLY a documents hit (no literary
    reuse at all) -- it must still appear in /reuse/marks with its
    n_possible_documents, not be silently dropped because the literary
    query's own result has no row for it."""
    _reset_reuse_state(monkeypatch, tmp_path)
    index_dir, metadata_db = _build_fixture(tmp_path)
    monkeypatch.setenv('TESSERAE_DOCUMENTS', '1')
    monkeypatch.setenv('TESSERAE_DOCUMENTS_INDEX_DIR', index_dir)
    monkeypatch.setenv('TESSERAE_DOCUMENTS_META', metadata_db)
    docs.reset_caches()
    client = app.test_client()
    r = _get(client, _route('/reuse/marks'), work='vergil.aeneid', language='la')
    assert r.status_code == 200
    out = json.loads(r.get_data())
    by_ref = {l['ref']: l for l in out['lines']}
    assert by_ref['verg. aen. 1.1']['n_documents'] == 1
    assert by_ref['verg. aen. 1.1']['n_possible_documents'] == 0
    assert by_ref['verg. aen. 2.1']['n_documents'] == 0
    assert by_ref['verg. aen. 2.1']['n_possible_documents'] == 1
    assert by_ref['verg. aen. 2.1']['n_works'] == 0
    docs.reset_caches()


def test_order_free_pair_is_shown_as_possible_when_the_table_has_a_rule_column(monkeypatch, tmp_path):
    """A pair found by the order-free rule has jaccard 0 by construction (the
    Pompeian fullers' parody of Aeneid 1.1), so the old keep clause hid it.
    With a `rule` column it is admitted; without one the clause is unchanged."""
    _reset_reuse_state(monkeypatch, tmp_path)
    index_dir, metadata_db = _build_fixture(tmp_path)
    _write_documents_reuse_db(str(tmp_path / 'reuse_pairs'), 'la', with_rule=True, pairs_rows=[
        ('vergil.aeneid', 'verg. aen. 1.1', 0, 'edr:GRAFFITO1', 'edr__pompeii.tess',
         'edr:GRAFFITO1', 0, 16, 1.0, 1, 0, 'ordered'),
        ('vergil.aeneid', 'verg. aen. 1.1', 0, 'edh:FRAG1', 'edh__pompeii.tess',
         'edh:FRAG1', 0, 1, 0.0, 1, 1, 'reorder'),
    ])
    monkeypatch.setenv('TESSERAE_DOCUMENTS', '1')
    monkeypatch.setenv('TESSERAE_DOCUMENTS_INDEX_DIR', index_dir)
    monkeypatch.setenv('TESSERAE_DOCUMENTS_META', metadata_db)
    docs.reset_caches()
    client = app.test_client()
    out = json.loads(_get(client, _route('/reuse/line'), work='vergil.aeneid', ref='verg. aen. 1.1', language='la').get_data())
    by_id = {h['doc_id']: h for h in out['documents']}
    assert by_id['edr:GRAFFITO1']['tier'] == 'strict'
    assert by_id['edh:FRAG1']['tier'] == 'possible'
    marks = json.loads(_get(client, _route('/reuse/marks'), work='vergil.aeneid', language='la').get_data())
    line = next(l for l in marks['lines'] if l['ref'] == 'verg. aen. 1.1')
    assert line['n_documents'] == 1 and line['n_possible_documents'] == 1
    docs.reset_caches()
