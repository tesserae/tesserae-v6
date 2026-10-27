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
        'parts': 20, 'estimated_seconds': round(
            fusion.FUSION_PART_BASE_SECONDS + 20 * fusion.FUSION_SECONDS_PER_PART
            + 9731 * 9896 / 1e6 * fusion.FUSION_PART_SECONDS_PER_MILLION_PAIRS),
        'source_lines': 9731, 'target_lines': 9896, 'cached': False,
    }


def test_one_book_against_one_book_is_not_in_parts_and_takes_the_floor(client):
    body = ask(client, 'small_a.tess', 'small_b.tess').get_json()
    assert body['in_parts'] is False and body['parts'] == 1
    assert body['pairs'] == 700 * 750
    assert body['estimated_seconds'] == 60                # 8.9 s of work, floored


def test_threshold_decides_in_parts(client):
    mid = ask(client, 'mid_a.tess', 'mid_b.tess').get_json()      # 4.25 million pairs
    assert mid['pairs'] > fusion.FUSION_PART_THRESHOLD and mid['in_parts'] is True
    assert mid['parts'] == 5
    assert mid['estimated_seconds'] == round(
        fusion.FUSION_PART_BASE_SECONDS + 5 * fusion.FUSION_SECONDS_PER_PART
        + 2500 * 1700 / 1e6 * fusion.FUSION_PART_SECONDS_PER_MILLION_PAIRS)


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


def test_cached_pair_runs_no_parts_and_says_so(client, tmp_path, monkeypatch):
    """A pair already in the results cache answers at once, so the page must not
    warn of a long search (2026-10-18, the Persian default pair)."""
    import backend.cache as C
    monkeypatch.setattr(C, 'CACHE_DIR', str(tmp_path / 'results_cache'))
    settings = F._default_fusion_cache_settings('la', 5000, use_meter=False)
    C.save_cached_results('big_a.tess', 'big_b.tess', 'la', settings, [{'score': 1}], {'total': 1})
    body = ask(client, 'big_a.tess', 'big_b.tess', max_results='5000', use_meter='0').get_json()
    assert body['cached'] is True and body['in_parts'] is False and body['estimated_seconds'] == 0
    # another key (meter on) is not cached and is estimated as before
    body = ask(client, 'big_a.tess', 'big_b.tess', max_results='5000', use_meter='1').get_json()
    assert body['cached'] is False and body['in_parts'] is True and body['parts'] == 20


def test_estimate_follows_the_part_count_and_matches_the_measured_runs():
    """Offline runs of 2026-10-27 after the speed changes: 174 s, 205 s, 138 s and
    91 s (the constants were fitted to them), each within thirteen percent."""
    for n_src, n_tgt, measured in ((9502, 1252, 173.6), (9896, 694, 205.1),
                                   (7423, 824, 138.1), (694, 9896, 90.7)):
        got = fusion.estimate_fusion(n_src, n_tgt)['estimated_seconds']
        assert abs(got - measured) / measured < 0.13, (n_src, n_tgt, got)
    # more parts cost more at the same pair count
    a = fusion.estimate_fusion(5000, 2000)['estimated_seconds']
    b = fusion.estimate_fusion(10000, 1000)['estimated_seconds']
    assert b > a
