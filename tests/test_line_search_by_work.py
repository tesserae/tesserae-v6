"""Line search's whole-corpus counts by work (2026-10-07): the corpus chart
drew from the first 500 lines only, so a common pair left out the authors
being compared. _count_candidates_by_work counts every co-occurring line the
index returned, once per work."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend import app as A  # noqa: E402


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
