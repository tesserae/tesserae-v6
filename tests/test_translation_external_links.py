"""translations.for_passage's external_links field: additive, present whether
or not an aligned translation also exists for the work.

Ghalib (ghalib.diwan_wikisource) has no aligned-translation file at all --
Pritchett's translation carries no licence to copy -- so for this work
external_links is the ONLY thing the Translation tab has to show. These
tests pin that `available: False` case down explicitly, plus the case where
a work has both an aligned translation and a link.
"""
import backend.translations as translations
import backend.translation_links as translation_links

FIXTURE_WITH_TRANSLATION = {
    'tess_work': 'xx/bothwork',
    'language': 'la',
    'sources': [{'translator': 'Translator A', 'year': 1900}],
    'license': 'Public domain.',
    'attribution': 'Translator A (1900)',
    'mean_source_lines_per_translation_unit': 1,
    'alignment_confidence': 'high',
    'units': ['Unit zero text.'],
    'ref_to_unit': {'wk. 1.1': 0},
}

ONE_LINK = [{'translator': 'Frances W. Pritchett',
             'site_title': 'A Desertful of Roses',
             'source_url': 'https://franpritchett.com/00ghalib/',
             'url': 'https://franpritchett.com/00ghalib/001/1_01.html'}]


def _patch_load(monkeypatch, mapping):
    def fake_load(work):
        key = translations._norm_work(work)
        return mapping.get(key)
    monkeypatch.setattr(translations, '_load', fake_load)


def _patch_links(monkeypatch, value):
    monkeypatch.setattr(translation_links, 'for_refs', lambda work, refs: value)


def test_no_aligned_translation_but_a_link_exists(monkeypatch):
    """Ghalib's actual shape: no aligned-translation file, but a Pritchett
    verse link. available stays False (there is no translation TEXT), and
    external_links carries the link rather than the field vanishing."""
    _patch_load(monkeypatch, {})
    _patch_links(monkeypatch, ONE_LINK)
    out = translations.for_passage('ghalib.diwan_wikisource',
                                    ['ghalib.diwan_wikisource.ghazal.1.1'])
    assert out['available'] is False
    assert out['external_links'] == ONE_LINK


def test_no_aligned_translation_and_no_link_is_an_empty_list_not_missing(monkeypatch):
    _patch_load(monkeypatch, {})
    _patch_links(monkeypatch, [])
    out = translations.for_passage('some.other.work', ['some.other.work.1.1'])
    assert out['available'] is False
    assert out['external_links'] == []


def test_aligned_translation_exists_but_selected_lines_are_uncovered(monkeypatch):
    """The 'has a translation, but not for these lines' branch also carries
    external_links, in case the same selection has a Pritchett-style link
    even though it falls outside the aligned translation's coverage."""
    _patch_load(monkeypatch, {'bothwork': FIXTURE_WITH_TRANSLATION})
    _patch_links(monkeypatch, ONE_LINK)
    out = translations.for_passage('xx/bothwork', ['wk. 9.9'])
    assert out['available'] is False
    assert out['external_links'] == ONE_LINK


def test_aligned_translation_and_external_link_both_present(monkeypatch):
    """A work that has BOTH an aligned translation and an external link
    shows the translation text as before, with the link added alongside."""
    _patch_load(monkeypatch, {'bothwork': FIXTURE_WITH_TRANSLATION})
    _patch_links(monkeypatch, ONE_LINK)
    out = translations.for_passage('xx/bothwork', ['wk. 1.1'])
    assert out['available'] is True
    assert out['text'] == 'Unit zero text.'
    assert out['external_links'] == ONE_LINK


def test_aligned_translation_present_but_no_external_link(monkeypatch):
    _patch_load(monkeypatch, {'bothwork': FIXTURE_WITH_TRANSLATION})
    _patch_links(monkeypatch, [])
    out = translations.for_passage('xx/bothwork', ['wk. 1.1'])
    assert out['available'] is True
    assert out['external_links'] == []
