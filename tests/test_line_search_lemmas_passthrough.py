"""The optional `lemmas` parameter of Line Search: dictionary forms searched as given.

The results page's corpus panel sends a parallel's shared lemmas. Lemmatizing
them a second time turned Greek lemmas such as "αγορευω" into other strings
and the search returned nothing.
"""
import os
import sys
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.blueprints import line_search as ls  # noqa: E402
from backend.line_search_params import _read_params  # noqa: E402
from backend.line_search_support import _normalize_lemma  # noqa: E402


def _params(**body):
    base = {'query': 'αγορευω θεοπροπια', 'language': 'grc', 'search_type': 'lemma'}
    base.update(body)
    return _read_params(base)


def test_parameter_reads_a_list_or_a_spaced_string():
    assert _params(lemmas=['αγορευω', ' θεοπροπια ', '']).lemmas == ('αγορευω', 'θεοπροπια')
    assert _params(lemmas='αγορευω θεοπροπια').lemmas == ('αγορευω', 'θεοπροπια')
    assert _params().lemmas == ()
    assert _params(lemmas=5).lemmas == ()


def test_lemmas_are_the_normalized_set_and_no_lemmatizer_runs():
    p = _params(lemmas=['αγορευω', 'θεοπροπια'])
    with mock.patch.object(ls.text_processor, 'lemmatize_word',
                           side_effect=AssertionError('lemmatizer called')):
        got = ls._query_lemmas(p)
    assert got == {_normalize_lemma('αγορευω', 'grc'), _normalize_lemma('θεοπροπια', 'grc')}


def test_lemmas_ignored_for_other_search_types():
    p = _params(lemmas=['αγορευω', 'θεοπροπια'], search_type='exact')
    assert ls._query_lemmas(p) == {_normalize_lemma(t, 'grc') for t in p.query.split()}


def test_absent_parameter_still_uses_the_lemmatizer():
    p = _params()
    with mock.patch.object(ls.text_processor, 'lemmatize_word', return_value=['x']) as m:
        got = ls._query_lemmas(p)
    assert m.called and got == {'x'}


def test_greek_pair_finds_a_fixture_line():
    # Fixture: the set a posting lookup would key on equals the unaccented lemma pair.
    lines = {'l1': {'αγορευω', 'θεοπροπια', 'και'}, 'l2': {'και'}}
    q = ls._query_lemmas(_params(lemmas=['ἀγορεύω', 'θεοπροπία']))
    assert [k for k, v in lines.items() if q <= v] == ['l1']
