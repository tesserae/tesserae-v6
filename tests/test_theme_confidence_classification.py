"""Theme Search confidence: a pervasive theme in one language's own corpus
(love in Persian lyric, praise of God in Hebrew scripture) must not read as
"nothing resembles the query" just because its within-language head_lift is
weak. These exercise the classification function on fixed numbers, with no
index loaded, per the fix for the single-language false-negative (2026-10-08):
a Persian search for "passionate love" came back Rumi, Rudaki and Anvari
addressing the beloved and still reported 'low'.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.passage_index import (  # noqa: E402
    _confidence_level,
    _confidence_note,
    _confidence_note_fitted,
    _is_pervasive,
    _is_short_query,
    HEAD_WEAK,
    HEAD_STRONG,
    PERVASIVE_EXCESS_BASELINE,
)


# --- _is_pervasive ----------------------------------------------------------

def test_is_pervasive_true_when_language_baseline_well_above_global():
    assert _is_pervasive(0.80, 0.78) is True   # 0.02 >= 0.015


def test_is_pervasive_false_just_under_the_margin():
    assert _is_pervasive(0.80, 0.79) is False  # 0.01 < 0.015


def test_is_pervasive_false_at_exactly_the_margin_boundary_minus_epsilon():
    assert _is_pervasive(0.78 + PERVASIVE_EXCESS_BASELINE - 0.001, 0.78) is False


def test_is_pervasive_true_at_exactly_the_margin():
    assert _is_pervasive(0.78 + PERVASIVE_EXCESS_BASELINE, 0.78) is True


def test_is_pervasive_false_without_both_baselines():
    assert _is_pervasive(None, 0.78) is False
    assert _is_pervasive(0.80, None) is False
    assert _is_pervasive(None, None) is False


# --- _confidence_level -------------------------------------------------------

def test_weak_head_lift_alone_is_low():
    assert _confidence_level(0.05, 0.90) == 'low'


def test_weak_head_lift_with_elevated_language_baseline_is_pervasive():
    # Same head_lift/coherence as the previous case, but the language this
    # search was narrowed to already resembles the query far more than the
    # whole corpus does -- the Persian "love" case.
    assert _confidence_level(0.05, 0.90, baseline=0.80, global_baseline=0.78) == 'pervasive'


def test_weak_head_lift_with_baseline_only_slightly_elevated_stays_low():
    assert _confidence_level(0.05, 0.90, baseline=0.80, global_baseline=0.79) == 'low'


def test_moderate_head_lift_without_pervasive_signal_is_moderate():
    mid = (HEAD_WEAK + HEAD_STRONG) / 2
    assert _confidence_level(mid, 0.93) == 'moderate'


def test_moderate_head_lift_with_pervasive_signal_is_pervasive():
    mid = (HEAD_WEAK + HEAD_STRONG) / 2
    assert _confidence_level(mid, 0.93, baseline=0.80, global_baseline=0.78) == 'pervasive'


def test_strong_head_lift_is_strong_even_with_elevated_baseline():
    # A genuinely specific match stands out even in a saturated language,
    # and that should win over the pervasive reading, not be masked by it.
    assert _confidence_level(HEAD_STRONG + 0.01, 0.93,
                             baseline=0.85, global_baseline=0.78) == 'strong'


def test_degenerate_coherence_is_low_regardless_of_baseline():
    # No structure in the results at all is the absence of a match, not a
    # common one, so the pervasive signal must not override it.
    assert _confidence_level(0.05, 0.999, baseline=0.90, global_baseline=0.70) == 'low'


def test_pervasive_requires_a_single_language_search():
    # No baseline figures (a multi-language or "all languages" search)
    # falls back to the original two-outcome reading.
    assert _confidence_level(0.05, 0.90) == 'low'
    mid = (HEAD_WEAK + HEAD_STRONG) / 2
    assert _confidence_level(mid, 0.93) == 'moderate'


# --- _is_short_query ----------------------------------------------------------

def test_short_query_one_word():
    assert _is_short_query('love') is True


def test_short_query_three_words():
    assert _is_short_query('wine and love') is True


def test_short_query_over_three_words_is_not_short():
    assert _is_short_query('a lover waits at the door all night') is False


def test_short_query_handles_empty_and_none():
    assert _is_short_query('') is True
    assert _is_short_query(None) is True


# --- _confidence_note_fitted / _confidence_note ------------------------------

def test_strong_has_no_note():
    assert _confidence_note_fitted('strong') is None
    assert _confidence_note('strong', query='love') is None


def test_low_note_says_nothing_resembles():
    note = _confidence_note_fitted('low')
    assert 'does not appear to contain' in note


def test_moderate_note_is_the_existing_caution():
    note = _confidence_note_fitted('moderate')
    assert 'Moderate confidence' in note


def test_pervasive_note_names_the_language():
    note = _confidence_note_fitted('pervasive', language='fa')
    assert 'the Persian corpus' in note
    assert 'describe what happens in it' in note


def test_pervasive_note_falls_back_without_a_known_language():
    assert 'this part of the corpus' in _confidence_note_fitted('pervasive', language=None)
    assert 'this part of the corpus' in _confidence_note_fitted('pervasive', language='zz')


def test_short_query_hint_appended_to_low_note():
    note = _confidence_note('low', query='love')
    assert 'does not appear to contain' in note
    assert 'only a few words' in note


def test_short_query_hint_not_appended_to_a_full_sentence():
    note = _confidence_note('low', query='a lover waits at the beloved\'s door all night')
    assert 'only a few words' not in note


def test_short_query_hint_appended_to_pervasive_note():
    note = _confidence_note('pervasive', query='wine', language='fa')
    assert 'the Persian corpus' in note
    assert 'only a few words' in note


def test_short_query_hint_never_appended_to_strong():
    assert _confidence_note('strong', query='love') is None
