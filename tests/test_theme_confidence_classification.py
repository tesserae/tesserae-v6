"""Theme Search confidence: a pervasive theme in one language's own corpus
(love in Persian lyric, praise of God in Hebrew scripture) must not read as
"nothing resembles the query" just because its within-language head_lift is
weak. These exercise the classification function on fixed numbers, with no
index loaded, per the fix for the single-language false-negative (2026-10-08):
a Persian search for "passionate love" came back Rumi, Rudaki and Anvari
addressing the beloved and still reported 'low'.

The fix that shipped promotes 'low'/'moderate' to 'pervasive' on top of the
existing, whole-corpus head_lift/coherence rule; it never recomputes
head_lift or coherence from one language's own rows. An earlier version did
recompute them and was measured, against production
(evaluation/scripts/calibrate_confidence.py), to make Latin, Greek, and
English WORSE than the unfixed rule, because one language's own windows
cluster more tightly in this embedding than the whole corpus does. These
tests pin the promote-only behaviour so that regression cannot return
silently.
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


# --- _confidence_level is unchanged by the fix: whole-corpus only ----------

def test_weak_head_lift_is_low():
    assert _confidence_level(0.05, 0.90) == 'low'


def test_moderate_head_lift_is_moderate():
    mid = (HEAD_WEAK + HEAD_STRONG) / 2
    assert _confidence_level(mid, 0.93) == 'moderate'


def test_strong_head_lift_is_strong():
    assert _confidence_level(HEAD_STRONG + 0.01, 0.93) == 'strong'


def test_degenerate_coherence_is_low():
    assert _confidence_level(0.05, 0.999) == 'low'


# --- _is_pervasive: the promote-only check ----------------------------------

def test_pervasive_true_when_language_baseline_well_above_global_and_level_low():
    assert _is_pervasive('low', 0.90, 0.80, 0.78) is True   # 0.02 >= 0.005


def test_pervasive_true_for_moderate_too():
    assert _is_pervasive('moderate', 0.93, 0.80, 0.78) is True


def test_pervasive_false_just_under_the_margin():
    assert _is_pervasive('low', 0.90, 0.78 + PERVASIVE_EXCESS_BASELINE - 0.001, 0.78) is False


def test_pervasive_true_at_exactly_the_margin():
    assert _is_pervasive('low', 0.90, 0.78 + PERVASIVE_EXCESS_BASELINE, 0.78) is True


def test_pervasive_never_promotes_strong():
    # A genuinely specific match already got the best outcome; a weaker
    # outcome must never displace it.
    assert _is_pervasive('strong', 0.90, 0.95, 0.70) is False


def test_pervasive_never_promotes_degenerate_coherence():
    # No structure in the results at all is the absence of a match, not a
    # common one, however far the baselines are apart.
    assert _is_pervasive('low', 0.999, 0.95, 0.70) is False


def test_pervasive_false_without_both_baselines():
    assert _is_pervasive('low', 0.90, None, 0.78) is False
    assert _is_pervasive('low', 0.90, 0.80, None) is False
    assert _is_pervasive('low', 0.90, None, None) is False


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


def test_short_query_hint_not_repeated_on_pervasive_note():
    # The pervasive note already asks the reader to describe what happens,
    # so the short-query hint would say the same thing twice.
    note = _confidence_note('pervasive', query='wine', language='fa')
    assert 'the Persian corpus' in note
    assert 'only a few words' not in note
    assert 'who does what' in note


def test_short_query_hint_never_appended_to_strong():
    assert _confidence_note('strong', query='love') is None


# --- end-to-end classification pattern, as find_by_text applies it --------

def _classify(head_lift, coherence, lang_baseline=None, global_baseline=None):
    """The exact two-step pattern find_by_text uses: the whole-corpus level
    first, then an independent promotion check. Lets these tests pin the
    SHAPE of the fix, not just its two halves separately."""
    level = _confidence_level(head_lift, coherence)
    if lang_baseline is not None and global_baseline is not None:
        if _is_pervasive(level, coherence, lang_baseline, global_baseline):
            level = 'pervasive'
    return level


def test_unfiltered_search_is_never_promoted():
    # No language narrowed the search, so no baselines are given: behaviour
    # is exactly the old, whole-corpus rule.
    assert _classify(0.05, 0.90) == 'low'


def test_single_language_weak_lift_with_elevated_baseline_promotes():
    assert _classify(0.05, 0.90, lang_baseline=0.80, global_baseline=0.78) == 'pervasive'


def test_single_language_weak_lift_without_elevated_baseline_stays_low():
    # Matches the measured case for Latin, Greek, and English: the
    # within-language baseline for these probe queries never rose far
    # enough above the whole corpus's for promotion, so the rule correctly
    # leaves them exactly as the unfixed rule already called them.
    assert _classify(0.05, 0.90, lang_baseline=0.78, global_baseline=0.782) == 'low'


def test_single_language_strong_lift_is_never_demoted_by_a_low_baseline():
    assert _classify(HEAD_STRONG + 0.01, 0.93, lang_baseline=0.70, global_baseline=0.78) == 'strong'
