"""A passage-sized query over the documents collection searches on its rarest
words (2026-10-11): a Tacitus chapter took over four minutes against the
documents index before this cap."""
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import backend.app  # noqa: E402,F401  (the application must be built first)
from backend.blueprints import documents as A  # noqa: E402  (the helpers live here now)


def _conn(freqs):
    c = sqlite3.connect(':memory:')
    c.execute('CREATE TABLE lemma_doc_freq (lemma TEXT PRIMARY KEY, df INTEGER)')
    c.executemany('INSERT INTO lemma_doc_freq VALUES (?, ?)', list(freqs.items()))
    return c


def test_short_query_is_left_alone():
    out, reduced = A._rarest_documents_lemmas({'a', 'b', 'c'}, 'la', 12, conn=_conn({'a': 5}))
    assert out == {'a', 'b', 'c'} and reduced is None


def test_long_query_keeps_the_rarest_and_drops_unseen_first():
    freqs = {f'l{i}': i * 10 for i in range(1, 16)}      # l1 rarest ... l15 commonest
    freqs['zz'] = 0                                      # never in the documents
    lemmas = set(freqs) | {'unseen'}
    out, reduced = A._rarest_documents_lemmas(lemmas, 'la', 12, conn=_conn(freqs))
    assert reduced == 17
    assert out == {f'l{i}' for i in range(1, 13)}
    assert 'zz' not in out and 'unseen' not in out


def test_no_connection_means_no_reduction(monkeypatch):
    import backend.documents as docs
    monkeypatch.setattr(docs, 'get_connection', lambda lang: None)
    lemmas = {f'l{i}' for i in range(20)}
    out, reduced = A._rarest_documents_lemmas(lemmas, 'la', 12)
    assert out == lemmas and reduced is None
