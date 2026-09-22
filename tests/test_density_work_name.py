"""The Reader's gutter must answer for the book you are reading.

`connection_density(work)` matches the index's own work id exactly, and falls
back to the whole work only when the caller names the whole work. That
fallback is deliberate and its comment explains why it must not catch a part:
collapsing `vergil.aeneid.part.6` to `vergil.aeneid` paints book 3's and book
7's densities beside book 6's lines.

The index stores work ids without the `.tess` suffix, so a caller who passed
the corpus filename missed the exact match and got the fallback, which is the
wrong answer in the exact way that comment describes. Found on 2026-09-21
while precomputing the cache: the same text answered with 4 windows under
`cicero.philippicae.part.7` and 173 under `cicero.philippicae.part.7.tess`.

The Reader strips the suffix before it asks, so no reader saw this. Anything
else calling the endpoint did.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest  # noqa: E402

from backend import passage_index  # noqa: E402

RECORDS = [
    {'id': 'w1', 'work': 'cicero.philippicae.part.1', 'scale': 'fine',
     'ref_start': 'cic. phil. 1.1', 'ref_end': 'cic. phil. 1.3', 'language': 'la'},
    {'id': 'w2', 'work': 'cicero.philippicae.part.7', 'scale': 'fine',
     'ref_start': 'cic. phil. 7.1', 'ref_end': 'cic. phil. 7.3', 'language': 'la'},
    {'id': 'w3', 'work': 'cicero.philippicae.part.7', 'scale': 'fine',
     'ref_start': 'cic. phil. 7.4', 'ref_end': 'cic. phil. 7.6', 'language': 'la'},
]


@pytest.fixture
def index(tmp_path, monkeypatch):
    """A tiny index, and a cache directory of its own."""
    monkeypatch.setattr(passage_index, '_records', RECORDS)
    by_work = {}
    for i, r in enumerate(RECORDS):
        by_work.setdefault(passage_index._norm_work(r['work']), []).append(i)
        by_work.setdefault(r['work'], []).append(i)
    monkeypatch.setattr(passage_index, '_by_work', by_work)
    monkeypatch.setattr(passage_index, '_DENSITY_CACHE', str(tmp_path))
    monkeypatch.setitem(passage_index._state, 'loaded', True)
    monkeypatch.setitem(passage_index._state, 'ok', True)
    # The density figure needs the embeddings. Stub the scoring, so these
    # tests are about WHICH windows are answered for rather than their
    # values: _row_scores yields (row index, scores across the whole corpus)
    # for each row it is given.
    import numpy as np

    def fake_row_scores(rows, *a, **k):
        for row in rows:
            yield row, np.zeros(len(RECORDS), dtype='float32')

    monkeypatch.setattr(passage_index, '_row_scores', fake_row_scores, raising=False)
    return tmp_path


def _refs(answer):
    return [w['ref_start'] for w in answer.get('windows', [])]


def test_a_part_answers_for_its_own_lines(index):
    out = passage_index.connection_density('cicero.philippicae.part.7')
    assert _refs(out) == ['cic. phil. 7.1', 'cic. phil. 7.4']


def test_the_corpus_filename_gives_the_same_answer(index):
    """The bug: with the suffix this fell through to the whole work."""
    bare = passage_index.connection_density('cicero.philippicae.part.7')
    with_suffix = passage_index.connection_density('cicero.philippicae.part.7.tess')
    assert _refs(with_suffix) == _refs(bare)
    assert 'cic. phil. 1.1' not in _refs(with_suffix)


def test_a_language_directory_is_accepted_too(index):
    out = passage_index.connection_density('la/cicero.philippicae.part.7.tess')
    assert _refs(out) == ['cic. phil. 7.1', 'cic. phil. 7.4']


def test_naming_the_whole_work_still_answers_for_all_of_it(index):
    out = passage_index.connection_density('cicero.philippicae')
    assert 'cic. phil. 1.1' in _refs(out)
    assert 'cic. phil. 7.1' in _refs(out)


def test_both_spellings_write_one_cache_file(index):
    passage_index.connection_density('cicero.philippicae.part.7')
    passage_index.connection_density('cicero.philippicae.part.7.tess')
    files = sorted(os.listdir(index))
    assert len([f for f in files if 'part.7' in f]) == 1, files
