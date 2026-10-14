"""One rule for a bad number in a request: a 400 with a plain message."""
import os
import sys
import types

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest  # noqa: E402

from backend.app import app, API_PREFIX  # noqa: E402
from backend.blueprints import admin, hapax  # noqa: E402
from backend.request_params import BadParameter, float_param, int_param  # noqa: E402


# ---- the helper ----

def test_absent_and_empty_give_the_default():
    assert int_param({}, 'n', 7) == 7
    assert int_param({'n': ''}, 'n', 7) == 7
    assert int_param({'n': None}, 'n', 7) == 7


def test_whole_numbers_parse_from_strings_and_json():
    assert int_param({'n': '12'}, 'n', 0) == 12
    assert int_param({'n': 12}, 'n', 0) == 12
    assert int_param({'n': '-3'}, 'n', 0) == -3
    assert int_param({'n': 5.9}, 'n', 0) == 5


@pytest.mark.parametrize('bad', ['abc', '1.5', '1e3', [1], {'a': 1}])
def test_not_a_whole_number_is_a_400(bad):
    with pytest.raises(BadParameter) as caught:
        int_param({'n': bad}, 'n', 0)
    assert caught.value.code == 400
    assert caught.value.message == 'n must be a whole number'


def test_range_is_checked():
    assert int_param({'n': '5'}, 'n', 0, minimum=5, maximum=5) == 5
    with pytest.raises(BadParameter, match='n must be 1 or greater'):
        int_param({'n': '0'}, 'n', 0, minimum=1)
    with pytest.raises(BadParameter, match='n must be 10 or less'):
        int_param({'n': '11'}, 'n', 0, maximum=10)


def test_float_param():
    assert float_param({}, 'r', 0.9) == 0.9
    assert float_param({'r': '0.25'}, 'r', 0.9) == 0.25
    with pytest.raises(BadParameter, match='r must be a number'):
        float_param({'r': 'high'}, 'r', 0.9)


# ---- the routes that were unguarded ----

def url(path):
    return f'{API_PREFIX}{path}' if API_PREFIX else path


@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as c:
        yield c


@pytest.mark.parametrize('path,param', [
    ('/rare-lemmata', 'max_occurrences'),
    ('/rare-lemmata', 'min_occurrences'),
    ('/rare-lemmata', 'limit'),
    ('/rare-word-cloud', 'max_occurrences'),
    ('/rare-word-cloud', 'limit'),
    ('/rare-bigrams', 'limit'),
    ('/rare-bigrams', 'min_rarity'),
])
def test_hapax_reads_answer_400(client, path, param):
    response = client.get(url(path) + f'?{param}=abc')
    assert response.status_code == 400
    kind = 'a number' if param == 'min_rarity' else 'a whole number'
    assert response.get_json() == {'error': f'{param} must be {kind}'}


@pytest.mark.parametrize('path,param', [
    ('/hapax-search', 'max_occurrences'),
    ('/rare-bigram-search', 'limit'),
    ('/rare-bigram-search', 'stoplist_size'),
])
def test_hapax_searches_answer_400(client, monkeypatch, path, param):
    monkeypatch.setattr(hapax, '_parse_search_params', lambda data: ('a', 'b', 'la'))
    response = client.post(url(path), json={param: 'abc'})
    assert response.status_code == 400
    assert response.get_json() == {'error': f'{param} must be a whole number'}


def test_dictionary_review_answers_400(client, monkeypatch):
    with client.session_transaction() as sess:
        sess['admin_user_id'] = 7
        sess['admin_roles'] = ['ADMIN']
        sess['admin_session_version'] = 1
    user = types.SimpleNamespace(id=7, session_version=1)
    monkeypatch.setattr(admin, 'User', types.SimpleNamespace(
        query=types.SimpleNamespace(get=lambda _id: user)))
    for param in ('limit', 'offset'):
        response = client.get(url_admin('/admin/dictionary-review') + f'?{param}=abc')
        assert response.status_code == 400
        assert response.get_json() == {'error': f'{param} must be a whole number'}


def url_admin(path):
    return f'{API_PREFIX}{path}' if API_PREFIX else path
