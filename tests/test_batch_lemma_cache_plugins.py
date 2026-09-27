"""The cache builder analyses plugin languages with their own handlers, or
refuses, and never writes a cache of empty units.

Until 2026-09-26 the fast builder sent every language it did not know to
the Latin tokenizer, which strips non-Latin letters. A 6,236-line Arabic
file cached as 6,236 empty units in zero seconds, reported success, and
reached the index with 0 postings (issue #495). The plugin languages
register their handlers only when the web app module is imported, so any
script that imports the processor directly saw none of them. Hebrew and
Coptic caches on the live site were written by the web server and are
correct; rebuilt offline with the old script they would have been emptied.
"""
import importlib.util
import os
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    'batch_lemma_cache', ROOT / 'scripts' / 'batch_lemma_cache.py')
blc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(blc)


@pytest.fixture(scope='module')
def registered():
    return blc.register_plugin_languages()


@pytest.fixture(scope='module')
def tp(registered):
    return blc.FastTextProcessor()


def tess(tmp_path, name, lines):
    p = tmp_path / name
    p.write_text('\n'.join(f'<{name[:-5]} {i + 1}.1>\t{text}' for i, text in enumerate(lines)) + '\n',
                 encoding='utf-8')
    return str(p)


def test_the_plugins_register(registered):
    assert 'he' in registered
    assert 'cop' in registered


def test_a_hebrew_file_gets_hebrew_tokens(tp, tmp_path):
    path = tess(tmp_path, 'hebrew_test.tess', ['בְּרֵאשִׁית בָּרָא אֱלֹהִים', 'וַיֹּאמֶר אֱלֹהִים יְהִי אוֹר'])
    units = tp.process_file(path, 'he', 'line')
    assert len(units) == 2
    assert all(u['tokens'] for u in units), units
    assert all(u['lemmas'] for u in units), units
    # and they are Hebrew, not the Latin tokenizer's leavings
    assert any('א' <= ch <= 'ת' for ch in units[0]['tokens'][0])


def test_a_coptic_file_gets_coptic_tokens(tp, tmp_path):
    path = tess(tmp_path, 'coptic_test.tess', ['ⲁⲛⲟⲕ ⲡⲉ ⲡⲛⲟⲩⲧⲉ', 'ϩⲛ ⲧⲉϩⲟⲩⲉⲓⲧⲉ'])
    units = tp.process_file(path, 'cop', 'line')
    assert len(units) == 2
    assert all(u['tokens'] for u in units), units


def test_latin_still_works_the_old_way(tp, tmp_path):
    path = tess(tmp_path, 'latin_test.tess', ['arma virumque cano', 'Troiae qui primus ab oris'])
    units = tp.process_file(path, 'la', 'line')
    assert [u['tokens'] for u in units] == [['arma', 'uirumque', 'cano'], ['troiae', 'qui', 'primus', 'ab', 'oris']]


def test_an_unknown_language_is_refused_not_treated_as_latin(tp, tmp_path):
    path = tess(tmp_path, 'mystery_test.tess', ['some words here'])
    with pytest.raises(ValueError, match='no analyser'):
        tp.process_file(path, 'xx', 'line')


def test_a_file_of_empty_units_is_recognised():
    assert blc.all_units_empty([{'tokens': []}, {'tokens': []}])
    assert not blc.all_units_empty([{'tokens': []}, {'tokens': ['a']}])
    assert not blc.all_units_empty([])
