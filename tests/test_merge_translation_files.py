"""merge_translation_files.merge: every source of a merged file carries a license."""
import importlib.util
import os
import sys

DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'scripts', 'translations')
sys.path.insert(0, DIR)
spec = importlib.util.spec_from_file_location('merge_translation_files', os.path.join(DIR, 'merge_translation_files.py'))
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

A = {   # a Loeb-style file: its one source has its own license
    'tess_work': 'grc/fix.work', 'sources': [{'translator': 'Jones', 'license': 'Public domain in the United States (1933)'}],
    'units': ['a1', 'a2'], 'ref_to_unit': {'1.1': 0, '1.2': 1}, 'attribution': 'Jones', 'license': 'Loeb terms',
    'verified_by': 'x', 'notes': '',
}
B = {   # a Bohn-style file: the source has no license, the file does
    'tess_work': 'grc/fix.work', 'sources': [{'translator': 'Shilleto'}],
    'units': ['b1', 'b2', 'b3'], 'ref_to_unit': {'1.1': 0, '1.2': 1, '1.3': 2}, 'attribution': 'Shilleto',
    'license': 'Public domain (published 1886)', 'verified_by': 'y', 'notes': 'n',
}
REFS = ['1.1', '1.2', '1.3']


def test_every_source_has_a_license():
    out, taken = mod.merge(A, B, REFS)
    assert [s['license'] for s in out['sources']] == ['Public domain in the United States (1933)', 'Public domain (published 1886)']
    assert taken == {'primary': 2, 'secondary': 1}


def test_file_level_license_names_each_source():
    out, _ = mod.merge(A, B, REFS)
    assert out['license'] == ('Jones: Public domain in the United States (1933); '
                              'Shilleto: Public domain (published 1886).')


def test_units_and_source_indexes_follow_the_primary_first():
    out, _ = mod.merge(A, B, REFS)
    assert out['units'] == ['a1', 'a2', 'b3']
    assert out['unit_sources'] == [0, 0, 1]
    assert out['ref_to_unit'] == {'1.1': 0, '1.2': 1, '1.3': 2}


def test_inputs_are_not_changed():
    mod.merge(A, B, REFS)
    assert 'license' not in B['sources'][0]


def test_source_with_no_license_anywhere_stays_without_one():
    b = dict(B, license='')
    out, _ = mod.merge(A, b, REFS)
    assert 'license' not in out['sources'][1]
    assert out['license'] == 'Jones: Public domain in the United States (1933).'


def test_a_repeated_translator_and_license_is_named_once():
    a = dict(A, sources=[{'translator': 'Jones', 'license': 'PD'}, {'translator': 'Jones', 'license': 'PD'}])
    out, _ = mod.merge(a, B, REFS)
    assert out['license'] == 'Jones: PD; Shilleto: Public domain (published 1886).'
