"""A work whose passage windows are all prose-sized gets a gutter and a place
in the connection map.

Since 2026-10-11 a long prose work is cut into paragraph-sized windows
(scale 'prose'). A work imported after that date has no described fine
windows, so the Reader's request for the fine scale found no rows and the
gutter stayed empty, and the map builder's fine-only subset left the work out
of the connection map. Found 2026-10-19 with Cicero's De legibus: 37 works
were in that state (the parts of Cassius Dio and Diodorus among them).

Both now fall back to the prose windows when a work has no fine windows. A
work that has both scales keeps using its fine windows, as before.
"""
import importlib.util
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest  # noqa: E402

from backend import passage_index  # noqa: E402

RECORDS = [
    # A work with fine windows only.
    {'id': 'vergil.aeneid.part.1:fine:0', 'work': 'vergil.aeneid.part.1', 'scale': 'fine',
     'ref_start': 'verg. aen. 1.1', 'ref_end': 'verg. aen. 1.7', 'language': 'la'},
    # A work with both: its fine windows serve the gutter and the map.
    {'id': 'livy.ab_urbe_condita:fine:0', 'work': 'livy.ab_urbe_condita', 'scale': 'fine',
     'ref_start': 'liv. 1.1', 'ref_end': 'liv. 1.1', 'language': 'la'},
    {'id': 'livy.ab_urbe_condita:prosem:0', 'work': 'livy.ab_urbe_condita', 'scale': 'prose',
     'ref_start': 'liv. 1.1', 'ref_end': 'liv. 1.3', 'language': 'la'},
    # A work with prose windows only.
    {'id': 'cicero.de_legibus:prosem:0', 'work': 'cicero.de_legibus', 'scale': 'prose',
     'ref_start': 'cic. leg. 1.1', 'ref_end': 'cic. leg. 1.2', 'language': 'la'},
    {'id': 'cicero.de_legibus:prosem:1', 'work': 'cicero.de_legibus', 'scale': 'prose',
     'ref_start': 'cic. leg. 1.3', 'ref_end': 'cic. leg. 1.4', 'language': 'la'},
    # Parts of one work: an early part with fine windows and a later part cut
    # into prose windows only (Cassius Dio books 36 to 55 are in that state).
    # The parts are different text, so both belong in the map, each with the
    # windows it has.
    {'id': 'cassius_dio.roman_history.part.1:fine:0', 'work': 'cassius_dio.roman_history.part.1',
     'scale': 'fine', 'ref_start': 'dio 1.1', 'ref_end': 'dio 1.2', 'language': 'grc'},
    {'id': 'cassius_dio.roman_history.part.36:prosem:0', 'work': 'cassius_dio.roman_history.part.36',
     'scale': 'prose', 'ref_start': 'dio 36.1', 'ref_end': 'dio 36.3', 'language': 'grc'},
    # A prose-only work in a language the map does not serve.
    {'id': 'ibn.kitab:prosem:0', 'work': 'ibn.kitab', 'scale': 'prose',
     'ref_start': 'ibn. 1.1', 'ref_end': 'ibn. 1.2', 'language': 'ar'},
]


@pytest.fixture
def index(tmp_path, monkeypatch):
    monkeypatch.setattr(passage_index, '_records', RECORDS)
    by_work = {}
    for i, r in enumerate(RECORDS):
        by_work.setdefault(passage_index._norm_work(r['work']), []).append(i)
        by_work.setdefault(r['work'], []).append(i)
    monkeypatch.setattr(passage_index, '_by_work', by_work)
    monkeypatch.setattr(passage_index, '_DENSITY_CACHE', str(tmp_path))
    monkeypatch.setitem(passage_index._state, 'loaded', True)
    monkeypatch.setitem(passage_index._state, 'ok', True)
    import numpy as np

    def fake_row_scores(rows, *a, **k):
        for row in rows:
            yield row, np.zeros(len(RECORDS), dtype='float32')

    monkeypatch.setattr(passage_index, '_row_scores', fake_row_scores, raising=False)
    monkeypatch.setattr(passage_index, '_density_cache_path',
                        lambda work, scale: str(tmp_path / f'{work}.{scale}.json'))


def _ids(result):
    return [w['id'] for w in result['windows']]


def test_prose_only_work_answers_with_its_prose_windows(index):
    out = passage_index.connection_density('cicero.de_legibus', scale='fine')
    assert _ids(out) == ['cicero.de_legibus:prosem:0', 'cicero.de_legibus:prosem:1']


def test_work_with_both_scales_keeps_its_fine_windows(index):
    out = passage_index.connection_density('livy.ab_urbe_condita', scale='fine')
    assert _ids(out) == ['livy.ab_urbe_condita:fine:0']


def test_coarse_request_does_not_fall_back(index):
    out = passage_index.connection_density('cicero.de_legibus', scale='coarse')
    assert out['windows'] == []


def _builder():
    spec = importlib.util.spec_from_file_location(
        'build_connections_map',
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     'scripts', 'build_connections_map.py'))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_map_subset_includes_prose_windows_of_works_without_fine_windows():
    mod = _builder()
    sub = mod.select_subset(RECORDS)
    ids = [RECORDS[i]['id'] for i in sub]
    assert ids == ['vergil.aeneid.part.1:fine:0', 'livy.ab_urbe_condita:fine:0',
                   'cicero.de_legibus:prosem:0', 'cicero.de_legibus:prosem:1',
                   'cassius_dio.roman_history.part.1:fine:0',
                   'cassius_dio.roman_history.part.36:prosem:0']


def test_a_prose_only_part_joins_the_map_beside_its_fine_parts():
    """The rule keys on the part id the Reader opens, not on the whole work.
    In the live index of 2026-10-19 the 37 prose-only works were mostly later
    parts of works whose earlier parts have fine windows (Cassius Dio 36 to
    55, Diodorus 1 to 5 and 18 to 20, Appian 1), and no whole-work id with
    fine windows stood beside prose-only parts of the same work, so keying
    on the part id adds the missing parts without doubling any text."""
    mod = _builder()
    sub = mod.select_subset(RECORDS)
    ids = [RECORDS[i]['id'] for i in sub]
    assert 'cassius_dio.roman_history.part.36:prosem:0' in ids
    assert 'cassius_dio.roman_history.part.1:fine:0' in ids
    assert 'livy.ab_urbe_condita:prosem:0' not in ids


def test_map_subset_respects_the_served_languages():
    mod = _builder()
    sub = mod.select_subset(RECORDS, languages=('la',))
    assert all(RECORDS[i]['language'] == 'la' for i in sub)
    assert 'ibn.kitab:prosem:0' not in [RECORDS[i]['id'] for i in sub]
