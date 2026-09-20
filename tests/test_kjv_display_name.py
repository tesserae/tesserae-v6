"""The 70 world_english_bible.* files hold the Authorized (King James) Version
of 1611, a legacy mislabel (NC, 2026-09-20). File identifiers are unchanged;
only the display name users see is fixed, in backend.utils.DISPLAY_NAMES via
format_display_name.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from backend import utils


def test_world_english_bible_displays_as_king_james_bible():
    assert utils.DISPLAY_NAMES['world_english_bible'] == 'King James Bible'
    assert utils.format_display_name('world_english_bible') == 'King James Bible'
