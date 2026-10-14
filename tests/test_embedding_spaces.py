"""English has two sets of line embeddings (2026-10-13): MiniLM (384) for English-English
search and SPhilBERTa (768) for cross-language search. Every other language has one."""
import inspect

import numpy as np

from backend import embedding_storage as es
from backend import precompute_embeddings, semantic_similarity as ss
from backend.blueprints import admin

DIMENSIONS = {'all-MiniLM-L6-v2': 384, 'bowphs/SPhilBerta': 768}


def test_model_choices_agree_with_the_dimensions_of_the_files():
    assert DIMENSIONS[ss.model_name_for('en')] == 384
    assert DIMENSIONS[ss.cross_model_name_for('en')] == 768
    for lang in ('la', 'grc'):
        assert ss.model_name_for(lang) == ss.cross_model_name_for(lang) == 'bowphs/SPhilBerta'
    assert ss.cross_model_name_for('he') == ss.model_name_for('he')
    assert ss.cross_model_name_for('fa') == ss.model_name_for('fa')


def test_builders_take_the_model_from_the_search_functions():
    for module in (admin, precompute_embeddings):
        src = inspect.getsource(module)
        assert 'all-MiniLM' not in src and 'bowphs/SPhilBerta' not in src
        assert 'model_name_for' in src
    assert 'cross_model_name_for' in inspect.getsource(admin)
    assert 'cross_model_name_for' in inspect.getsource(precompute_embeddings)


def test_paths_and_round_trip_by_space(tmp_path, monkeypatch):
    monkeypatch.setattr(es, 'EMBEDDINGS_DIR', str(tmp_path))
    monkeypatch.setattr(es, 'MANIFEST_FILE', str(tmp_path / 'manifest.json'))
    monkeypatch.setattr(es, '_manifest_cache', None)
    t = 'texts/en/a.b.tess'
    assert es.get_embedding_path(t, 'en').endswith('/en/a.b.npy')
    assert es.get_embedding_path(t, 'en', 'cross').endswith('/en_cross/a.b.npy')
    assert es.get_metadata_path(t, 'en', 'cross').endswith('/en_cross/a.b.meta.json')
    # Latin and Greek: one set serves both spaces.
    assert es.get_embedding_path(t, 'la', 'cross') == es.get_embedding_path(t, 'la')
    assert es.get_embedding_path(t, 'grc', 'cross') == es.get_embedding_path(t, 'grc')
    assert es.save_embeddings(t, 'en', np.ones((3, 384), dtype='float32'), ['r1', 'r2', 'r3'])
    assert not es.has_embeddings(t, 'en', 'cross')
    assert es.save_embeddings(t, 'en', np.ones((3, 768), dtype='float32'), ['r1', 'r2', 'r3'], space='cross')
    assert es.load_embeddings(t, 'en').shape == (3, 384)
    assert es.load_embeddings(t, 'en', 'cross').shape == (3, 768)
    assert es.cross_embeddings_available('en')
    manifest = es.load_manifest()
    assert t in manifest['texts'] and manifest['texts'][t]['embedding_dim'] == 384
    assert manifest['cross_texts'][t]['embedding_dim'] == 768


def test_unknown_space_is_refused():
    try:
        es.get_embedding_path('texts/en/a.tess', 'en', 'sideways')
    except ValueError:
        return
    raise AssertionError('a bad space was accepted')
