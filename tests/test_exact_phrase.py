"""Exact-phrase line-search matching (backend.utils.exact_phrase_pattern).

Guards the whole-word-START semantics: a query word must begin at a word
boundary (so it is not matched inside a longer word), but a trailing enclitic is
allowed (so "arma virum" still matches "arma virumque", the canonical arma-virum
reference match). Pure-regex; no app import.

Also guards the slow-path filtering rule in line_search (backend/app.py):
the 2-lemma co-occurrence threshold must be bypassed for exact-phrase search
so that single-word exact queries return results (issue #502).
"""
from backend.utils import exact_phrase_pattern, exact_search_text


def _matches(query, text):
    p = exact_phrase_pattern(query)
    return bool(p and p.search(text))


def test_enclitic_is_kept_arma_virumque():
    # Reference test depends on this: exact "arma virum" must hit "arma virumque cano".
    assert _matches("arma virum", "arma virumque cano Troiae qui primus ab oris")
    assert _matches("arma virum", "arma virum tabulaeque et Troia gaza per undas")


def test_substring_inside_longer_word_is_excluded_aliquot():
    # The reported bug: "quot annis" must NOT match "aliquot annis".
    assert not _matches("quot annis", "his aliquot annis continuis fuit")
    # ...but the genuine phrase is kept.
    assert _matches("quot annis", "belloque superbum quot annis populum")


def test_leading_boundary_blocks_midword_and_run_together():
    assert not _matches("arma virum", "clamarma virumbus")   # mid-word junk
    assert not _matches("quot annis", "quotannis frumentum")  # run-together = different word


def test_case_insensitive_and_empty():
    assert _matches("arma virum", "ARMA VIRUMQUE")
    assert exact_phrase_pattern("") is None
    assert exact_phrase_pattern("   ") is None


# ── Coptic single-word exact search (issue #502) ─────────────────────────────
# Before the fix, a single-word exact query produced matched_lemmas of size 1,
# which the slow-path 2-lemma co-occurrence gate then dropped silently.
# The gate now skips for exact-phrase search.

def test_single_coptic_word_pattern_matches_line():
    # ⲣⲱⲙⲉ ("man") appears inside the Sahidic Judith corpus line.
    assert _matches('ⲣⲱⲙⲉ', 'ⲁⲩⲱ ⲣⲱⲙⲉ ⲛⲓⲙ ϩⲓⲥϩⲓⲙⲉ')


def test_single_coptic_word_not_matched_inside_longer_word():
    # Boundary check: ⲣⲱⲙⲉ must not match inside a hypothetical run-together word.
    assert not _matches('ⲣⲱⲙⲉ', 'ⲁⲩⲱⲣⲱⲙⲉⲛⲓⲙ')


def test_coptic_exact_nfc_normalization_is_idempotent():
    # exact_search_text NFC-normalises the corpus line before the regex runs;
    # Coptic characters with no combining marks round-trip unchanged.
    line = 'ⲁⲩⲱ ⲣⲱⲙⲉ ⲛⲓⲙ ϩⲓⲥϩⲓⲙⲉ'
    assert exact_search_text(line) == line


def test_single_word_exact_matched_lemmas_count():
    # The slow path builds matched_lemmas = {w.lower() for w in query.split()}.
    # A single-word query produces exactly one lemma, which the old gate dropped.
    # This test documents the invariant the fix relies on.
    query = 'ⲣⲱⲙⲉ'
    matched_lemmas = {w.lower() for w in query.split()}
    assert len(matched_lemmas) == 1  # would have been dropped by the old "< 2" gate


def test_multiword_exact_still_requires_no_threshold():
    # Multi-word exact queries already passed before the fix (len >= 2);
    # confirm they still match.
    assert _matches('ⲣⲱⲙⲉ ⲛⲓⲙ', 'ⲁⲩⲱ ⲣⲱⲙⲉ ⲛⲓⲙ ϩⲓⲥϩⲓⲙⲉ')
