"""same_names_for_window: "same people and places", a second Similar
Passages grouping by shared RARE proper names (research/theme_search/
names_panel/NOTES.md, research/specs/2026-10-07_names_panel_spec.md).

No live index needed: a tiny fake window_names.db is built in a tmp dir and
the passage index's module state (`_records`, `_emb`, `_by_work`, `_ids`) is
monkeypatched directly, the same pattern tests/test_passages_works_route.py
and tests/test_window_for_passage.py already use.
"""
import json
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import pytest

from backend.app import app  # noqa: E402
from backend import passage_index as pi  # noqa: E402

N_WINDOWS = 1000
IDF_CELAI = 6.2146   # ln(1000 / (1+1))   -- rare
IDF_KLAND = 5.1160   # ln(1000 / (1+5))   -- rare
IDF_ITAQU = 0.2217   # ln(1000 / (1+800)) -- common, NOT a rare name
IDF_THIN = 4.6052    # ln(1000 / (1+9))   -- barely rare


def _build_names_db(path, rows, df):
    """rows: list of (window_id, key, form). df: {key: doc_freq}."""
    con = sqlite3.connect(path)
    con.execute('CREATE TABLE window_names (id TEXT, k TEXT, form TEXT)')
    con.execute('CREATE INDEX ix_wn_id ON window_names(id)')
    con.execute('CREATE INDEX ix_wn_k ON window_names(k)')
    con.executemany('INSERT INTO window_names VALUES (?,?,?)', rows)
    con.execute('CREATE TABLE name_df (k TEXT PRIMARY KEY, df INTEGER)')
    con.executemany('INSERT INTO name_df VALUES (?,?)', df.items())
    con.execute('CREATE TABLE meta (key TEXT, value TEXT)')
    con.execute("INSERT INTO meta VALUES ('windows', ?)", (str(N_WINDOWS),))
    con.commit()
    con.close()


@pytest.fixture(autouse=True)
def _reset_names_state(monkeypatch):
    """Every test gets its own 'process-lifetime' name-index cache, never a
    connection left open by a previous test or pointed at a previous tmp db."""
    monkeypatch.setattr(pi, '_names_state',
                        {'checked': False, 'conn': None, 'df': None, 'N': 0})
    monkeypatch.setattr(pi, '_row_by_id', None)
    monkeypatch.setitem(pi._state, 'loaded', True)
    monkeypatch.setitem(pi._state, 'ok', True)
    monkeypatch.setitem(pi._state, 'error', None)
    monkeypatch.setattr(pi, '_undescribed', set())
    monkeypatch.delenv('TESSERAE_HELD_LANGUAGES', raising=False)
    monkeypatch.delenv('TESSERAE_LANGUAGES', raising=False)


def _install(monkeypatch, records, emb):
    """Install a fake, already-loaded passage index."""
    monkeypatch.setattr(pi, '_records', records)
    monkeypatch.setattr(pi, '_ids', [r['id'] for r in records])
    monkeypatch.setattr(pi, '_emb', np.asarray(emb, dtype=np.float32))
    by_work = {}
    for i, r in enumerate(records):
        by_work.setdefault(pi._norm_work(r.get('work')), []).append(i)
    monkeypatch.setattr(pi, '_by_work', by_work)


def _rec(id_, work, language='la', scale='fine', gist='a passage'):
    return {'id': id_, 'work': work, 'language': language, 'scale': scale,
            'ref_start': '1.1', 'ref_end': '1.2',
            'desc': {'gist': gist}}


# ---------------------------------------------------------------------------
# The core scoring function
# ---------------------------------------------------------------------------

RECORDS = [
    _rec('src:fine:0', 'work_a.historiae.part.1', 'la'),            # 0 source
    _rec('b:fine:2', 'work_b.annals.part.5', 'grc'),                 # 1 shares 'celai'
    _rec('c:fine:1', 'work_c.walter_alexandreis', 'la'),             # 2 shares 'celai' + 'kland'
    _rec('d:fine:0', 'work_a.historiae.part.2', 'la'),               # 3 same base work: excluded
    _rec('e:coarse:0', 'work_e.text', 'la', scale='coarse'),         # 4 coarse scale: excluded
    _rec('f:fine:0', 'work_f.text', 'la'),                           # 5 shares only common word
    _rec('g:fine:3', 'servius.in_aeneidem', 'la'),                   # 6 commentary: set aside
    _rec('src2:fine:0', 'weak.work.part.1', 'la'),                   # 7 a weak-strength source
]

# dot(src, x) via the first coordinate (src = [1, 0])
EMB = [
    [1.0, 0.0],      # 0 src
    [0.80, 0.6],     # 1 b   -> raw dot 0.80
    [0.797, 0.604],  # 2 c   -> raw dot 0.797, but shares two rare keys
    [0.95, 0.312],   # 3 d
    [0.99, 0.141],   # 4 e
    [0.99, 0.141],   # 5 f
    [0.85, 0.527],   # 6 g
    [1.0, 0.0],      # 7 src2
]

NAME_ROWS = [
    ('src:fine:0', 'celai', 'Celaenae'),
    ('src:fine:0', 'kland', 'Cleander'),
    ('src:fine:0', 'itaqu', 'Itaque'),
    ('b:fine:2', 'celai', 'Kelainai'),
    ('c:fine:1', 'celai', 'Celaenis'),
    ('c:fine:1', 'kland', 'Cleandro'),
    ('d:fine:0', 'celai', 'Celaenas'),
    ('e:coarse:0', 'celai', 'Celaenarum'),
    ('f:fine:0', 'itaqu', 'Itaque'),
    ('g:fine:3', 'celai', 'Celaenae'),
    ('src2:fine:0', 'thinn', 'Thinnaeus'),
]
NAME_DF = {'celai': 1, 'kland': 5, 'itaqu': 800, 'thinn': 9}


def _setup(monkeypatch, tmp_path):
    db = str(tmp_path / 'window_names.db')
    _build_names_db(db, NAME_ROWS, NAME_DF)
    monkeypatch.setattr(pi, '_NAMES_PATH', db)
    _install(monkeypatch, RECORDS, EMB)


def test_missing_name_index_returns_none(monkeypatch, tmp_path):
    monkeypatch.setattr(pi, '_NAMES_PATH', str(tmp_path / 'absent.db'))
    _install(monkeypatch, RECORDS, EMB)
    assert pi.same_names_for_window('src:fine:0') is None


def test_rare_name_filtering_drops_candidates_sharing_only_a_common_word(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    out = pi.same_names_for_window('src:fine:0')
    ids = {r['id'] for r in out['results']} | {r['id'] for r in out['commentaries']}
    assert 'f:fine:0' not in ids, 'shared only the common word itaqu, not a rare name'
    assert out['strength'] == pytest.approx((IDF_CELAI - 4.5) + (IDF_KLAND - 4.5), abs=1e-3)


def test_same_base_work_is_excluded(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    out = pi.same_names_for_window('src:fine:0')
    ids = {r['id'] for r in out['results']} | {r['id'] for r in out['commentaries']}
    assert 'd:fine:0' not in ids, 'same base work as the source (work_a.historiae) must be excluded'


def test_coarse_scale_candidates_are_excluded(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    out = pi.same_names_for_window('src:fine:0')
    ids = {r['id'] for r in out['results']} | {r['id'] for r in out['commentaries']}
    assert 'e:coarse:0' not in ids


def test_commentaries_are_set_aside_from_results(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    out = pi.same_names_for_window('src:fine:0')
    result_ids = {r['id'] for r in out['results']}
    commentary_ids = {r['id'] for r in out['commentaries']}
    assert 'g:fine:3' in commentary_ids
    assert 'g:fine:3' not in result_ids


def test_score_ordering_rewards_shared_name_rarity_not_just_content(monkeypatch, tmp_path):
    """b has the higher raw content score (0.80 vs 0.797) but c shares TWO
    rare names against b's one, and the combined score puts c first."""
    _setup(monkeypatch, tmp_path)
    out = pi.same_names_for_window('src:fine:0')
    ids = [r['id'] for r in out['results']]
    assert ids == ['c:fine:1', 'b:fine:2'], ids
    c = next(r for r in out['results'] if r['id'] == 'c:fine:1')
    b = next(r for r in out['results'] if r['id'] == 'b:fine:2')
    assert c['score'] > b['score']


def test_shared_names_use_the_source_windows_spelling(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    out = pi.same_names_for_window('src:fine:0')
    c = next(r for r in out['results'] if r['id'] == 'c:fine:1')
    # The source spelled it "Celaenae" and "Cleander"; c's own window_names
    # rows say "Celaenis"/"Cleandro", but the card uses the SOURCE's spelling.
    assert c['shared_names'] == ['Celaenae', 'Cleander']
    b = next(r for r in out['results'] if r['id'] == 'b:fine:2')
    assert b['shared_names'] == ['Celaenae']


def test_results_are_shaped_like_find_similar_to_window(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    out = pi.same_names_for_window('src:fine:0')
    r = out['results'][0]
    for key in ('id', 'language', 'work', 'scale', 'ref_start', 'ref_end',
               'score', 'gist', 'themes', 'author', 'title', 'display_name'):
        assert key in r, f'{key} missing from a same_names result card'


def test_weak_flag_for_a_thin_strength_source(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    out = pi.same_names_for_window('src2:fine:0')
    assert out['strength'] == pytest.approx(IDF_THIN - 4.5, abs=1e-3)
    assert out['weak'] is True


def test_not_weak_when_strength_clears_the_threshold(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    out = pi.same_names_for_window('src:fine:0')
    assert out['weak'] is False


def test_unknown_window_returns_none(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    assert pi.same_names_for_window('does-not-exist') is None


# ---------------------------------------------------------------------------
# The route: /passages/similar?same_names=1
# ---------------------------------------------------------------------------

ROUTE_RECORDS = [
    _rec('rsrc:fine:0', 'rsrc.work.part.1', 'la'),
    _rec('rdup:fine:0', 'rdup.work', 'la'),      # shares a rare name AND scores high on content
    _rec('rother:fine:0', 'rother.work', 'la'),  # content-similar only, no shared name
    _rec('rfiller1:fine:0', 'rfiller1.work', 'la'),
    _rec('rfiller2:fine:0', 'rfiller2.work', 'la'),
]
ROUTE_EMB = [
    [1.0, 0.0],
    [0.95, 0.312],
    [0.85, 0.527],
    [0.40, 0.917],
    [0.30, 0.954],
]
ROUTE_NAME_ROWS = [
    ('rsrc:fine:0', 'uniqn', 'Uniquella'),
    ('rdup:fine:0', 'uniqn', 'Uniquilla'),
]
ROUTE_NAME_DF = {'uniqn': 1}


def _route():
    return next(str(r) for r in app.url_map.iter_rules()
                if str(r).endswith('/passages/similar'))


def test_route_without_the_parameter_is_byte_for_byte_unchanged(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    client = app.test_client()
    direct = pi.find_similar_to_window('src:fine:0', limit=15, languages=None,
                                       include_same_work=False,
                                       suppress_other_versions=True)
    direct['presentation'] = (
        'These passages resemble the selection in CONTENT (scene type, theme, '
        'situation) rather than in wording. Say what kind of resemblance each '
        'shows, and note that a cross-language match shares no vocabulary. '
        'A result carrying `also_in` is one scriptural passage present in several '
        'of the corpus versions, collapsed into a single entry.')
    r = client.get(f'{_route()}?window=src:fine:0')
    assert r.status_code == 200
    got = json.loads(r.get_data())
    assert 'same_names' not in got
    assert got == direct


def test_route_with_the_parameter_adds_same_names_and_dedupes_results(monkeypatch, tmp_path):
    db = str(tmp_path / 'window_names.db')
    _build_names_db(db, ROUTE_NAME_ROWS, ROUTE_NAME_DF)
    monkeypatch.setattr(pi, '_NAMES_PATH', db)
    _install(monkeypatch, ROUTE_RECORDS, ROUTE_EMB)

    client = app.test_client()
    plain = client.get(f'{_route()}?window=rsrc:fine:0')
    plain_ids = {r['id'] for r in json.loads(plain.get_data())['results']}
    assert 'rdup:fine:0' in plain_ids, 'test setup: rdup must show up in the plain content ranking'

    r = client.get(f'{_route()}?window=rsrc:fine:0&same_names=1')
    assert r.status_code == 200
    got = json.loads(r.get_data())
    assert got['same_names'] is not None
    same_ids = {x['id'] for x in got['same_names']['results']} | \
              {x['id'] for x in got['same_names']['commentaries']}
    assert 'rdup:fine:0' in same_ids
    result_ids = {r['id'] for r in got['results']}
    assert 'rdup:fine:0' not in result_ids, \
        'a window already shown under same_names must not also appear in results'
    assert 'rother:fine:0' in result_ids, 'a window with no shared name stays in the plain group'


def test_route_same_names_null_when_index_absent(monkeypatch, tmp_path):
    monkeypatch.setattr(pi, '_NAMES_PATH', str(tmp_path / 'absent.db'))
    _install(monkeypatch, ROUTE_RECORDS, ROUTE_EMB)
    client = app.test_client()
    r = client.get(f'{_route()}?window=rsrc:fine:0&same_names=1')
    got = json.loads(r.get_data())
    assert got['same_names'] is None
