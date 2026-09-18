"""GET /reuse/line and GET /reuse/marks: the corpus-wide verbatim reuse table
(backend/reuse_table.py, cache/reuse_pairs/<lang>.db) that backs the Reader's
"quoted in N works" marker and Reuse tab.

Builds a small fixture SQLite db (the same three-table shape
scripts/reuse/build_reuse_table.py writes) plus tiny lemma-cache JSON files,
so this runs in CI with no real reuse table or corpus present -- the pattern
tests/test_passages_works_route.py uses for the passage index.
"""
import json
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.app import app  # noqa: E402
from backend import reuse_table  # noqa: E402


def _route(suffix):
    return next(str(r) for r in app.url_map.iter_rules() if str(r).endswith(suffix))


def _get(client, route, **params):
    qs = '&'.join(f'{k}={v}' for k, v in params.items() if v not in (None, ''))
    return client.get(f'{route}?{qs}')


def _write_lemma_cache(lemmas_dir, language, work, refs_and_texts):
    lang_dir = os.path.join(lemmas_dir, language)
    os.makedirs(lang_dir, exist_ok=True)
    units = [{'ref': ref, 'text': text, 'tokens': text.lower().split()}
              for ref, text in refs_and_texts]
    data = {'text_id': work, 'language': language, 'units_line': units}
    with open(os.path.join(lang_dir, work + '.json'), 'w', encoding='utf-8') as f:
        json.dump(data, f)


def _write_reuse_db(reuse_dir, language, pairs_rows, line_counts_rows, meta_rows):
    os.makedirs(reuse_dir, exist_ok=True)
    db_path = os.path.join(reuse_dir, f'{language}.db')
    if os.path.exists(db_path):
        os.remove(db_path)
    conn = sqlite3.connect(db_path)
    conn.execute("""CREATE TABLE pairs (
        work_a TEXT, line_a_ref TEXT, work_b TEXT, line_b_ref TEXT,
        shared INTEGER, jaccard REAL, span_len INTEGER
    )""")
    conn.executemany("INSERT INTO pairs VALUES (?,?,?,?,?,?,?)", pairs_rows)
    conn.execute("CREATE TABLE line_counts (work TEXT, line_ref TEXT, n_works INTEGER)")
    conn.executemany("INSERT INTO line_counts VALUES (?,?,?)", line_counts_rows)
    conn.execute("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT)")
    conn.executemany("INSERT INTO meta VALUES (?,?)", meta_rows)
    conn.commit()
    conn.close()


def _reset_reuse_table_state(monkeypatch, tmp_path):
    """Point reuse_table at a fixture directory and clear its cached state
    (open connections, the per-work lemma-cache memo) so tests don't bleed
    into each other or into a real cache/reuse_pairs directory."""
    monkeypatch.setattr(reuse_table, 'DB_DIR', str(tmp_path / 'reuse_pairs'))
    monkeypatch.setattr(reuse_table, 'CACHE_LEMMAS_DIR', str(tmp_path / 'lemmas'))
    monkeypatch.setattr(reuse_table, '_connections', {})
    reuse_table._load_work_lines.cache_clear()


def _build_fixture(tmp_path, language='la'):
    _write_lemma_cache(str(tmp_path / 'lemmas'), language, 'vergil.aeneid', [
        ('verg. aen. 1.1', 'Arma virumque cano, Troiae qui primus ab oris'),
        ('verg. aen. 1.2', 'Italiam fato profugus'),
        ('verg. aen. 1.3', 'Lavinaque venit litora'),
    ])
    _write_lemma_cache(str(tmp_path / 'lemmas'), language, 'macrobius.saturnalia', [
        ('macro. sat. 5.2.8', 'Troiae qui primus ab oris, quoted at length'),
    ])
    _write_lemma_cache(str(tmp_path / 'lemmas'), language, 'servius.commentary', [
        ('serv. 1.1', 'a note on arma virumque'),
    ])
    _write_reuse_db(
        str(tmp_path / 'reuse_pairs'), language,
        pairs_rows=[
            ('vergil.aeneid', 'verg. aen. 1.1', 'macrobius.saturnalia', 'macro. sat. 5.2.8', 10, 0.2, 1),
            ('servius.commentary', 'serv. 1.1', 'vergil.aeneid', 'verg. aen. 1.1', 4, 0.15, 1),
        ],
        line_counts_rows=[
            ('vergil.aeneid', 'verg. aen. 1.1', 2),
            ('vergil.aeneid', 'verg. aen. 1.3', 1),
        ],
        meta_rows=[
            ('built_at', '2026-09-19T00:00:00+00:00'),
            ('corpus_version', '2026-08-16'),
            ('language', language),
        ],
    )


# --- /reuse/line -------------------------------------------------------

def test_line_combines_both_directions_ordered_by_shared(monkeypatch, tmp_path):
    _reset_reuse_table_state(monkeypatch, tmp_path)
    _build_fixture(tmp_path)
    client = app.test_client()
    r = _get(client, _route('/reuse/line'), work='vergil.aeneid', ref='verg. aen. 1.1', language='la')
    assert r.status_code == 200
    out = json.loads(r.get_data())
    assert out['available'] is True
    works = [(q['work'], q['ref']) for q in out['quotations']]
    assert ('macrobius.saturnalia', 'macro. sat. 5.2.8') in works
    assert ('servius.commentary', 'serv. 1.1') in works
    # ordered by shared descending: macrobius (10) before servius (4)
    assert out['quotations'][0]['work'] == 'macrobius.saturnalia'
    assert out['quotations'][0]['shared'] == 10


def test_line_carries_the_actual_line_text_and_what_the_reader_needs(monkeypatch, tmp_path):
    _reset_reuse_table_state(monkeypatch, tmp_path)
    _build_fixture(tmp_path)
    client = app.test_client()
    r = _get(client, _route('/reuse/line'), work='vergil.aeneid', ref='verg. aen. 1.1', language='la')
    out = json.loads(r.get_data())
    macro = next(q for q in out['quotations'] if q['work'] == 'macrobius.saturnalia')
    assert macro['text'] == 'Troiae qui primus ab oris, quoted at length'
    assert macro['ref'] == 'macro. sat. 5.2.8'
    assert macro['language'] == 'la'
    assert 'jaccard' in macro and 'span_len' in macro


def test_line_carries_meta(monkeypatch, tmp_path):
    _reset_reuse_table_state(monkeypatch, tmp_path)
    _build_fixture(tmp_path)
    client = app.test_client()
    r = _get(client, _route('/reuse/line'), work='vergil.aeneid', ref='verg. aen. 1.1', language='la')
    out = json.loads(r.get_data())
    assert out['meta']['corpus_version'] == '2026-08-16'


def test_line_no_matches_is_a_normal_empty_result_not_an_error(monkeypatch, tmp_path):
    _reset_reuse_table_state(monkeypatch, tmp_path)
    _build_fixture(tmp_path)
    client = app.test_client()
    r = _get(client, _route('/reuse/line'), work='vergil.aeneid', ref='verg. aen. 1.2', language='la')
    assert r.status_code == 200
    out = json.loads(r.get_data())
    assert out['available'] is True
    assert out['quotations'] == []


def test_line_missing_params_is_400(monkeypatch, tmp_path):
    _reset_reuse_table_state(monkeypatch, tmp_path)
    _build_fixture(tmp_path)
    client = app.test_client()
    r = _get(client, _route('/reuse/line'), work='vergil.aeneid', language='la')
    assert r.status_code == 400


def test_line_missing_language_table_is_404_plain_message(monkeypatch, tmp_path):
    _reset_reuse_table_state(monkeypatch, tmp_path)
    _build_fixture(tmp_path)
    client = app.test_client()
    r = _get(client, _route('/reuse/line'), work='vergil.aeneid', ref='verg. aen. 1.1', language='grc')
    assert r.status_code == 404
    out = json.loads(r.get_data())
    assert 'error' in out and isinstance(out['error'], str) and out['error']


# --- /reuse/marks --------------------------------------------------------

def test_marks_returns_all_reused_lines_when_no_range_given(monkeypatch, tmp_path):
    _reset_reuse_table_state(monkeypatch, tmp_path)
    _build_fixture(tmp_path)
    client = app.test_client()
    r = _get(client, _route('/reuse/marks'), work='vergil.aeneid', language='la')
    assert r.status_code == 200
    out = json.loads(r.get_data())
    assert out['available'] is True
    refs = {row['ref']: row['n_works'] for row in out['lines']}
    assert refs == {'verg. aen. 1.1': 2, 'verg. aen. 1.3': 1}


def test_marks_range_uses_line_order_not_string_order(monkeypatch, tmp_path):
    """verg. aen. 1.3 is line-order after 1.1 but before nothing else here --
    a range of just line 1 must exclude it even though ref strings could
    mislead a naive comparison on a work with double-digit line numbers."""
    _reset_reuse_table_state(monkeypatch, tmp_path)
    _build_fixture(tmp_path)
    client = app.test_client()
    r = _get(client, _route('/reuse/marks'), work='vergil.aeneid',
              ref_start='verg. aen. 1.1', ref_end='verg. aen. 1.1', language='la')
    out = json.loads(r.get_data())
    assert [row['ref'] for row in out['lines']] == ['verg. aen. 1.1']


def test_marks_missing_work_is_400(monkeypatch, tmp_path):
    _reset_reuse_table_state(monkeypatch, tmp_path)
    _build_fixture(tmp_path)
    client = app.test_client()
    r = _get(client, _route('/reuse/marks'), language='la')
    assert r.status_code == 400


def test_marks_missing_language_table_is_404_plain_message(monkeypatch, tmp_path):
    _reset_reuse_table_state(monkeypatch, tmp_path)
    _build_fixture(tmp_path)
    client = app.test_client()
    r = _get(client, _route('/reuse/marks'), work='vergil.aeneid', language='grc')
    assert r.status_code == 404
    out = json.loads(r.get_data())
    assert 'error' in out
