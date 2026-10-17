"""The Latin u/v and i/j fold reaches Line Search's exact-mode prefilter.

The prefilter must match wherever the phrase pattern matches (it only drops
the word-start tests), so the fold has to be in both, from one helper.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.blueprints import line_search as LS  # noqa: E402
from backend.utils import exact_phrase_pattern  # noqa: E402

MARTIAL = "Protinus ITALIAM concepit et ARMA VIRVMQVE,"
RAW = "<mart. 8.55.18>\tsome other line\n<mart. 8.55.19>\t" + MARTIAL + "\n<mart. 8.55.20>\tnec minus\n"


def test_prefilter_and_pattern_agree_on_the_latin_fold():
    assert exact_phrase_pattern("arma virum", "la").search(MARTIAL)
    assert LS._exact_prefilter_pattern("arma virum", "la").search(MARTIAL)
    assert LS._exact_candidate_lines(RAW, LS._exact_prefilter_pattern("arma virum", "la")) == [1]
    # Without the language neither matches the V spelling, so the two still agree.
    assert not exact_phrase_pattern("arma virum").search(MARTIAL)
    assert not LS._exact_prefilter_pattern("arma virum").search(MARTIAL)


def test_escaped_metacharacters_survive_the_fold():
    # re.escape never puts a backslash before a letter, so folding letters
    # cannot corrupt an escape; a query with punctuation still compiles and matches.
    p = exact_phrase_pattern("vir(um)", "la")
    assert p.search("uir(um) fortis")
    assert not p.search("virum fortis")
