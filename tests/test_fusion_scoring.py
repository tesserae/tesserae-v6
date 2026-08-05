"""
Unit tests for Tesserae V6 fusion scoring math.

Tests the pure functions in backend/fusion.py that don't require
a running server, database, or loaded corpus. Covers:
  - Reference parsing (parse_ref, parse_range_ref)
  - Window unit construction (make_window_units)
  - Window filtering helpers (_matched_word_indices, _check_line_span,
    _which_line_has_matches, _trim_to_line)
  - Syntax scoring (_compute_syntax_score, _compute_structural_score)
  - Fusion scoring (fuse_results — with mock channel results)

Run:  pytest tests/test_fusion_scoring.py -v
"""

import math
import sys
import os

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


# ── Reference Parsing ──────────────────────────────────────────────────────

class TestParseRef:
    def test_standard_ref(self):
        from backend.fusion import parse_ref
        assert parse_ref("luc. 1.5") == (1, 5)

    def test_aeneid_ref(self):
        from backend.fusion import parse_ref
        assert parse_ref("verg. aen. 7.622") == (7, 622)

    def test_single_number(self):
        from backend.fusion import parse_ref
        # Only one number — can't extract book and line
        assert parse_ref("fragment 3") == (None, None)

    def test_empty_ref(self):
        from backend.fusion import parse_ref
        assert parse_ref("") == (None, None)

    def test_three_numbers(self):
        from backend.fusion import parse_ref
        # Takes last two numbers
        assert parse_ref("homer. il. 1.2.3") == (2, 3)


class TestParseRangeRef:
    def test_same_book_range(self):
        from backend.fusion import parse_range_ref
        assert parse_range_ref("luc. 1.5-luc. 1.6") == (1, 5, 6)

    def test_single_line_ref(self):
        from backend.fusion import parse_range_ref
        assert parse_range_ref("verg. aen. 7.622") == (7, 622, 622)

    def test_cross_book_range(self):
        from backend.fusion import parse_range_ref
        # Different books — falls back to start line only
        assert parse_range_ref("luc. 1.5-luc. 2.6") == (1, 5, 5)

    def test_empty_ref(self):
        from backend.fusion import parse_range_ref
        assert parse_range_ref("") == (None, None, None)


# ── Window Unit Construction ───────────────────────────────────────────────

class TestMakeWindowUnits:
    def _make_unit(self, ref, tokens, lemmas=None, text=None):
        return {
            'ref': ref,
            'text': text or ' '.join(tokens),
            'tokens': tokens,
            'lemmas': lemmas or tokens,
            'pos_tags': ['NOUN'] * len(tokens),
        }

    def test_two_lines_produce_one_window(self):
        from backend.fusion import make_window_units
        units = [
            self._make_unit("luc. 1.1", ["arma", "virum"]),
            self._make_unit("luc. 1.2", ["cano", "troiae"]),
        ]
        windows = make_window_units(units)
        assert len(windows) == 1

    def test_window_has_combined_tokens(self):
        from backend.fusion import make_window_units
        units = [
            self._make_unit("luc. 1.1", ["arma", "virum"]),
            self._make_unit("luc. 1.2", ["cano", "troiae"]),
        ]
        windows = make_window_units(units)
        assert windows[0]['tokens'] == ["arma", "virum", "cano", "troiae"]

    def test_window_has_range_ref(self):
        from backend.fusion import make_window_units
        units = [
            self._make_unit("luc. 1.1", ["arma", "virum"]),
            self._make_unit("luc. 1.2", ["cano", "troiae"]),
        ]
        windows = make_window_units(units)
        assert windows[0]['ref'] == "luc. 1.1-luc. 1.2"

    def test_window_has_line_token_counts(self):
        from backend.fusion import make_window_units
        units = [
            self._make_unit("luc. 1.1", ["arma", "virum"]),
            self._make_unit("luc. 1.2", ["cano", "troiae", "qui"]),
        ]
        windows = make_window_units(units)
        assert windows[0]['line_token_counts'] == [2, 3]

    def test_window_text_has_newline(self):
        from backend.fusion import make_window_units
        units = [
            self._make_unit("luc. 1.1", ["arma", "virum"], text="arma virum"),
            self._make_unit("luc. 1.2", ["cano", "troiae"], text="cano troiae"),
        ]
        windows = make_window_units(units)
        assert '\n' in windows[0]['text']

    def test_three_lines_produce_two_windows(self):
        from backend.fusion import make_window_units
        units = [
            self._make_unit("luc. 1.1", ["a"]),
            self._make_unit("luc. 1.2", ["b"]),
            self._make_unit("luc. 1.3", ["c"]),
        ]
        windows = make_window_units(units)
        assert len(windows) == 2

    def test_single_line_produces_no_windows(self):
        from backend.fusion import make_window_units
        units = [self._make_unit("luc. 1.1", ["arma"])]
        windows = make_window_units(units)
        assert len(windows) == 0

    def test_empty_input(self):
        from backend.fusion import make_window_units
        assert make_window_units([]) == []


# ── Window Filtering Helpers ───────────────────────────────────────────────

class TestMatchedWordIndices:
    def test_finds_word(self):
        from backend.fusion import _matched_word_indices
        assert _matched_word_indices(["arma", "virum", "cano"], "virum") == [1]

    def test_case_insensitive(self):
        from backend.fusion import _matched_word_indices
        assert _matched_word_indices(["Arma", "virum"], "arma") == [0]

    def test_multiple_occurrences(self):
        from backend.fusion import _matched_word_indices
        assert _matched_word_indices(["et", "arma", "et"], "et") == [0, 2]

    def test_empty_tokens(self):
        from backend.fusion import _matched_word_indices
        assert _matched_word_indices([], "arma") == []

    def test_empty_word(self):
        from backend.fusion import _matched_word_indices
        assert _matched_word_indices(["arma"], "") == []


class TestCheckLineSpan:
    def test_spans_boundary(self):
        from backend.fusion import _check_line_span
        # Positions on both sides of boundary at index 3
        assert _check_line_span([1, 4], 3) is True

    def test_all_before_boundary(self):
        from backend.fusion import _check_line_span
        assert _check_line_span([0, 1, 2], 3) is False

    def test_all_after_boundary(self):
        from backend.fusion import _check_line_span
        assert _check_line_span([3, 4, 5], 3) is False

    def test_empty_positions(self):
        from backend.fusion import _check_line_span
        assert _check_line_span([], 3) is False


class TestWhichLineHasMatches:
    def test_more_on_line0(self):
        from backend.fusion import _which_line_has_matches
        assert _which_line_has_matches([0, 1, 2, 5], 4) == 0

    def test_more_on_line1(self):
        from backend.fusion import _which_line_has_matches
        assert _which_line_has_matches([0, 4, 5, 6], 4) == 1

    def test_tie_favors_line0(self):
        from backend.fusion import _which_line_has_matches
        assert _which_line_has_matches([0, 1, 4, 5], 4) == 0

    def test_empty_positions(self):
        from backend.fusion import _which_line_has_matches
        assert _which_line_has_matches([], 3) == 0


class TestTrimToLine:
    def _make_side(self, tokens_line1, tokens_line2, highlights=None):
        all_tokens = tokens_line1 + tokens_line2
        return {
            'ref': 'luc. 1.1-luc. 1.2',
            'text': ' '.join(tokens_line1) + '\n' + ' '.join(tokens_line2),
            'tokens': all_tokens,
            'highlight_indices': highlights or [],
            'line_token_counts': [len(tokens_line1), len(tokens_line2)],
            'line_refs': ['luc. 1.1', 'luc. 1.2'],
        }

    def test_trim_to_line0(self):
        from backend.fusion import _trim_to_line
        side = self._make_side(["arma", "virum"], ["cano", "troiae"], [0, 1, 3])
        result = _trim_to_line(side, 0)
        assert result['tokens'] == ["arma", "virum"]
        assert result['highlight_indices'] == [0, 1]
        assert result['text'] == "arma virum"

    def test_trim_to_line1(self):
        from backend.fusion import _trim_to_line
        side = self._make_side(["arma", "virum"], ["cano", "troiae"], [0, 2, 3])
        result = _trim_to_line(side, 1)
        assert result['tokens'] == ["cano", "troiae"]
        # Highlights re-indexed: original 2→0, 3→1
        assert result['highlight_indices'] == [0, 1]

    def test_trim_removes_window_metadata(self):
        from backend.fusion import _trim_to_line
        side = self._make_side(["a", "b"], ["c", "d"])
        result = _trim_to_line(side, 0)
        assert 'line_token_counts' not in result
        assert 'line_refs' not in result

    def test_trim_keeps_range_ref(self):
        from backend.fusion import _trim_to_line
        side = self._make_side(["a", "b"], ["c", "d"])
        result = _trim_to_line(side, 0)
        # Range ref preserved for merge_line_and_window identification
        assert '-' in result['ref']


# ── Syntax Scoring ─────────────────────────────────────────────────────────

class TestComputeSyntaxScore:
    def test_identical_parses(self):
        from backend.fusion import _compute_syntax_score
        parse = {
            "lemmas": ["arma", "cano"],
            "upos": ["NOUN", "VERB"],
            "heads": [1, 0],
            "deprels": ["obj", "root"],
        }
        score = _compute_syntax_score(parse, parse)
        assert score > 0

    def test_no_shared_lemmas(self):
        from backend.fusion import _compute_syntax_score
        p1 = {"lemmas": ["arma", "cano"], "upos": ["NOUN", "VERB"],
               "heads": [1, 0], "deprels": ["obj", "root"]}
        p2 = {"lemmas": ["rex", "sum"], "upos": ["NOUN", "AUX"],
               "heads": [1, 0], "deprels": ["nsubj", "root"]}
        score = _compute_syntax_score(p1, p2)
        assert score == 0  # No shared lemmas → no syntax score

    def test_empty_parse(self):
        from backend.fusion import _compute_syntax_score
        p1 = {"lemmas": [], "upos": [], "heads": [], "deprels": []}
        p2 = {"lemmas": ["arma"], "upos": ["NOUN"], "heads": [0], "deprels": ["root"]}
        score = _compute_syntax_score(p1, p2)
        assert score == 0


class TestComputeStructuralScore:
    def test_identical_heads(self):
        from backend.fusion import _compute_structural_score
        # Must include upos (non-PUNCT) for filtering to work
        upos = ["VERB", "NOUN", "NOUN", "VERB", "NOUN", "NOUN", "VERB"]
        p1 = {"heads": [0, 1, 4, 1, 4, 4, 1],
               "deprels": ["root", "nsubj", "obj", "conj", "obj", "obl", "conj"],
               "upos": upos}
        score = _compute_structural_score(p1, p1)
        assert score > 0

    def test_different_heads(self):
        from backend.fusion import _compute_structural_score
        upos4 = ["VERB", "NOUN", "NOUN", "VERB"]
        p1 = {"heads": [0, 1, 4, 1], "deprels": ["root", "nsubj", "obj", "conj"], "upos": upos4}
        p2 = {"heads": [2, 0, 3, 2], "deprels": ["nsubj", "root", "advmod", "obj"], "upos": upos4}
        score = _compute_structural_score(p1, p2)
        assert score == 0  # Different head patterns


# ── Fusion Scoring ─────────────────────────────────────────────────────────

class TestFuseResults:
    """Test fuse_results with mock channel data (no DB or corpus needed).

    We pass language=None and pre-built channel results to test the
    scoring math in isolation. IDF lookups will fail gracefully,
    treating all words as unknown (df=0, skipped in geom mean).
    """

    def _make_result(self, source_ref, target_ref, score, src_text="", tgt_text="",
                     src_tokens=None, tgt_tokens=None, src_lemmas=None, tgt_lemmas=None,
                     src_highlights=None, tgt_highlights=None, matched_words=None):
        return {
            "source": {
                "ref": source_ref,
                "text": src_text,
                "tokens": src_tokens or [],
                "lemmas": src_lemmas or [],
                "highlight_indices": src_highlights or [],
            },
            "target": {
                "ref": target_ref,
                "text": tgt_text,
                "tokens": tgt_tokens or [],
                "lemmas": tgt_lemmas or [],
                "highlight_indices": tgt_highlights or [],
            },
            "overall_score": score,
            "matched_words": matched_words or [],
        }

    def test_single_channel_single_pair(self):
        from backend.fusion import fuse_results, CHANNEL_WEIGHTS
        channel_results = {
            "lemma": [self._make_result("luc. 1.1", "verg. aen. 1.1", 5.0)],
        }
        results = fuse_results(channel_results, language='la')
        assert len(results) == 1
        assert results[0]["source"]["ref"] == "luc. 1.1"

    def test_multi_channel_same_pair_scores_higher(self):
        from backend.fusion import fuse_results
        # Same pair found by one channel
        single = fuse_results({
            "lemma": [self._make_result("luc. 1.1", "verg. aen. 1.1", 5.0)],
        }, language='la')
        # Same pair found by two channels
        double = fuse_results({
            "lemma": [self._make_result("luc. 1.1", "verg. aen. 1.1", 5.0)],
            "exact": [self._make_result("luc. 1.1", "verg. aen. 1.1", 5.0)],
        }, language='la')
        assert double[0]["fused_score"] > single[0]["fused_score"]

    def test_results_sorted_by_score(self):
        from backend.fusion import fuse_results
        channel_results = {
            "lemma": [
                self._make_result("luc. 1.1", "verg. aen. 1.1", 2.0),
                self._make_result("luc. 1.2", "verg. aen. 1.2", 8.0),
                self._make_result("luc. 1.3", "verg. aen. 1.3", 5.0),
            ],
        }
        results = fuse_results(channel_results, language='la')
        scores = [r["fused_score"] for r in results]
        assert scores == sorted(scores, reverse=True)

    def test_channel_names_accumulated(self):
        from backend.fusion import fuse_results
        channel_results = {
            "lemma": [self._make_result("luc. 1.1", "verg. aen. 1.1", 5.0)],
            "exact": [self._make_result("luc. 1.1", "verg. aen. 1.1", 3.0)],
            "sound": [self._make_result("luc. 1.1", "verg. aen. 1.1", 2.0)],
        }
        results = fuse_results(channel_results, language='la')
        channels = results[0]["channels"]
        assert "lemma" in channels
        assert "exact" in channels
        assert "sound" in channels

    def test_empty_channel_results(self):
        from backend.fusion import fuse_results
        results = fuse_results({}, language='la')
        assert results == []

    def test_channel_weights_applied(self):
        from backend.fusion import fuse_results
        # Sound has weight 4.0, exact has weight 1.0
        # Same raw score but different weighted contributions
        sound_only = fuse_results({
            "sound": [self._make_result("luc. 1.1", "verg. aen. 1.1", 5.0)],
        }, language='la')
        exact_only = fuse_results({
            "exact": [self._make_result("luc. 1.1", "verg. aen. 1.1", 5.0)],
        }, language='la')
        assert sound_only[0]["fused_score"] > exact_only[0]["fused_score"]

    def test_max_results_limits_output(self):
        from backend.fusion import fuse_results
        channel_results = {
            "lemma": [
                self._make_result(f"luc. 1.{i}", f"verg. aen. 1.{i}", float(i))
                for i in range(100)
            ],
        }
        results = fuse_results(channel_results, language='la')
        # Default max_results in fuse_results is large, but we can verify
        # results are at least bounded and sorted
        assert len(results) <= 100
        scores = [r["fused_score"] for r in results]
        assert scores == sorted(scores, reverse=True)


# ── Weight-profile firewall (Coptic tuning must not touch Latin/Greek) ──────

class TestWeightProfileFirewall:
    """get_weight_profile is the firewall that keeps the biblical-Coptic tuning
    from affecting Latin/Greek/English searches. Verify the routing."""

    def test_coptic_gets_biblical_profile(self):
        from backend.fusion import get_weight_profile, WEIGHT_PROFILES
        assert get_weight_profile(language='cop') == WEIGHT_PROFILES['biblical_coptic']

    def test_latin_greek_english_get_latin_epic(self):
        from backend.fusion import get_weight_profile, WEIGHT_PROFILES
        for lang in ('la', 'grc', 'en'):
            assert get_weight_profile(language=lang) == WEIGHT_PROFILES['latin_epic']

    def test_none_and_unknown_default_to_latin_epic(self):
        from backend.fusion import get_weight_profile, WEIGHT_PROFILES
        assert get_weight_profile(language=None) == WEIGHT_PROFILES['latin_epic']
        assert get_weight_profile(language='zz') == WEIGHT_PROFILES['latin_epic']

    def test_explicit_profile_name_overrides_language(self):
        from backend.fusion import get_weight_profile, WEIGHT_PROFILES
        assert get_weight_profile(language='la', profile_name='biblical_coptic') \
            == WEIGHT_PROFILES['biblical_coptic']

    def test_quotation_inert_for_latin(self):
        # The quotation channel must carry zero weight under the Latin profile,
        # so it cannot alter Latin/Greek scoring.
        from backend.fusion import get_weight_profile
        assert get_weight_profile(language='la').get('quotation', 0.0) == 0.0


# ── Quotation channel + rarity-bypass (Coptic biblical-prose path) ──────────

class TestQuotationChannel:
    """The quotation channel (biblical_coptic profile) contributes its score
    while bypassing the rarity multiplier, and the non-quotation base is clamped
    at zero so the penalty can never invert."""

    def _mk(self, score):
        return {
            "source": {"ref": "shenoute.abraham.1", "text": "", "tokens": [],
                       "lemmas": [], "highlight_indices": []},
            "target": {"ref": "sahidic.psalms.1.1", "text": "", "tokens": [],
                       "lemmas": [], "highlight_indices": []},
            "overall_score": score,
            "matched_words": [],
        }

    def test_quotation_pair_scored_under_biblical_coptic(self):
        from backend.fusion import fuse_results
        results = fuse_results({
            "quotation": [self._mk(6.0)],
            "lemma": [self._mk(2.0)],
        }, language='cop')
        assert len(results) == 1
        assert "quotation" in results[0]["channels"]
        assert results[0]["fused_score"] > 0

    def test_large_quotation_contribution_does_not_produce_negative(self):
        # Even if the quotation contribution dominates the base, the clamped
        # non-quotation base keeps the fused score non-negative.
        from backend.fusion import fuse_results
        results = fuse_results({
            "quotation": [self._mk(50.0)],
        }, language='cop')
        assert len(results) == 1
        assert results[0]["fused_score"] >= 0


# ── Constants Sanity Checks ────────────────────────────────────────────────

class TestScoringConstants:
    """Verify scoring constants are within expected ranges."""

    def test_channel_weights_positive(self):
        from backend.fusion import CHANNEL_WEIGHTS
        for name, weight in CHANNEL_WEIGHTS.items():
            # The quotation channel defaults to 0.0 in CHANNEL_WEIGHTS; it is
            # enabled and weighted per-search via WEIGHT_PROFILES (biblical_coptic).
            if name == "quotation":
                assert weight >= 0, f"Channel {name} has negative weight {weight}"
                continue
            assert weight > 0, f"Channel {name} has non-positive weight {weight}"

    def test_convergence_bonus_positive(self):
        from backend.fusion import CONVERGENCE_BONUS
        assert CONVERGENCE_BONUS > 0

    def test_idf_floor_between_0_and_1(self):
        from backend.fusion import RARITY_IDF_FLOOR
        assert 0 < RARITY_IDF_FLOOR < 1

    def test_idf_threshold_reasonable(self):
        from backend.fusion import RARITY_IDF_THRESHOLD
        assert 0.5 < RARITY_IDF_THRESHOLD < 5.0

    def test_penalty_power_positive(self):
        from backend.fusion import RARITY_PENALTY_POWER
        assert RARITY_PENALTY_POWER > 0

    def test_ten_channels_defined(self):
        from backend.fusion import CHANNEL_WEIGHTS
        # 10 core channels plus the quotation channel added for biblical/Coptic
        # verbatim-run detection (default weight 0.0, enabled via WEIGHT_PROFILES).
        assert len(CHANNEL_WEIGHTS) == 11, (
            f"Expected 11 channels, found {len(CHANNEL_WEIGHTS)}: "
            f"{list(CHANNEL_WEIGHTS.keys())}"
        )

    def test_expected_channels_present(self):
        from backend.fusion import CHANNEL_WEIGHTS
        expected = {
            "edit_distance", "sound", "exact", "lemma", "dictionary",
            "semantic", "rare_word", "syntax", "syntax_structural", "lemma_min1",
            "quotation",
        }
        assert set(CHANNEL_WEIGHTS.keys()) == expected


# ── Text Pair Frequency Baseline Tests ─────────────────────────────────────

class TestTextPairFrequencyBaseline:
    """Test calculations, routing, and database queries when using text_pair frequency baseline."""

    def _make_channel_results(self, lemmas_and_dfs):
        """Helper: create mock channel results for given lemmas.

        lemmas_and_dfs: list of (lemma, source_word, target_word) tuples
        """
        matched_words = []
        for lemma, sw, tw in lemmas_and_dfs:
            matched_words.append({
                "lemma": lemma,
                "source_word": sw,
                "target_word": tw,
                "type": "lemma",
                "similarity": 1.0,
            })
        return {
            "lemma": [
                {
                    "source": {
                        "ref": "luc. 1.1",
                        "text": " ".join(l for l, _, _ in lemmas_and_dfs),
                        "tokens": [l for l, _, _ in lemmas_and_dfs],
                        "lemmas": [l for l, _, _ in lemmas_and_dfs],
                        "highlight_indices": list(range(len(lemmas_and_dfs))),
                    },
                    "target": {
                        "ref": "verg. aen. 1.1",
                        "text": " ".join(l for l, _, _ in lemmas_and_dfs),
                        "tokens": [l for l, _, _ in lemmas_and_dfs],
                        "lemmas": [l for l, _, _ in lemmas_and_dfs],
                        "highlight_indices": list(range(len(lemmas_and_dfs))),
                    },
                    "score": 1.0,
                    "overall_score": 1.0,
                    "matched_words": matched_words,
                    "match_basis": "lemma",
                }
            ]
        }

    def test_text_pair_idf_scale_not_capped(self, monkeypatch):
        """Verify _idf_scale is NOT capped at 2.0 for text_pair basis."""
        from backend.fusion import fuse_results
        import backend.fusion as fusion

        # For text_pair with N=10 (tokens): _idf_scale = log(1429)/log(10) ≈ 3.15
        # If capped at 2.0, score would be heavily penalized (rarity multiplier floor).
        mock_freqs = {'rara': 6}
        monkeypatch.setattr(fusion, '_get_text_pair_doc_freqs',
                            lambda lemmas, s, t, lang: mock_freqs)
        monkeypatch.setattr(fusion, '_get_text_pair_total_tokens', lambda s, t, lang: 10)
        monkeypatch.setattr(fusion, '_get_total_texts', lambda lang: 1429)

        channel_results = self._make_channel_results([('rara', 'rara', 'rara')])
        results_uncapped = fuse_results(channel_results, freq_basis='text_pair',
                                       source_id='src.tess', target_id='tgt.tess',
                                       language='la')

        # Compare to a standard corpus run where a tiny N=10 baseline is capped at 2.0
        # By setting freq_basis='meter' (where N=10 and cap applies):
        monkeypatch.setattr(fusion, '_get_text_meter', lambda tid: 'hexameter')
        monkeypatch.setattr(fusion, '_get_meter_total_texts', lambda m, lang: 10)
        monkeypatch.setattr(fusion, '_get_meter_doc_freqs', lambda l, m, lang: mock_freqs)
        results_capped = fuse_results(channel_results, freq_basis='meter',
                                     source_id='src.tess', target_id='tgt.tess',
                                     language='la')

        assert len(results_uncapped) == 1
        assert len(results_capped) == 1
        # The uncapped text-pair run must score significantly higher than the capped run
        # because the rarity multiplier isn't artificially compressed by the 2.0 scaling cap.
        assert results_uncapped[0]["fused_score"] > results_capped[0]["fused_score"]

    def test_text_pair_fallback_when_no_ids(self, monkeypatch):
        """Verify text_pair falls back to corpus when source_id/target_id are None."""
        from backend.fusion import fuse_results
        import backend.fusion as fusion

        mock_corpus = {'verbum': 500}
        monkeypatch.setattr(fusion, '_get_corpus_doc_freqs',
                            lambda lemmas, lang: mock_corpus)
        monkeypatch.setattr(fusion, '_get_total_texts', lambda lang: 1429)

        channel_results = self._make_channel_results([('verbum', 'verbum', 'verbum')])

        # Without source_id/target_id, it should fall back to corpus freqs
        results_fallback = fuse_results(channel_results, freq_basis='text_pair',
                                        source_id=None, target_id=None, language='la')

        # Run direct corpus for comparison
        results_corpus = fuse_results(channel_results, freq_basis='corpus',
                                      source_id=None, target_id=None, language='la')

        assert len(results_fallback) == 1
        assert len(results_corpus) == 1
        # Fallback to corpus means the scores should be identical
        assert results_fallback[0]["fused_score"] == results_corpus[0]["fused_score"]

    def test_text_pair_rare_vs_common_word_ordering(self, monkeypatch):
        """Verify that a rare word scores higher than a common word under text_pair token frequency."""
        from backend.fusion import fuse_results
        import backend.fusion as fusion

        monkeypatch.setattr(fusion, '_get_total_texts', lambda lang: 1429)
        monkeypatch.setattr(fusion, '_get_text_pair_total_tokens', lambda s, t, lang: 50000)

        # 1. Rare word
        monkeypatch.setattr(fusion, '_get_text_pair_doc_freqs',
                            lambda lemmas, s, t, lang: {'rare': 1})
        channel_results_rare = self._make_channel_results([('rare', 'rare', 'rare')])
        results_rare = fuse_results(channel_results_rare, freq_basis='text_pair',
                                    source_id='src.tess', target_id='tgt.tess',
                                    language='la')

        # 2. Common word
        monkeypatch.setattr(fusion, '_get_text_pair_doc_freqs',
                            lambda lemmas, s, t, lang: {'common': 20000})
        channel_results_common = self._make_channel_results([('common', 'common', 'common')])
        results_common = fuse_results(channel_results_common, freq_basis='text_pair',
                                      source_id='src.tess', target_id='tgt.tess',
                                      language='la')

        assert len(results_rare) == 1
        assert len(results_common) == 1
        # A rare word (tf=1) must outscore a common word (tf=20000) under local text-pair baseline
        assert results_rare[0]["fused_score"] > results_common[0]["fused_score"]

    def test_text_pair_same_text_edge_case(self, monkeypatch):
        """Verify text_pair scores self-comparisons reasonably with token frequencies."""
        from backend.fusion import fuse_results
        import backend.fusion as fusion

        mock_freqs = {'amor': 3000}
        monkeypatch.setattr(fusion, '_get_text_pair_doc_freqs',
                            lambda lemmas, s, t, lang: mock_freqs)
        # For self-comparison, N = total tokens of 1 text
        monkeypatch.setattr(fusion, '_get_text_pair_total_tokens', lambda s, t, lang: 10000 if s == t else 20000)
        monkeypatch.setattr(fusion, '_get_total_texts', lambda lang: 1429)

        channel_results = self._make_channel_results([('amor', 'amor', 'amor')])
        
        # Self-comparison (source_id == target_id, N=10000)
        results_self = fuse_results(channel_results, freq_basis='text_pair',
                                    source_id='same_text.tess',
                                    target_id='same_text.tess', language='la')

        # Cross-comparison (source_id != target_id, N=20000)
        results_cross = fuse_results(channel_results, freq_basis='text_pair',
                                     source_id='src.tess',
                                     target_id='tgt.tess', language='la')

        assert len(results_self) == 1
        assert len(results_cross) == 1
        # Self comparison shouldn't collapse to 0 anymore
        assert results_self[0]["fused_score"] > 0
        # Under token frequency, N=20000 vs N=10000 for the same word count (3000) means
        # the word is proportionally rarer in the cross-comparison (N=20000), so it scores higher.
        assert results_cross[0]["fused_score"] > results_self[0]["fused_score"]

    def test_text_pair_real_db_query(self):
        """Verify that _get_text_pair_doc_freqs successfully executes queries on a real SQLite database.

        Requires data/inverted_index/en_index.db to be present.
        """
        import os
        import pytest
        from backend.fusion import _get_text_pair_doc_freqs

        db_path = "data/inverted_index/en_index.db"
        if not os.path.exists(db_path):
            pytest.skip("en_index.db not found on disk, skipping real DB query test.")

        # Test querying actual index for a known file present in standard en_index
        text_id = "carroll.alice_in_wonderland.tess"
        from backend.inverted_index import get_connection
        conn = get_connection("en")
        if conn:
            cur = conn.cursor()
            cur.execute("SELECT 1 FROM texts WHERE filename IN (?, ?) LIMIT 1", (text_id, text_id[:-5]))
            if cur.fetchone() is None:
                pytest.skip(f"{text_id} not found in en_index.db, skipping real DB query test.")
        else:
            pytest.skip("Could not open en_index.db via get_connection, skipping real DB query test.")
        freqs = _get_text_pair_doc_freqs(
            lemmas=["alice", "rabbit", "nonexistentword12345"],
            source_id=text_id,
            target_id=text_id,
            language="en"
        )

        assert isinstance(freqs, dict)
        # 'alice' and 'rabbit' should appear in the index for Alice in Wonderland
        assert freqs.get("alice", 0) >= 1
        assert freqs.get("rabbit", 0) >= 1
        # Non-existent words should return 0 frequency
        assert freqs.get("nonexistentword12345", 0) == 0

