#!/usr/bin/env python3
"""
Shared pieces of the cross-language fusion benchmarks (Greek source, Latin target).

Used by benchmark_knauer_crosslingual.py and benchmark_juhnke_crosslingual.py.
The scoring code is the Knauer script's, moved here without change so that both
benchmarks rank Greek lines by the same fused cross-language score:

    score = 1.2 * cosine + 2.0 * dictionary + 0.5 * syntax, scaled by a rarity
    multiplier, plus a convergence bonus when two channels agree.
"""

import math
import os
import re
import sys
import unicodedata
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

TEXTS_DIR = PROJECT_ROOT / "texts"
BENCHMARKS_DIR = PROJECT_ROOT / "evaluation" / "benchmarks"


def normalize_ref(ref):
    """Extract (book, line) from a reference string."""
    nums = re.findall(r'\d+', ref)
    if len(nums) >= 2:
        return (int(nums[-2]), int(nums[-1]))
    elif len(nums) == 1:
        return (0, int(nums[0]))
    return None


def ref_matches(result_ref, gold_ref, tolerance=3):
    r = normalize_ref(result_ref)
    g = normalize_ref(gold_ref)
    if r is None or g is None:
        return False
    return r[0] == g[0] and abs(r[1] - g[1]) <= tolerance


def strip_accents(s):
    nfd = unicodedata.normalize('NFD', s.lower())
    return ''.join(c for c in nfd if unicodedata.category(c) != 'Mn')


def build_dictionary_scores(grc_units, lat_units, lat_indices=None):
    """Build dictionary match sets for (grc_idx, lat_idx) pairs.

    lat_indices, when given, limits the Latin side to those unit indexes. The
    result for a pair does not depend on the other Latin units, so a restricted
    run returns exactly the entries a full run would hold for those units.
    """
    from backend.synonym_dict import (
        get_greek_latin_dict, CURATED_GREEK_LATIN,
        CROSSLINGUAL_STOPLIST_GREEK, CROSSLINGUAL_STOPLIST_LATIN
    )
    _, gl_dict_norm = get_greek_latin_dict()

    # Inverted index: latin_lemma -> set of unit_idx
    lat_index = {}
    indices = range(len(lat_units)) if lat_indices is None else lat_indices
    for idx in indices:
        unit = lat_units[idx]
        for lemma in unit.get('lemmas', []):
            ln = lemma.lower()
            if ln not in CROSSLINGUAL_STOPLIST_LATIN:
                lat_index.setdefault(ln, set()).add(idx)

    pair_matches = {}

    for grc_idx, grc_unit in enumerate(grc_units):
        for grc_lemma in set(grc_unit.get('lemmas', [])):
            grc_norm = strip_accents(grc_lemma)
            if grc_norm in CROSSLINGUAL_STOPLIST_GREEK:
                continue
            grc_lookup = grc_norm.replace('ς', 'σ')

            translations = set()
            curated = CURATED_GREEK_LATIN.get(grc_lookup, [])
            if curated:
                translations.update(w.lower().replace('v', 'u') for w in curated)
            dict_trans = gl_dict_norm.get(grc_norm, set()) or gl_dict_norm.get(grc_lookup, set()) if gl_dict_norm else set()
            if dict_trans:
                translations.update(w.lower().replace('v', 'u') for w in dict_trans)
            if not translations:
                continue

            for lat_lemma in translations:
                if lat_lemma in CROSSLINGUAL_STOPLIST_LATIN:
                    continue
                lat_units_hit = lat_index.get(lat_lemma, set())
                for lat_idx in lat_units_hit:
                    key = (grc_idx, lat_idx)
                    pair_matches.setdefault(key, set()).add((grc_norm, lat_lemma))

    return pair_matches


def make_fused_scorer(grc_path, lat_path, grc_units, lat_units, grc_emb, lat_emb,
                      lat_indices=None, verbose=True, lone_pair_rule=None,
                      cancellation=None):
    """Return fused_score(grc_idx, lat_idx) for one Greek text against one Latin text.

    grc_emb and lat_emb are the loaded embedding arrays (or None). lat_indices
    limits the dictionary channel to those Latin units (see build_dictionary_scores).
    The IDF tables and the syntax channel always use the whole of both texts.

    lone_pair_rule 'baseline' leaves the rarity multiplier as it is. 'v2' holds the
    multiplier at 1.0 for a pair with exactly one matched dictionary pair and no
    syntax (the rarity boost then cannot lift a lone pair). None reads the
    environment variable XL_RARITY_VARIANT, default 'baseline', so every existing
    caller keeps its numbers. The returned function carries the parts it scores
    from as fused_score.parts (cosine matrix, dictionary matches, syntax scores,
    the IDF function), which the live search's evaluation path reads.
    cancellation, when given, is passed to the syntax search.
    """
    if lone_pair_rule is None:
        lone_pair_rule = os.environ.get('XL_RARITY_VARIANT', 'baseline')
    if lone_pair_rule not in ('baseline', 'v2'):
        raise ValueError(f"lone_pair_rule must be 'baseline' or 'v2', not {lone_pair_rule!r}")
    grc_file = os.path.basename(str(grc_path))
    lat_file = os.path.basename(str(lat_path))

    # --- Full cosine similarity matrix ---
    if grc_emb is None or lat_emb is None:
        print("  WARNING: No embeddings found, semantic-only evaluation impossible")
        cosine_matrix = np.zeros((len(grc_units), len(lat_units)))
    else:
        grc_emb = grc_emb[:len(grc_units)]
        lat_emb = lat_emb[:len(lat_units)]
        grc_norms = np.linalg.norm(grc_emb, axis=1, keepdims=True)
        lat_norms = np.linalg.norm(lat_emb, axis=1, keepdims=True)
        grc_emb = grc_emb / (grc_norms + 1e-8)
        lat_emb = lat_emb / (lat_norms + 1e-8)
        cosine_matrix = grc_emb @ lat_emb.T  # (n_grc, n_lat)
    if verbose:
        print(f"  Cosine matrix: {cosine_matrix.shape}")

    # --- Dictionary matches ---
    dict_matches = build_dictionary_scores(grc_units, lat_units, lat_indices)
    if verbose:
        print(f"  Dictionary pairs: {len(dict_matches)}")

    # --- IDF baseline (genre-aware where possible; matches search.py + export). ---
    from backend.fusion import (
        _get_corpus_doc_freqs, _get_total_texts,
        _get_meter_doc_freqs, _get_meter_text_ids, _get_text_meter,
    )

    grc_lemmas = set()
    for unit in grc_units:
        for lemma in unit.get('lemmas', []):
            grc_lemmas.add(strip_accents(lemma))
    lat_lemmas = set()
    for unit in lat_units:
        for lemma in unit.get('lemmas', []):
            lat_lemmas.add(lemma.lower())

    grc_meter = _get_text_meter(grc_file)
    lat_meter = _get_text_meter(lat_file)
    use_genre = (grc_meter and grc_meter == lat_meter)
    if use_genre:
        gids = _get_meter_text_ids(grc_meter, 'grc')
        lids = _get_meter_text_ids(lat_meter, 'la')
        if gids and lids:
            grc_df_map = _get_meter_doc_freqs(grc_lemmas, grc_meter, 'grc')
            lat_df_map = _get_meter_doc_freqs(lat_lemmas, lat_meter, 'la')
            grc_total, lat_total = len(gids), len(lids)
        else:
            use_genre = False
    if not use_genre:
        grc_df_map = _get_corpus_doc_freqs(grc_lemmas, 'grc')
        lat_df_map = _get_corpus_doc_freqs(lat_lemmas, 'la')
        grc_total = _get_total_texts('grc')
        lat_total = _get_total_texts('la')

    def calc_idf(lemma, is_greek=False):
        if is_greek:
            key = strip_accents(lemma)
            df = grc_df_map.get(key, 0)
            total = grc_total
        else:
            key = lemma.lower()
            df = lat_df_map.get(key, 0)
            total = lat_total
        return math.log((total + 1) / (df + 1)) + 1

    # --- Syntax matches (structural fingerprint, cross-lingual) ---
    syntax_scores = {}
    try:
        from backend.fusion import find_syntax_matches
        syntax_results = find_syntax_matches(
            grc_units, lat_units, grc_file, lat_file,
            min_score=0.1, max_results=50000,
            source_language='grc', target_language='la',
            **({'cancellation': cancellation} if cancellation is not None else {}),
        )
        if isinstance(syntax_results, dict):
            grc_ref_to_idx = {u.get('ref', ''): i for i, u in enumerate(grc_units)}
            lat_ref_to_idx = {u.get('ref', ''): i for i, u in enumerate(lat_units)}
            for sub_ch, sub_results in syntax_results.items():
                if sub_results:
                    for r in sub_results:
                        src_ref = r.get('source', {}).get('ref', '')
                        tgt_ref = r.get('target', {}).get('ref', '')
                        score = r.get('score', r.get('overall_score', 0))
                        si = grc_ref_to_idx.get(src_ref)
                        ti = lat_ref_to_idx.get(tgt_ref)
                        if si is not None and ti is not None:
                            pair_key = (si, ti)
                            if score > syntax_scores.get(pair_key, 0):
                                syntax_scores[pair_key] = score
        if verbose:
            print(f"  Syntax pairs: {len(syntax_scores)}")
    except Exception as e:
        print(f"  Syntax skipped: {e}")

    # --- Scoring ---
    SEMANTIC_WEIGHT = 1.2
    DICTIONARY_WEIGHT = 2.0
    SYNTAX_WEIGHT = 0.5
    CONVERGENCE_BONUS = 0.5

    # V3-style rarity parameters (mirror backend/fusion.py + search.py + export).
    RARITY_IDF_FLOOR_X = 0.05
    RARITY_IDF_THRESHOLD_X = 1.5
    RARITY_NEAR_STOPWORD_CUTOFF_X = 0.1
    RARITY_RAMP_OFFSET_X = 0.1
    RARITY_BOOST_WEIGHT_X = 0.5
    RARITY_BOOST_CAP_X = 2.0

    def fused_score(grc_idx, lat_idx):
        cosine = float(cosine_matrix[grc_idx, lat_idx])
        has_semantic = cosine > 0.3

        wms = dict_matches.get((grc_idx, lat_idx))
        has_dict = wms is not None and len(wms) > 0
        dict_word_count = len(wms) if has_dict else 0

        syn_score = syntax_scores.get((grc_idx, lat_idx), 0.0)
        has_syntax = syn_score > 0

        dict_score = 0.0
        matched_idfs = []
        if has_dict:
            total_idf = 0.0
            for grc_l, lat_l in wms:
                pair_idf = (calc_idf(grc_l, is_greek=True) + calc_idf(lat_l, is_greek=False)) / 2
                matched_idfs.append(pair_idf)
                total_idf += pair_idf
            avg_idf = total_idf / len(wms)
            dict_score = min(avg_idf / 10.0, 1.0) * math.sqrt(dict_word_count)

        n_channels = (1 if has_semantic else 0) + (1 if has_dict else 0) + (1 if has_syntax else 0)

        rarity_mult = 1.0
        geom_mean_idf = 1.0
        if matched_idfs:
            log_sum = sum(math.log(max(v, 1e-3)) for v in matched_idfs)
            geom_mean_idf = math.exp(log_sum / len(matched_idfs))
            if geom_mean_idf < RARITY_NEAR_STOPWORD_CUTOFF_X:
                rarity_mult = RARITY_IDF_FLOOR_X
            elif geom_mean_idf < RARITY_IDF_THRESHOLD_X:
                t = ((geom_mean_idf - RARITY_NEAR_STOPWORD_CUTOFF_X)
                     / (RARITY_IDF_THRESHOLD_X - RARITY_NEAR_STOPWORD_CUTOFF_X))
                ramp_start = RARITY_IDF_FLOOR_X + RARITY_RAMP_OFFSET_X
                rarity_mult = ramp_start + t * (1.0 - ramp_start)
            else:
                channel_factor = max(0.0, min(1.0, (n_channels - 1) / 5.0))
                boost = (RARITY_BOOST_WEIGHT_X * channel_factor
                         * math.log(geom_mean_idf / RARITY_IDF_THRESHOLD_X))
                rarity_mult = min(RARITY_BOOST_CAP_X, 1.0 + boost)

        # A lone dictionary pair without syntax cannot be lifted by the rarity boost.
        if (lone_pair_rule == 'v2' and has_dict and dict_word_count == 1
                and not has_syntax and rarity_mult > 1.0):
            rarity_mult = 1.0

        base = (cosine * SEMANTIC_WEIGHT) + (dict_score * DICTIONARY_WEIGHT) + (syn_score * SYNTAX_WEIGHT)
        score = base * (rarity_mult ** 2)

        if n_channels >= 2 and matched_idfs:
            idf_weight = min(1.0, geom_mean_idf) ** 2
            score += CONVERGENCE_BONUS * idf_weight
        elif n_channels >= 2:
            score += CONVERGENCE_BONUS

        return score

    fused_score.parts = {
        'cosine_matrix': cosine_matrix,
        'dict_matches': dict_matches,
        'syntax_scores': syntax_scores,
        'calc_idf': calc_idf,
    }
    return fused_score, len(syntax_scores)
