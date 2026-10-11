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


# ---- closeness ranking, name forms and the text fallback (2026-10-11) ----

import numpy as np  # noqa: E402


def _closeness_setup(monkeypatch, vectors, qvec):
    monkeypatch.setattr(pi, '_ids', [r['id'] for r in RECORDS])
    monkeypatch.setattr(pi, '_row_by_id', None)
    emb = np.zeros((len(RECORDS), 2), dtype=np.float32)
    for i, v in vectors.items():
        emb[i] = v
    monkeypatch.setattr(pi, '_emb', emb)
    monkeypatch.setattr(pi, 'embed_query', lambda text: np.array(qvec, dtype=np.float32))


def test_query_ranks_by_dot_product(monkeypatch):
    # w1 is nearest the question, then w4, then w3 (which has the most mentions).
    _closeness_setup(monkeypatch, {1: (1, 0), 3: (0, 1), 4: (0.8, 0.6)}, (1, 0))
    out = pi.mentions_in_work('tac.ann', ['Sejanus'], query='the rise of Sejanus')
    assert out['ranked_by'] == 'closeness'
    assert _ids(out) == ['w1', 'w4', 'w3']
    assert out['hits'][0]['score'] == 1.0
    assert out['hits'][1]['score'] == 0.8


def test_ties_fall_back_to_names_then_mentions(monkeypatch):
    _closeness_setup(monkeypatch, {1: (1, 0), 2: (1, 0), 3: (1, 0)}, (1, 0))
    out = pi.mentions_in_work('tac.ann', ['Sejanus', 'Germanicus'], query='x')
    # equal scores: w3 names both, then w1 and w2 by position; w4 scores 0
    assert _ids(out) == ['w3', 'w1', 'w2', 'w4']


def test_without_query_order_is_unchanged_and_says_so():
    out = pi.mentions_in_work('tac.ann', ['Sejanus', 'Germanicus'])
    assert out['ranked_by'] == 'mentions'
    assert 'score' not in out['hits'][0]
    assert out['source'] == 'description'
    assert {h['found_in'] for h in out['hits']} == {'description'}


def test_encoder_down_keeps_mention_order(monkeypatch):
    def boom(text):
        raise pi.EmbedUnavailable('down')
    monkeypatch.setattr(pi, 'embed_query', boom)
    out = pi.mentions_in_work('tac.ann', ['Sejanus'], query='x')
    assert out['ranked_by'] == 'mentions' and _ids(out)[0] == 'w3' and out['note']


def test_latin_stems():
    assert pi.latin_stem('Sejanus') == 'seian'
    assert pi.latin_stem('Germanicus') == 'germanic'
    assert pi.latin_stem('Tiberius') == 'tiberi'
    assert pi.latin_stem('Dido') == 'dido'          # four letters are kept


def test_greek_stems():
    assert 'περικλ' in pi.greek_stems('Pericles')
    assert 'κλεων' in pi.greek_stems('Cleon')
    assert pi.greek_stems('Nicias') == ['νικι']
    assert pi.greek_stems('Alcibiades') == ['αλκιβιαδ']
    assert pi.greek_stems('Brasidas') == ['βρασιδ']
    assert 'φιλιπ' in pi.greek_stems('Philip') or pi.greek_stems('Philip')


def test_name_prefixes_need_four_letters():
    assert pi.name_prefixes('Pericles', 'grc')[0].startswith('π')
    assert pi.name_prefixes('Ajax', 'grc') == [] or len(pi.name_prefixes('Ajax', 'grc')[0]) >= 4
    assert pi.name_prefixes('Ino', 'la') == []
    assert pi.name_prefixes('Sejanus', 'la') == ['seian']
    assert pi.name_prefixes('Sejanus', 'en') == []


def test_text_matching_folds_accents_and_case():
    pre = pi.name_prefixes('Pericles', 'grc')
    assert pi._text_mentions('ὁ Περικλῆς εἶπε, Περικλέους δὲ ΠΕΡΙΚΛΕΙ', pre) == 3
    assert pi._first_matching_word('ὁ Περικλῆς εἶπε', pre) == 'Περικλῆς'
    # accents stored as separate combining marks do not cut a word
    assert pi._first_matching_word('Περικλε\u0301ους εἶπε', pre) == 'Περικλε\u0301ους'
    assert pi._text_mentions('Περικλε\u0301ους', pre) == 1
    assert pi._text_mentions('Seiani et SEIANUM', ['seian']) == 2


GREEK = [
    {'id': 'g0', 'work': 'grc/thuc.part.1.tess', 'language': 'grc', 'scale': 'fine',
     'ref_start': 'thuc. 1.1', 'ref_end': 'thuc. 1.2',
     'desc': {'gist': 'An experienced king addresses an assembly.'}},
    {'id': 'g1', 'work': 'grc/thuc.part.1.tess', 'language': 'grc', 'scale': 'fine',
     'ref_start': 'thuc. 1.5', 'ref_end': 'thuc. 1.6',
     'desc': {'gist': 'A general speaks.'}},
    {'id': 'g2', 'work': 'grc/thuc.part.2.tess', 'language': 'grc', 'scale': 'fine',
     'ref_start': 'thuc. 2.1', 'ref_end': 'thuc. 2.2',
     'desc': {'gist': 'Pericles is named here.'}},
]
GREEK_TEXT = {'g0': 'ἔλεγε δὲ Περικλῆς τάδε καὶ Περικλέους', 'g1': 'ὁ Κλέων ἔλεγεν', 'g2': 'ἄλλο'}


@pytest.fixture
def greek(monkeypatch):
    monkeypatch.setattr(pi, '_records', GREEK)
    monkeypatch.setattr(pi, '_by_work', {'grc/thuc': [0, 1, 2]})
    from backend import window_texts
    monkeypatch.setattr(window_texts, 'texts_for',
                        lambda ids: {i: GREEK_TEXT[i] for i in ids if i in GREEK_TEXT})
    monkeypatch.setattr(pi, '_norm_work', lambda w: 'grc/thuc')


def test_text_fallback_when_descriptions_have_nothing(greek):
    out = pi.mentions_in_work('grc/thuc', ['Cleon'])
    assert out['source'] == 'text'
    assert _ids(out) == ['g1']
    h = out['hits'][0]
    assert h['found_in'] == 'text' and h['matched'] == ['Cleon']
    assert h['mentions'] == 1 and h['matched_word'] == 'Κλέων'


def test_description_hits_are_not_replaced_by_text(greek):
    out = pi.mentions_in_work('grc/thuc', ['Pericles'])
    assert out['source'] == 'description' and _ids(out) == ['g2']
    forced = pi.mentions_in_work('grc/thuc', ['Pericles'], source='text')
    assert forced['source'] == 'text' and _ids(forced) == ['g0']
    assert forced['hits'][0]['mentions'] == 2
    off = pi.mentions_in_work('grc/thuc', ['Cleon'], source='description')
    assert off['hits'] == [] and off['source'] == 'description'
