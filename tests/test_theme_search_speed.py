"""Theme Search speed-ups that must not change an answer (2026-10-14).

Each of these saves time by not repeating work, and each test checks that the
saved work is the only thing that changed:
  * the reader's scores are asked for once per (query, window)
  * the query vector is fetched from the encoder once per exact text
  * the word index is asked once per match string
  * the whole-index sort is done once and handed to every ranking
  * passage texts are read by several threads and come back the same
"""
import os
import sqlite3

import numpy as np
import pytest

os.environ.setdefault('SESSION_SECRET', 'test-only-not-a-secret')

from backend import passage_index as pi  # noqa: E402
from backend import reader_client, reader_rerank, window_texts  # noqa: E402


def _result(i, score):
    return {'id': f'w{i}', 'work': 'synth.work', 'ref_start': '1.1', 'ref_end': '1.5',
            'score': score, 'gist': f'gist {i}'}


@pytest.fixture
def stub_reader(monkeypatch):
    monkeypatch.setattr(reader_rerank.window_texts, 'texts_for',
                        lambda ids: {i: f'text of {i}' for i in ids})
    monkeypatch.setattr(reader_rerank.translations, 'for_passage',
                        lambda work, refs: {'available': False})
    calls = []

    def score(query, passages, timeout=6.0):
        calls.append([p['id'] for p in passages])
        return {p['id']: (int(p['id'][1:]) * 7 % 11) / 10.0 for p in passages}
    monkeypatch.setattr(reader_client, 'score', score)
    return calls


def test_reader_scores_are_asked_for_once(stub_reader):
    first, meta1 = reader_rerank.apply('q', [_result(i, 1.0 - i / 100) for i in range(6)])
    second, meta2 = reader_rerank.apply('q', [_result(i, 1.0 - i / 100) for i in range(6)])
    assert len(stub_reader) == 1
    assert [r['id'] for r in first] == [r['id'] for r in second]
    assert [r['reader_score'] for r in first] == [r['reader_score'] for r in second]
    assert meta1['applied'] and meta2['applied']


def test_reader_is_asked_only_for_windows_it_has_not_seen(stub_reader):
    reader_rerank.apply('q', [_result(i, 1.0 - i / 100) for i in range(4)])
    out, _ = reader_rerank.apply('q', [_result(i, 1.0 - i / 100) for i in range(2, 7)])
    assert stub_reader[1] == ['w4', 'w5', 'w6']
    assert all('reader_score' in r for r in out)


def test_reader_cache_is_per_query(stub_reader):
    reader_rerank.apply('one', [_result(i, 1.0) for i in range(3)])
    reader_rerank.apply('two', [_result(i, 1.0) for i in range(3)])
    assert len(stub_reader) == 2


def test_a_failed_reader_call_is_not_cached(monkeypatch, stub_reader):
    monkeypatch.setattr(reader_client, 'score', lambda q, p, timeout=6.0: None)
    out, meta = reader_rerank.apply('q', [_result(i, 1.0 - i / 100) for i in range(3)])
    assert meta == {'applied': False}
    assert [r['id'] for r in out] == ['w0', 'w1', 'w2']
    assert not reader_rerank._SCORE_CACHE


def test_reader_cache_is_dropped_when_the_texts_file_changes(stub_reader, monkeypatch, tmp_path):
    db = tmp_path / 'window_texts.db'
    db.write_bytes(b'a')
    monkeypatch.setattr(reader_rerank.window_texts, 'DB', str(db))
    reader_rerank.apply('q', [_result(0, 1.0)])
    db.write_bytes(b'ab')
    reader_rerank.apply('q', [_result(0, 1.0)])
    assert len(stub_reader) == 2


def test_query_vector_is_fetched_once(monkeypatch):
    calls = []

    def fake(text):
        calls.append(text)
        return np.arange(4, dtype=np.float32)
    monkeypatch.setattr(pi, '_embed_query_uncached', fake)
    a = pi.embed_query('query: x')
    b = pi.embed_query('query: x')
    pi.embed_query('query: y')
    assert calls == ['query: x', 'query: y']
    assert np.array_equal(a, b)
    assert not a.flags.writeable


def test_a_failed_encoder_call_is_not_cached(monkeypatch):
    def boom(text):
        raise pi.EmbedUnavailable('down')
    monkeypatch.setattr(pi, '_embed_query_uncached', boom)
    with pytest.raises(pi.EmbedUnavailable):
        pi.embed_query('query: z')
    assert 'query: z' not in pi._QUERY_VECTORS


def test_rank_with_a_given_order_equals_rank_without(monkeypatch):
    rng = np.random.default_rng(3)
    records = [{'id': f'r{i}', 'language': 'la', 'work': f'w{i % 7}', 'scale': 'fine',
                'ref_start': f'{i}.1', 'ref_end': f'{i}.2',
                'desc': {'gist': 'x', 'themes': [], 'mode': None,
                         'names_in_text': None, 'names_unverified': []}}
               for i in range(60)]
    monkeypatch.setattr(pi, '_records', records)
    scores = rng.random(60).astype(np.float32)
    plain = pi._rank(scores, 12, per_work=2, baseline=0.0)
    given = pi._rank(scores, 12, per_work=2, baseline=0.0, order=np.argsort(-scores))
    assert plain == given


@pytest.fixture
def texts_db(tmp_path, monkeypatch):
    path = tmp_path / 'window_texts.db'
    conn = sqlite3.connect(path)
    conn.execute('CREATE TABLE window_texts (id TEXT PRIMARY KEY, text TEXT, work TEXT, language TEXT)')
    conn.executemany('INSERT INTO window_texts VALUES (?,?,?,?)',
                     [(f'id{i}', f'text {i}', 'w', 'la') for i in range(500)])
    conn.commit()
    conn.close()
    monkeypatch.setattr(window_texts, 'DB', str(path))
    window_texts._local.__dict__.pop('conn', None)
    yield
    window_texts._local.__dict__.pop('conn', None)


def test_many_texts_are_read_in_slices_and_come_back_whole(texts_db):
    ids = [f'id{i}' for i in range(0, 500, 2)] + ['missing']
    assert len(ids) >= window_texts._PARALLEL_MIN
    got = window_texts.texts_for(ids)
    assert got == {f'id{i}': f'text {i}' for i in range(0, 500, 2)}


def test_few_texts_are_read_in_the_calling_thread(texts_db):
    assert window_texts.texts_for(['id1', 'id2', 'nope']) == {'id1': 'text 1', 'id2': 'text 2'}
