"""Checks on data/documents/formula_words_{la,grc}.txt (stage 2 review,
2026-10-08): one word per line (comments start with '#'), no personal
names/praenomina, the three Latin additions present, soft-penalty intent
documented in the header."""
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

PRAENOMINA_AND_SIMILAR = {
    "caius", "lucius", "marcus", "cai", "luci", "marci",
    "gaius", "gai", "publius", "publi", "titus", "titi",
    "quintus", "quinti", "sextus", "sexti", "aulus", "auli",
    "tiberius", "tiberi", "appius", "appi",
}


def _words(filename):
    path = os.path.join(ROOT, "data", "documents", filename)
    words = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if not line or line.startswith("#"):
                continue
            words.append(line)
    return words


def test_latin_list_one_word_per_line_no_blank_or_duplicate():
    words = _words("formula_words_la.txt")
    assert len(words) == len(set(words)), "duplicate words"
    assert all(" " not in w for w in words), "more than one word on a line"
    assert all(w == w.lower() for w in words), "not lowercase"


def test_latin_list_excludes_praenomina_and_filiation_names():
    words = set(_words("formula_words_la.txt"))
    overlap = words & PRAENOMINA_AND_SIMILAR
    assert not overlap, f"names leaked into the formula list: {overlap}"


def test_latin_list_includes_the_three_requested_additions():
    words = set(_words("formula_words_la.txt"))
    for w in ("solvit", "fronte", "pedes"):
        assert w in words


def test_latin_list_excludes_numerals():
    # Roman numeral letter sequences (I V X L C D M only) should never
    # appear as standalone "words" in this list.
    words = _words("formula_words_la.txt")
    numeral_chars = set("ivxlcdm")
    for w in words:
        assert not set(w) <= numeral_chars, f"looks like a numeral: {w}"


def test_greek_list_one_word_per_line_no_blank_or_duplicate():
    words = _words("formula_words_grc.txt")
    assert len(words) >= 1
    assert len(words) == len(set(words))
    assert all(" " not in w for w in words)


def test_both_files_header_mentions_soft_penalty_not_hard_stoplist():
    for filename in ("formula_words_la.txt", "formula_words_grc.txt"):
        path = os.path.join(ROOT, "data", "documents", filename)
        header = open(path, "r", encoding="utf-8").read()
        assert "soft" in header.lower()
        assert "not a hard stoplist" in header.lower() or "not finalized" in header.lower()
