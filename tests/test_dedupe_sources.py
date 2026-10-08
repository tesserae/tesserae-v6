"""Tests for scripts/documents/dedupe_sources.py, using small inline toy
records (no network, no corpus data)."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scripts.documents.dedupe_sources import (
    merge_edh_edr_pair,
    pick_date_source,
    pick_place_source,
    pick_text_source,
)


def _rec(**kw):
    base = {
        "source": "edh", "tm_id": 1, "hgv_id": None, "edh_id": None,
        "edr_id": None, "edcs_id": None, "languages": ["la"],
        "bilingual": False, "title": None, "object_type": None,
        "material": None, "date_not_before": None, "date_not_after": None,
        "findspot": {"ancient_place": None, "modern_place": None,
                     "region": None, "pleiades_id": None},
        "lines": [], "text": "", "supplied_chars": 0, "total_chars": 0,
        "gap_count": 0, "supplied_share": 0.0,
    }
    base.update(kw)
    return base


def test_text_pick_prefers_lower_supplied_share():
    edh = _rec(text="abc", supplied_chars=1, total_chars=4, supplied_share=0.25)
    edr = _rec(text="abcd", supplied_chars=2, total_chars=4, supplied_share=0.5)
    assert pick_text_source(edh, edr) == "edh"


def test_text_pick_tie_breaks_to_more_total_chars():
    edh = _rec(supplied_chars=1, total_chars=2, supplied_share=0.5)
    edr = _rec(supplied_chars=2, total_chars=4, supplied_share=0.5)
    assert pick_text_source(edh, edr) == "edr"


def test_date_pick_prefers_narrower_nonnull_range():
    edh = _rec(date_not_before=100, date_not_after=200)
    edr = _rec(date_not_before=120, date_not_after=140)
    assert pick_date_source(edh, edr) == "edr"


def test_date_pick_null_loses_to_real_range():
    edh = _rec(date_not_before=None, date_not_after=None)
    edr = _rec(date_not_before=1, date_not_after=50)
    assert pick_date_source(edh, edr) == "edr"


def test_place_pick_prefers_ancient_place_and_pleiades():
    edh = _rec(findspot={"ancient_place": None, "modern_place": "X",
                          "region": None, "pleiades_id": None})
    edr = _rec(findspot={"ancient_place": "Roma", "modern_place": "Roma",
                          "region": "Roma", "pleiades_id": "423025"})
    assert pick_place_source(edh, edr) == "edr"


def test_place_pick_tie_breaks_to_edr():
    fs = {"ancient_place": "Roma", "modern_place": "Roma",
          "region": "Roma", "pleiades_id": None}
    edh = _rec(findspot=dict(fs))
    edr = _rec(findspot=dict(fs))
    assert pick_place_source(edh, edr) == "edr"


def test_merge_carries_both_ids_and_provenance():
    edh = _rec(edh_id="HD000001", text="a", supplied_chars=0, total_chars=1,
                date_not_before=None, date_not_after=None)
    edr = _rec(edr_id="EDR000001", text="ab", supplied_chars=0, total_chars=2,
                date_not_before=1, date_not_after=10)
    merged = merge_edh_edr_pair(edh, edr)
    assert merged["edh_id"] == "HD000001"
    assert merged["edr_id"] == "EDR000001"
    assert merged["provenance"]["ids"] == "both"
    # EDR has a real date range and EDH does not: date comes from EDR.
    assert merged["provenance"]["date"] == "edr"
    assert merged["date_not_before"] == 1
