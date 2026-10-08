"""Tests for scripts/documents/dedupe_sources.py, using small inline toy
records (no network, no corpus data)."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scripts.documents.dedupe_sources import (
    attach_place_links,
    load_edh_place_links,
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


def test_place_pick_prefers_the_side_with_a_resolved_pleiades_id():
    # revised 2026-10-08 rule: a resolved place_pleiades_id (attached from
    # the Trismegistos crosswalk) wins outright over the other side,
    # regardless of findspot text detail.
    edh = _rec(place_pleiades_id="570316",
               findspot={"ancient_place": None, "modern_place": "X",
                         "region": None, "pleiades_id": None})
    edr = _rec(place_pleiades_id=None,
               findspot={"ancient_place": "Roma", "modern_place": "Roma",
                         "region": "Roma", "pleiades_id": None})
    assert pick_place_source(edh, edr) == "edh"


def test_place_pick_falls_back_to_longer_place_name_when_neither_has_an_id():
    edh = _rec(place_pleiades_id=None,
               findspot={"ancient_place": "Roma", "modern_place": None,
                         "region": None, "pleiades_id": None})
    edr = _rec(place_pleiades_id=None,
               findspot={"ancient_place": "Latium et Campania cum insulis",
                         "modern_place": None, "region": None, "pleiades_id": None})
    assert pick_place_source(edh, edr) == "edr"


def test_place_pick_tie_breaks_to_edh_not_edr():
    fs = {"ancient_place": "Roma", "modern_place": "Roma",
          "region": "Roma", "pleiades_id": None}
    edh = _rec(findspot=dict(fs), place_pleiades_id=None)
    edr = _rec(findspot=dict(fs), place_pleiades_id=None)
    assert pick_place_source(edh, edr) == "edh"


def test_load_edh_place_links_parses_tsv(tmp_path):
    path = tmp_path / "edh_place_links.tsv"
    path.write_text(
        "edh_id\ttm_place_id\tpleiades_id\tancient_place_text\n"
        "HD033001\t29683\t570316\tTimacum Minus\n"
        "HD000002\t\t\t\n",
        encoding="utf-8",
    )
    links = load_edh_place_links(str(path))
    assert links["HD033001"] == {"place_tm_id": 29683, "place_pleiades_id": "570316"}
    assert links["HD000002"] == {"place_tm_id": None, "place_pleiades_id": None}


def test_load_edh_place_links_returns_empty_dict_for_falsy_path():
    assert load_edh_place_links(None) == {}
    assert load_edh_place_links("") == {}


def test_attach_place_links_sets_fields_or_none():
    links = {"HD033001": {"place_tm_id": 29683, "place_pleiades_id": "570316"}}
    rec = _rec(edh_id="HD033001")
    attach_place_links(rec, links)
    assert rec["place_tm_id"] == 29683
    assert rec["place_pleiades_id"] == "570316"

    rec2 = _rec(edh_id="HD999999")  # not in links
    attach_place_links(rec2, links)
    assert rec2["place_tm_id"] is None
    assert rec2["place_pleiades_id"] is None

    rec3 = _rec(edh_id=None)
    attach_place_links(rec3, links)
    assert rec3["place_pleiades_id"] is None


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


def test_merge_attaches_edh_place_identifiers_even_when_edr_findspot_text_wins():
    # EDH has a Trismegistos place reference (place_tm_id) that did not
    # resolve through the crosswalk (place_pleiades_id is None, a real
    # case: the crosswalk covers 73.6% of EDH, not 100%). With neither
    # side holding a resolved Pleiades id, pick_place_source falls back
    # to the longer place name, which is EDR's here, so EDR's findspot
    # TEXT wins. The EDH place_tm_id is still attached regardless: the
    # identifier and the display text are different sub-fields
    # (2026-10-08 review).
    edh = _rec(edh_id="HD000001", place_tm_id=29683, place_pleiades_id=None,
               findspot={"ancient_place": "X", "modern_place": None,
                         "region": None, "pleiades_id": None})
    edr = _rec(edr_id="EDR000001", place_tm_id=None, place_pleiades_id=None,
               findspot={"ancient_place": "Roma Longer Name", "modern_place": "Roma",
                         "region": "Roma", "pleiades_id": None})
    merged = merge_edh_edr_pair(edh, edr)
    assert merged["provenance"]["findspot"] == "edr"  # EDR's longer name wins
    assert merged["place_tm_id"] == 29683              # EDH's identifier kept
    assert merged["place_pleiades_id"] is None
