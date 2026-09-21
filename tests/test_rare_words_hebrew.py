"""The Rare Words Explorer had no Hebrew data at all.

`regenerate_rare_words_cache` in backend/blueprints/hapax.py had a branch for
Latin, Greek, English and Coptic and none for Hebrew, so it wrote an empty
list and the page would have shown nothing for a language the site otherwise
serves in full (39 books, its own index, its own Reader). NC asked for Hebrew
on 2026-09-21; these tests cover the branch that answers that.

They feed a small frequency cache rather than the real one, so they say what
the rule is instead of what today's corpus happens to contain.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest  # noqa: E402

from backend.blueprints import hapax  # noqa: E402
from backend.hebrew.stopwords import HEBREW_STOP_WORDS  # noqa: E402

A_STOPWORD = sorted(HEBREW_STOP_WORDS)[0]

FREQUENCIES = {
    'מהפכה': 10,      # a real rare word, at the top of the range
    'תער': 1,          # a real rare word, at the bottom
    'יהוה': 6827,      # far too common to be rare
    'ב': 4,            # one letter: a clitic, not a word
    'דבר־': 3,         # carries a maqaf, a transcription artifact
    'ABC': 2,          # not Hebrew script at all
    A_STOPWORD: 5,     # a curated function word
}


@pytest.fixture
def written(tmp_path, monkeypatch):
    """Run the regeneration against the fixture frequencies, in a temp dir."""
    # regenerate_rare_words_cache imports load_frequency_cache INSIDE the
    # function (hapax.py:1551), so the module-level name on `hapax` is not
    # the one it calls. Patch the source module instead; patching `hapax`
    # silently did nothing and every test here errored on the real cache
    # being absent.
    import backend.frequency_cache as frequency_cache
    monkeypatch.setattr(frequency_cache, 'load_frequency_cache',
                        lambda language: {'frequencies': FREQUENCIES})
    monkeypatch.setattr(hapax, 'load_frequency_cache',
                        lambda language: {'frequencies': FREQUENCIES})
    monkeypatch.setattr(hapax, 'clear_rare_words_memory_cache', lambda language: None)
    monkeypatch.chdir(tmp_path)
    assert hapax.regenerate_rare_words_cache('he') is True
    with open(tmp_path / 'cache' / 'rare_words' / 'he.json', encoding='utf-8') as fh:
        return json.load(fh)


def test_hebrew_produces_rare_words_at_all(written):
    assert written['total'] > 0
    assert {w['lemma'] for w in written['words']} == {'מהפכה', 'תער'}


def test_the_display_form_is_the_consonantal_lemma(written):
    for word in written['words']:
        assert word['display'] == word['lemma']


def test_a_common_word_is_not_rare(written):
    assert 'יהוה' not in {w['lemma'] for w in written['words']}


def test_single_letters_and_artifacts_are_dropped(written):
    lemmas = {w['lemma'] for w in written['words']}
    assert 'ב' not in lemmas          # a clitic
    assert 'דבר־' not in lemmas       # maqaf
    assert 'ABC' not in lemmas        # not Hebrew script


def test_curated_function_words_are_dropped(written):
    assert A_STOPWORD not in {w['lemma'] for w in written['words']}


def test_counts_are_carried_through(written):
    by_lemma = {w['lemma']: w['count'] for w in written['words']}
    assert by_lemma == {'מהפכה': 10, 'תער': 1}
