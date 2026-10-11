"""mentions_in_work: windows of one work whose description names a person.

A fixture index of eight windows over two works, no built index needed.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend import passage_index as pi  # noqa: E402


def _rec(i, work, ref, participants='', gist='', setting='', themes=None):
    return {'id': f'w{i}', 'work': work, 'language': 'la', 'scale': 'fine',
            'ref_start': ref, 'ref_end': ref,
            'desc': {'participants': participants, 'gist': gist, 'setting': setting,
                     'themes': themes or []}}


RECORDS = [
    _rec(0, 'la/tac.ann.part.1.tess', 'tac. ann. 1.5', gist='Livia hides the death of Augustus.'),
    _rec(1, 'la/tac.ann.part.1.tess', 'tac. ann. 1.24', participants='Sejanus and Drusus'),
    _rec(2, 'la/tac.ann.part.2.tess', 'tac. ann. 2.10', gist='Germanicus fights Arminius.'),
    _rec(3, 'la/tac.ann.part.2.tess', 'tac. ann. 2.9', participants='Germanicus, Sejanus',
         gist='Sejanus watches Germanicus; Sejanus smiles.'),
    _rec(4, 'la/tac.ann.part.3.tess', 'tac. ann. 3.1', themes=['the Didonian fleet', 'sejanus']),
    _rec(5, 'la/tac.ann.part.3.tess', 'tac. ann. 3.2', gist="Dido's name is used."),
    _rec(6, 'la/verg.aen.tess', 'verg. aen. 4.1', participants='Dido', gist='Dido burns.'),
    _rec(7, 'la/verg.aen.tess', 'verg. aen. 1.1', setting='Carthage, Dido present'),
]


@pytest.fixture(autouse=True)
def index(monkeypatch):
    monkeypatch.setitem(pi._state, 'loaded', True)
    monkeypatch.setitem(pi._state, 'ok', True)
    monkeypatch.setitem(pi._state, 'error', None)
    monkeypatch.setattr(pi, '_records', RECORDS)
    by_work = {}
    for i, r in enumerate(RECORDS):
        by_work.setdefault(pi._norm_work(r['work']), []).append(i)
    monkeypatch.setattr(pi, '_by_work', by_work)


def _ids(out):
    return [h['id'] for h in out['hits']]


def test_ranks_by_distinct_names_then_mentions_then_position():
    out = pi.mentions_in_work('tac.ann', ['Sejanus', 'Germanicus'])
    # w3 matches both names; w1, w2, w4 match one. Among those, w4 has one
    # mention each, so position decides: part 1, part 2, part 3.
    assert _ids(out) == ['w3', 'w1', 'w2', 'w4']
    assert out['hits'][0]['matched'] == ['Sejanus', 'Germanicus']
    assert out['hits'][0]['mentions'] == 5


def test_more_mentions_outrank_fewer_for_the_same_name_count():
    out = pi.mentions_in_work('tac.ann', ['Sejanus'])
    assert _ids(out)[0] == 'w3'   # three mentions
    assert set(_ids(out)) == {'w1', 'w3', 'w4'}


def test_whole_word_matching():
    out = pi.mentions_in_work('tac.ann', ['Dido'])
    # "Didonian" does not match; "Dido's" does (the apostrophe is a boundary).
    assert _ids(out) == ['w5']


def test_case_insensitive_and_fields_joined():
    out = pi.mentions_in_work('verg.aen', ['dido'])
    assert _ids(out) == ['w6', 'w7']      # w6 has two mentions, w7 one (setting)


def test_books_filter_and_books_searched():
    out = pi.mentions_in_work('tac.ann', ['Sejanus'], books=[1, 2, 9])
    assert _ids(out) == ['w3', 'w1']
    assert out['books_searched'] == [1, 2]


def test_part_id_restricts_to_that_book():
    out = pi.mentions_in_work('tac.ann.part.1', ['Sejanus'])
    assert _ids(out) == ['w1']


def test_unknown_work():
    out = pi.mentions_in_work('nobody.nothing', ['Dido'])
    assert out['hits'] == [] and out['note']


def test_parse_books():
    assert pi.parse_books('1,2') == [1, 2]
    assert pi.parse_books('1-3,5') == [1, 2, 3, 5]
    assert pi.parse_books('x,3-1') == []


def test_one_entry_per_passage_across_scales(monkeypatch):
    """The index holds a window at two scales with the same opening
    reference; the names list shows the passage once (2026-10-11)."""
    coarse = dict(_rec(8, 'la/tac.ann.part.1.tess', 'tac. ann. 1.24', participants='Sejanus'))
    coarse['scale'] = 'coarse'
    records = RECORDS + [coarse]
    monkeypatch.setattr(pi, '_records', records)
    by_work = {}
    for i, r in enumerate(records):
        by_work.setdefault(pi._norm_work(r['work']), []).append(i)
    monkeypatch.setattr(pi, '_by_work', by_work)
    out = pi.mentions_in_work('tac.ann', ['Sejanus'])
    refs = [h['ref_start'] for h in out['hits']]
    assert refs.count('tac. ann. 1.24') == 1
    assert len(refs) == len(set(refs))
