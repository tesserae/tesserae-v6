"""The Hebrew-Greek route choice added 2026-09-30 (see backend/lxx_pivot.py).

``_crosslingual_fusion_core`` dispatches a Hebrew-Greek search to the
Septuagint pivot, the direct dictionary route, or both, based on
``settings['hebrew_greek_route']``. These tests monkeypatch the pivot
(``_lxx_pivot_core``) and the direct route (``_direct_crosslingual_core``)
so the dispatch logic is checked in isolation, without running any real
matching.
"""
import pytest

from backend.blueprints import search as S


def _params(route=None):
    settings = {'min_matches': 2}
    if route is not None:
        settings['hebrew_greek_route'] = route
    return {
        'source_id': 'hebrew_bible.genesis', 'target_id': 'septuaginta.genesis',
        'language': 'he', 'source_language': 'he', 'target_language': 'grc',
        'settings': settings,
        'source_path': '/x/he/hebrew_bible.genesis.tess',
        'target_path': '/x/grc/septuaginta.genesis.tess',
        'is_crosslingual': True,
    }


def _pivot_result():
    return {
        'results': [
            {'source': {'ref': 'genesis 1.1', 'hebrew_ref': 'hebrew_bible.genesis.1.1'},
             'target': {'ref': '1.1'}},
        ],
        'via_septuagint': True,
        'septuagint_text': 'septuaginta.genesis',
    }


def _direct_result():
    return {
        'results': [
            # Same Hebrew line (1.1) as the pivot result above: should be
            # dropped from a 'both' merge, kept standing alone under 'direct'.
            {'source': {'ref': '1.1'}, 'target': {'ref': 'x'}},
            # A different Hebrew line: always kept.
            {'source': {'ref': '2.3'}, 'target': {'ref': 'y'}},
        ],
        'source_lines': 50, 'target_lines': 50,
    }


def test_septuagint_default_returns_pivot_without_running_direct(monkeypatch):
    calls = {'pivot': 0, 'direct': 0}

    def fake_pivot(params, su, tu, settings):
        calls['pivot'] += 1
        return _pivot_result()

    def fake_direct(params, su, tu, settings, cancellation=None, req_meta=None):
        calls['direct'] += 1
        return _direct_result()

    monkeypatch.setattr(S, '_lxx_pivot_core', fake_pivot)
    monkeypatch.setattr(S, '_direct_crosslingual_core', fake_direct)

    out = S._crosslingual_fusion_core(_params(), [], [], {'min_matches': 2})
    assert calls == {'pivot': 1, 'direct': 0}
    assert out['results'][0]['source']['hebrew_ref'] == 'hebrew_bible.genesis.1.1'


def test_septuagint_default_falls_through_to_direct_without_counterpart(monkeypatch):
    calls = {'pivot': 0, 'direct': 0}

    def fake_pivot(params, su, tu, settings):
        calls['pivot'] += 1
        return None  # no routed counterpart

    def fake_direct(params, su, tu, settings, cancellation=None, req_meta=None):
        calls['direct'] += 1
        return _direct_result()

    monkeypatch.setattr(S, '_lxx_pivot_core', fake_pivot)
    monkeypatch.setattr(S, '_direct_crosslingual_core', fake_direct)

    out = S._crosslingual_fusion_core(_params(), [], [], {'min_matches': 2})
    assert calls == {'pivot': 1, 'direct': 1}
    assert len(out['results']) == 2


def test_direct_route_never_calls_the_pivot(monkeypatch):
    def fake_pivot(params, su, tu, settings):
        raise AssertionError("direct route must not call the pivot")

    def fake_direct(params, su, tu, settings, cancellation=None, req_meta=None):
        return _direct_result()

    monkeypatch.setattr(S, '_lxx_pivot_core', fake_pivot)
    monkeypatch.setattr(S, '_direct_crosslingual_core', fake_direct)

    params = _params(route='direct')
    out = S._crosslingual_fusion_core(params, [], [], params['settings'])
    assert len(out['results']) == 2
    # Plain 'direct' requests are not relabelled -- there is nothing to
    # distinguish them from.
    assert 'route' not in out['results'][0]


def test_both_merges_pivot_first_then_unanswered_direct_lines(monkeypatch):
    def fake_pivot(params, su, tu, settings):
        return _pivot_result()

    def fake_direct(params, su, tu, settings, cancellation=None, req_meta=None):
        return _direct_result()

    monkeypatch.setattr(S, '_lxx_pivot_core', fake_pivot)
    monkeypatch.setattr(S, '_direct_crosslingual_core', fake_direct)

    params = _params(route='both')
    out = S._crosslingual_fusion_core(params, [], [], params['settings'])

    assert out['hebrew_greek_route'] == 'both'
    # Pivot's one result, then only the direct result for the UNCOVERED
    # Hebrew line (2.3); the direct result for 1.1 is dropped as a duplicate
    # of what the pivot already answered.
    assert len(out['results']) == 2
    assert out['results'][0]['route'] == 'septuagint'
    assert out['results'][0]['source']['hebrew_ref'] == 'hebrew_bible.genesis.1.1'
    assert out['results'][1]['route'] == 'direct'
    assert out['results'][1]['source']['ref'] == '2.3'
    assert out['total_matches'] == 2


def test_both_without_a_counterpart_behaves_like_direct(monkeypatch):
    def fake_pivot(params, su, tu, settings):
        return None

    def fake_direct(params, su, tu, settings, cancellation=None, req_meta=None):
        return _direct_result()

    monkeypatch.setattr(S, '_lxx_pivot_core', fake_pivot)
    monkeypatch.setattr(S, '_direct_crosslingual_core', fake_direct)

    params = _params(route='both')
    out = S._crosslingual_fusion_core(params, [], [], params['settings'])
    assert len(out['results']) == 2
    assert 'route' not in out['results'][0]


def test_non_hebrew_greek_pair_ignores_the_setting(monkeypatch):
    """hebrew_greek_route is meaningless for grc-la; it must not affect that
    pair, and the pivot must never be consulted."""
    def fake_pivot(params, su, tu, settings):
        raise AssertionError("pivot must not run for a non-Hebrew-Greek pair")

    def fake_direct(params, su, tu, settings, cancellation=None, req_meta=None):
        return {'results': [{'source': {'ref': '1.1'}, 'target': {'ref': 'a'}}]}

    monkeypatch.setattr(S, '_lxx_pivot_core', fake_pivot)
    monkeypatch.setattr(S, '_direct_crosslingual_core', fake_direct)

    params = {
        'source_id': 'vergil.aeneid', 'target_id': 'homer.iliad',
        'language': 'grc', 'source_language': 'grc', 'target_language': 'la',
        'settings': {'hebrew_greek_route': 'both'},
        'source_path': '/x', 'target_path': '/y', 'is_crosslingual': True,
    }
    out = S._crosslingual_fusion_core(params, [], [], params['settings'])
    assert len(out['results']) == 1
