"""
Unit tests for backend/formula_filter.py.

Pure-function tests with fake bigram/lemma tables injected directly, so they
need no corpus, index, or cache files on disk.

Run:  pytest tests/test_formula_filter.py -v
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from backend.formula_filter import formula_count_for_row, apply_formula_filter


def _mw(lemma, frequency):
    return {'lemma': lemma, 'frequency': frequency}


class TestFormulaCountForRow:
    def test_bigram_present(self):
        # Two shared lemmas: the rarer two form the bigram key (sorted
        # alphabetically by make_bigram_key, so order of args doesn't matter).
        matched_words = [_mw('amor', 50), _mw('bellum', 10)]
        bigram_table = {'amor|bellum': 7}
        count, basis = formula_count_for_row(
            matched_words, 'la', bigram_table=bigram_table)
        assert (count, basis) == (7, 'bigram')

    def test_bigram_picks_two_rarest_of_three(self):
        # Three shared lemmas: 'rex' (freq 2) and 'bellum' (freq 10) are the
        # two rarest; the common 'et' (freq 9000) must NOT be part of the key.
        matched_words = [_mw('et', 9000), _mw('bellum', 10), _mw('rex', 2)]
        bigram_table = {'bellum|rex': 3, 'et|rex': 500}
        count, basis = formula_count_for_row(
            matched_words, 'la', bigram_table=bigram_table)
        assert (count, basis) == (3, 'bigram')

    def test_bigram_missing_pair_is_null(self):
        matched_words = [_mw('amor', 50), _mw('bellum', 10)]
        bigram_table = {'other|pair': 4}
        count, basis = formula_count_for_row(
            matched_words, 'la', bigram_table=bigram_table)
        assert count is None
        assert basis == 'bigram'

    def test_single_lemma_uses_word_basis(self):
        matched_words = [_mw('amor', 50)]
        lemma_table = {'amor': 42}
        count, basis = formula_count_for_row(
            matched_words, 'la', lemma_table=lemma_table)
        assert (count, basis) == (42, 'word')

    def test_single_lemma_missing_from_table_is_null(self):
        matched_words = [_mw('amor', 50)]
        lemma_table = {'other': 42}
        count, basis = formula_count_for_row(
            matched_words, 'la', lemma_table=lemma_table)
        assert count is None
        assert basis == 'word'

    def test_no_table_available_is_null(self):
        matched_words = [_mw('amor', 50), _mw('bellum', 10)]
        count, basis = formula_count_for_row(
            matched_words, 'zz', bigram_table=None)
        # 'zz' has no real index/cache on disk, and no table was injected,
        # so the real (empty) loaders apply and the result is null.
        assert count is None

    def test_empty_matched_words_is_null(self):
        assert formula_count_for_row([], 'la') == (None, None)
        assert formula_count_for_row(None, 'la') == (None, None)

    def test_matched_words_with_no_real_lemmas_is_null(self):
        # Scorer-internal markup rows (no 'lemma' key, or empty) carry nothing.
        matched_words = [{'frequency': 10}, {'lemma': '', 'frequency': 5}]
        assert formula_count_for_row(matched_words, 'la') == (None, None)

    def test_missing_frequency_defaults_so_sort_does_not_crash(self):
        matched_words = [{'lemma': 'amor'}, {'lemma': 'bellum', 'frequency': 5}]
        bigram_table = {'amor|bellum': 2}
        count, basis = formula_count_for_row(
            matched_words, 'la', bigram_table=bigram_table)
        assert (count, basis) == (2, 'bigram')


class TestApplyFormulaFilter:
    def _rows(self):
        return [
            {'id': 'a', 'formula_count': 2},
            {'id': 'b', 'formula_count': 20},
            {'id': 'c', 'formula_count': None},
            {'id': 'd', 'formula_count': 5},
        ]

    def test_no_filter_when_max_is_none(self):
        rows = self._rows()
        kept, hidden = apply_formula_filter(rows, formula_max=None, formula_only=False)
        assert kept == rows
        assert hidden == 0

    def test_hide_mode_hides_rows_above_max_keeps_unknown(self):
        rows = self._rows()
        kept, hidden = apply_formula_filter(rows, formula_max=5, formula_only=False)
        ids = [r['id'] for r in kept]
        # 'b' (20) is hidden; 'c' (unknown) is kept — can't call it a formula
        # without a count, so it is never hidden by this mode.
        assert ids == ['a', 'c', 'd']
        assert hidden == 1

    def test_only_mode_keeps_rows_at_or_above_max_excludes_unknown(self):
        rows = self._rows()
        kept, hidden = apply_formula_filter(rows, formula_max=5, formula_only=True)
        ids = [r['id'] for r in kept]
        # 'd' (== 5) and 'b' (20) qualify; 'a' (2) and 'c' (unknown) do not.
        assert ids == ['b', 'd']
        assert hidden == 2

    def test_invalid_max_is_a_no_op(self):
        rows = self._rows()
        kept, hidden = apply_formula_filter(rows, formula_max='not-a-number', formula_only=False)
        assert kept == rows
        assert hidden == 0

    def test_empty_list(self):
        kept, hidden = apply_formula_filter([], formula_max=5, formula_only=True)
        assert kept == []
        assert hidden == 0
