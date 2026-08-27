"""Both spellings of the translation endpoint answer.

Two routes in the passages blueprint are declared without the /passages/ prefix
their neighbours carry, so they live at /translation and /lexical-density. That
is not a bug -- the frontend calls those paths -- but the prefixed spelling
returned a 404 that reads exactly like a stale deploy, and it cost an hour of
debugging during the translation rollout on 2026-08-27. Both spellings now reach
the same view, and this pins that down: nothing in the app breaks when an alias
disappears, the path simply starts 404ing again for whoever guesses it from the
neighbouring routes.

TWO THINGS THIS TEST HAS TO GET RIGHT, both learned by getting them wrong:

  * the prefix. backend/app.py mounts every route under API_PREFIX, which is ""
    behind Apache (where the vhost supplies /api) and "/api" when Flask serves
    directly. conftest sets TESSERAE_DIRECT_SERVER, so under pytest the paths
    carry /api. The prefix is read from the app rather than written out, so this
    passes in either mode.

  * the assertion. A 200 proves nothing here, because the app answers an
    unmatched path with the single-page-app fallback, which is a 200 of HTML.
    A first draft of this test asserted only the status and passed on a route
    that did not exist. So it asserts the endpoint's own JSON shape.
"""
import pytest

from backend.app import API_PREFIX, app

P = API_PREFIX


@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as c:
        yield c


@pytest.mark.parametrize('path', [f'{P}/translation', f'{P}/passages/translation'])
def test_translation_answers_at_both_paths(client, path):
    r = client.get(path, query_string={'work': 'la/vergil.aeneid',
                                       'refs': 'verg. aen. 1.1'})
    assert r.status_code == 200, f'{path} returned {r.status_code}'
    # Not just a 200: the SPA fallback is a 200 of HTML. This must be the view.
    assert r.is_json, f'{path} did not reach the endpoint (got {r.content_type})'
    assert 'available' in r.get_json()


@pytest.mark.parametrize('path', [f'{P}/lexical-density',
                                  f'{P}/passages/lexical-density'])
def test_lexical_density_answers_at_both_paths(client, path):
    r = client.get(path, query_string={'work': 'la/vergil.aeneid'})
    assert r.status_code == 200, f'{path} returned {r.status_code}'
    assert r.is_json, f'{path} did not reach the endpoint (got {r.content_type})'
    assert 'lines' in r.get_json()


def test_the_alias_reaches_the_real_view(client):
    """Not a stub that answers anything: the view's own argument check fires."""
    r = client.get(f'{P}/passages/translation')
    assert r.is_json
    body = r.get_json()
    assert body['available'] is False
    assert 'work is required' in body['reason']
