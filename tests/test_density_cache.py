"""The Reader's gutter must not pay for the index it does not need.

NC reported the Reader's dropdowns "all frozen". The dropdowns were fine; the
server was not. /api/passages/density took 18 seconds on EVERY request, because
its cache directory sat under data/passage_index/, which is owned by
ncoffee:zodfaculty while the web user tess-flask is in tess-flask, users and
tessdev. The directory could never be created, so nothing was ever cached, and
each Reader visit recomputed a matrix multiply against the whole corpus. Three
Apache workers, CPU-bound under the GIL, and the site stops answering.

Two guards, because the bug had two halves.
"""
import os

from backend import passage_index


def test_the_cache_lives_somewhere_the_web_user_can_write():
    """Every other runtime cache on this system writes under cache/. This one
    did not, and that was the whole bug. The check is that it is under cache/,
    not that it happens to be writable by whoever runs the tests."""
    parts = os.path.normpath(passage_index._DENSITY_CACHE).split(os.sep)
    assert 'cache' in parts, passage_index._DENSITY_CACHE
    assert 'passage_index' not in parts, (
        'the density cache is back under data/passage_index/, which the web '
        'user cannot write')


def test_naming_the_cache_file_does_not_load_the_index(monkeypatch):
    """index_fingerprint names the cache file and used to call _ensure_loaded()
    for len(_ids) -- so asking WHICH index this is pulled in 1.2 GB, thirteen
    seconds on a cold worker, even when the answer was already cached."""
    called = []
    monkeypatch.setattr(passage_index, '_ensure_loaded',
                        lambda: called.append(1))
    passage_index.index_fingerprint()
    assert not called, 'index_fingerprint loaded the index'


def test_a_cached_answer_is_served_without_loading_the_index(monkeypatch, tmp_path):
    """The cache read has to come BEFORE _ensure_loaded(), or a hit costs the
    same thirteen seconds as a miss."""
    import json
    monkeypatch.setattr(passage_index, '_DENSITY_CACHE', str(tmp_path))
    path = passage_index._density_cache_path('some.work', 'fine')
    with open(path, 'w', encoding='utf-8') as fh:
        json.dump({'work': 'some.work', 'windows': [], 'peak': 0}, fh)

    called = []
    monkeypatch.setattr(passage_index, '_ensure_loaded',
                        lambda: called.append(1))
    out = passage_index.connection_density('some.work', 'fine')
    assert out['work'] == 'some.work'
    assert not called, 'a cache hit still loaded the index'


def test_the_fingerprint_changes_when_the_index_does(tmp_path, monkeypatch):
    monkeypatch.setattr(passage_index, '_DATA_DIR', str(tmp_path))
    (tmp_path / 'ids.json').write_text('[]', encoding='utf-8')
    (tmp_path / 'embeddings.npy').write_bytes(b'x')
    first = passage_index.index_fingerprint()
    (tmp_path / 'ids.json').write_text('["a", "b"]', encoding='utf-8')
    assert passage_index.index_fingerprint() != first
