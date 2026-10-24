"""GET /api/texts/structure/<work>: a work's story list for the Reader."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest  # noqa: E402
from flask import Flask  # noqa: E402

from backend.blueprints import corpus as corpus_mod  # noqa: E402


@pytest.fixture
def client():
    app = Flask(__name__)
    app.register_blueprint(corpus_mod.corpus_bp, url_prefix='/api')
    with app.test_client() as c:
        yield c


def test_shahnameh_stories(client):
    r = client.get('/api/texts/structure/ferdowsi.shahnameh')
    assert r.status_code == 200
    d = r.get_json()
    assert d['work'] == 'ferdowsi.shahnameh' and d['unit'] == 'story'
    assert len(d['sections']) == 857
    s = d['sections'][150]
    assert s['number'] == 151
    assert s['first_ref'] == 'ferdowsi.shahnameh.151.1.1'
    assert {'title_en', 'title_fa', 'last_ref', 'n_couplets'} <= set(s)
    assert 'ganjoor_poem_id' not in s


@pytest.mark.parametrize('work', ['verg.aen', 'no.such.work', '..', 'Ferdowsi.Shahnameh', 'a..b'])
def test_no_structure_is_404(client, work):
    r = client.get(f'/api/texts/structure/{work}')
    assert r.status_code == 404
    if r.is_json:
        assert r.get_json() == {'error': 'no structure'}
