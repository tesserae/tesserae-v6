"""The batch lemma-cache builder must normalize Greek the way the server does.

On 2026-09-10 the builder looked Greek tokens up in the lemma table with their
accents on, so every accented token missed the table and the fallback kept the
accents. The postings it wrote for the Greek Anthology could not match any
query, because the server normalizes queries (no diacritics, final sigma as
sigma) before looking them up. This pins the two normalizations together.
"""
import importlib.util
import os

import pytest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _batch_module():
    path = os.path.join(HERE, 'scripts', 'batch_lemma_cache.py')
    spec = importlib.util.spec_from_file_location('batch_lemma_cache', path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _server_normalize():
    from backend import text_processor
    for name in dir(text_processor):
        obj = getattr(text_processor, name)
        if isinstance(obj, type) and hasattr(obj, '_normalize_greek_token'):
            return obj.__new__(obj)._normalize_greek_token
    pytest.skip('server normalizer not found')


TOKENS = ['χείματος', 'ἠνεμόεντος', 'αἰθέρος', 'οἰχομένοιο', 'πορφυρέη',
          'ὥρη', 'τέμπη', 'ἀχιλλεύς', 'μῆνις', 'θεά']


def test_batch_normalization_matches_the_server():
    batch = _batch_module().FastTextProcessor.normalize_greek
    server = _server_normalize()
    for tok in TOKENS:
        # The tokenizers lower-case before either normalizer runs.
        assert batch(tok.lower()) == server(tok.lower()), tok


def test_normalization_strips_accents_and_final_sigma():
    batch = _batch_module().FastTextProcessor.normalize_greek
    assert batch('ἀχιλλεύς') == 'αχιλλευσ'
    assert batch('χείματος') == 'χειματοσ'
    assert batch('ὥρη') == 'ωρη'
