"""Line search's whole-corpus counts by work (2026-10-07): the corpus chart
drew from the first 500 lines only, so a common pair left out the authors
being compared. _count_candidates_by_work counts every co-occurring line the
index returned, once per work."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import backend.app  # noqa: E402,F401  (the application must be built first)
from backend.blueprints import line_search as A  # noqa: E402  (the helpers live here now)


def test_counts_a_work_once_whole_file_preferred(monkeypatch):
    monkeypatch.setattr(A, 'resolve_text_path', lambda d, l, f: f)
    monkeypatch.setattr(A, 'get_text_metadata', lambda p: {
        'author': p.split('.')[0].title(), 'title': p.split('.')[1].title()})
    cands = {
        'hafez.diwan.tess': [('r1',), ('r2',), ('r3',)],
        'saeb.diwan.part.1.tess': [('a',)] * 4,
        'saeb.diwan.part.2.tess': [('b',)] * 6,
        'vergil.aeneid.tess': [('x',)] * 2,
        'vergil.aeneid.part.1.tess': [('x',)] * 2,
    }
    dates = {'hafez': {'year': 1390, 'era': 'Timurid'}, 'saeb': {'year': 1676, 'era': 'Safavid'}}
    out = A._count_candidates_by_work(cands, 'fa', dates)
    by = {w['work_id']: w for w in out}
    assert by['hafez.diwan']['count'] == 3
    assert by['saeb.diwan']['count'] == 10            # book files summed
    assert by['vergil.aeneid']['count'] == 2          # whole file, not whole + book
    assert by['hafez.diwan']['author'] == 'Hafez' and by['hafez.diwan']['year'] == 1390
    assert [w['work_id'] for w in out][:2] == ['hafez.diwan', 'saeb.diwan']   # by year


def test_counts_only_candidates_within_the_closeness_rule(monkeypatch):
    """2026-10-11: the chart counted a Tacitus line that the list under it did
    not show, because the count ignored the closeness rule the list applies
    (passes_distance_filter: the smallest gap between two different matched
    words within 4 tokens in prose, 10 in verse). A prose candidate whose
    nearest pair is further apart than that is not counted; a verse candidate
    within the rule is; a match tuple without positions is counted as before."""
    monkeypatch.setattr(A, 'resolve_text_path', lambda d, l, f: f)
    monkeypatch.setattr(A, 'get_text_metadata', lambda p: {
        'author': p.split('.')[0].title(), 'title': p.split('.')[1].title()})
    monkeypatch.setattr(A, '_get_max_distance', lambda f, lang: 4 if f.startswith('tacitus') else 10)
    far = {'infero': [12], 'latium': [53]}
    near = {'infero': [3], 'latium': [5]}
    repeated = {'infero': [3, 90], 'latium': [93]}     # one close pair among far ones
    verse_ok = {'arma': [1], 'vir': [11]}               # gap 10, within the verse rule
    verse_far = {'arma': [1], 'vir': [12]}              # gap 11, outside it
    cands = {
        'tacitus.historiae.part.3.tess': [('3.55', ['infero', 'latium'], far)],
        'tacitus.historiae.part.4.tess': [('4.1', ['infero', 'latium'], near),
                                          ('4.2', ['infero', 'latium'], far),
                                          ('4.3', ['infero', 'latium'], repeated)],
        'vergil.aeneid.part.1.tess': [('1.1', ['arma', 'vir'], verse_ok),
                                      ('1.2', ['arma', 'vir'], verse_far),
                                      ('1.3', ['arma', 'vir'], None),
                                      ('1.4', ['arma'], {'arma': [7]})],
        'solinus.collectanea.tess': [('2.6',)],
    }
    out = A._count_candidates_by_work(cands, 'la', {})
    by = {w['work_id']: w for w in out}
    assert by['tacitus.historiae']['count'] == 2       # 4.1 and 4.3; 3.55 and 4.2 too far apart
    assert by['vergil.aeneid']['count'] == 3           # 1.1 within the rule, 1.3 and 1.4 unpositioned
    assert by['solinus.collectanea']['count'] == 1     # old-style tuple, counted as before
    assert sum(w['count'] for w in out) == 6
