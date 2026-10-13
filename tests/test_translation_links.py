"""backend/translation_links.py: the loader behind translation.external_links.

Pritchett's Ghalib translations carry no stated licence, so the Reader's
Translation tab links to her own page instead of copying her English. This
table is additive and separate from the aligned-translation files in
data/translations/: a work can have a link table, an aligned translation,
both, or neither.
"""
import json

import backend.translation_links as translation_links


def _write_table(tmp_path, filename, payload):
    tmp_path.mkdir(parents=True, exist_ok=True)
    with open(tmp_path / filename, 'w', encoding='utf-8') as fh:
        json.dump(payload, fh)


def _reset(monkeypatch, directory):
    monkeypatch.setattr(translation_links, '_DIR', str(directory))
    monkeypatch.setattr(translation_links, '_index', None)


FIXTURE = {
    'work': 'ghalib.diwan_wikisource',
    'translator': 'Frances W. Pritchett',
    'site_title': 'A Desertful of Roses',
    'source_url': 'https://franpritchett.com/00ghalib/',
    'links': {
        'ghalib.diwan_wikisource.ghazal.1.1': {'url': 'https://example.org/001/1_01.html'},
        'ghalib.diwan_wikisource.ghazal.1.2': {'url': 'https://example.org/001/1_01.html'},
        'ghalib.diwan_wikisource.ghazal.1.3': {'url': 'https://example.org/001/1_02.html'},
    },
}


def test_for_refs_returns_the_linked_url(tmp_path, monkeypatch):
    _write_table(tmp_path, 'ur__ghalib_pritchett_links.json', FIXTURE)
    _reset(monkeypatch, tmp_path)
    out = translation_links.for_refs(
        'ghalib.diwan_wikisource', ['ghalib.diwan_wikisource.ghazal.1.1'])
    assert out == [{
        'translator': 'Frances W. Pritchett',
        'site_title': 'A Desertful of Roses',
        'source_url': 'https://franpritchett.com/00ghalib/',
        'url': 'https://example.org/001/1_01.html',
    }]


def test_two_refs_sharing_one_verse_url_are_not_duplicated(tmp_path, monkeypatch):
    """Two misras of the same couplet point at the same Pritchett verse page;
    a selection spanning both must show the link once, not twice."""
    _write_table(tmp_path, 'ur__ghalib_pritchett_links.json', FIXTURE)
    _reset(monkeypatch, tmp_path)
    out = translation_links.for_refs(
        'ghalib.diwan_wikisource',
        ['ghalib.diwan_wikisource.ghazal.1.1', 'ghalib.diwan_wikisource.ghazal.1.2'])
    assert len(out) == 1
    assert out[0]['url'] == 'https://example.org/001/1_01.html'


def test_distinct_verse_urls_both_appear_in_first_seen_order(tmp_path, monkeypatch):
    _write_table(tmp_path, 'ur__ghalib_pritchett_links.json', FIXTURE)
    _reset(monkeypatch, tmp_path)
    out = translation_links.for_refs(
        'ghalib.diwan_wikisource',
        ['ghalib.diwan_wikisource.ghazal.1.3', 'ghalib.diwan_wikisource.ghazal.1.1'])
    assert [e['url'] for e in out] == [
        'https://example.org/001/1_02.html', 'https://example.org/001/1_01.html']


def test_unlinked_ref_is_simply_absent(tmp_path, monkeypatch):
    _write_table(tmp_path, 'ur__ghalib_pritchett_links.json', FIXTURE)
    _reset(monkeypatch, tmp_path)
    out = translation_links.for_refs(
        'ghalib.diwan_wikisource', ['ghalib.diwan_wikisource.ghazal.99.1'])
    assert out == []


def test_work_with_no_table_at_all_returns_empty_list_not_error(tmp_path, monkeypatch):
    _write_table(tmp_path, 'ur__ghalib_pritchett_links.json', FIXTURE)
    _reset(monkeypatch, tmp_path)
    out = translation_links.for_refs('some.other.work', ['some.other.work.1.1'])
    assert out == []


def test_empty_refs_returns_empty_list(tmp_path, monkeypatch):
    _write_table(tmp_path, 'ur__ghalib_pritchett_links.json', FIXTURE)
    _reset(monkeypatch, tmp_path)
    assert translation_links.for_refs('ghalib.diwan_wikisource', []) == []
    assert translation_links.for_refs('ghalib.diwan_wikisource', None) == []


def test_no_links_directory_at_all_is_handled(tmp_path, monkeypatch):
    _reset(monkeypatch, tmp_path / 'does_not_exist')
    assert translation_links.for_refs('ghalib.diwan_wikisource', ['x.1.1']) == []
    assert translation_links.available_works() == []


def test_a_file_missing_the_work_key_is_skipped_not_fatal(tmp_path, monkeypatch, caplog):
    _write_table(tmp_path, 'broken.json', {'links': {'a.1.1': {'url': 'https://x'}}})
    _write_table(tmp_path, 'ur__ghalib_pritchett_links.json', FIXTURE)
    _reset(monkeypatch, tmp_path)
    # the good file still loads despite the broken one sitting next to it
    out = translation_links.for_refs(
        'ghalib.diwan_wikisource', ['ghalib.diwan_wikisource.ghazal.1.1'])
    assert out and out[0]['url'] == 'https://example.org/001/1_01.html'


def test_available_works_lists_the_normalized_work_id(tmp_path, monkeypatch):
    _write_table(tmp_path, 'ur__ghalib_pritchett_links.json', FIXTURE)
    _reset(monkeypatch, tmp_path)
    assert translation_links.available_works() == ['ghalib.diwan_wikisource']
