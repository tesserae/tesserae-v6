"""The English cross-language pairs are held back until backend/embeddings/en_cross holds files (2026-10-13)."""
import numpy as np

from backend import embedding_storage
from backend.blueprints.meta import crosslingual_held
from backend.blueprints.search import _held_reason


def _empty_embeddings_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(embedding_storage, 'EMBEDDINGS_DIR', str(tmp_path))
    return tmp_path


def test_held_while_the_cross_folder_is_empty_or_missing(tmp_path, monkeypatch):
    _empty_embeddings_dir(tmp_path, monkeypatch)
    for state in ('missing', 'empty', 'only meta'):
        if state != 'missing':
            (tmp_path / 'en_cross').mkdir(exist_ok=True)
        if state == 'only meta':
            (tmp_path / 'en_cross' / 'x.meta.json').write_text('{}')
        held = crosslingual_held()
        assert set(held) == {'la-en', 'grc-en'}
        for reason in held.values():
            assert 'English' in reason and 're-embedded' in reason
        assert _held_reason('en', 'la') == held['la-en']
        assert _held_reason('grc', 'en') == held['grc-en']
        assert _held_reason('grc', 'la') is None
        assert _held_reason('he', 'grc') is None


def test_hold_lifts_itself_when_the_cross_folder_has_a_file(tmp_path, monkeypatch):
    _empty_embeddings_dir(tmp_path, monkeypatch)
    (tmp_path / 'en_cross').mkdir()
    np.save(tmp_path / 'en_cross' / 'x.npy', np.zeros((2, 768), dtype='float32'))
    assert crosslingual_held() == {}
    assert _held_reason('la', 'en') is None
    assert _held_reason('en', 'grc') is None


def test_the_monolingual_english_folder_does_not_lift_the_hold(tmp_path, monkeypatch):
    _empty_embeddings_dir(tmp_path, monkeypatch)
    (tmp_path / 'en').mkdir()
    np.save(tmp_path / 'en' / 'x.npy', np.zeros((2, 384), dtype='float32'))
    assert set(crosslingual_held()) == {'la-en', 'grc-en'}
