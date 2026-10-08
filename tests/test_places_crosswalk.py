"""Tests for scripts/documents/places_crosswalk.py, using small inline
toy fixtures (no network, no corpus data)."""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scripts.documents.places_crosswalk import (
    TM_URI_RE,
    build_crosswalk_from_edh_geography,
    find_disagreements,
    merge_crosswalks,
)


def test_tm_uri_regex_extracts_id_and_ignores_leading_zeros():
    m = TM_URI_RE.search("http://www.trismegistos.org/place/029683")
    assert m and int(m.group(1)) == 29683
    m2 = TM_URI_RE.search("https://www.trismegistos.org/place/15743")
    assert m2 and int(m2.group(1)) == 15743
    assert TM_URI_RE.search("http://www.geonames.org/786413") is None


def test_build_crosswalk_from_edh_geography(tmp_path):
    data = {
        "features": [
            {"properties": {
                "trismegistos_geo_uri": "https://www.trismegistos.org/place/15743",
                "pleiades_uri": "https://pleiades.stoa.org/places/570316",
                "ancient_findspot": "Isthmia",
            }},
            {"properties": {
                # missing pleiades_uri: must be skipped, not crash.
                "trismegistos_geo_uri": "https://www.trismegistos.org/place/99999",
                "ancient_findspot": "NoPleiades",
            }},
        ]
    }
    path = tmp_path / "geo.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    cw = build_crosswalk_from_edh_geography(str(path))
    assert cw[15743]["pleiades_id"] == "570316"
    assert cw[15743]["ancient_findspot"] == "Isthmia"
    assert 99999 not in cw


def test_merge_crosswalks_primary_wins_on_conflict_and_tallies():
    primary = {1: {"pleiades_id": "100", "source": "edh_geography"}}
    secondary = {
        1: {"pleiades_id": "999", "source": "pleiades_dump"},   # disagree
        2: {"pleiades_id": "200", "source": "pleiades_dump"},   # added
    }
    merged, stats = merge_crosswalks(primary, secondary)
    assert merged[1]["pleiades_id"] == "100"  # primary wins
    assert merged[2]["pleiades_id"] == "200"  # filled from secondary
    assert stats == {"agree": 0, "disagree": 1, "added_from_secondary": 1}


def test_merge_crosswalks_agreement_counted():
    primary = {1: {"pleiades_id": "100", "source": "edh_geography"}}
    secondary = {1: {"pleiades_id": "100", "source": "pleiades_dump"}}
    merged, stats = merge_crosswalks(primary, secondary)
    assert stats["agree"] == 1
    assert stats["disagree"] == 0


def test_find_disagreements_lists_only_conflicting_shared_ids():
    primary = {
        1: {"pleiades_id": "100", "ancient_findspot": "Roma"},
        2: {"pleiades_id": "200", "ancient_findspot": "Ostia"},
        3: {"pleiades_id": "300", "ancient_findspot": "Only in EDH"},
    }
    secondary = {
        1: {"pleiades_id": "999", "title": "Roma (different)"},  # disagree
        2: {"pleiades_id": "200", "title": "Ostia"},              # agree
        4: {"pleiades_id": "400", "title": "Only in Pleiades"},   # no overlap
    }
    rows = find_disagreements(primary, secondary)
    assert rows == [(1, "100", "999", "Roma", "Roma (different)")]
