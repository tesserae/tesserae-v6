"""One rule for Latin u/v and i/j.

Five functions used to answer this question, three of them called
`normalize_latin`, and they disagreed: the matcher folded v to u and ignored
i and j, the distance filter folded both but kept case, the wildcard search
also folded the archaic word-final -om, and the lemma-table builder folded
and lowercased. Two words could therefore be equivalent in one part of a
search and different in another, with nothing erroring.

These tests pin the rule, and in particular pin the reason there are two of
them: the stored data.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest  # noqa: E402

from backend.latin_orthography import fold_latin, fold_latin_surface  # noqa: E402


class TestTheLemmaRule:
    def test_folds_v_and_j_and_lowercases(self):
        assert fold_latin('Virum') == 'uirum'
        assert fold_latin('JAM') == 'iam'
        assert fold_latin('ceruos') == 'ceruos'

    def test_is_idempotent(self):
        for word in ('Virum', 'iam', 'diuom', 'QVOM'):
            assert fold_latin(fold_latin(word)) == fold_latin(word)

    def test_leaves_the_archaic_ending_alone(self):
        """The tables hold "diuom" itself, so a query must keep it."""
        assert fold_latin('divom') == 'diuom'
        assert fold_latin('aequom') == 'aequom'

    def test_handles_nothing_gracefully(self):
        assert fold_latin('') == ''
        assert fold_latin(None) is None


class TestTheSurfaceRule:
    def test_keeps_case(self):
        assert fold_latin_surface('Virum') == 'Uirum'
        assert fold_latin_surface('JAM') == 'IAM'

    def test_folds_the_archaic_ending(self):
        assert fold_latin_surface('divom') == 'diuum'
        assert fold_latin_surface('Divom') == 'Diuum'
        assert fold_latin_surface('DIVOM') == 'DIUUM'

    def test_only_at_a_word_end(self):
        assert fold_latin_surface('omnia') == 'omnia'
        assert fold_latin_surface('comes') == 'comes'

    def test_the_ending_can_be_switched_off(self):
        assert fold_latin_surface('divom', archaic_om=False) == 'diuom'


class TestEveryCallerAgrees:
    def test_the_three_search_modules_share_one_function(self):
        from backend import distance_filter, matcher, wildcard_search
        assert matcher.normalize_latin is fold_latin
        assert distance_filter.normalize_latin is fold_latin
        # the wildcard search searches printed text, so it has the other rule
        assert wildcard_search.normalize_latin is fold_latin_surface

    def test_the_app_uses_the_lemma_rule(self):
        from backend import app
        assert app._normalize_latin_lemma is fold_latin

    @pytest.mark.parametrize('word', ['Virum', 'jam', 'IAM', 'seruom', 'divom'])
    def test_matcher_and_distance_filter_never_disagree(self, word):
        from backend import distance_filter, matcher
        assert matcher.normalize_latin(word) == distance_filter.normalize_latin(word)


TABLE = '/var/www/tesseraev6_flask/data/lemma_tables/latin_lemmas.json'


@pytest.mark.skipif(not os.path.exists(TABLE), reason='needs the production lemma table')
class TestTheRuleMatchesTheStoredData:
    """The rule is not a preference. It is what the data already is."""

    @staticmethod
    def _table():
        with open(TABLE, encoding='utf-8') as fh:
            return json.load(fh)

    def test_every_table_key_is_already_in_the_folded_form(self):
        """111,739 keys, one exception, and the exception is dead weight."""
        table = self._table()
        unfolded = [k for k in table if fold_latin(k) != k]
        assert unfolded == ['jampridem']
        # It can never be reached: a query is folded before the lookup, and
        # the folded form is in the table anyway, with the same lemma. It is
        # a stray from the table build, recorded rather than silently fixed.
        assert table['jampridem'] == table['iampridem']

    def test_the_surface_rule_would_return_the_WRONG_lemma(self):
        """Not a miss: a different word.

        The September 2026 review proposed one rule for everything, including
        the archaic -om ending. In the table "diuom" is a form of deus, the
        god, while "diuum" is a form of diuus, the divine one. Folding the
        ending before a lookup silently turns one into the other.
        """
        table = self._table()
        assert table['diuom'] == 'deus'
        assert table['diuum'] == 'diuus'
        assert table[fold_latin_surface('diuom')] != table['diuom']

    def test_the_other_archaic_keys_are_harmless_either_way(self):
        table = self._table()
        for archaic, classical in (('aequom', 'aequum'), ('nouom', 'nouum')):
            assert table[archaic] == table[classical]


class TestWhatTheOldRulesGotWrong:
    """The two behaviour changes, each with the case that shows them.

    Measured on the production corpus on 2026-09-21, not argued from
    principle.
    """

    def test_a_function_word_spelled_with_j_is_now_recognised(self):
        """The matcher folded v to u and left j alone, so a stoplist holding
        "iam" did not recognise a text's "jam". The Latin corpus writes it
        that way 1,691 times, and 1,705 function-word occurrences in all were
        escaping the stoplist and being treated as matchable content."""
        from backend import matcher
        assert matcher.normalize_latin('jam') == matcher.normalize_latin('iam')
        assert matcher.normalize_latin('Jam') == 'iam'

    def test_a_capitalised_first_word_now_matches_its_lemma(self):
        """The distance filter kept case, so the opening word of a line, which
        is capitalised in most editions, never equalled the lowercase matched
        word the index had returned. Two matched words in a line were found as
        one, and the distance between them was measured from the wrong place."""
        from backend.distance_filter import calculate_match_distance
        line = 'Arma virumque cano Troiae qui primus ab oris'
        assert calculate_match_distance(line, ['arma', 'oris'], 'la') == 7

    def test_both_halves_of_a_v_u_pair_still_agree(self):
        from backend import distance_filter, matcher
        for a, b in (('virum', 'uirum'), ('Virum', 'uirum'), ('jam', 'iam')):
            assert matcher.normalize_latin(a) == matcher.normalize_latin(b)
            assert distance_filter.normalize_latin(a) == distance_filter.normalize_latin(b)
