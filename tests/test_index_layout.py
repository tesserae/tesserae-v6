"""Tests for scripts/documents/index_layout.py."""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scripts.documents.index_layout import (
    TESS_LINE_RE,
    century_of,
    classify,
    clean_text,
    find_oversized_short_buckets,
    local_id,
    long_doc_tess_lines,
    region_of,
    short_bucket_filename,
    short_bucket_key,
    short_doc_tess_line,
    slugify,
    tag_prefix,
    validate_full_corpus_regex,
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


def test_century_of_handles_ad_bc_and_undated():
    assert century_of(None) == "undated"
    assert century_of(1) == "1_ad"
    assert century_of(100) == "1_ad"
    assert century_of(101) == "2_ad"
    assert century_of(-1) == "1_bc"
    assert century_of(-100) == "1_bc"
    assert century_of(-101) == "2_bc"


def test_find_oversized_short_buckets_over_threshold(tmp_path, monkeypatch):
    import scripts.documents.index_layout as il
    monkeypatch.setattr(il, "BUCKET_SPLIT_THRESHOLD", 2)
    path = tmp_path / "toy.jsonl"
    with open(path, "w", encoding="utf-8") as f:
        for i in range(3):
            f.write(json.dumps(_rec(id=f"edh:{i}", edh_id=f"H{i}",
                                      findspot={"region": "Roma"})) + "\n")
        f.write(json.dumps(_rec(id="edh:x", edh_id="Hx",
                                  findspot={"region": "Dalmatia"})) + "\n")
    oversized = find_oversized_short_buckets(str(path), threshold=2)
    assert oversized == {("edh", "roma")}


def test_short_bucket_key_splits_only_oversized_buckets():
    rec_roma = _rec(findspot={"region": "Roma"}, date_not_before=101)
    rec_dalmatia = _rec(findspot={"region": "Dalmatia"}, date_not_before=101)
    oversized = {("edh", "roma")}
    assert short_bucket_key(rec_roma, oversized) == ("edh", "roma", "2_ad")
    assert short_bucket_key(rec_dalmatia, oversized) == ("edh", "dalmatia")


def test_short_bucket_filename_includes_century_only_when_split():
    assert short_bucket_filename(("edh", "roma")) == "roma"
    assert short_bucket_filename(("edh", "roma", "2_ad")) == "roma__2_ad"


def test_validate_full_corpus_regex_reports_zero_failures_on_clean_corpus(tmp_path):
    path = tmp_path / "toy.jsonl"
    with open(path, "w", encoding="utf-8") as f:
        f.write(json.dumps(_rec(lines=[{"text": "Dis Manibus."}])) + "\n")
    result = validate_full_corpus_regex(str(path))
    assert result["all_lines_matched_tess_regex"] is True
    assert result["total_lines_checked"] == 1
    assert result["regex_failures"] == []
