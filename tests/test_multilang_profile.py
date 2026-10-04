"""Persian, Urdu and Arabic searches must pick up the persian_ghazal profile,
and no other language's default may change (2026-09-05)."""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from backend.fusion import get_weight_profile, WEIGHT_PROFILES, CHANNEL_WEIGHTS  # noqa: E402

_NO_PERSIAN_GHAZAL = 'persian_ghazal' not in WEIGHT_PROFILES
_SKIP_REASON = (
    "stage 2b: backend.fusion.WEIGHT_PROFILES has no 'persian_ghazal' key on "
    "main; the Persian/Urdu/Arabic default weight profile is applied to "
    "fusion.py in stage 2b."
)


@pytest.mark.skipif(_NO_PERSIAN_GHAZAL, reason=_SKIP_REASON)
def test_fa_ur_ar_default_to_persian_ghazal():
    for lang in ('fa', 'ur', 'ar'):
        assert get_weight_profile(language=lang) == WEIGHT_PROFILES['persian_ghazal'], lang


@pytest.mark.skipif(_NO_PERSIAN_GHAZAL, reason=_SKIP_REASON)
def test_persian_ghazal_shape_and_intent():
    p = WEIGHT_PROFILES['persian_ghazal']
    assert set(p) == set(CHANNEL_WEIGHTS)
    assert p['rare_word'] < CHANNEL_WEIGHTS['rare_word']
    assert p['lemma'] > CHANNEL_WEIGHTS['lemma']
    # The default quotation weight was 0 when this profile was written; main
    # set it to 10 on 2026-09-19 (measured on prose quotations of Vergil), so
    # only the profile's own value is asserted here.
    assert p['quotation'] > 0


def test_other_language_defaults_unchanged():
    assert get_weight_profile(language='cop') == WEIGHT_PROFILES['biblical_coptic']
    assert get_weight_profile(language='he') == WEIGHT_PROFILES['biblical_hebrew']
    assert get_weight_profile(language='en') == WEIGHT_PROFILES['english']
    for lang in ('la', 'grc', None, 'xx'):
        assert get_weight_profile(language=lang) == WEIGHT_PROFILES['latin_epic'], lang
    assert WEIGHT_PROFILES['latin_epic'] == CHANNEL_WEIGHTS
