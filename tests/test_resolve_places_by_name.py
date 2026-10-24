"""Name normalization and the sibling rule of scripts/documents/resolve_places_by_name.py, on a tiny fixture."""
import collections
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'scripts', 'documents'))
import resolve_places_by_name as r  # noqa: E402


def test_fold_and_variants():
    assert r.fold('Salonæ, Bei?') == 'salonae bei'
    vs = [r.fold(v) for v in r.variants('Ostia - Portus?')]
    assert vs[0] == 'ostia portus' and 'ostia' in vs
    assert 'tergeste' in [r.fold(v) for v in r.variants('Tergeste, bei')]
    assert 'philippi' in [r.fold(v) for v in r.variants('Colonia Iulia Augusta Philippensium (= Philippi)')]
    assert 'salona' in [r.fold(v) for v in r.variants('Salonae?')]
    assert 'virunum' in [r.fold(v) for v in r.variants('Municipium Claudium Virunum')]
    assert r.variants('') == []


PLACES = {
    '1': {'title': 'Roma', 'names': ['Roma'], 'types': ['urban'], 'desc': '', 'roman': True},
    '2': {'title': 'Ostia', 'names': ['Ostia'], 'types': ['settlement'], 'desc': '', 'roman': True},
    '3': {'title': 'Mediolanum', 'names': ['Mediolanum'], 'types': ['settlement'], 'desc': '', 'roman': True},
    '4': {'title': 'Mediolanum', 'names': ['Mediolanum'], 'types': ['settlement'], 'desc': '', 'roman': True},
}
POINTS = {'1': (41.9, 12.5, 'Roma'), '2': (41.75, 12.29, 'Ostia'), '3': (45.46, 9.19, 'Mediolanum'),
          '4': (46.56, 2.2, 'Mediolanum')}


def _indexes():
    t, n = collections.defaultdict(list), collections.defaultdict(list)
    for pid, pl in PLACES.items():
        t[r.fold(pl['title'])].append(pid)
        for nm in pl['names']:
            n[r.fold(nm)].append(pid)
    return t, n


def _run(unresolved, sib, env=None):
    t, n = _indexes()
    return r.resolve_names(unresolved, sib, PLACES, t, n, POINTS, env or {})


def test_sibling_rule_takes_dominant_place_and_ignores_suffix():
    sib = {'roma': {'': collections.Counter({'1': 9, '2': 1})}}
    res, left = _run({('Roma?', ''): {'n': 5, 'region': None, 'modern': None}}, sib)
    assert res[('Roma?', '')][1] == '1' and res[('Roma?', '')][2] == 'a'


def test_sibling_split_is_not_taken():
    sib = {'roma': {'': collections.Counter({'1': 5, '2': 5})}}
    res, left = _run({('Roma', ''): {'n': 5, 'region': None, 'modern': None}}, sib)
    assert ('Roma', '') not in res and left


def test_title_overrides_siblings_that_do_not_hold_the_name():
    # EDH files Ostia under Roma: the siblings say 1, but only place 2 is called Ostia
    sib = {'ostia': {'': collections.Counter({'1': 20})}}
    res, _ = _run({('Ostia - Portus', ''): {'n': 3, 'region': None, 'modern': None}}, sib)
    assert res[('Ostia - Portus', '')][1] == '2'


def test_region_chooses_between_namesakes():
    env = {'Transpadana (Regio XI)': (45.8, 7.9, 100.0)}
    res, _ = _run({('Mediolanum', 'Transpadana (Regio XI)'): {'n': 4, 'region': 'Transpadana (Regio XI)', 'modern': 'Milano'}}, {}, env)
    assert res[('Mediolanum', 'Transpadana (Regio XI)')][1] == '3'


def test_ambiguous_and_unknown_are_left():
    res, left = _run({('Mediolanum', ''): {'n': 4, 'region': None, 'modern': None},
                      ('unbekannt', ''): {'n': 9, 'region': None, 'modern': None},
                      ('Roma/Ostia', ''): {'n': 2, 'region': None, 'modern': None}}, {})
    assert not res and {x[0] for x in left} == {'Mediolanum', 'unbekannt', 'Roma/Ostia'}


def test_sibling_id_is_not_copied_across_different_region_fields():
    sib = {'roma': {'Germania superior': collections.Counter({'1': 9})}}
    res, left = _run({('Roma', 'Dacia'): {'n': 5, 'region': 'Dacia', 'modern': None}}, sib)
    assert ('Roma', 'Dacia') not in res or res[('Roma', 'Dacia')][2] != 'a'
    res, _ = _run({('Roma', 'Germania superior'): {'n': 5, 'region': 'Germania superior', 'modern': None}}, sib)
    assert res[('Roma', 'Germania superior')][1] == '1'


def test_hand_unresolved_names_and_unplaced_namesakes_far_apart_stay_unresolved():
    sib = {'apollonopolis': {'': collections.Counter({'1': 9})}}
    res, left = _run({('Apollonopolis', ''): {'n': 5, 'region': None, 'modern': None},
                      ('Aquae (Civitas Aurelia Aquensis), bei', 'Germania superior'): {'n': 2, 'region': 'Germania superior', 'modern': None}}, sib)
    assert not res and len(left) == 2
    res, left = _run({('Mediolanum', ''): {'n': 4, 'region': None, 'modern': None}}, {})
    assert not res and 'apart' in left[0][2]
