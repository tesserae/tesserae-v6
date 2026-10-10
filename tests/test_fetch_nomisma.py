"""scripts/coins/fetch_nomisma.py: blank nodes holding rdf:value, and the ids a types file uses."""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts", "coins"))
import fetch_nomisma as f  # noqa: E402


def test_blank_node_with_a_value_gives_the_value():
    b = {"o": {"type": "bnode", "value": "b0"}, "v": {"value": "http://nomisma.org/id/ptolemy_i"}}
    assert f._o(b) == {"v": "http://nomisma.org/id/ptolemy_i", "l": None}


def test_blank_node_without_a_value_is_dropped():
    assert f._o({"o": {"type": "bnode", "value": "b1"}}) is None


def test_literal_keeps_its_language():
    b = {"o": {"type": "literal", "value": "Zeus seated", "xml:lang": "en"}}
    assert f._o(b) == {"v": "Zeus seated", "l": "en"}


def test_used_ids_sorts_ids_by_kind(tmp_path):
    t = "http://numismatics.org/pella/id/x"
    rows = [
        {"t": t, "p": f.NMO + "hasMint", "o": {"v": "http://nomisma.org/id/pella_macedon", "l": None}},
        {"t": t, "p": f.NMO + "hasStatedAuthority", "o": {"v": "http://nomisma.org/id/philip_ii", "l": None}},
        {"t": t, "p": f.NMO + "hasDenomination", "o": {"v": "http://nomisma.org/id/tetradrachm", "l": None}},
        {"t": t, "side": "obverse", "p": f.NMO + "hasPortrait", "o": {"v": "http://nomisma.org/id/zeus", "l": None}},
        {"t": t, "side": "obverse", "p": f.NMO + "hasPortrait",
         "o": {"v": "http://collection.britishmuseum.org/id/person-institution/61143", "l": None}},
    ]
    p = tmp_path / "t.jsonl"
    p.write_text("".join(json.dumps(r) + "\n" for r in rows))
    ids = f.used_ids(str(p))
    assert ids == {"http://nomisma.org/id/pella_macedon": "mint",
                   "http://nomisma.org/id/philip_ii": "people",
                   "http://nomisma.org/id/tetradrachm": "label",
                   "http://nomisma.org/id/zeus": "people"}
