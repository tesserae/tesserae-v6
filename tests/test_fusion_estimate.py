"""GET /fusion-estimate: what a fusion search will cost, from the line counts alone."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest  # noqa: E402
from flask import Flask  # noqa: E402

from backend import fusion  # noqa: E402
import backend.blueprints.fusion as F  # noqa: E402

COUNTS = {'big_a.tess': 9731, 'big_b.tess': 9896, 'small_a.tess': 700, 'small_b.tess': 750,
          'mid_a.tess': 2500, 'mid_b.tess': 1700, 'tiny_a.tess': 10, 'tiny_b.tess': 12}


@pytest.fixture
def client(tmp_path):
    (tmp_path / 'la').mkdir()
    for name in COUNTS:
        (tmp_path / 'la' / name).write_text('x')
    loaded = []

    def units(text_id, language, unit_type, processor):
        loaded.append((text_id, unit_type))
        return [{}] * COUNTS[text_id]

    F.init_fusion_blueprint(None, None, None, str(tmp_path), units)
    app = Flask(__name__)
    app.register_blueprint(F.fusion_bp)
    c = app.test_client()
    c.loaded = loaded
    return c


def ask(client, source, target, **extra):
    q = {'source': source, 'target': target, 'language': 'la', **extra}
    return client.get('/fusion-estimate', query_string=q)


def test_whole_thebaid_against_whole_aeneid_is_in_parts(client):
    body = ask(client, 'big_a.tess', 'big_b.tess').get_json()
    assert body == {
        'pairs': 9731 * 9896, 'in_parts': True,
        'parts': 20, 'estimated_seconds': round(9731 * 9896 / 1e6 * 17),
        'source_lines': 9731, 'target_lines': 9896,
    }
    assert 1600 <= body['estimated_seconds'] <= 1650      # the measured 26 min 42 s


def test_one_book_against_one_book_is_not_in_parts_and_takes_the_floor(client):
    body = ask(client, 'small_a.tess', 'small_b.tess').get_json()
    assert body['in_parts'] is False and body['parts'] == 1
    assert body['pairs'] == 700 * 750
    assert body['estimated_seconds'] == 60                # 8.9 s of work, floored


def test_threshold_decides_in_parts(client):
    mid = ask(client, 'mid_a.tess', 'mid_b.tess').get_json()      # 4.25 million pairs
    assert mid['pairs'] > fusion.FUSION_PART_THRESHOLD and mid['in_parts'] is True
    assert mid['parts'] == 5
    assert mid['estimated_seconds'] == round(2500 * 1700 / 1e6 * 17)


def test_floor_applies_to_a_tiny_pair(client):
    assert ask(client, 'tiny_a.tess', 'tiny_b.tess').get_json()['estimated_seconds'] == 60


def test_estimate_function_matches_the_route_and_follows_the_part_size(monkeypatch):
    monkeypatch.setattr(fusion, 'FUSION_PART_SOURCE_LINES', 1000)
    assert fusion.estimate_fusion(9731, 9896)['parts'] == 10
    assert fusion.estimate_fusion(1000, 9896)['in_parts'] is False   # fits one part


def test_missing_parameters_and_unknown_texts(client):
    assert client.get('/fusion-estimate').status_code == 400
    assert ask(client, 'big_a.tess', 'nope.tess').status_code == 404


def test_phrase_unit_type_is_passed_on(client):
    ask(client, 'small_a.tess', 'small_b.tess', source_unit_type='phrase')
    assert ('small_a.tess', 'phrase') in client.loaded
    assert ('small_b.tess', 'line') in client.loaded
