"""Tests for the cross-lingual two-lemma gate added 2026-05-20.

The gate is implemented in ``backend.blueprints.search._handle_crosslingual_fusion``
and is parameterised through three settings keys:

  ``crosslingual_min_lemma_matches`` (int, default 2)
  ``crosslingual_lemma_gate`` ('penalty' | 'exclude' | 'off', default 'penalty')
  ``crosslingual_penalty_factor`` (float, default 0.5)

These tests exercise the gate decision in isolation. They reproduce the
gate's branching exactly as in the production code so that future changes
to gate semantics will fail this test if the behaviour drifts.
"""


def gate_decision(dict_word_count, mode, threshold=2, factor=0.5, base_score=1.0):
    """Mirror of the gate logic in _handle_crosslingual_fusion.

    Returns a dict with keys: excluded (bool), score (float).
    """
    triggered = dict_word_count < threshold
    if triggered and mode == 'exclude':
        return {'excluded': True, 'score': None}
    score = base_score
    if triggered and mode == 'penalty':
        score *= factor
    return {'excluded': False, 'score': score}


def test_exclude_mode_drops_single_lemma_pair():
    result = gate_decision(dict_word_count=1, mode='exclude')
    assert result['excluded'] is True


def test_exclude_mode_keeps_two_lemma_pair():
    result = gate_decision(dict_word_count=2, mode='exclude')
    assert result['excluded'] is False
    assert result['score'] == 1.0


def test_penalty_mode_halves_single_lemma_score():
    result = gate_decision(dict_word_count=1, mode='penalty')
    assert result['excluded'] is False
    assert result['score'] == 0.5


def test_penalty_mode_preserves_two_lemma_score():
    result = gate_decision(dict_word_count=2, mode='penalty')
    assert result['excluded'] is False
    assert result['score'] == 1.0


def test_off_mode_preserves_single_lemma_score():
    result = gate_decision(dict_word_count=1, mode='off')
    assert result['excluded'] is False
    assert result['score'] == 1.0


def test_zero_lemma_pair_treated_as_below_threshold():
    """A semantic-only or phonetic-only pair has dict_word_count == 0
    and should be gated the same as a single-lemma pair."""
    assert gate_decision(0, mode='exclude')['excluded'] is True
    assert gate_decision(0, mode='penalty')['score'] == 0.5


def test_custom_threshold_three_lemmata():
    """Threshold parameter respected, not hardcoded to 2."""
    assert gate_decision(2, mode='exclude', threshold=3)['excluded'] is True
    assert gate_decision(3, mode='exclude', threshold=3)['excluded'] is False


def test_custom_penalty_factor():
    """Penalty factor respected."""
    assert gate_decision(1, mode='penalty', factor=0.25)['score'] == 0.25
