"""The quotation channel, tested through the SCORER rather than around it.

WHY THIS FILE EXISTS

tests/test_fusion_scoring.py already covers the quotation channel, and it passed
throughout the eleven weeks the channel was dead in production. It builds a
match with the score already attached and hands it to fusion:

    "quotation": [self._mk(6.0)]

That proves fusion weights a quotation score correctly, which it does. It cannot
see whether anything ever PRODUCES a quotation score. Nothing did: the Coptic
work shipped in e99c778, a hand-assembled commit that carried matcher.py and
fusion.py and omitted scorer.py, so `_score_quotation_match` never reached
production. Quotation matches fell through to the generic lemma path and scored
0.0 with empty matched_words, penalised by the IDF rarity rule the channel was
built to bypass.

The lesson is not "write more tests". It is that a test which supplies the value
under test cannot detect that the value is never computed. So every test here
starts from a raw match of the shape matcher.find_quotation_matches emits and
goes through the real scorer.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DEPLOYMENT_ENV', 'dev')

from backend.scorer import Scorer  # noqa: E402


def raw_quotation_match(tokens):
    """A match exactly as matcher.find_quotation_matches emits one."""
    return {
        'source_idx': 0, 'target_idx': 0,
        'match_basis': 'quotation', 'match_type': 'quotation',
        'run_length': len(tokens), 'run_text': list(tokens),
        'source_position': 0, 'target_position': 0,
        'quotation_score': len(tokens) / 5.0,
    }


def unit(tokens):
    return {'ref': '1.1', 'text': ' '.join(tokens), 'tokens': list(tokens),
            'words': list(tokens), 'lemmas': [], 'index': 0, 'line_number': 1}


@pytest.fixture
def scorer():
    return Scorer()


def test_quotation_run_gets_a_nonzero_score(scorer):
    """The regression. Production returned 0.0 here for eleven weeks."""
    toks = ['pjoeis', 'nai', 'pe', 'panoute', 'auw', 'pasoter']
    out = scorer.score_matches([raw_quotation_match(toks)],
                               [unit(toks)], [unit(toks)], {})
    assert len(out) == 1
    assert out[0]['overall_score'] > 0, (
        'a six-token verbatim run scored zero: the scorer has no quotation '
        'branch, so the match fell through to the lemma path')


def test_matched_words_are_populated(scorer):
    """Empty matched_words is what made the 35.052 weight multiply nothing."""
    toks = ['pjoeis', 'nai', 'pe', 'panoute', 'auw', 'pasoter']
    out = scorer.score_matches([raw_quotation_match(toks)],
                               [unit(toks)], [unit(toks)], {})
    mw = out[0]['matched_words']
    assert mw, 'matched_words empty: fusion has nothing to weight'
    assert all(w['lemma'].startswith('[QUOT:') for w in mw), (
        'run tokens must carry the [QUOT:] marker, which is what keeps them '
        'out of the IDF rarity penalty')


def test_score_is_run_length_over_five_and_uncapped(scorer):
    """The formula the article documents. A 10-word run must beat a 5-word run."""
    for n, expected in ((5, 1.0), (10, 2.0)):
        toks = [f'w{i}' for i in range(n)]
        out = scorer.score_matches([raw_quotation_match(toks)],
                                   [unit(toks)], [unit(toks)], {})
        assert out[0]['overall_score'] == pytest.approx(expected), (
            f'{n}-token run scored {out[0]["overall_score"]}, expected {expected}')


def test_quotation_bypasses_idf(scorer):
    """The whole point: common words must still score.

    A run of the commonest possible words is precisely the case the rarity
    penalty suppresses, and precisely the case biblical prose quotation looks
    like.
    """
    toks = ['and', 'the', 'lord', 'said', 'to', 'him']
    out = scorer.score_matches([raw_quotation_match(toks)],
                               [unit(toks)], [unit(toks)], {})
    assert out[0]['overall_score'] == pytest.approx(1.2)
