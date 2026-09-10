"""Regression test for the GET /fusion-search settings passthrough added
2026-09-10 (connector parity gap 5: fusion_search gains source_unit_type,
target_unit_type, and weights).

The one thing this MUST NOT do is change the cache key for a plain call with
no overrides -- that would silently orphan every fusion result already
cached under the old key shape. _default_fusion_cache_settings is a pure
function, so this is checked directly against backend.cache.get_cache_key
rather than through a live fusion run.
"""
from backend.blueprints.fusion import _default_fusion_cache_settings
from backend.cache import get_cache_key


def test_default_call_is_byte_identical_to_pre_parity_shape():
    """A caller that passes none of the new overrides gets the exact settings
    dict (and therefore cache key) GET /fusion-search always produced."""
    settings = _default_fusion_cache_settings('la', 5000, use_meter=False)
    assert settings == {
        'match_type': 'fusion',
        'result_version': 2,
        'mode': 'merged',
        'max_results': 5000,
        'language': 'la',
        'source_unit_type': 'line',
        'target_unit_type': 'line',
        'use_meter': False,
        'freq_basis': 'corpus',
    }


def test_default_call_cache_key_matches_hardcoded_old_shape():
    old_shape = {
        'match_type': 'fusion', 'result_version': 2, 'mode': 'merged',
        'max_results': 5000, 'language': 'la', 'source_unit_type': 'line',
        'target_unit_type': 'line', 'use_meter': False, 'freq_basis': 'corpus',
    }
    new = _default_fusion_cache_settings('la', 5000, use_meter=False)
    assert get_cache_key('s.tess', 't.tess', 'la', old_shape) == \
        get_cache_key('s.tess', 't.tess', 'la', new)


def test_empty_channel_weights_omitted_from_settings():
    """channel_weights={} must NOT appear in the settings dict (matching the
    POST route's rule), so a default-weight run keeps hitting the same
    cache entries as before this existed."""
    settings = _default_fusion_cache_settings('la', 5000, channel_weights={})
    assert 'channel_weights' not in settings
    settings_none = _default_fusion_cache_settings('la', 5000, channel_weights=None)
    assert 'channel_weights' not in settings_none


def test_unit_type_override_changes_cache_key():
    default = _default_fusion_cache_settings('la', 5000)
    phrase = _default_fusion_cache_settings('la', 5000, source_unit_type='phrase')
    assert phrase['source_unit_type'] == 'phrase'
    assert get_cache_key('s.tess', 't.tess', 'la', default) != \
        get_cache_key('s.tess', 't.tess', 'la', phrase)


def test_channel_weights_override_changes_cache_key():
    default = _default_fusion_cache_settings('la', 5000)
    weighted = _default_fusion_cache_settings('la', 5000, channel_weights={'semantic': 2.0})
    assert weighted['channel_weights'] == {'semantic': 2.0}
    assert get_cache_key('s.tess', 't.tess', 'la', default) != \
        get_cache_key('s.tess', 't.tess', 'la', weighted)
