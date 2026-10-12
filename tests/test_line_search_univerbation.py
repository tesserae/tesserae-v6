"""Line Search, Latin lemma mode: a word that editors print either joined or
apart (quousque / quo usque, respublica / res publica) is matched both ways
(backend/univerbation.py).

The unit tests need only the lemmatiser. The integration tests run the Flask
test client against the real Latin index and are skipped where it is absent,
like the other Line Search integration tests. The corpus-frequency stoplist
is read from the production cache file when present (the ten commonest
lemmas, including qui, are dropped from a query as on the live site) and is
empty otherwise; building it cold takes hours.
"""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend import univerbation as U  # noqa: E402
import backend.app as _appmod  # noqa: E402
from backend.app import app, _univerbation_lemmatize as LEM  # noqa: E402
from backend.lexical_density import _index_path  # noqa: E402

_FREQ_FILE = '/var/www/tesseraev6_flask/cache/frequencies/la.json'


@pytest.fixture(autouse=True)
def _fixed_table():
    U._TABLE = None
    yield
    U._TABLE = None


# ---------------------------------------------------------------- table

def test_table_loads_and_every_entry_differs_from_its_parts():
    table = U.load_table(LEM)
    assert U.dropped_entries() == []
    assert set(table) == set(U.UNIVERBATIONS_LA)
    for entry in table.values():
        for part in entry.part_lemmas:
            assert not (entry.joined_lemmas & part), entry.joined


def test_entry_whose_joined_lemma_is_a_part_lemma_is_dropped(monkeypatch):
    monkeypatch.setitem(U.UNIVERBATIONS_LA, 'uirumque', ('uirum', 'que'))
    table = U.load_table(lambda w: {'uir'} if w.startswith('uir') else {w})
    assert 'uirumque' not in table
    assert ('uirumque', 'joined lemma equals a part lemma') in U.dropped_entries()


def test_expand_parts_maps_the_parts_to_the_joined_lemma():
    out = U.expand_parts(['quo', 'usque', 'tandem'], LEM)
    assert out == {'qui': {'quousque'}, 'usque': {'quousque'}}
    assert U.expand_parts(['arma', 'uirum'], LEM) == {}
    # "qui usque" is not the particle pair quo usque
    assert U.expand_parts(['qui', 'usque'], LEM) == {}


def test_expand_parts_reads_inflected_compounds_by_lemma():
    out = U.expand_parts(['rem', 'publicam'], LEM)
    assert out == {'res': {'respublica'}, 'publicus': {'respublica'}}


def test_expand_joined_maps_the_joined_lemma_to_its_other_parts():
    fb, seq = U.expand_joined(['quousque', 'tandem'], LEM, stopwords={'qui', 'et'})
    assert fb == {'quousque': {'usque'}}
    assert seq == {'quousque': ((frozenset({'qui'}), frozenset({'usque'})), ('quo', 'usque'))}


# ------------------------------------------------------------ one line

def _line(words, lemmas):
    return [[l] for l in lemmas], words


def test_joined_token_answers_the_parts_and_is_marked_once():
    fwd = U.expand_parts(['quo', 'usque', 'tandem', 'abutere'], LEM)
    lem_sets, toks = _line(['quousque', 'tandem', 'abuteris'], ['quousque', 'tandem', 'abutor'])
    matched, words, pos = U.match_line(lem_sets, toks, {'usque', 'tandem', 'abutor'}, fwd, {})
    assert matched == {'usque', 'tandem', 'abutor'}
    assert words == ['quousque', 'tandem', 'abuteris']
    assert pos == [0, 1, 2]
    assert len(matched) >= 2  # min_matched for a multi-word query


def test_a_stray_part_elsewhere_in_the_line_does_not_widen_the_match():
    fwd = U.expand_parts(['quo', 'usque', 'tandem'], LEM)
    filler = ['x'] * 30
    lem_sets, toks = _line(['quousque', 'tandem'] + filler + ['usque'],
                           ['quousque', 'tandem'] + filler + ['usque'])
    matched, words, pos = U.match_line(lem_sets, toks, {'usque', 'tandem'}, fwd, {})
    assert pos == [0, 1]


def test_parts_must_stand_next_to_each_other_for_the_joined_query_word():
    fb, seq = U.expand_joined(['quousque', 'tandem'], LEM, stopwords={'qui'})
    q = {'quousque', 'tandem'}
    # qui ... usque ... tandem, not adjacent: only tandem answers
    lem_sets, toks = _line(['quid', 'est', 'usque', 'tandem'], ['qui', 'sum', 'usque', 'tandem'])
    matched, _, _ = U.match_line(lem_sets, toks, q, {}, seq)
    assert matched == {'tandem'}
    # quo usque tandem: adjacent and in order, both part tokens are marked
    lem_sets, toks = _line(['quo', 'usque', 'tandem'], ['qui', 'usque', 'tandem'])
    matched, words, pos = U.match_line(lem_sets, toks, q, {}, seq)
    assert matched == {'quousque', 'tandem'}
    assert words == ['quo', 'usque', 'tandem'] and pos == [0, 1, 2]
    # cuius usque: qui by lemma, but not the particle quo
    lem_sets, toks = _line(['cuius', 'usque', 'tandem'], ['qui', 'usque', 'tandem'])
    assert U.match_line(lem_sets, toks, q, {}, seq)[0] == {'tandem'}
    # usque quo: wrong order
    lem_sets, toks = _line(['usque', 'quo'], ['usque', 'qui'])
    assert U.match_line(lem_sets, toks, q, {}, seq)[0] == set()


def test_surface_hits_count_a_joined_token_as_the_parts():
    from backend.app import _surface_hits
    assert _surface_hits('quo usque tandem abutere', ['quousque', 'tandem', 'abuteris'], 'la') == 3
    assert _surface_hits('quousque tandem', ['quo', 'usque', 'tandem'], 'la') == 2
    assert _surface_hits('arma virum', ['arma', 'virum'], 'la') == 2


# --------------------------------------------------- live Latin index

if not os.path.exists(_index_path('la')):
    pytest.skip('Latin inverted index not present; integration test',
                allow_module_level=True)


def _freq(*a, **k):
    if os.path.exists(_FREQ_FILE):
        with open(_FREQ_FILE, encoding='utf-8') as f:
            return json.load(f)
    return {'frequencies': {}}


@pytest.fixture(scope='module')
def search():
    mp = pytest.MonkeyPatch()
    mp.setattr(_appmod, 'get_corpus_frequencies', _freq)
    route = next(str(r) for r in app.url_map.iter_rules() if str(r).endswith('/line-search'))
    client = app.test_client()

    def run(query, **kw):
        r = client.post(route, json=dict(query=query, language='la', search_type='lemma',
                                         max_results=500, **kw))
        assert r.status_code == 200
        return r.get_json()
    yield run
    mp.undo()


def _find(data, author_part, work_part, locus):
    for r in data['results']:
        if author_part in r['author'] and work_part in r['work'] and r['locus'] == locus:
            return r
    return None


def test_query_with_parts_finds_the_joined_word(search):
    d = search('quo usque tandem abutere')
    r = _find(d, 'Lucifer', 'Moriendum', '12')
    assert r is not None
    assert 'quousque' in r['matched_words']
    assert len(r['matched_lemmas']) >= 3
    assert r['quotation'] is True  # the joined word counts as the parts it stands for
    assert r['span'] <= 4


def test_query_with_the_joined_word_finds_the_parts(search):
    d = search('quousque tandem')
    r = _find(d, 'Cicero', 'In Catilinam', '1.1')
    assert r is not None
    assert 'quo' in r['matched_words'] and 'usque' in r['matched_words']
    # a line with qui and tandem apart is not a hit
    for row in d['results']:
        low = [w.lower() for w in row['matched_words']]
        assert ('quousque' in low) or ('quo' in low and 'usque' in low)


def test_res_publica_matches_the_compound_in_any_form(search):
    d = search('res publica')
    forms = {w.lower() for r in d['results'] for w in r['matched_words']}
    assert forms & {'rempublicam', 'reipublicae'}
    assert any('respublica' in [w.lower() for w in r['matched_words']] for r in d['results'])


def test_arma_virum_is_unchanged(search, monkeypatch):
    d = search('arma virum')
    authors = {r['author'] for r in d['results']}
    assert {'Ovid', 'Quintilian', 'Seneca'} <= authors
    monkeypatch.setattr(U, 'UNIVERBATIONS_LA', {})
    U._TABLE = None
    off = search('arma virum')
    assert d['total'] == off['total']
    assert [(r['text_id'], r['locus']) for r in d['results']] == \
        [(r['text_id'], r['locus']) for r in off['results']]
