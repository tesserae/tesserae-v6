"""The results-reading prompt carries the two rules added on 2 October 2026
after a live reading called arua/arva a spelling difference and called a
parallel 'shared stock' with no fact behind it."""
from backend.assistant import prompts


def test_u_v_rule_present():
    assert 'u and v are one letter' in prompts.ANALYZE_SYSTEM
    assert 'arua and arva' in prompts.ANALYZE_SYSTEM


def test_convention_claims_need_a_fact():
    assert 'a hedge is not a fact' in prompts.ANALYZE_SYSTEM
    assert '"likely", "probably" or "may"' in prompts.ANALYZE_SYSTEM
    assert '"appears" or "seems"' in prompts.ANALYZE_SYSTEM


def test_suggests_is_a_hedge_too():
    """3 October 2026: a live reading of Aeneid 1 against Punica 1 wrote
    "suggesting a targeted echo" and "supports a reading where"."""
    assert '"suggests", "suggesting"' in prompts.ANALYZE_SYSTEM
    assert '"supports a reading"' in prompts.ANALYZE_SYSTEM


def test_vergil_not_virgil():
    assert 'Vergil, never Virgil' in prompts.ANALYZE_SYSTEM
