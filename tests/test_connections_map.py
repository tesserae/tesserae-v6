"""Tests for the four /api/passages/map* routes and their backend.connections_map
reader, against a small hand-built fixture SQLite db -- never the real,
multi-gigabyte cache scripts/build_connections_map.py produces.

The fixture has three genuine allusive pairs (Homer-Vergil, Statius-Vergil,
Homer-Statius) and one curated translation pair (the Greek New Testament and
the World English Bible New Testament), so every test below can assert that
the translation pair is excluded by default and included on request.
"""
import json
import math
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest  # noqa: E402

from backend.app import app  # noqa: E402
from backend import connections_map  # noqa: E402


WORKS = [
    # work, language, author_key, author_display, year, era_label, century,
    # century_label, genre, window_count, total_links, links_per_window
    ('homer.iliad', 'grc', 'homer', 'Homer', -750, 'Archaic', -8, '8th c. BCE',
     'epic', 200, 15, 0.075),
    ('vergil.aeneid', 'la', 'vergil', 'Vergil', -19, 'Augustan', -1, '1st c. BCE',
     'epic', 100, 15, 0.15),
    ('statius.thebaid', 'la', 'statius', 'Statius', 96, 'Silver Age', 1, '1st c. CE',
     'epic', 80, 8, 0.1),
    ('novum_testamentum.matthaeus', 'grc', 'novum_testamentum', 'Novum Testamentum',
     None, None, None, None, None, 40, 40, 1.0),
    ('world_english_bible.new_testament', 'en', 'world_english_bible',
     'World English Bible', None, None, None, None, None, 50, 40, 0.8),
]

# work_a, work_b, lang_a, lang_b, count, count_notrans, curated, heuristic
WORK_PAIRS = [
    ('homer.iliad', 'vergil.aeneid', 'grc', 'la', 6, 6, 0, 0),
    ('homer.iliad', 'statius.thebaid', 'grc', 'la', 5, 5, 0, 0),
    ('statius.thebaid', 'vergil.aeneid', 'la', 'la', 4, 4, 0, 0),
    ('novum_testamentum.matthaeus', 'world_english_bible.new_testament', 'grc', 'en',
     40, 0, 1, 0),
]

WINDOWS = [
    ('grc-1', 'homer.iliad', 'grc', '1.1', '1.10', 'Achilles rages at Agamemnon.'),
    ('la-1', 'vergil.aeneid', 'la', '1.1', '1.10', 'Arms and the man I sing.'),
    ('la-2', 'statius.thebaid', 'la', '1.1', '1.10', 'Fraternal war at Thebes.'),
]

EDGES = [
    ('grc-1', 'la-1', 0.91, 'homer.iliad', 'vergil.aeneid', 0, 0),
    ('la-1', 'grc-1', 0.90, 'vergil.aeneid', 'homer.iliad', 0, 0),
    ('grc-1', 'la-2', 0.85, 'homer.iliad', 'statius.thebaid', 0, 0),
]


def _build_fixture_db(path, built_at='2026-09-18T00:00:00', subset_windows=None):
    conn = sqlite3.connect(path)
    conn.executescript('''
        CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT);
        CREATE TABLE works (
            work TEXT PRIMARY KEY, language TEXT, author_key TEXT, author_display TEXT,
            year INTEGER, era_label TEXT, century INTEGER, century_label TEXT,
            genre TEXT, window_count INTEGER, total_links INTEGER, links_per_window REAL
        );
        CREATE TABLE windows (
            id TEXT PRIMARY KEY, work TEXT, language TEXT, ref_start TEXT, ref_end TEXT, gist TEXT
        );
        CREATE TABLE edges (
            window_a TEXT, window_b TEXT, score REAL,
            work_a TEXT, work_b TEXT, pos_a INTEGER, pos_b INTEGER
        );
        CREATE TABLE work_pairs (
            work_a TEXT, work_b TEXT, lang_a TEXT, lang_b TEXT,
            count INTEGER, count_notrans INTEGER,
            is_translation_curated INTEGER, is_translation_heuristic INTEGER,
            PRIMARY KEY (work_a, work_b)
        );
    ''')
    conn.executemany('INSERT INTO works VALUES (?,?,?,?,?,?,?,?,?,?,?,?)', WORKS)
    conn.executemany('INSERT INTO windows VALUES (?,?,?,?,?,?)', WINDOWS)
    conn.executemany('INSERT INTO edges VALUES (?,?,?,?,?,?,?)', EDGES)
    conn.executemany('INSERT INTO work_pairs VALUES (?,?,?,?,?,?,?,?)', WORK_PAIRS)
    conn.executemany('INSERT INTO meta VALUES (?,?)',
                     [('built_at', json.dumps(built_at)),
                      ('edges_kept', json.dumps(len(EDGES))),
                      ('subset_windows', json.dumps(
                          subset_windows if subset_windows is not None else len(WINDOWS)))])
    conn.commit()
    conn.close()


@pytest.fixture
def fixture_db(tmp_path, monkeypatch):
    path = str(tmp_path / 'fixture.db')
    _build_fixture_db(path)
    monkeypatch.setattr(connections_map, '_db_path', lambda: path)
    # An empty cache dir: the exact-match path above is what these tests
    # exercise, and an accidental fallback to a real dev-checkout cache
    # (see the staleness tests below for that path, deliberately) would
    # make this fixture non-hermetic.
    monkeypatch.setattr(connections_map, '_cache_dir', lambda: str(tmp_path / 'empty'))
    # "Current index" = exactly this fixture's own windows, i.e. nothing has
    # been retired -- get_pair/get_books_map's window-existence filter is a
    # separate concern, covered by its own tests below.
    monkeypatch.setattr(connections_map, '_current_ids', lambda: {w[0] for w in WINDOWS})
    # Hermetic against the real (large, scripture-heavy) data/translation_
    # pairs.json -- the live curated-pairs overlay is its own concern,
    # covered by its own tests below, not an incidental side effect of
    # whatever the real corpus's curated list happens to contain.
    monkeypatch.setattr(connections_map, '_curated_pairs', lambda: set())
    return path


@pytest.fixture
def client():
    return app.test_client()


def _get(client, path, **params):
    qs = '&'.join(f'{k}={v}' for k, v in params.items() if v not in (None, ''))
    r = client.get(f'{path}?{qs}' if qs else path)
    return r.status_code, json.loads(r.get_data())


# --------------------------------------------------------------------------
# /api/passages/map
# --------------------------------------------------------------------------

def test_map_404s_when_no_cache_is_built(client, monkeypatch, tmp_path):
    monkeypatch.setattr(connections_map, '_db_path', lambda: '/nonexistent/path.db')
    # No fallback cache present either -- a genuinely fresh checkout,
    # not just a fingerprint miss (see the staleness tests for that path).
    monkeypatch.setattr(connections_map, '_cache_dir', lambda: str(tmp_path / 'empty'))
    status, body = _get(client, '/api/passages/map', view='work')
    assert status == 404
    assert 'error' in body


def test_map_work_view_excludes_translation_pairs_by_default(client, fixture_db):
    status, body = _get(client, '/api/passages/map', view='work')
    assert status == 200
    assert 'novum_testamentum.matthaeus' not in body['ids']
    assert 'world_english_bible.new_testament' not in body['ids']
    assert 'homer.iliad' in body['ids'] and 'vergil.aeneid' in body['ids']
    # translation pair's edges (40) were counted as excluded
    assert body['translation_pairs_hidden'] == 1


def test_map_work_view_includes_translation_pairs_when_asked(client, fixture_db):
    status, body = _get(client, '/api/passages/map', view='work', translations=1)
    assert status == 200
    assert 'novum_testamentum.matthaeus' in body['ids']
    assert 'world_english_bible.new_testament' in body['ids']
    assert body['translation_pairs_hidden'] == 0


def test_map_work_view_cell_value_is_symmetric(client, fixture_db):
    status, body = _get(client, '/api/passages/map', view='work')
    ia = body['ids'].index('homer.iliad')
    ib = body['ids'].index('vergil.aeneid')
    assert body['counts'][ia][ib] == body['counts'][ib][ia] == 6


# --------------------------------------------------------------------------
# Log colour scale + legend (NC, 2026-09-19): a linear count/max scale left
# nearly every cell pale; percentile rank then made the top fifth of cells
# fully dark. Colour is now log(1 + count) / log(1 + largest count), and the
# response carries a legend naming the low/middle/high raw counts. Fixture
# counts (translations hidden): homer-vergil 6, homer-statius 5,
# statius-vergil 4 -- each appears twice in the symmetric matrix, so sorted
# nonzero = [4,4,5,5,6,6], median 5.
# --------------------------------------------------------------------------

def test_map_legend_reports_low_middle_high_raw_counts(client, fixture_db):
    status, body = _get(client, '/api/passages/map', view='work')
    assert status == 200
    assert body['legend'] == {'low': 4, 'mid': 5, 'high': 6}


def test_map_normalised_is_log_scaled_not_share_of_max(client, fixture_db):
    status, body = _get(client, '/api/passages/map', view='work')
    ids = body['ids']
    ia, ib, ic = ids.index('homer.iliad'), ids.index('vergil.aeneid'), ids.index('statius.thebaid')
    # homer-vergil = 6, the largest count -> exactly 1.0.
    assert body['normalised'][ia][ib] == 1.0
    # homer-statius = 5 sits at log(6)/log(7), not 5/6 (linear) and not the
    # 4/6 a percentile rank would give.
    assert body['normalised'][ia][ic] == pytest.approx(math.log1p(5) / math.log1p(6))
    # statius-vergil = 4 (the smallest) sits at log(5)/log(7).
    assert body['normalised'][ic][ib] == pytest.approx(math.log1p(4) / math.log1p(6))


def test_log_scale_keeps_small_counts_visible_and_only_the_largest_dark():
    # A small symmetric matrix standing in for a heavily skewed real one:
    # one huge outlier (100) alongside ordinary small counts.
    counts = [[0, 1, 2], [1, 0, 100], [2, 100, 0]]
    normalised, legend = connections_map._log_scale(counts)
    assert legend == {'low': 1, 'mid': 2, 'high': 100}
    # The outlier is the darkest cell...
    assert normalised[1][2] == normalised[2][1] == 1.0
    # ...the small counts are lifted off the floor (a linear scale would put
    # them at 0.01 and 0.02) but stay clearly below the middle, unlike a
    # percentile rank, which would spread them evenly up to the top.
    assert normalised[0][1] == normalised[1][0] == pytest.approx(math.log1p(1) / math.log1p(100))
    assert normalised[0][2] == normalised[2][0] == pytest.approx(math.log1p(2) / math.log1p(100))
    assert 0.1 < normalised[0][1] < normalised[0][2] < 0.3


def test_log_scale_with_no_nonzero_cells_is_all_zero():
    counts = [[0, 0], [0, 0]]
    normalised, legend = connections_map._log_scale(counts)
    assert normalised == [[0.0, 0.0], [0.0, 0.0]]
    assert legend == {'low': 0, 'mid': 0, 'high': 0}


def test_cell_works_matrix_carries_a_legend_too(client, nested_fixture_db):
    status, body = _get(client, '/api/passages/map/cell', view='author',
                        a='homer::grc', b='vergil::la')
    assert status == 200
    assert body['works_matrix']['legend'] == {'low': 3, 'mid': 4.5, 'high': 6}


def test_map_languages_filter_restricts_entities(client, fixture_db):
    status, body = _get(client, '/api/passages/map', view='work', languages='la')
    assert status == 200
    # homer.iliad is grc, both surviving la-la and la-grc pairs need grc on
    # both sides to appear, so with languages=la only the la-la pair (Statius
    # x Vergil) can appear; homer.iliad must be gone entirely.
    assert 'homer.iliad' not in body['ids']


def test_map_author_view_groups_by_author_and_language(client, fixture_db):
    status, body = _get(client, '/api/passages/map', view='author')
    assert status == 200
    assert any('Homer (grc)' in lbl for lbl in body['labels'])
    assert any('Vergil (la)' in lbl for lbl in body['labels'])


def test_map_century_view_groups_by_century_and_language(client, fixture_db):
    status, body = _get(client, '/api/passages/map', view='century')
    assert status == 200
    assert any('BCE' in lbl for lbl in body['labels'])
    # Undated works (the NT/WEB fixture rows) contribute nothing to this view.
    assert len(body['ids']) <= 3


# --------------------------------------------------------------------------
# Chronological ordering (NC, 2026-09-19): the Top N control still chooses
# entities by link count, but the grid then displays them in date order --
# BCE first, undated authors/works last -- rather than by how connected they
# happen to be, so a reader can trace a line of descent across the row.
# --------------------------------------------------------------------------

def test_map_author_view_orders_rows_chronologically_bce_first(client, fixture_db):
    status, body = _get(client, '/api/passages/map', view='author', translations=1)
    assert status == 200
    # Homer (-750), World English Bible (scripture override -600, by its OT
    # source), Vergil (-19), Novum Testamentum (scripture override 80),
    # Statius (96) -- NC, 2026-09-19: scripture entities sort by the text
    # they transmit, not by an edition/translation date.
    assert body['ids'] == [
        'homer::grc', 'world_english_bible::en', 'vergil::la',
        'novum_testamentum::grc', 'statius::la',
    ]


def test_map_work_view_orders_rows_chronologically(client, fixture_db):
    status, body = _get(client, '/api/passages/map', view='work', translations=1)
    assert status == 200
    assert body['ids'] == [
        'homer.iliad', 'world_english_bible.new_testament', 'vergil.aeneid',
        'novum_testamentum.matthaeus', 'statius.thebaid',
    ]


# --------------------------------------------------------------------------
# Scripture/translation date overrides (NC, 2026-09-19): "Bibles sort late"
# -- author_dates.json dates the EDITION, not the text it transmits.
# --------------------------------------------------------------------------

def test_scripture_override_table_covers_the_named_entities():
    assert connections_map.SCRIPTURE_AUTHOR_DATE_OVERRIDES[('he', 'hebrew_bible')]['year'] == -600
    assert connections_map.SCRIPTURE_AUTHOR_DATE_OVERRIDES[('grc', 'septuaginta')]['year'] == -250
    assert connections_map.SCRIPTURE_AUTHOR_DATE_OVERRIDES[('grc', 'novum_testamentum')]['year'] == 80
    assert connections_map.SCRIPTURE_AUTHOR_DATE_OVERRIDES[('cop', 'bohairic')]['year'] == 300
    assert connections_map.SCRIPTURE_AUTHOR_DATE_OVERRIDES[('cop', 'sahidic')]['year'] == 300
    assert connections_map.SCRIPTURE_AUTHOR_DATE_OVERRIDES[('cop', 'sahidica')]['year'] == 300
    web = connections_map.SCRIPTURE_AUTHOR_DATE_OVERRIDES[('en', 'world_english_bible')]
    assert web['year'] == -600
    assert web['label_suffix'] == '(tr.)'
    assert connections_map.SCRIPTURE_WORK_DATE_OVERRIDES['jerome.vulgate']['year'] == 400


def test_scripture_override_is_keyed_by_work_before_author():
    # jerome.vulgate must override even though 'jerome' the author-key is not
    # itself in the author-level table (Jerome also wrote non-Bible works).
    assert connections_map._scripture_override('jerome.vulgate', 'la', 'jerome') == {'year': 400}
    assert connections_map._scripture_override('jerome.epistulae', 'la', 'jerome') is None


def test_scripture_override_does_not_touch_a_real_author():
    # Eobanus versified Homer but is an author, not a Bible -- NC's own
    # example of what must NOT be overridden.
    assert connections_map._scripture_override('eobanus.theocritus', 'la', 'eobanus') is None


def test_map_author_view_marks_the_world_english_bible_label_translated(client, fixture_db):
    status, body = _get(client, '/api/passages/map', view='author', translations=1)
    assert status == 200
    idx = body['ids'].index('world_english_bible::en')
    assert body['labels'][idx].startswith('World English Bible')
    assert body['labels'][idx].endswith('(tr.)')


def test_map_author_view_does_not_mark_hebrew_bible_translated(client, fixture_db):
    # Hebrew Bible is the original-language witness, not a translation --
    # only the label_suffix entries (World English Bible) get marked.
    status, body = _get(client, '/api/passages/map', view='author', translations=1)
    idx = body['ids'].index('novum_testamentum::grc')
    assert '(tr.)' not in body['labels'][idx]


def test_map_century_view_orders_rows_chronologically(client, fixture_db):
    status, body = _get(client, '/api/passages/map', view='century')
    assert status == 200
    # -8 (Homer) before -1 (Vergil) before 1 (Statius): BCE negative, ascending.
    centuries = [int(e.split('::', 1)[0]) for e in body['ids']]
    assert centuries == sorted(centuries)


def test_map_genre_view_orders_rows_alphabetically(client, fixture_db):
    status, body = _get(client, '/api/passages/map', view='genre')
    assert status == 200
    assert body['labels'] == sorted(body['labels'], key=str.lower)


def test_map_genre_view_groups_by_genre_only(client, fixture_db):
    status, body = _get(client, '/api/passages/map', view='genre')
    assert status == 200
    assert body['labels'] == ['epic']


def test_map_unknown_view_reports_an_error(client, fixture_db):
    status, body = _get(client, '/api/passages/map', view='nonsense')
    assert status == 200
    assert 'error' in body


# --------------------------------------------------------------------------
# /api/passages/map/cell
# --------------------------------------------------------------------------

def test_cell_returns_the_work_pairs_behind_it(client, fixture_db):
    status, body = _get(client, '/api/passages/map/cell', view='work',
                        a='homer.iliad', b='vergil.aeneid')
    assert status == 200
    assert body['count'] == 1
    assert body['work_pairs'][0]['count'] == 6
    assert body['work_pairs'][0]['is_translation'] is False


def test_cell_404s_when_no_cache_is_built(client, monkeypatch, tmp_path):
    monkeypatch.setattr(connections_map, '_db_path', lambda: '/nonexistent/path.db')
    # No fallback cache present either -- a genuinely fresh checkout,
    # not just a fingerprint miss (see the staleness tests for that path).
    monkeypatch.setattr(connections_map, '_cache_dir', lambda: str(tmp_path / 'empty'))
    status, body = _get(client, '/api/passages/map/cell', view='work', a='x', b='y')
    assert status == 404


# --------------------------------------------------------------------------
# Live curated-pairs overlay (NC, 2026-09-19): "World English Bible against
# the Hebrew Bible and the Septuagint are the darkest cells... check why the
# curated and heuristic flags miss them." A cache's own is_translation_
# curated/is_translation_heuristic columns and count_notrans are baked in at
# BUILD time from whatever data/translation_pairs.json held THEN; fixing the
# JSON does nothing to an already-built cache until the next ~40-minute
# rebuild. _is_translation_pair() also checks the CURRENT JSON, live, on
# every request, so a curated-list fix is effective immediately -- these
# tests build a fixture row that is NOT flagged curated/heuristic (exactly
# the stale-cache scenario) and confirm the live JSON alone is enough to
# hide it.
# --------------------------------------------------------------------------

def test_live_curated_pairs_overlay_hides_a_pair_the_cache_itself_missed(
        client, fixture_db, monkeypatch):
    # homer.iliad <-> vergil.aeneid is built with curated=0, heuristic=0 (see
    # WORK_PAIRS) -- exactly a work pair whose cache predates a curated-list
    # fix. The live JSON says otherwise.
    monkeypatch.setattr(connections_map, '_curated_pairs',
                        lambda: {tuple(sorted(('homer.iliad', 'vergil.aeneid')))})
    status, body = _get(client, '/api/passages/map', view='work')
    assert status == 200
    ia = body['ids'].index('homer.iliad')
    ib = body['ids'].index('vergil.aeneid')
    assert body['counts'][ia][ib] == 0
    # The fixture's own baked-curated pair (novum_testamentum x web) plus
    # this newly-live-curated one.
    assert body['translation_pairs_hidden'] == 2


def test_live_curated_pairs_overlay_includes_it_when_translations_are_shown(
        client, fixture_db, monkeypatch):
    monkeypatch.setattr(connections_map, '_curated_pairs',
                        lambda: {tuple(sorted(('homer.iliad', 'vergil.aeneid')))})
    status, body = _get(client, '/api/passages/map', view='work', translations=1)
    assert status == 200
    ia = body['ids'].index('homer.iliad')
    ib = body['ids'].index('vergil.aeneid')
    assert body['counts'][ia][ib] == 6


def test_live_curated_pairs_overlay_applies_to_the_cell_route_too(
        client, fixture_db, monkeypatch):
    monkeypatch.setattr(connections_map, '_curated_pairs',
                        lambda: {tuple(sorted(('homer.iliad', 'vergil.aeneid')))})
    status, body = _get(client, '/api/passages/map/cell', view='work',
                        a='homer.iliad', b='vergil.aeneid')
    assert status == 200
    # Not flagged curated in the cache itself, but excluded (and so absent
    # from the list) once the live JSON is checked, exactly like a real
    # is_translation_curated=1 row.
    assert body['work_pairs'] == []


def test_curated_pairs_are_loaded_from_the_real_translation_pairs_json(monkeypatch):
    # Not a fixture test: this is the actual regenerated file, checked
    # directly, so a regression in the generator or the JSON itself is
    # caught here rather than only by the (mocked) fixture tests above.
    monkeypatch.setattr(connections_map, '_curated_pairs_cache', None)
    pairs = connections_map._curated_pairs()
    assert tuple(sorted(('world_english_bible.pentateuch', 'hebrew_bible.genesis'))) in pairs
    assert tuple(sorted(('world_english_bible.pentateuch', 'hebrew_bible.leviticus'))) in pairs
    assert tuple(sorted(('world_english_bible.pentateuch', 'hebrew_bible.numbers'))) in pairs
    assert tuple(sorted(('world_english_bible.pentateuch', 'hebrew_bible.deuteronomy'))) in pairs
    assert tuple(sorted(('world_english_bible.writings', 'hebrew_bible.psalms'))) in pairs
    assert tuple(sorted(('world_english_bible.pentateuch', 'septuaginta.genesis'))) in pairs
    assert tuple(sorted(('bohairic.genesis', 'world_english_bible.pentateuch'))) in pairs
    assert tuple(sorted(('bohairic.matthew', 'world_english_bible.new_testament'))) in pairs
    # The one hand-added literary pair (not scripture) survives regeneration.
    assert tuple(sorted(('eobanus.iliad', 'homer.iliad'))) in pairs


# --------------------------------------------------------------------------
# /api/passages/map/pair
# --------------------------------------------------------------------------

def test_pair_returns_window_level_edges_with_reader_urls(client, fixture_db):
    status, body = _get(client, '/api/passages/map/pair',
                        work_a='homer.iliad', work_b='vergil.aeneid')
    assert status == 200
    top = body['pairs'][0]
    assert top['score'] == 0.91
    assert top['window_a']['gist'] == 'Achilles rages at Agamemnon.'
    assert top['window_a']['reader_url'].startswith('/read?work=homer.iliad.tess')
    assert 'tab=similar' in top['window_a']['reader_url']


def test_pair_windows_carry_a_proper_title(client, fixture_db):
    # NC, 2026-09-19: the passage-pair list must show "author and work in
    # full, then the reference" -- a proper title, not the raw work slug.
    status, body = _get(client, '/api/passages/map/pair',
                        work_a='homer.iliad', work_b='vergil.aeneid')
    assert status == 200
    top = body['pairs'][0]
    assert top['window_a']['title'] == 'Iliad'
    assert top['window_a']['author_display'] == 'Homer'
    assert top['window_b']['title'] == 'Aeneid'
    assert top['window_b']['author_display'] == 'Vergil'


def test_work_label_uses_a_proper_title_not_the_raw_slug():
    assert connections_map._work_label('quintus_smyrnaeus.fall_of_troy', 'Quintus Smyrnaeus') \
        == 'Quintus Smyrnaeus, Fall of Troy'
    assert connections_map._work_label('homer.iliad', 'Homer') == 'Homer, Iliad'


# --------------------------------------------------------------------------
# Dedup + correct side ordering (NC, 2026-09-19): the fixture's EDGES table
# carries the Homer x Vergil pair twice -- once found from Homer's own
# neighbour search (grc-1 -> la-1, score 0.91) and once from Vergil's
# (la-1 -> grc-1, score 0.90) -- because cosine similarity is symmetric and
# each window runs its own top-k search. That is one passage pair, not two.
# --------------------------------------------------------------------------

def test_pair_deduplicates_the_reverse_direction_edge(client, fixture_db):
    status, body = _get(client, '/api/passages/map/pair',
                        work_a='homer.iliad', work_b='vergil.aeneid')
    assert status == 200
    # Only ONE pair for Homer x Vergil, not one per direction.
    assert body['count'] == 1
    assert len(body['pairs']) == 1
    # The higher-scoring direction (0.91) is the one kept.
    assert body['pairs'][0]['score'] == 0.91


def test_pair_always_shows_work_a_on_the_left_regardless_of_edge_direction(client, fixture_db):
    # Reversing the caller's work_a/work_b must still put work_a's own
    # window under the 'window_a' key -- previously this was read off
    # whichever edges row direction happened to match, which is exactly the
    # "shown reversed" half of the same bug.
    status, body = _get(client, '/api/passages/map/pair',
                        work_a='vergil.aeneid', work_b='homer.iliad')
    assert status == 200
    assert body['count'] == 1
    pair = body['pairs'][0]
    assert pair['window_a']['work'] == 'vergil.aeneid'
    assert pair['window_b']['work'] == 'homer.iliad'


def test_pair_reports_a_plain_error_for_an_unknown_work(client, fixture_db):
    status, body = _get(client, '/api/passages/map/pair',
                        work_a='homer.iliad', work_b='nonexistent.work')
    assert status == 200
    assert 'error' in body


def test_pair_404s_when_no_cache_is_built(client, monkeypatch, tmp_path):
    monkeypatch.setattr(connections_map, '_db_path', lambda: '/nonexistent/path.db')
    # No fallback cache present either -- a genuinely fresh checkout,
    # not just a fingerprint miss (see the staleness tests for that path).
    monkeypatch.setattr(connections_map, '_cache_dir', lambda: str(tmp_path / 'empty'))
    status, body = _get(client, '/api/passages/map/pair', work_a='a', work_b='b')
    assert status == 404


# --------------------------------------------------------------------------
# /api/passages/map/work
# --------------------------------------------------------------------------

def test_work_route_lists_connections_sorted_by_strength(client, fixture_db):
    status, body = _get(client, '/api/passages/map/work', work='homer.iliad')
    assert status == 200
    assert body['work'] == 'homer.iliad'
    assert [c['work'] for c in body['connections']] == ['vergil.aeneid', 'statius.thebaid']


def test_work_route_404s_when_no_cache_is_built(client, monkeypatch, tmp_path):
    monkeypatch.setattr(connections_map, '_db_path', lambda: '/nonexistent/path.db')
    # No fallback cache present either -- a genuinely fresh checkout,
    # not just a fingerprint miss (see the staleness tests for that path).
    monkeypatch.setattr(connections_map, '_cache_dir', lambda: str(tmp_path / 'empty'))
    status, body = _get(client, '/api/passages/map/work', work='homer.iliad')
    assert status == 404


def test_work_route_reports_a_plain_error_for_an_unknown_work(client, fixture_db):
    status, body = _get(client, '/api/passages/map/work', work='nonexistent.work')
    assert status == 200
    assert 'error' in body


# --------------------------------------------------------------------------
# _book_of (NC, 2026-09-19): the grouping key for the third drill-down level.
# --------------------------------------------------------------------------

def test_book_of_multi_level_ref_uses_the_first_level():
    assert connections_map._book_of('hom. il. 4.446') == ('b4', '4')


def test_book_of_three_level_ref_still_uses_the_first_level():
    assert connections_map._book_of('abael. epist. 2.2.7') == ('b2', '2')


def test_book_of_single_level_ref_blocks_by_100_lines():
    assert connections_map._book_of('apophthegmata.patrum.37') == ('block1', '1')
    assert connections_map._book_of('apophthegmata.patrum.145') == ('block101', '101')


def test_book_of_no_locus_number_is_none():
    assert connections_map._book_of('') == (None, None)
    assert connections_map._book_of(None) == (None, None)


# --------------------------------------------------------------------------
# Nested grids (NC, 2026-09-19): a second fixture with two works for one
# author and multi-book refs, kept separate from `fixture_db` above so that
# fixture's exact-order assertions stay untouched.
# --------------------------------------------------------------------------

NESTED_WORKS = [
    ('homer.iliad', 'grc', 'homer', 'Homer', -750, 'Archaic', -8, '8th c. BCE',
     'epic', 200, 0, 0.0),
    ('vergil.aeneid', 'la', 'vergil', 'Vergil', -19, 'Augustan', -1, '1st c. BCE',
     'epic', 100, 0, 0.0),
    ('vergil.georgics', 'la', 'vergil', 'Vergil', -29, 'Augustan', -1, '1st c. BCE',
     'didactic', 50, 0, 0.0),
    ('statius.thebaid', 'la', 'statius', 'Statius', 96, 'Silver Age', 1, '1st c. CE',
     'epic', 80, 0, 0.0),
]

NESTED_WORK_PAIRS = [
    ('homer.iliad', 'vergil.aeneid', 'grc', 'la', 6, 6, 0, 0),
    ('homer.iliad', 'vergil.georgics', 'grc', 'la', 3, 3, 0, 0),
    ('statius.thebaid', 'vergil.aeneid', 'la', 'la', 4, 4, 0, 0),
]

# Statius book 1 (st-1) links to Vergil book 1 twice (vg-1, vg-2); Statius
# book 2 (st-2) links to Vergil book 2 once (vg-3). No book-1 x book-2 links
# at all, so the books grid should show that off-diagonal emptiness too.
NESTED_WINDOWS = [
    ('st-1', 'statius.thebaid', 'la', '1.1', '1.10', 'The Argive host, book one.'),
    ('st-2', 'statius.thebaid', 'la', '2.100', '2.110', 'The Argive host, book two.'),
    ('vg-1', 'vergil.aeneid', 'la', '1.1', '1.10', 'Arms and the man, book one.'),
    ('vg-2', 'vergil.aeneid', 'la', '1.50', '1.60', 'Juno nurses her anger, book one.'),
    ('vg-3', 'vergil.aeneid', 'la', '2.200', '2.210', 'Troy falls in flame, book two.'),
]

NESTED_EDGES = [
    ('st-1', 'vg-1', 0.80, 'statius.thebaid', 'vergil.aeneid', 0, 0),
    ('st-1', 'vg-2', 0.70, 'statius.thebaid', 'vergil.aeneid', 0, 0),
    ('st-2', 'vg-3', 0.75, 'statius.thebaid', 'vergil.aeneid', 0, 0),
]


def _build_nested_fixture_db(path):
    conn = sqlite3.connect(path)
    conn.executescript('''
        CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT);
        CREATE TABLE works (
            work TEXT PRIMARY KEY, language TEXT, author_key TEXT, author_display TEXT,
            year INTEGER, era_label TEXT, century INTEGER, century_label TEXT,
            genre TEXT, window_count INTEGER, total_links INTEGER, links_per_window REAL
        );
        CREATE TABLE windows (
            id TEXT PRIMARY KEY, work TEXT, language TEXT, ref_start TEXT, ref_end TEXT, gist TEXT
        );
        CREATE TABLE edges (
            window_a TEXT, window_b TEXT, score REAL,
            work_a TEXT, work_b TEXT, pos_a INTEGER, pos_b INTEGER
        );
        CREATE TABLE work_pairs (
            work_a TEXT, work_b TEXT, lang_a TEXT, lang_b TEXT,
            count INTEGER, count_notrans INTEGER,
            is_translation_curated INTEGER, is_translation_heuristic INTEGER,
            PRIMARY KEY (work_a, work_b)
        );
    ''')
    conn.executemany('INSERT INTO works VALUES (?,?,?,?,?,?,?,?,?,?,?,?)', NESTED_WORKS)
    conn.executemany('INSERT INTO windows VALUES (?,?,?,?,?,?)', NESTED_WINDOWS)
    conn.executemany('INSERT INTO edges VALUES (?,?,?,?,?,?,?)', NESTED_EDGES)
    conn.executemany('INSERT INTO work_pairs VALUES (?,?,?,?,?,?,?,?)', NESTED_WORK_PAIRS)
    conn.executemany('INSERT INTO meta VALUES (?,?)',
                     [('built_at', json.dumps('2026-09-19T00:00:00')),
                      ('edges_kept', json.dumps(len(NESTED_EDGES)))])
    conn.commit()
    conn.close()


@pytest.fixture
def nested_fixture_db(tmp_path, monkeypatch):
    path = str(tmp_path / 'nested_fixture.db')
    _build_nested_fixture_db(path)
    monkeypatch.setattr(connections_map, '_db_path', lambda: path)
    monkeypatch.setattr(connections_map, '_cache_dir', lambda: str(tmp_path / 'empty'))
    monkeypatch.setattr(connections_map, '_current_ids', lambda: {w[0] for w in NESTED_WINDOWS})
    monkeypatch.setattr(connections_map, '_curated_pairs', lambda: set())
    return path


# --------------------------------------------------------------------------
# /api/passages/map/cell -- the "second heatmap" data (works_matrix)
# --------------------------------------------------------------------------

def test_cell_author_view_includes_a_works_matrix(client, nested_fixture_db):
    status, body = _get(client, '/api/passages/map/cell', view='author',
                        a='homer::grc', b='vergil::la')
    assert status == 200
    wm = body['works_matrix']
    assert wm is not None
    assert wm['ids_a'] == ['homer.iliad']
    assert wm['ids_b'] == ['vergil.aeneid', 'vergil.georgics']
    assert wm['counts'] == [[6, 3]]
    assert wm['normalised'][0][0] == 1.0
    # Proper titles, not the raw underscored slug (NC, 2026-09-19).
    assert wm['labels_a'] == ['Homer, Iliad']
    assert wm['labels_b'] == ['Vergil, Aeneid', 'Vergil, Georgics']


def test_cell_work_view_works_matrix_is_a_single_cell(client, nested_fixture_db):
    status, body = _get(client, '/api/passages/map/cell', view='work',
                        a='statius.thebaid', b='vergil.aeneid')
    assert status == 200
    wm = body['works_matrix']
    assert wm['ids_a'] == ['statius.thebaid']
    assert wm['ids_b'] == ['vergil.aeneid']
    assert wm['counts'] == [[4]]


def test_cell_works_matrix_is_none_with_no_matching_rows(client, nested_fixture_db):
    status, body = _get(client, '/api/passages/map/cell', view='author',
                        a='homer::grc', b='statius::la')
    assert status == 200
    assert body['works_matrix'] is None
    assert body['work_pairs'] == []


# --------------------------------------------------------------------------
# /api/passages/map/books -- the third drill-down level
# --------------------------------------------------------------------------

def test_books_route_groups_edges_by_first_locus_level(client, nested_fixture_db):
    status, body = _get(client, '/api/passages/map/books',
                        work_a='statius.thebaid', work_b='vergil.aeneid')
    assert status == 200
    assert body['ids_a'] == ['b1', 'b2']
    assert body['labels_a'] == ['1', '2']
    assert body['ids_b'] == ['b1', 'b2']
    assert body['labels_b'] == ['1', '2']
    assert body['counts'] == [[2, 0], [0, 1]]
    assert body['normalised'][0][0] == 1.0


def test_books_route_404s_when_no_cache_is_built(client, monkeypatch, tmp_path):
    monkeypatch.setattr(connections_map, '_db_path', lambda: '/nonexistent/path.db')
    # No fallback cache present either -- a genuinely fresh checkout,
    # not just a fingerprint miss (see the staleness tests for that path).
    monkeypatch.setattr(connections_map, '_cache_dir', lambda: str(tmp_path / 'empty'))
    status, body = _get(client, '/api/passages/map/books', work_a='a', work_b='b')
    assert status == 404


def test_books_route_reports_a_plain_error_for_an_unknown_work(client, nested_fixture_db):
    status, body = _get(client, '/api/passages/map/books',
                        work_a='statius.thebaid', work_b='nonexistent.work')
    assert status == 200
    assert 'error' in body


# --------------------------------------------------------------------------
# /api/passages/map/pair?book_a=&book_b= -- the books grid's own cell click
# --------------------------------------------------------------------------

def test_pair_filters_to_the_requested_books(client, nested_fixture_db):
    status, body = _get(client, '/api/passages/map/pair',
                        work_a='statius.thebaid', work_b='vergil.aeneid',
                        book_a='b1', book_b='b1')
    assert status == 200
    assert body['count'] == 2
    assert all(p['window_a']['ref_start'].startswith('1.') for p in body['pairs'])
    assert all(p['window_b']['ref_start'].startswith('1.') for p in body['pairs'])


def test_pair_book_filter_excludes_the_other_book_pair(client, nested_fixture_db):
    status, body = _get(client, '/api/passages/map/pair',
                        work_a='statius.thebaid', work_b='vergil.aeneid',
                        book_a='b2', book_b='b2')
    assert status == 200
    assert body['count'] == 1
    assert body['pairs'][0]['window_a']['ref_start'] == '2.100'
    assert body['pairs'][0]['window_b']['ref_start'] == '2.200'


# --------------------------------------------------------------------------
# Staleness fallback (NC, 2026-09-19): a corpus edit changes
# index_fingerprint() long before a ~40-minute rebuild can catch up. When no
# cache matches exactly, the most recently built cache present is served
# instead of a flat "not built", marked `stale` in the response.
# --------------------------------------------------------------------------

# Realistic 'work:scale:index' ids -- the shape _stale_info actually parses
# (work prefix, then scale, then a local index) -- one per fixture WORKS
# entry, standing in for "nothing has changed since this cache was built".
# All five WORKS entries are always in a fixture db's own works table, so
# this counts as the full population every time.
FULL_CURRENT_IDS = {f'{w[0]}:fine:0' for w in WORKS}


def _isolate_cache_dir(monkeypatch, cache_dir, exact_path, current_ids):
    """No exact-fingerprint match at `exact_path`; `cache_dir` is where the
    fallback scan looks; `current_ids` stands in for the current index's own
    window ids (get_pair/get_books_map's existence filter, and the stale
    window count)."""
    monkeypatch.setattr(connections_map, '_db_path', lambda: exact_path)
    monkeypatch.setattr(connections_map, '_cache_dir', lambda: str(cache_dir))
    monkeypatch.setattr(connections_map, '_current_ids', lambda: current_ids)
    monkeypatch.setattr(connections_map, '_curated_pairs', lambda: set())


def test_stale_window_count_compares_the_same_population_add_and_remove(
        client, monkeypatch, tmp_path):
    """NC, 2026-09-19 correction: window_diff must be a true before/after of
    the SAME population (fine-scale windows of works this cache covers), not
    the cache's own five-work subset against the whole corpus (which could
    read "changed by 300,000 windows" for a two-window edit). Fixture: one
    id is REMOVED (statius.thebaid's window retired) and one is ADDED for a
    work this cache does not cover at all (growth elsewhere in the corpus,
    a different language's text). The addition must not move the count --
    only the in-scope retirement should.
    """
    cache_dir = tmp_path / 'cache'
    cache_dir.mkdir()
    old_path = str(cache_dir / 'old-fingerprint.db')
    _build_fixture_db(old_path, built_at='2026-09-18T12:00:00', subset_windows=5)
    current_ids = (FULL_CURRENT_IDS - {'statius.thebaid:fine:0'}) | {'brand_new_author.new_work:fine:0'}
    _isolate_cache_dir(monkeypatch, cache_dir, str(cache_dir / 'current-fingerprint.db'), current_ids)

    status, body = _get(client, '/api/passages/map', view='work')
    assert status == 200
    # The fallback data is still real data (from the old cache), not empty.
    assert 'homer.iliad' in body['ids']
    assert body['stale'] == {
        'cache_built_at': '2026-09-18T12:00:00',
        'cache_window_count': 5,
        'current_window_count': 4,   # 5 - 1 retired; the addition outside scope doesn't count
        'window_diff': 1,
    }


def test_stale_window_count_ignores_non_fine_scale_ids(client, monkeypatch, tmp_path):
    # A coarse-scale id for one of the cache's own works must not be counted
    # -- the cache's own subset_windows is fine-scale only.
    cache_dir = tmp_path / 'cache'
    cache_dir.mkdir()
    old_path = str(cache_dir / 'old-fingerprint.db')
    _build_fixture_db(old_path, built_at='2026-09-18T12:00:00', subset_windows=5)
    current_ids = FULL_CURRENT_IDS | {'homer.iliad:coarse:0'}
    _isolate_cache_dir(monkeypatch, cache_dir, str(cache_dir / 'current-fingerprint.db'), current_ids)

    status, body = _get(client, '/api/passages/map', view='work')
    assert status == 200
    assert body['stale']['current_window_count'] == 5
    assert body['stale']['window_diff'] == 0


def test_stale_window_count_normalizes_part_files_to_their_base_work(client, monkeypatch, tmp_path):
    # A window id from a .part.N file must count against its base work, the
    # same normalization scripts/build_connections_map.py's norm_work() does
    # (and so the same id the works table itself keys on).
    cache_dir = tmp_path / 'cache'
    cache_dir.mkdir()
    old_path = str(cache_dir / 'old-fingerprint.db')
    _build_fixture_db(old_path, built_at='2026-09-18T12:00:00', subset_windows=5)
    current_ids = (FULL_CURRENT_IDS - {'homer.iliad:fine:0'}) | {'homer.iliad.part.1:fine:0'}
    _isolate_cache_dir(monkeypatch, cache_dir, str(cache_dir / 'current-fingerprint.db'), current_ids)

    status, body = _get(client, '/api/passages/map', view='work')
    assert status == 200
    assert body['stale']['current_window_count'] == 5
    assert body['stale']['window_diff'] == 0


def test_cell_and_pair_and_books_and_work_routes_all_report_stale_too(
        client, monkeypatch, tmp_path):
    # The notice belongs on every route that reads the cache, not just the
    # top-level map -- a reader can land on any of them directly.
    cache_dir = tmp_path / 'cache'
    cache_dir.mkdir()
    old_path = str(cache_dir / 'old-fingerprint.db')
    _build_fixture_db(old_path, built_at='2026-09-18T12:00:00', subset_windows=3)
    _isolate_cache_dir(monkeypatch, cache_dir, str(cache_dir / 'current-fingerprint.db'),
                       FULL_CURRENT_IDS)

    _, cell_body = _get(client, '/api/passages/map/cell', view='work',
                        a='homer.iliad', b='vergil.aeneid')
    assert cell_body['stale']['cache_built_at'] == '2026-09-18T12:00:00'

    _, pair_body = _get(client, '/api/passages/map/pair',
                        work_a='homer.iliad', work_b='vergil.aeneid')
    assert pair_body['stale']['cache_built_at'] == '2026-09-18T12:00:00'

    _, work_body = _get(client, '/api/passages/map/work', work='homer.iliad')
    assert work_body['stale']['cache_built_at'] == '2026-09-18T12:00:00'


def test_map_prefers_the_most_recently_built_cache_among_several_stale_ones(
        client, monkeypatch, tmp_path):
    cache_dir = tmp_path / 'cache'
    cache_dir.mkdir()
    older = str(cache_dir / 'a.db')
    newer = str(cache_dir / 'b.db')
    _build_fixture_db(older, built_at='2026-09-01T00:00:00')
    _build_fixture_db(newer, built_at='2026-09-18T12:00:00')
    _isolate_cache_dir(monkeypatch, cache_dir, str(cache_dir / 'current-fingerprint.db'),
                       FULL_CURRENT_IDS)

    status, body = _get(client, '/api/passages/map', view='work')
    assert status == 200
    assert body['stale']['cache_built_at'] == '2026-09-18T12:00:00'


def test_map_uses_the_exact_match_with_no_stale_notice_when_one_exists(
        client, monkeypatch, tmp_path):
    # An older cache sits right next to the current one -- the exact match
    # must win outright, with no `stale` key at all (NC: "keep the exact
    # match path as is when it matches").
    cache_dir = tmp_path / 'cache'
    cache_dir.mkdir()
    exact_path = str(cache_dir / 'current-fingerprint.db')
    _build_fixture_db(exact_path)
    _build_fixture_db(str(cache_dir / 'old-fingerprint.db'), built_at='2020-01-01T00:00:00')
    monkeypatch.setattr(connections_map, '_db_path', lambda: exact_path)
    monkeypatch.setattr(connections_map, '_cache_dir', lambda: str(cache_dir))
    monkeypatch.setattr(connections_map, '_current_ids', lambda: FULL_CURRENT_IDS)
    monkeypatch.setattr(connections_map, '_curated_pairs', lambda: set())

    status, body = _get(client, '/api/passages/map', view='work')
    assert status == 200
    assert 'stale' not in body


def test_meta_reports_stale_when_falling_back(monkeypatch, tmp_path):
    # connections_map.meta() has no Flask route of its own yet (reserved for
    # a future status display) -- called directly.
    cache_dir = tmp_path / 'cache'
    cache_dir.mkdir()
    old_path = str(cache_dir / 'old-fingerprint.db')
    _build_fixture_db(old_path, built_at='2026-09-18T12:00:00', subset_windows=3)
    _isolate_cache_dir(monkeypatch, cache_dir, str(cache_dir / 'current-fingerprint.db'),
                       FULL_CURRENT_IDS)
    out = connections_map.meta()
    assert out['built_at'] == '2026-09-18T12:00:00'
    assert out['stale']['cache_built_at'] == '2026-09-18T12:00:00'


# --------------------------------------------------------------------------
# Window-existence filtering (NC, 2026-09-19): a retired window can still
# sit in an old (or even the current) cache's edges table; the drill-down
# must never link the Reader to a passage the corpus no longer has.
# --------------------------------------------------------------------------

def test_pair_skips_an_edge_whose_window_has_been_retired(client, nested_fixture_db, monkeypatch):
    # Without any retirement, book 1 has two pairs (st-1 x vg-1, st-1 x vg-2).
    status, body = _get(client, '/api/passages/map/pair',
                        work_a='statius.thebaid', work_b='vergil.aeneid',
                        book_a='b1', book_b='b1')
    assert body['count'] == 2

    # vg-2 is retired from the current index.
    monkeypatch.setattr(connections_map, '_current_ids',
                        lambda: {w[0] for w in NESTED_WINDOWS if w[0] != 'vg-2'})
    status, body = _get(client, '/api/passages/map/pair',
                        work_a='statius.thebaid', work_b='vergil.aeneid',
                        book_a='b1', book_b='b1')
    assert status == 200
    assert body['count'] == 1
    assert body['pairs'][0]['window_b']['window_id'] == 'vg-1'


def test_pair_id_filter_fails_open_when_current_ids_is_unreadable(client, nested_fixture_db, monkeypatch):
    # An empty current-ids set means ids.json could not be read (an
    # environment problem), not "every window is gone" -- the filter must
    # not silently zero out every result in that case.
    monkeypatch.setattr(connections_map, '_current_ids', lambda: set())
    status, body = _get(client, '/api/passages/map/pair',
                        work_a='statius.thebaid', work_b='vergil.aeneid')
    assert status == 200
    assert body['count'] == 3


def test_books_map_skips_an_edge_whose_window_has_been_retired(client, nested_fixture_db, monkeypatch):
    # Without any retirement, book1 x book1 has 2 edges (see the fixture).
    status, body = _get(client, '/api/passages/map/books',
                        work_a='statius.thebaid', work_b='vergil.aeneid')
    assert body['counts'][0][0] == 2

    monkeypatch.setattr(connections_map, '_current_ids',
                        lambda: {w[0] for w in NESTED_WINDOWS if w[0] != 'vg-2'})
    status, body = _get(client, '/api/passages/map/books',
                        work_a='statius.thebaid', work_b='vergil.aeneid')
    assert status == 200
    assert body['counts'][0][0] == 1
