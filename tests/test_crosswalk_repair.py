"""The distance rule and the repair rule of the crosswalk check, on a tiny fixture."""
import os
import sqlite3
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts', 'documents'))
import apply_crosswalk_repair as A  # noqa: E402
import check_crosswalk_against_edh as C  # noqa: E402
import crosswalk_repair_lib as L  # noqa: E402

POINTS = {'roma': (41.89, 12.49), 'ostia': (41.756, 12.291), 'aalen': (48.678, 10.151), 'aquileia': (45.770, 13.371),
          'virunum': (46.7, 14.4), 'turris': (40.84, 8.40), 'cremona': (45.13, 10.03)}
PTS = {'1': POINTS['roma'], '2': POINTS['ostia'], '3': POINTS['aalen'], '4': POINTS['aquileia'], '5': POINTS['virunum'],
       '6': POINTS['turris']}
EXTRACT = {'1': {'title': 'Roma', 'names': ['Roma'], 'repr': list(POINTS['roma']), 'bbox': None, 'types': []},
           '2': {'title': 'Ostia', 'names': ['Ostia'], 'repr': list(POINTS['ostia']), 'bbox': None, 'types': []},
           '3': {'title': 'Aquileia', 'names': ['Aquileia'], 'repr': list(POINTS['aalen']), 'bbox': None, 'types': []},
           '4': {'title': 'Aquileia', 'names': ['Aquileia'], 'repr': list(POINTS['aquileia']), 'bbox': None, 'types': []},
           '7': {'title': 'Unlocated', 'names': ['Unlocated'], 'repr': None, 'bbox': [10.0, 20.0, 12.0, 22.0], 'types': []},
           '8': {'title': 'Nowhere', 'names': ['Nowhere'], 'repr': None, 'bbox': None, 'types': []}}


def feat(name, pid, lat, lon):
    return {'pleiades': pid, 'name': name, 'lat': lat, 'lon': lon, 'edh_uri': ''}


def test_haversine_known_distance():
    assert abs(L.haversine_km(41.89, 12.49, 41.756, 12.291) - 22.3) < 0.5


def test_summary_uses_median_and_majority_id():
    feats = [feat('Ostia', '2', 41.75, 12.29), feat('Ostia', '2', 41.76, 12.29), feat('Ostia, bei', '1', 41.77, 12.30),
             feat('Ostia?', None, 41.76, 12.28)]
    s = L.tm_summary(feats)
    assert s['edh_id'] == '2'
    assert abs(s['center'][0] - 41.76) < 0.006
    assert s['names'][0] == 'ostia'
    assert s['last_feature_id'] == '1'


def test_rule1_ostia_under_roma_is_a_suspect_though_only_22_km_away():
    s = L.tm_summary([feat('Ostia', '2', 41.756, 12.291)] * 3)
    rule, dc, de = L.classify_row('1', s, PTS)
    assert rule == 1 and 20 < dc < 25 and de < dc / 2


def test_rule1_needs_edh_to_be_closer():
    s = L.tm_summary([feat('Roma', '1', 41.89, 12.49), feat('Roma', '1', 41.89, 12.49)])
    assert L.classify_row('1', s, PTS)[0] is None
    # near but not twice as near as the crosswalk's id: not a suspect
    s2 = L.tm_summary([feat('Roma', '2', 41.82, 12.39)] * 2)
    assert L.classify_row('1', s2, PTS)[0] is None


def test_rule2_far_row_is_a_suspect_even_when_edh_agrees():
    s = L.tm_summary([feat('Aquileia', '3', 45.77, 13.37)] * 2)  # EDH's own uri is the German Aquileia
    rule, dc, de = L.classify_row('3', s, PTS, EXTRACT)
    assert rule == 2 and dc > 400


def test_repair_rule1_takes_edh_id_and_rule2_the_nearest_title_match():
    s = L.tm_summary([feat('Ostia', '2', 41.756, 12.291)] * 2)
    idx = L.build_name_indexes(EXTRACT)
    assert L.repair_row('1', 1, s, PTS, EXTRACT, idx) == ('2', 'rule1_edh_majority_id')
    s2 = L.tm_summary([feat('Aquileia', '3', 45.77, 13.37)] * 2)
    pid, how = L.repair_row('3', 2, s2, PTS, EXTRACT, idx)
    assert pid == '4' and how == 'rule2_nearest_title_match'


def test_repair_leaves_the_row_when_no_place_of_that_name_is_near():
    s = L.tm_summary([feat('Nowhere', None, 45.0, 13.0)])
    assert L.repair_row('3', 2, s, PTS, EXTRACT, L.build_name_indexes(EXTRACT)) == (None, 'no_candidate')


def test_point_falls_back_to_bbox_center_and_none():
    assert L.point_of('7', {}, EXTRACT) == (21.0, 11.0, 'bbox center')
    assert L.point_of('8', {}, EXTRACT) is None
    assert L.point_of('1', PTS, EXTRACT)[2] == 'points file'


def test_analyze_never_flags_a_row_that_agrees_with_edh():
    rows = [{'tm_place_id': '10', 'pleiades_id': '2', 'source': 'edh_geography', 'label': 'Ostia'},
            {'tm_place_id': '11', 'pleiades_id': '1', 'source': 'edh_geography', 'label': 'Roma'}]
    geo = {'10': [feat('Ostia', '2', 41.756, 12.291)], '11': [feat('Ostia', '2', 41.756, 12.291)]}
    recs = C.analyze(rows, geo, PTS, EXTRACT, L.build_name_indexes(EXTRACT), {}, {'10': 5, '11': 5})
    assert [r['rule'] for r in recs] == [None, 1]
    assert recs[1]['repair_id'] == '2'


def test_apply_changes_crosswalk_derived_ids_and_keeps_minority_region_and_source_ids():
    c = sqlite3.connect(':memory:')
    c.execute('CREATE TABLE documents (id TEXT, place_tm_id INTEGER, pleiades_id TEXT, ancient_place TEXT, region TEXT)')
    c.executemany('INSERT INTO documents VALUES (?,?,?,?,?)', [
        ('a', 3327, '3', 'Aquileia', 'Venetia'), ('b', 3327, '3', 'Aquileia', 'Venetia'),
        ('c', 3327, '3', 'Aquileia', 'Venetia'), ('h', 3327, '3', 'Aquileia', 'Raetia'),
        ('s', 3327, '9', 'Aquileia', 'Venetia'),  # an id from the source itself
        ('n', None, None, 'Hermopolites (?)', None)])
    out, counts = A.plan(c, {'3327': '3'}, {'3327': '4'}, {}, hermopolites_id='756575')
    assert out['a'] == ('4', 'A_crosswalk') and out['b'][0] == '4'
    assert 'h' not in out and counts['A_minority_region_kept'] == 1
    assert 's' not in out and counts['A_source_kept_would_differ'] == 1
    assert out['n'] == ('756575', 'C_hermopolites')
