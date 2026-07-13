#!/usr/bin/env python3
"""
Unit tests for core search and matching logic in backend/matcher.py.
Tests are kept fast, deterministic, and isolated without requiring a database
or loading massive corpus index files.
"""

import os
import sys
import pytest
from collections import Counter

# Ensure project root is in python path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.matcher import (
    normalize_greek,
    normalize_latin,
    transliterate_greek_to_latin,
    find_crosslingual_phonetic_matches,
    Matcher
)


# ── 1. Basic Text Normalization & Transliteration ────────────────────

def test_normalize_greek():
    # Accent/diacritic stripping and lowercasing
    assert normalize_greek("μῆνιν") == "μηνιν"
    assert normalize_greek("ἄειδε") == "αειδε"
    assert normalize_greek("Θεά") == "θεα"
    assert normalize_greek("") == ""


def test_normalize_latin():
    # Lowercasing and u/v equivalence
    assert normalize_latin("virumque") == "uirumque"
    assert normalize_latin("URBS") == "urbs"
    assert normalize_latin("VIVUS") == "uiuus"


def test_transliterate_greek_to_latin():
    # Greek character mappings to Latin phonetics
    assert transliterate_greek_to_latin("μῆνιν") == "menin"
    assert transliterate_greek_to_latin("ἄειδε") == "aeide"
    assert transliterate_greek_to_latin("θεά") == "thea"
    # Sigma replacement and passthrough of non-Greek
    assert transliterate_greek_to_latin("χῶρος") == "choros"
    assert transliterate_greek_to_latin("latin-text") == "latin-text"


# ── 2. Stoplist Building Tests ───────────────────────────────────────

@pytest.fixture
def sample_units():
    # Tiny hand-crafted units for frequency counting
    return [
        {"tokens": ["arma", "virumque", "cano"], "lemmas": ["arma", "vir", "cano"]},
        {"tokens": ["arma", "et", "bella"], "lemmas": ["arma", "et", "bellum"]},
        {"tokens": ["et", "cano", "bella"], "lemmas": ["et", "cano", "bellum"]},
    ]


def test_build_stoplist_manual(sample_units):
    m = Matcher()
    # Explicit top list size stoplist
    stoplist = m.build_stoplist_manual(sample_units, stoplist_size=2, language='la')
    # Should include base stopwords + the top 2 manually computed (et, arma)
    assert "et" in stoplist
    assert "arma" in stoplist
    # Base stops must be merged
    assert "in" in stoplist


def test_build_stoplist(sample_units):
    m = Matcher()
    # Build stoplist using Zipf elbow detection
    # Mocking corpus frequencies
    corpus_freqs = {"arma": 100, "et": 90, "cano": 10}
    stoplist = m.build_stoplist(
        sample_units, 
        sample_units, 
        stoplist_basis='corpus', 
        language='la', 
        corpus_frequencies=corpus_freqs,
        match_type='lemma'
    )
    # Should contain default Latin stops plus top frequency words
    assert "et" in stoplist
    assert "in" in stoplist


# ── 3. Exact and Lemma Matching Tests ─────────────────────────────────

def test_find_exact_matches():
    m = Matcher()
    
    # Exact matching strictly checks identical surface forms (tokens)
    source_units = [
        {"tokens": ["arma", "virumque", "cano"], "lemmas": ["arma", "vir", "cano"]}
    ]
    target_units = [
        {"tokens": ["arma", "virumque", "belli"], "lemmas": ["arma", "vir", "bellum"]}
    ]
    
    # Exact match for "arma", "virumque"
    matches, stop_words_count = m.find_matches(
        source_units,
        target_units,
        settings={"match_type": "exact", "min_matches": 2, "stoplist_size": -1}
    )
    
    assert len(matches) == 1
    assert matches[0]["source_idx"] == 0
    assert matches[0]["target_idx"] == 0
    assert set(matches[0]["matched_lemmas"]) == {"arma", "virumque"}


def test_find_lemma_matches():
    m = Matcher()
    
    # Lemma matching checks base dictionary forms
    source_units = [
        {"tokens": ["armis", "virumque"], "lemmas": ["arma", "vir"]}
    ]
    target_units = [
        {"tokens": ["armorum", "viro"], "lemmas": ["arma", "vir"]}
    ]
    
    matches, _ = m.find_matches(
        source_units,
        target_units,
        settings={"match_type": "lemma", "min_matches": 2, "stoplist_size": -1}
    )
    
    assert len(matches) == 1
    assert set(matches[0]["matched_lemmas"]) == {"arma", "vir"}


def test_find_matches_min_matches_filter():
    m = Matcher()
    
    source_units = [
        {"tokens": ["armis", "virumque"], "lemmas": ["arma", "vir"]}
    ]
    target_units = [
        {"tokens": ["armorum", "belli"], "lemmas": ["arma", "bellum"]}
    ]
    
    # Needs at least 2 matching lemmas, but only "arma" matches
    matches, _ = m.find_matches(
        source_units,
        target_units,
        settings={"match_type": "lemma", "min_matches": 2, "stoplist_size": -1}
    )
    assert len(matches) == 0


# ── 4. Synonym / Semantic Matching ───────────────────────────────────

def test_find_synonym_matches():
    m = Matcher()
    # Seed synonyms directly
    m.synonym_dict = {
        "ensis": {"gladius", "spatha"},
        "gladius": {"ensis", "spatha"}
    }
    
    source_units = [
        {"tokens": ["ensis", "arma"], "lemmas": ["ensis", "arma"]}
    ]
    target_units = [
        {"tokens": ["gladius", "arma"], "lemmas": ["gladius", "arma"]}
    ]
    
    matches, _ = m.find_matches(
        source_units,
        target_units,
        settings={"match_type": "syn", "min_matches": 2, "stoplist_size": -1}
    )
    
    assert len(matches) == 1
    assert set(matches[0]["matched_lemmas"]) == {"ensis", "arma"}


# ── 5. Sound & Edit Distance Matching ────────────────────────────────

def test_find_sound_matches():
    m = Matcher()
    
    # Sound matching computes trigram overlaps of tokens
    source_units = [
        {"tokens": ["claudere"], "lemmas": ["claudo"]}
    ]
    target_units = [
        {"tokens": ["claudite"], "lemmas": ["claudo"]}
    ]
    
    matches, _ = m.find_sound_matches(
        source_units,
        target_units,
        settings={"min_sound_score": 0.2, "sound_top_n": 5}
    )
    
    assert len(matches) > 0
    assert matches[0]["source_idx"] == 0
    assert matches[0]["target_idx"] == 0
    assert matches[0]["sound_score"] > 0


def test_find_edit_distance_matches():
    m = Matcher()
    
    # Edit distance (fuzz Levenshtein similarity) matching
    source_units = [
        {"tokens": ["liber", "arma"], "lemmas": ["liber", "arma"]}
    ]
    target_units = [
        {"tokens": ["libri", "arma"], "lemmas": ["liber", "arma"]}
    ]
    
    matches, _ = m.find_edit_distance_matches(
        source_units,
        target_units,
        settings={"min_similarity": 0.60, "max_results": 10}
    )
    
    assert len(matches) > 0
    assert matches[0]["source_idx"] == 0
    assert matches[0]["target_idx"] == 0


# ── 6. Crosslingual Phonetic Matching ───────────────────────────────

def test_find_crosslingual_phonetic_matches():
    # Source is Greek, target is Latin/transliterated
    source_units = [
        {"tokens": ["μῆνιν"], "lemmas": ["μηνιν"]}
    ]
    target_units = [
        {"tokens": ["menim"], "lemmas": ["menim"]}
    ]
    
    matches = find_crosslingual_phonetic_matches(
        source_units,
        target_units,
        source_language="grc",
        target_language="la",
        min_similarity=0.70,
        min_token_len=3
    )
    
    assert len(matches) > 0
    # Key is (src_idx, tgt_idx)
    assert (0, 0) in matches
    match_detail = matches[(0, 0)][0]
    assert match_detail["source_token"] == "menin" # transliterated
    assert match_detail["target_token"] == "menim"
    assert match_detail["source_original"] == "μῆνιν"
    assert match_detail["similarity"] > 0.70
