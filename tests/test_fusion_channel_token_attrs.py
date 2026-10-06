"""Tests for per-channel token attribution in fusion results (#237).

fuse_results() now emits `channel_token_attrs` on every result: a dict keyed
by channel name, each value holding the sorted source and target token-position
lists that channel matched.  This lets a display layer use distinct rendering
(bold for lemma, italic for sound, etc.) without re-running the search.

Run:  pytest tests/test_fusion_channel_token_attrs.py -v
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


def _result(source_ref, target_ref, score,
            src_highlights=None, tgt_highlights=None, matched_words=None):
    return {
        "source": {
            "ref": source_ref,
            "text": "",
            "tokens": [],
            "lemmas": [],
            "highlight_indices": src_highlights or [],
        },
        "target": {
            "ref": target_ref,
            "text": "",
            "tokens": [],
            "lemmas": [],
            "highlight_indices": tgt_highlights or [],
        },
        "overall_score": score,
        "matched_words": matched_words or [],
    }


class TestChannelTokenAttrs:
    def test_field_present_on_every_result(self):
        """Every fuse_results entry carries channel_token_attrs."""
        from backend.fusion import fuse_results
        results = fuse_results({
            "lemma": [_result("luc. 1.1", "verg. aen. 1.1", 5.0,
                              src_highlights=[2, 5], tgt_highlights=[1, 4])],
        }, language='la')
        assert len(results) == 1
        assert "channel_token_attrs" in results[0]

    def test_single_channel_positions_preserved(self):
        """Token positions from a single channel are faithfully recorded."""
        from backend.fusion import fuse_results
        results = fuse_results({
            "lemma": [_result("luc. 1.1", "verg. aen. 1.1", 5.0,
                              src_highlights=[0, 3, 7], tgt_highlights=[2, 6])],
        }, language='la')
        attrs = results[0]["channel_token_attrs"]
        assert "lemma" in attrs
        assert attrs["lemma"]["source"] == [0, 3, 7]
        assert attrs["lemma"]["target"] == [2, 6]

    def test_positions_are_sorted_lists(self):
        """Output positions must be sorted lists (not sets or unsorted arrays)."""
        from backend.fusion import fuse_results
        results = fuse_results({
            "sound": [_result("luc. 1.1", "verg. aen. 1.1", 3.0,
                              src_highlights=[5, 1, 3], tgt_highlights=[4, 0])],
        }, language='la')
        attrs = results[0]["channel_token_attrs"]
        src = attrs["sound"]["source"]
        tgt = attrs["sound"]["target"]
        assert isinstance(src, list)
        assert isinstance(tgt, list)
        assert src == sorted(src)
        assert tgt == sorted(tgt)

    def test_multiple_channels_tracked_separately(self):
        """Each channel's positions are kept independent, not merged."""
        from backend.fusion import fuse_results
        results = fuse_results({
            "lemma": [_result("luc. 1.1", "verg. aen. 1.1", 5.0,
                              src_highlights=[2, 4], tgt_highlights=[1])],
            "sound": [_result("luc. 1.1", "verg. aen. 1.1", 2.0,
                              src_highlights=[0, 6], tgt_highlights=[3, 5])],
        }, language='la')
        attrs = results[0]["channel_token_attrs"]
        assert "lemma" in attrs
        assert "sound" in attrs
        # Lemma positions must not bleed into sound and vice-versa
        assert attrs["lemma"]["source"] == [2, 4]
        assert attrs["sound"]["source"] == [0, 6]
        assert attrs["lemma"]["target"] == [1]
        assert attrs["sound"]["target"] == [3, 5]

    def test_channel_token_attrs_keys_match_channels_list(self):
        """channel_token_attrs has exactly the keys named in channels."""
        from backend.fusion import fuse_results
        results = fuse_results({
            "lemma": [_result("luc. 1.1", "verg. aen. 1.1", 5.0,
                              src_highlights=[1], tgt_highlights=[2])],
            "exact": [_result("luc. 1.1", "verg. aen. 1.1", 3.0,
                              src_highlights=[1], tgt_highlights=[2])],
        }, language='la')
        r = results[0]
        assert set(r["channel_token_attrs"].keys()) == set(r["channels"])

    def test_duplicate_positions_within_channel_are_deduplicated(self):
        """If two channel results for the same pair both hit position 3, it appears once."""
        from backend.fusion import fuse_results
        # Two lemma results for the same pair (e.g. from line and window passes)
        # with overlapping positions.
        results = fuse_results({
            "lemma": [
                _result("luc. 1.1", "verg. aen. 1.1", 5.0,
                        src_highlights=[1, 3], tgt_highlights=[0]),
                _result("luc. 1.1", "verg. aen. 1.1", 4.0,
                        src_highlights=[3, 5], tgt_highlights=[0, 2]),
            ],
        }, language='la')
        attrs = results[0]["channel_token_attrs"]
        # Position 3 was in both results; it must appear exactly once.
        assert attrs["lemma"]["source"].count(3) == 1
        assert sorted(attrs["lemma"]["source"]) == attrs["lemma"]["source"]

    def test_channel_with_no_highlights_has_empty_lists(self):
        """A channel that matched but produced no highlight indices gets empty lists."""
        from backend.fusion import fuse_results
        results = fuse_results({
            "semantic": [_result("luc. 1.1", "verg. aen. 1.1", 4.0,
                                 src_highlights=[], tgt_highlights=[])],
        }, language='la')
        attrs = results[0]["channel_token_attrs"]
        assert "semantic" in attrs
        assert attrs["semantic"]["source"] == []
        assert attrs["semantic"]["target"] == []

    def test_slim_fusion_result_passes_through_attrs(self):
        """_slim_fusion_result includes channel_token_attrs in the API payload."""
        import sys, os
        sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__))))
        from backend.blueprints.fusion import _slim_fusion_result
        fake_result = {
            "fused_score": 0.85,
            "channels": ["lemma", "sound"],
            "channel_token_attrs": {
                "lemma": {"source": [1, 3], "target": [0, 2]},
                "sound": {"source": [0], "target": [1]},
            },
            "source": {"ref": "luc. 1.1", "text": "arma virumque", "citation": None, "locus": None},
            "target": {"ref": "verg. aen. 1.1", "text": "arma virumque cano", "citation": None, "locus": None},
            "matched_words": [],
            "matched_lemmas": [],
        }
        slim = _slim_fusion_result(fake_result)
        assert "channel_token_attrs" in slim
        assert slim["channel_token_attrs"]["lemma"]["source"] == [1, 3]
        assert slim["channel_token_attrs"]["sound"]["target"] == [1]
