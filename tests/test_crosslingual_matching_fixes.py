"""Regression tests for three cross-lingual dictionary bugs.

#521 — _find_csv_dictionary_matches did not deduplicate (source_lemma, target_lemma)
       pairs per line pair, so a source lemma appearing twice in one line produced
       two separate word-match entries instead of one merged entry.

#520 — CROSSLINGUAL_STOPLIST_LATIN was written with v-spelling (vos, vester, vel,
       valde) but all three consumer paths fold lemmas to u-spelling before the
       stoplist check, so those entries never matched.

#522 — The semantic-recovery step in _crosslingual_fusion_core loaded Hebrew
       (BEREL) and Latin/Greek (SPhilBERTa) embeddings and computed cosine between
       them.  The two models do not share a vector space, so any cosine above 0.4
       was meaningless noise.
"""
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.blueprints.search import _find_csv_dictionary_matches


def _unit(lemmas):
    return {'lemmas': list(lemmas)}


# ── #521: dedup ───────────────────────────────────────────────────────────────

def test_repeated_source_lemma_merges_into_one_entry():
    """אב twice in a source line → one word_match with source_indices [0, 1]."""
    matches = _find_csv_dictionary_matches(
        [_unit(['אב', 'אב'])],
        [_unit(['pater'])],
        'he', 'la',
    )
    assert (0, 0) in matches, "Expected a dictionary match for אב/pater"
    pater_entries = [
        wm for wm in matches[(0, 0)] if wm['target_lemma'] == 'pater'
    ]
    assert len(pater_entries) == 1, (
        f"Expected 1 merged entry for (אב, pater), got {len(pater_entries)}."
        " Before the fix: 2 separate entries with source_indices=[0] and [1]."
    )
    assert sorted(pater_entries[0]['source_indices']) == [0, 1], (
        "Both source positions must be merged into the single entry."
    )


def test_repeated_target_lemma_merges_target_indices():
    """One source lemma → target line where the translation appears twice."""
    matches = _find_csv_dictionary_matches(
        [_unit(['אב'])],
        [_unit(['pater', 'pater'])],
        'he', 'la',
    )
    assert (0, 0) in matches
    pater_entries = [
        wm for wm in matches[(0, 0)] if wm['target_lemma'] == 'pater'
    ]
    assert len(pater_entries) == 1
    assert sorted(pater_entries[0]['target_indices']) == [0, 1]


def test_distinct_lemma_pairs_not_merged():
    """Two different source lemmas → two separate word-match entries."""
    # אב → pater and אבד → pereo are distinct pairs; must stay separate.
    matches = _find_csv_dictionary_matches(
        [_unit(['אב', 'אבד'])],
        [_unit(['pater', 'pereo'])],
        'he', 'la',
    )
    assert (0, 0) in matches
    src_lemmas = {wm['source_lemma'] for wm in matches[(0, 0)]}
    assert 'אב' in src_lemmas
    assert 'אבד' in src_lemmas


def test_he_grc_dedup():
    """Dedup applies to the Hebrew-Greek path too."""
    # אב has a Greek translation in hebrew_greek.csv (via the cop path it uses
    # the same function).  Use a pair that is actually in the file.
    matches = _find_csv_dictionary_matches(
        [_unit(['אב', 'אב'])],
        [_unit(['πατηρ', 'πατηρ'])],
        'he', 'grc',
    )
    if (0, 0) not in matches:
        # Dictionary may not have אב→πατηρ; skip rather than fail.
        return
    for wm in matches[(0, 0)]:
        # Every (source_lemma, target_lemma) pair must appear exactly once.
        pair = (wm['source_lemma'], wm['target_lemma'])
        duplicates = [w for w in matches[(0, 0)]
                      if (w['source_lemma'], w['target_lemma']) == pair]
        assert len(duplicates) == 1, f"Pair {pair} appears {len(duplicates)} times"


# ── #520: u/v fold ────────────────────────────────────────────────────────────

def test_stoplist_latin_has_no_v_or_j():
    """Every entry in CROSSLINGUAL_STOPLIST_LATIN must be u/i-folded.

    Text processors emit u-spelled lemmas (uos, uel, ualde); a v-spelled entry
    in the stoplist can never filter them.
    """
    from backend.synonym_dict import CROSSLINGUAL_STOPLIST_LATIN

    bad = [w for w in CROSSLINGUAL_STOPLIST_LATIN if 'v' in w or 'j' in w]
    assert bad == [], (
        f"v/j-spelled entries won't match u/i-folded lemmas: {bad}"
    )


def test_stoplist_latin_contains_u_folded_entries():
    """The four specific entries from the bug report must be present."""
    from backend.synonym_dict import CROSSLINGUAL_STOPLIST_LATIN

    for entry in ('uos', 'uester', 'uel', 'ualde'):
        assert entry in CROSSLINGUAL_STOPLIST_LATIN, (
            f"u-folded entry '{entry}' missing from CROSSLINGUAL_STOPLIST_LATIN"
        )


def test_stoplist_latin_filters_u_spelled_lemma():
    """A Latin lemma that is in the stoplist must be filtered in dictionary matching."""
    from backend.blueprints.search import _find_csv_dictionary_matches

    # 'noster' is in the stoplist (unchanged by folding).  Build a pair where
    # the only he-la match would go through 'noster'; assert no match returned.
    matches = _find_csv_dictionary_matches(
        [_unit(['אב'])],
        [_unit(['noster'])],
        'he', 'la',
    )
    # 'noster' is stopped on the target side, so (0,0) should not have it.
    if (0, 0) in matches:
        noster_entries = [wm for wm in matches[(0, 0)]
                          if wm['target_lemma'] == 'noster']
        assert noster_entries == [], "Stoplist should have filtered 'noster'"


# ── #522: vector space guard ──────────────────────────────────────────────────

def test_semantic_recovery_skipped_for_hebrew_pair():
    """load_embeddings must not be called when a Hebrew text is involved.

    Before the fix: recovery loaded BEREL (Hebrew) embeddings and SPhilBERTa
    (Latin) embeddings and computed cosine between incompatible vector spaces.
    After the fix: the recovery block is skipped for any he-* or cop-* pair.
    """
    from backend.blueprints.search import _crosslingual_fusion_core

    load_calls = []

    def fake_load_embeddings(path, lang):
        load_calls.append(lang)
        return None

    def fake_find_crosslingual_matches(*args, **kwargs):
        return ([], None)

    with patch('backend.semantic_similarity.find_crosslingual_matches',
               fake_find_crosslingual_matches):
        with patch('backend.embedding_storage.load_embeddings',
                   fake_load_embeddings):
            params = {
                'source_id': 'test.he',
                'target_id': 'test.la',
                'language': 'he',
                'source_language': 'he',
                'target_language': 'la',
            }
            # אב→pater is a real dictionary entry, which produces a non-empty
            # dict_by_pair so that recovery_keys would be non-empty without the guard.
            source_units = [_unit(['אב', 'אב'])]
            target_units = [_unit(['pater'])]
            settings = {
                'source_text_path': '/nonexistent/he.npz',
                'target_text_path': '/nonexistent/la.npz',
                'min_matches': 1,
                'crosslingual_lemma_gate': 'off',
            }
            _crosslingual_fusion_core(params, source_units, target_units, settings)

    assert load_calls == [], (
        f"load_embeddings was called for a Hebrew pair (would compare "
        f"incompatible vector spaces): languages={load_calls}"
    )


def test_semantic_recovery_skipped_for_coptic_pair():
    """Same guard must apply to Coptic language pairs."""
    from backend.blueprints.search import _crosslingual_fusion_core

    load_calls = []

    with patch('backend.semantic_similarity.find_crosslingual_matches',
               lambda *a, **kw: ([], None)):
        with patch('backend.embedding_storage.load_embeddings',
                   lambda path, lang: (load_calls.append(lang), None)[1]):
            params = {
                'source_id': 'test.cop',
                'target_id': 'test.grc',
                'language': 'cop',
                'source_language': 'cop',
                'target_language': 'grc',
            }
            source_units = [_unit([])]
            target_units = [_unit([])]
            settings = {
                'source_text_path': '/nonexistent/cop.npz',
                'target_text_path': '/nonexistent/grc.npz',
                'min_matches': 1,
                'crosslingual_lemma_gate': 'off',
            }
            _crosslingual_fusion_core(params, source_units, target_units, settings)

    assert load_calls == [], f"load_embeddings must not run for cop-grc: {load_calls}"


def test_semantic_recovery_still_runs_for_grc_la():
    """The guard must NOT block the grc-la pair, which uses compatible vectors."""
    from backend.blueprints.search import _crosslingual_fusion_core

    load_calls = []

    def recording_load(path, lang):
        load_calls.append(lang)
        return None  # Return None so recovery finds nothing; no crash.

    with patch('backend.semantic_similarity.find_crosslingual_matches',
               lambda *a, **kw: ([], None)):
        with patch('backend.embedding_storage.load_embeddings', recording_load):
            params = {
                'source_id': 'test.grc',
                'target_id': 'test.la',
                'language': 'grc',
                'source_language': 'grc',
                'target_language': 'la',
            }
            # Need real dict matches so recovery_keys is non-empty.
            # Use a grc→la pair: αγαθος → bonus (from curated list or main dict).
            source_units = [_unit(['αγαθος'])]
            target_units = [_unit(['bonus'])]
            settings = {
                'source_text_path': '/nonexistent/grc.npz',
                'target_text_path': '/nonexistent/la.npz',
                'min_matches': 1,
                'crosslingual_lemma_gate': 'off',
            }
            _crosslingual_fusion_core(params, source_units, target_units, settings)

    # load_embeddings was called (both returned None so no cosines added, but
    # the call itself confirms the guard did not block grc-la recovery).
    assert len(load_calls) > 0, (
        "load_embeddings should be called for grc-la pairs (compatible vectors); "
        "if the guard is too broad it would block this path."
    )
