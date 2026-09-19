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


def test_density_scores_a_work_in_chunks_of_at_most_256_rows(monkeypatch, tmp_path):
    """The score block is 2.5 MB per window at the current index size: a whole
    work in one _score_block call was 5 GB for the Punica and 11.6 GB for the
    Vulgate (2026-09-19). connection_density must ask for rows a chunk at a
    time and still report every window."""
    import numpy as np
    records = [{'id': f'w{i}', 'work': 'silius_italicus.punica', 'scale': 'fine',
                'ref_start': f'1.{i}', 'ref_end': f'1.{i}'} for i in range(600)]
    records += [{'id': f'o{i}', 'work': f'other.work_{i}', 'scale': 'fine',
                 'ref_start': '1.1', 'ref_end': '1.1'} for i in range(5)]
    by_work = {}
    for i, r in enumerate(records):
        by_work.setdefault(passage_index._norm_work(r['work']), []).append(i)
    monkeypatch.setitem(passage_index._state, 'loaded', True)
    monkeypatch.setitem(passage_index._state, 'ok', True)
    monkeypatch.setitem(passage_index._state, 'error', None)
    monkeypatch.setattr(passage_index, '_records', records)
    monkeypatch.setattr(passage_index, '_by_work', by_work)
    monkeypatch.setattr(passage_index, '_ensure_loaded', lambda: None)
    monkeypatch.setattr(passage_index, '_DENSITY_CACHE', str(tmp_path))
    monkeypatch.setattr(passage_index, 'index_fingerprint', lambda: 'test')
    calls = []

    def fake_score_block(rows, chunk=32768):
        calls.append(len(rows))
        rng = np.random.default_rng(len(calls))
        return rng.random((len(records), len(rows)), dtype=np.float32)
    monkeypatch.setattr(passage_index, '_score_block', fake_score_block)

    out = passage_index.connection_density('silius_italicus.punica', scale='fine')

    assert len(out['windows']) == 600
    assert sum(calls) == 600
    assert max(calls) <= 256
    assert len(calls) >= 3
