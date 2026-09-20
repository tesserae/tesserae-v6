"""English (and other non-Latin) line-search queries must not be folded with
the Latin u/v and i/j rule (2026-09-20): "jove" is indexed as "jove" and
"love" as "love"; folding them to "ioue" and "loue" returned only Spenser."""
import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.app import _normalize_lemma  # noqa: E402


def test_english_lemmas_keep_v_and_j():
    assert _normalize_lemma('jove', 'en') == 'jove'
    assert _normalize_lemma('Love', 'en') == 'love'
    assert _normalize_lemma('voice', 'en') == 'voice'


def test_latin_still_folds():
    assert _normalize_lemma('jove', 'la') == 'ioue'
    assert _normalize_lemma('virum', 'la') == 'uirum'


def test_greek_strips_accents():
    assert _normalize_lemma('μῆνις', 'grc') == 'μηνισ'


def test_other_scripts_are_only_lowercased():
    assert _normalize_lemma('ⲛⲟⲩⲧⲉ', 'cop') == 'ⲛⲟⲩⲧⲉ'
    assert _normalize_lemma('אֱלֹהִים', 'he') == 'אֱלֹהִים'
