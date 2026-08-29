"""A passage-sized line-search query reduces to its rarest words.

Integration test against the live Latin index (skipped where absent, like
the assistant suite): the Reader's Verbal Parallels tab sends whole
selections as queries, and the unreduced form of Aeneid 1.1-6 was measured
at 97 seconds. The cap keeps it interactive and the reference query
untouched.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.lexical_density import _index_path

if not os.path.exists(_index_path('la')):
    pytest.skip('Latin inverted index not present; integration test',
                allow_module_level=True)

import backend.app as _appmod  # noqa: E402
from backend.app import app  # noqa: E402

# The corpus-frequency stoplist augmentation is not under test, and building
# it cold takes minutes in a fresh process; the base stopword list is enough
# for these assertions.
_appmod.get_corpus_frequencies = lambda *a, **k: {'frequencies': {}}

AENEID_1_1_6 = ('Arma virumque cano, Troiae qui primus ab oris Italiam, fato '
                'profugus, Laviniaque venit litora, multum ille et terris '
                'iactatus et alto vi superum saevae memorem Iunonis ob iram; '
                'multa quoque et bello passus, dum conderet urbem, inferretque '
                'deos Latio, genus unde Latinum')


def _route():
    return next(str(r) for r in app.url_map.iter_rules()
                if str(r).endswith('/line-search'))


def _post(query):
    client = app.test_client()
    r = client.post(_route(), json={
        'query': query, 'language': 'la', 'search_type': 'lemma',
        'max_results': 25})
    assert r.status_code == 200
    return r.get_json()


def test_passage_query_reduces_and_says_so():
    d = _post(AENEID_1_1_6)
    red = d.get('query_reduced')
    assert red, 'passage-sized query was not reduced'
    assert red['from_lemmas'] > 12
    assert len(red['to_lemmas']) <= 12
    # The rarest words of this passage are its proper names and rare terms;
    # at least one must be among them, or the ranking is not by rarity.
    assert set(red['to_lemmas']) & {'lauinia', 'profugus', 'troia', 'iuno'}
    assert d.get('results'), 'reduced search returned nothing'


def test_short_query_is_untouched():
    d = _post('arma virumque')
    assert d.get('query_reduced') is None
    assert d.get('total', 0) > 0
