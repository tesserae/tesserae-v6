"""scripts/corpus/add_texts_to_index.py resolves lemma cache entries through
backend.lemma_cache.get_cache_path, so it finds the same file the app writes.
Runs the path function and load_units only, on temporary cache folders."""
import importlib.util
import json
import os

import pytest

from backend.lemma_cache import get_cache_path

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture(scope='module')
def script():
    spec = importlib.util.spec_from_file_location(
        'add_texts_to_index', os.path.join(ROOT, 'scripts', 'corpus', 'add_texts_to_index.py'))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


NAMES = [
    'vergil.aeneid.tess',
    'ἀριστοτέλης.ποιητική.tess',
    'odd/name.with.slash.tess',
    'ἀριστοτέλης.ποιητική.tess'.encode('utf-8').decode('utf-8', 'surrogateescape'),
]


@pytest.mark.parametrize('name', NAMES)
def test_path_equals_backend(script, tmp_path, name):
    cache = str(tmp_path)
    assert script.cache_entry_path(cache, 'la', name) == get_cache_path(name, 'la', cache_dir=cache)


@pytest.mark.parametrize('name', NAMES)
def test_load_units_reads_backend_file(script, tmp_path, name):
    target = get_cache_path(name, 'la', cache_dir=str(tmp_path))
    os.makedirs(os.path.dirname(target))
    with open(target, 'w', encoding='utf-8') as fh:
        json.dump({'units_line': [{'ref': '1.1', 'lemmas': ['a']}]}, fh)
    assert script.load_units(str(tmp_path), 'la', name) == [{'ref': '1.1', 'lemmas': ['a']}]


def test_legacy_bare_stem_still_found(script, tmp_path):
    os.makedirs(tmp_path / 'la')
    with open(tmp_path / 'la' / 'old.work.json', 'w') as fh:
        json.dump({'units_line': [{'ref': '1', 'lemmas': []}]}, fh)
    assert script.load_units(str(tmp_path), 'la', 'old.work.tess')


def test_missing_entry_exits(script, tmp_path):
    with pytest.raises(SystemExit):
        script.load_units(str(tmp_path), 'la', 'nothing.tess')
