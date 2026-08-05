"""Tests for result-cache key isolation."""

from backend.cache import get_cache_key


def test_result_version_only_changes_opted_in_cache_keys():
    settings = {
        'match_type': 'fusion',
        'source_unit_type': 'line',
        'target_unit_type': 'line',
        'freq_basis': 'corpus',
    }

    unversioned = get_cache_key('source.tess', 'target.tess', 'la', settings)
    unchanged_copy = get_cache_key(
        'source.tess', 'target.tess', 'la', dict(settings))
    versioned = get_cache_key(
        'source.tess', 'target.tess', 'la', {**settings, 'result_version': 2})

    assert unchanged_copy == unversioned
    assert versioned != unversioned
