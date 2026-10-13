"""The English cross-language pairs are held back with a reason (2026-10-13)."""
from backend.blueprints.meta import CROSSLINGUAL_HELD
from backend.blueprints.search import _held_reason


def test_held_pairs_are_the_two_english_ones_with_a_reason():
    assert set(CROSSLINGUAL_HELD) == {'la-en', 'grc-en'}
    for reason in CROSSLINGUAL_HELD.values():
        assert 'English' in reason and 're-embedded' in reason


def test_held_reason_reads_both_directions_and_leaves_open_pairs_alone():
    assert _held_reason('la', 'en') == CROSSLINGUAL_HELD['la-en']
    assert _held_reason('en', 'la') == CROSSLINGUAL_HELD['la-en']
    assert _held_reason('grc', 'la') is None
    assert _held_reason('he', 'grc') is None
