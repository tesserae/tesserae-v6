"""GET /fusion-search over a cached comparison: how it reports the size of the
comparison. A comparison with fewer results than the storage cap (5000) was
not truncated, so its true size is the stored count even for a cache written
before the count was stored (#262). One that fills the cap is reported capped.
"""
import pytest
from flask import Flask

import backend.blueprints.fusion as F

CAP = 5000


def _rows(n):
    return [{'source': {'ref': f'a. 1.{i}', 'text': 'x'}, 'target': {'ref': f'b. 2.{i}', 'text': 'y'},
             'fused_score': 5.0, 'channels': ['lemma']} for i in range(n)]


@pytest.fixture
def get(monkeypatch):
    app = Flask(__name__)
    app.register_blueprint(F.fusion_bp)
    served = {}

    monkeypatch.setattr(F, 'resolve_text_path', lambda *a, **k: '/tmp/x.tess')
    monkeypatch.setattr(F, '_poll_use_meter', lambda *a, **k: False)
    monkeypatch.setattr(F, 'ensure_cache_dir', lambda: None)
    monkeypatch.setattr(F, '_clear_fusion_status', lambda *a, **k: None)
    monkeypatch.setattr(F, 'get_cached_results', lambda *a, **k: (served['rows'], served['meta']))

    def call(rows, meta):
        served['rows'], served['meta'] = rows, meta
        r = app.test_client().get('/fusion-search?source=a.tess&target=b.tess&language=la')
        assert r.status_code == 200
        return r.get_json()
    return call


def test_old_cache_under_the_cap_reports_its_true_size(get):
    d = get(_rows(3), None)                       # written before total_candidates was stored
    assert d['cached'] is True and d['total'] == 3
    assert d['total_candidates'] == 3 and d['capped'] is False
    assert d['by_book']['population']['capped'] is False


def test_new_cache_under_the_cap_keeps_its_stored_count(get):
    d = get(_rows(3), {'total_candidates': 3})
    assert d['total_candidates'] == 3 and d['capped'] is False


def test_cache_that_fills_the_cap_is_reported_capped_with_its_true_size(get):
    d = get(_rows(CAP), {'total_candidates': 12000})
    assert d['total'] == CAP and d['total_candidates'] == 12000 and d['capped'] is True


def test_old_cache_that_fills_the_cap_is_capped_and_its_size_unknown(get):
    d = get(_rows(CAP), None)
    assert d['total_candidates'] is None and d['capped'] is True


def test_the_same_cached_comparison_is_served_identically_twice(get):
    rows = _rows(7)
    assert get(rows, {'total_candidates': 7}) == get(rows, {'total_candidates': 7})
