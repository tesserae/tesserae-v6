"""Tests for scripts/documents/index_layout.py."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scripts.documents.index_layout import (
    TESS_LINE_RE,
    classify,
    clean_text,
    local_id,
    long_doc_tess_lines,
    region_of,
    short_doc_tess_line,
    slugify,
    tag_prefix,
)


def _rec(**kw):
    base = {
        "source": "edh", "id": "edh:HD000001", "edh_id": "HD000001",
        "edr_id": None, "tm_id": 1, "lines": [], "text": "",
        "findspot": {"region": None},
    }
    base.update(kw)
    return base


def test_clean_text_collapses_embedded_newlines_and_tabs():
    assert clean_text("dono dedit.\n\t\t\t\t█\n\t\t\t\tSentonae") == "dono dedit. █ Sentonae"
    assert clean_text("  a   b  ") == "a b"


def test_slugify_handles_punctuation_and_none():
    assert slugify("Latium et Campania (Regio I)") == "latium_et_campania_regio_i"
    assert slugify(None) == "unknown_region"
    assert slugify("") == "unknown_region"


def test_local_id_prefers_source_specific_id_and_falls_back_to_tm():
    assert local_id(_rec(source="edh", edh_id="HD000001")) == "HD000001"
    assert local_id(_rec(source="edh+edr", tm_id=42)) == "tm42"
    assert local_id(_rec(source="papyri", id="papyri:219272b")) == "219272b"


def test_tag_prefix_merged_vs_single_source():
    assert tag_prefix(_rec(source="edh+edr")) == "merged"
    assert tag_prefix(_rec(source="edh")) == "edh"


def test_classify_short_vs_long_at_threshold():
    short = _rec(lines=[{"text": "x"}] * 10)
    long_ = _rec(lines=[{"text": "x"}] * 11)
    assert classify(short) == "short"
    assert classify(long_) == "long"


def test_short_doc_tess_line_joins_lines_with_slash_and_matches_tag_regex():
    rec = _rec(lines=[{"text": "Dis Manibus."}, {"text": "Verviciae"}])
    line = short_doc_tess_line(rec)
    assert line == "<edh.HD000001>\tDis Manibus. / Verviciae"
    assert TESS_LINE_RE.match(line)


def test_long_doc_tess_lines_one_per_line_numbered():
    rec = _rec(lines=[{"text": "a"}, {"text": "b"}, {"text": ""}, {"text": "c"}])
    lines = long_doc_tess_lines(rec)
    assert lines == ["<edh.HD000001.1>\ta", "<edh.HD000001.2>\tb", "<edh.HD000001.4>\tc"]
    for ln in lines:
        assert TESS_LINE_RE.match(ln)


def test_region_of_slugifies_findspot_region():
    rec = _rec(findspot={"region": "Dalmatia"})
    assert region_of(rec) == "dalmatia"
    rec2 = _rec(findspot={})
    assert region_of(rec2) == "unknown_region"
