"""The /api/text-descriptions endpoint: orientation blurbs per work."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from flask import Flask

from backend.blueprints.corpus import corpus_bp, load_descriptions


@pytest.fixture()
def client():
    app = Flask(__name__)
    app.register_blueprint(corpus_bp, url_prefix='/api')
    with app.test_client() as c:
        yield c


def test_data_file_is_valid_and_nonempty():
    data = load_descriptions()
    assert 'la' in data and len(data['la']) >= 20
    for work, blurb in data['la'].items():
        assert '.tess' not in work and '.part.' not in work, work
        assert isinstance(blurb, str) and len(blurb) > 80, work


def test_language_listing(client):
    d = client.get('/api/text-descriptions?language=la').get_json()
    assert 'justin.epitome' in d['descriptions']


def test_single_work_collapses_tess_and_part(client):
    one = client.get(
        '/api/text-descriptions?language=la&work=abelard.epistolae.part.2.tess'
    ).get_json()
    assert one['description'] and 'Abelard' in one['description']


def test_unknown_language_and_work_are_empty_not_errors(client):
    assert client.get('/api/text-descriptions?language=xx').get_json() == {
        'descriptions': {}}
    assert client.get(
        '/api/text-descriptions?language=la&work=nope.tess'
    ).get_json() == {'description': None}
