"""The Sahidica New Testament is held under the Wells license (searchable,
never redistributed): every Sahidica file must be in the registry, ignored by
.gitignore, and untracked. The generic live-registry tests in
tests/test_restricted_texts.py iterate every registry entry (ignore rule and
untracked status); these tests pin the Sahidica set itself."""
import os
import subprocess

import pytest

import backend.restricted_texts as restricted_texts

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COP = os.path.join(REPO_ROOT, 'texts', 'cop')


def _sahidica_files():
    if not os.path.isdir(COP):
        return []
    return sorted(f for f in os.listdir(COP)
                  if f.startswith('sahidica.') and f.endswith('.tess'))


def test_every_sahidica_file_is_in_the_registry_with_credit():
    files = _sahidica_files()
    if not files:
        pytest.skip('no texts/cop/sahidica.* on this checkout')
    for f in files:
        assert restricted_texts.is_restricted(f), f
        assert 'Wells' in restricted_texts.credit_for(f), f
    assert restricted_texts.is_restricted('sahidic.bible.tess')


def test_every_sahidica_file_is_matched_by_gitignore():
    files = _sahidica_files()
    if not files:
        pytest.skip('no texts/cop/sahidica.* on this checkout')
    for f in files + ['sahidic.bible.tess']:
        r = subprocess.run(['git', 'check-ignore', '-q', f'texts/cop/{f}'],
                           cwd=REPO_ROOT)
        assert r.returncode == 0, f'{f} is not matched by .gitignore'


def test_no_sahidica_file_is_tracked():
    r = subprocess.run(['git', 'ls-files', 'texts/cop'], cwd=REPO_ROOT,
                       capture_output=True, text=True)
    if r.returncode != 0:
        pytest.skip('not a git checkout')
    bad = [p for p in r.stdout.splitlines()
           if os.path.basename(p).startswith('sahidica.')
           or os.path.basename(p) == 'sahidic.bible.tess']
    assert not bad, bad


def test_the_old_testament_files_stay_unrestricted():
    assert not restricted_texts.is_restricted('sahidic.genesis.tess')
    assert not restricted_texts.is_restricted('sahidic.ot.tess')


def test_coptic_download_listing_withholds_the_sahidica_files():
    held = restricted_texts.filenames('cop', texts_root=os.path.join(REPO_ROOT, 'texts'))
    if not _sahidica_files():
        pytest.skip('no texts/cop/sahidica.* on this checkout')
    assert set(_sahidica_files()) <= set(held)
    assert 'sahidic.bible.tess' in held
