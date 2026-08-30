"""Hebrew channel enablement and default profile (2026-08-30).

Production Hebrew fusion ran only four lexical channels because 'he' was
missing from CHANNEL_LANGUAGE_SUPPORT; the semantic/sound/edit_distance/
quotation enablement lived unmerged on a dev branch. These tests pin the
enablement and the biblical_hebrew default so it cannot silently regress.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.fusion import (CHANNEL_LANGUAGE_SUPPORT, WEIGHT_PROFILES,
                            get_channels_for_language, get_weight_profile)


def test_hebrew_has_the_measured_channels():
    chans = set(get_channels_for_language('he'))
    assert {'lemma', 'exact', 'rare_word', 'lemma_min1',
            'semantic', 'sound', 'edit_distance', 'quotation'} <= chans
    assert 'dictionary' not in chans  # no Hebrew synonym CSV; monolingual he stays without it
    assert 'syntax' not in chans      # no syntax_hebrew.db


def test_hebrew_defaults_to_biblical_profile():
    assert get_weight_profile(language='he') == WEIGHT_PROFILES['biblical_hebrew']
    # The quotation channel must be live in it (weight 0 would silently
    # disable the channel that carries verbatim reuse).
    assert get_weight_profile(language='he')['quotation'] > 0


def test_classical_defaults_untouched():
    assert get_weight_profile(language='la') == WEIGHT_PROFILES['latin_epic']
    assert get_weight_profile(language='grc') == WEIGHT_PROFILES['latin_epic']
    assert 'he' not in CHANNEL_LANGUAGE_SUPPORT['syntax']


def test_explicit_profile_name_still_wins():
    assert get_weight_profile(language='he', profile_name='latin_epic') == \
        WEIGHT_PROFILES['latin_epic']
