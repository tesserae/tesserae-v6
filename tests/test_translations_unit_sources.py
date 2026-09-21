"""for_passage's attribution follows the units actually served, not just the
first entry in `sources`.

Some translation files now mix sources at the unit level (Silius Italicus:
J. D. Duff's 1927 public-domain Loeb for most of books 1-8, A. S. Kline's
non-commercial-licensed Poetry in Translation text for books 9-17 and the
gaps in 1-8). Before this, for_passage always credited sources[0], so a
passage served entirely from Kline's units was mislabelled as Duff's -- wrong
attribution, and a licence notice that never appeared. The fix reads
`unit_sources` (a list parallel to `units` giving each unit's index into
`sources`) when present and builds `attribution` from the distinct sources
of the units the request actually returned; a file with no `unit_sources`
key keeps exactly the old behaviour.
"""
import backend.translations as translations

FIXTURE_MIXED = {
    'tess_work': 'xx/testwork',
    'language': 'la',
    'sources': [
        {'translator': 'Translator A', 'year': 1900},
        {
            'translator': 'Translator B',
            'year': 2000,
            'publisher': 'Publisher B',
            'license': 'Free for any non-commercial purpose.',
            'short_attribution': 'Translator B (Publisher B), non-commercial use only',
        },
    ],
    'license': 'Mixed licence text.',
    'attribution': 'Translator A (1900) and Translator B (Publisher B)',
    'mean_source_lines_per_translation_unit': 1,
    'alignment_confidence': 'high',
    'units': ['Unit zero text.', 'Unit one text.', 'Unit two text.'],
    'unit_sources': [0, 1, 0],
    'ref_to_unit': {'wk. 1.1': 0, 'wk. 1.2': 1, 'wk. 2.1': 2},
}

FIXTURE_SINGLE_SOURCE = {
    'tess_work': 'xx/otherwork',
    'language': 'la',
    'sources': [{'translator': 'Translator A', 'year': 1900}],
    'license': 'Public domain.',
    'attribution': 'Translator A (1900)',
    'mean_source_lines_per_translation_unit': 1,
    'alignment_confidence': 'high',
    'units': ['Unit zero text.'],
    'ref_to_unit': {'wk. 1.1': 0},
}


def _patch_load(monkeypatch, mapping):
    def fake_load(work):
        key = translations._norm_work(work)
        return mapping.get(key)
    monkeypatch.setattr(translations, '_load', fake_load)


def test_passage_served_entirely_from_kline_units(monkeypatch):
    _patch_load(monkeypatch, {'testwork': FIXTURE_MIXED})
    out = translations.for_passage('xx/testwork', ['wk. 1.2'])
    assert out['available'] is True
    assert out['translator'] == 'Translator B'
    assert out['year'] == 2000
    assert out['attribution'] == 'Translator B (Publisher B), non-commercial use only'


def test_passage_served_entirely_from_duff_units(monkeypatch):
    _patch_load(monkeypatch, {'testwork': FIXTURE_MIXED})
    out = translations.for_passage('xx/testwork', ['wk. 1.1'])
    assert out['available'] is True
    assert out['translator'] == 'Translator A'
    assert out['year'] == 1900
    assert out['attribution'] == 'Translator A (1900)'


def test_mixed_passage_credits_both_sources_in_order_served(monkeypatch):
    _patch_load(monkeypatch, {'testwork': FIXTURE_MIXED})
    out = translations.for_passage('xx/testwork', ['wk. 1.1', 'wk. 1.2'])
    assert out['available'] is True
    assert out['attribution'] == (
        'Translator A (1900) and '
        'Translator B (Publisher B), non-commercial use only'
    )
    # a mixed passage still reports one (the first-served) translator/year,
    # not a garbled combination of both
    assert out['translator'] == 'Translator A'
    assert out['year'] == 1900


def test_mixed_passage_orders_attribution_by_first_ref_seen(monkeypatch):
    _patch_load(monkeypatch, {'testwork': FIXTURE_MIXED})
    out = translations.for_passage('xx/testwork', ['wk. 1.2', 'wk. 1.1'])
    assert out['attribution'] == (
        'Translator B (Publisher B), non-commercial use only and '
        'Translator A (1900)'
    )


def test_file_without_unit_sources_is_unchanged(monkeypatch):
    _patch_load(monkeypatch, {'otherwork': FIXTURE_SINGLE_SOURCE})
    out = translations.for_passage('xx/otherwork', ['wk. 1.1'])
    assert out['available'] is True
    assert out['translator'] == 'Translator A'
    assert out['year'] == 1900
    # falls straight back to the file's own top-level attribution, as before
    assert out['attribution'] == 'Translator A (1900)'
