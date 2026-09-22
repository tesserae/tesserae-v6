"""What the scorer promises, as tests.

backend/scorer.py decides how good a parallel is, and it is the heart of the
product: every ranked list the site shows is this file's opinion. The
September 2026 code review found it had no tests. The fusion layer above it
had some, and they hand it a match with the score already attached, which is
how a whole channel's scoring could be missing from production for eleven
weeks without a test noticing.

These pin the rules a classicist would state in words, using made-up lines
rather than the corpus, so they say what the scorer MEANS rather than what
today's numbers happen to be:

  a rarer shared word is worth more than a common one
  words close together are worth more than the same words far apart
  more shared words are worth more than fewer
  a score never leaves 0 to 1
  the words that earned the score are reported with it

They are deliberately about ORDER, not about absolute values, so tuning the
weights does not break them but reversing a rule does.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest  # noqa: E402

from backend.scorer import Scorer  # noqa: E402


def unit(ref, tokens, lemmas=None):
    """A line as the scorer receives it."""
    return {
        'ref': ref,
        'text': ' '.join(tokens),
        'tokens': tokens,
        'lemmas': lemmas if lemmas is not None else [t.lower() for t in tokens],
    }


def score_one(source, target, matched, settings=None, corpus=None):
    """Score a single lemma match between two lines, return the result."""
    scorer = Scorer()
    if corpus is not None:
        scorer.build_corpus_frequencies(corpus)
        settings = dict(settings or {}, frequency_source='corpus')
    match = {'source_idx': 0, 'target_idx': 0, 'matched_lemmas': list(matched),
             'match_basis': 'lemma'}
    results = scorer.score_matches([match], [source], [target], settings or {})
    assert len(results) == 1
    return results[0]


class TestRarity:
    def test_a_rare_shared_word_beats_a_common_one(self):
        """The whole idea of the ranking: two texts sharing "hapax" tell you
        more than two texts sharing "and"."""
        # a corpus where 'communis' is everywhere and 'rarus' is not
        common_filler = [unit(f'c.{i}', ['communis', 'alius', 'quidam']) for i in range(40)]
        corpus = [common_filler, [unit('r.1', ['rarus', 'alius', 'quidam'])]]

        src = unit('a.1', ['communis', 'alius'])
        tgt = unit('b.1', ['communis', 'alius'])
        common_score = score_one(src, tgt, ['communis', 'alius'], corpus=corpus)['score']

        src2 = unit('a.2', ['rarus', 'alius'])
        tgt2 = unit('b.2', ['rarus', 'alius'])
        rare_score = score_one(src2, tgt2, ['rarus', 'alius'], corpus=corpus)['score']

        assert rare_score > common_score


class TestDistance:
    def test_words_close_together_beat_the_same_words_far_apart(self):
        """Two shared words in one clause are a parallel. The same two words
        twenty words apart are usually a coincidence."""
        near_src = unit('a.1', ['arma', 'uirum', 'cano'])
        near_tgt = unit('b.1', ['arma', 'uirum', 'refero'])
        near = score_one(near_src, near_tgt, ['arma', 'uirum'])['score']

        filler = ['quidam'] * 18
        far_src = unit('a.2', ['arma'] + filler + ['uirum'])
        far_tgt = unit('b.2', ['arma'] + filler + ['uirum'])
        far = score_one(far_src, far_tgt, ['arma', 'uirum'])['score']

        assert near > far

    def test_the_span_is_measured_between_the_matched_words(self):
        scorer = Scorer()
        line = unit('a.1', ['alpha', 'beta', 'gamma', 'delta'])
        assert scorer._calculate_distance(line, {'alpha', 'delta'}, {}) == 3
        assert scorer._calculate_distance(line, {'beta', 'gamma'}, {}) == 1

    def test_a_single_matched_word_has_no_span(self):
        """One word cannot be near or far from itself, so the distance is the
        floor rather than zero, which would divide by the logarithm of one."""
        scorer = Scorer()
        line = unit('a.1', ['alpha', 'beta'])
        assert scorer._calculate_distance(line, {'alpha'}, {}) == 1


class TestHowManyWordsAreShared:
    def test_three_shared_words_beat_two(self):
        src = unit('a.1', ['arma', 'uirum', 'cano', 'troia'])
        tgt = unit('b.1', ['arma', 'uirum', 'cano', 'roma'])
        two = score_one(src, tgt, ['arma', 'uirum'])['score']
        three = score_one(src, tgt, ['arma', 'uirum', 'cano'])['score']
        assert three > two


class TestTheScoreStaysInRange:
    @pytest.mark.parametrize('tokens', [
        ['arma'], ['arma', 'uirum'], ['arma', 'uirum', 'cano', 'troia', 'oris'],
    ])
    def test_never_below_zero_or_above_one(self, tokens):
        src = unit('a.1', tokens)
        tgt = unit('b.1', tokens)
        result = score_one(src, tgt, tokens)
        assert 0.0 <= result['score'] <= 1.0


class TestTheEvidenceComesWithTheScore:
    def test_the_matched_words_are_reported(self):
        """A ranked list a scholar cannot check is not evidence. Every result
        carries the words it was scored on."""
        src = unit('a.1', ['arma', 'uirum', 'cano'])
        tgt = unit('b.1', ['arma', 'uirum', 'refero'])
        result = score_one(src, tgt, ['arma', 'uirum'])
        words = {w['word'] if isinstance(w, dict) and 'word' in w else w.get('lemma')
                 for w in result['matched_words']}
        assert {'arma', 'uirum'} <= words

    def test_each_matched_word_carries_its_rarity(self):
        src = unit('a.1', ['arma', 'uirum'])
        tgt = unit('b.1', ['arma', 'uirum'])
        result = score_one(src, tgt, ['arma', 'uirum'])
        for word in result['matched_words']:
            assert 'idf' in word, word
            assert word['idf'] > 0

    def test_both_sides_come_back_with_their_references(self):
        src = unit('verg. aen. 1.1', ['arma', 'uirum'])
        tgt = unit('luc. 1.1', ['arma', 'uirum'])
        result = score_one(src, tgt, ['arma', 'uirum'])
        assert result['source']['ref'] == 'verg. aen. 1.1'
        assert result['target']['ref'] == 'luc. 1.1'


class TestCountingTheCorpus:
    def test_frequencies_add_up_across_texts(self):
        scorer = Scorer()
        freqs = scorer.build_corpus_frequencies([
            [unit('a.1', ['arma', 'uirum']), unit('a.2', ['arma'])],
            [unit('b.1', ['arma', 'cano'])],
        ])
        assert freqs['arma'] == 3
        assert freqs['uirum'] == 1
        assert freqs['cano'] == 1

    def test_one_text_is_counted_on_its_own(self):
        scorer = Scorer()
        freqs = scorer.get_text_frequencies([unit('a.1', ['arma', 'arma', 'uirum'])])
        assert freqs['arma'] == 2
        assert freqs['uirum'] == 1
