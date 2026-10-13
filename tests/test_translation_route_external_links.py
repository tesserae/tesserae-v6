"""/passages/translation surfaces external_links end to end, through the real
Flask route and the real Ghalib link table built by
scripts/build_ghalib_pritchett_links.py -- not a mock.

Ghalib's opening ghazal ({1,1}, "naqsh faryaadii...") is Pritchett's own
example verse on her site's front page, so it is as stable a fixture as this
table has; if the build ever regresses to 0 links this is the test that
should catch it before test_translation_links.py's isolated-fixture tests
would (those pass even with an empty table on disk).
"""
import pytest

from backend.app import API_PREFIX, app

P = API_PREFIX


@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as c:
        yield c


def test_ghalib_opening_verse_carries_a_pritchett_link(client):
    r = client.get(f'{P}/passages/translation', query_string={
        'work': 'ghalib.diwan_wikisource',
        'refs': 'ghalib.diwan_wikisource.ghazal.1.1',
    })
    assert r.status_code == 200
    body = r.get_json()
    assert 'external_links' in body
    links = body['external_links']
    assert len(links) == 1
    assert links[0]['url'] == 'https://franpritchett.com/00ghalib/001/1_01.html'
    assert 'Pritchett' in links[0]['translator']
    assert links[0]['site_title'] == 'A Desertful of Roses'


def test_two_misras_of_one_couplet_yield_one_link_not_two(client):
    r = client.get(f'{P}/passages/translation', query_string={
        'work': 'ghalib.diwan_wikisource',
        'refs': 'ghalib.diwan_wikisource.ghazal.1.1|ghalib.diwan_wikisource.ghazal.1.2',
    })
    body = r.get_json()
    assert len(body['external_links']) == 1


def test_a_non_ghalib_work_still_returns_an_external_links_key(client):
    """Additive means present-but-empty elsewhere, not absent."""
    r = client.get(f'{P}/passages/translation', query_string={
        'work': 'la/vergil.aeneid', 'refs': 'verg. aen. 1.1'})
    body = r.get_json()
    assert 'external_links' in body
    assert body['external_links'] == []
