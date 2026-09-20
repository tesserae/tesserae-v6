"""scripts/batch_lemma_cache.py: the fast English lemmatizer must agree with
backend/text_processor.py on verbs (2026-09-19: it lemmatized as nouns only,
so "stood" and "went" stayed as they were in every English cache)."""
import importlib.util
import os
import pathlib

import pytest

spec = importlib.util.spec_from_file_location(
    'batch_lemma_cache', pathlib.Path(__file__).resolve().parents[1] / 'scripts' / 'batch_lemma_cache.py')
blc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(blc)


def _fast():
    tp = blc.FastTextProcessor()
    if not getattr(tp, 'english_lemmatizer', None):
        pytest.skip('NLTK WordNet not available here')
    try:
        tp.english_lemmatizer.lemmatize('stood', pos='v')
    except LookupError:
        pytest.skip('WordNet data not downloaded here')
    return tp


def test_fast_english_lemmatizer_reduces_past_tenses_like_the_main_processor():
    tp = _fast()
    out = tp.english_lemmatize(['Stood', 'went', 'fled', 'began', 'Fields', 'summons', 'read'])
    assert out[:5] == ['stand', 'go', 'flee', 'begin', 'field']
    assert out[6] == 'read'


def test_fast_english_lemmatizer_matches_backend_rule_on_a_milton_line():
    from backend.text_processor import TextProcessor
    tp = _fast()
    main = TextProcessor()
    tokens = ['fled', 'over', 'adria', 'to', 'the', 'hesperian', 'fields']
    try:
        expected = main._english_lemmatize(tokens)   # loads the models first
    except Exception:
        pytest.skip('main processor lemmatizer unavailable')
    assert tp.english_lemmatize(tokens) == expected
