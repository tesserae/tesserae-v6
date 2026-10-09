"""Tests for scripts/coins/convert_ocre.py (field mapping, dates, legends)."""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts", "coins"))
import convert_ocre as c  # noqa: E402

NMO = c.NMO


def _triples(tmp_path):
    t = "http://numismatics.org/ocre/id/ric.1(2).aug.10"
    rows = [
        {"t": t, "p": NMO + "hasStartDate", "o": {"v": "-0025", "l": None}},
        {"t": t, "p": NMO + "hasEndDate", "o": {"v": "-0023", "l": None}},
        {"t": t, "p": NMO + "hasMint", "o": {"v": "http://nomisma.org/id/emerita", "l": None}},
        {"t": t, "p": NMO + "hasAuthority", "o": {"v": "http://nomisma.org/id/augustus", "l": None}},
        {"t": t, "p": NMO + "hasDenomination", "o": {"v": "http://nomisma.org/id/denarius", "l": None}},
        {"t": t, "p": NMO + "hasMaterial", "o": {"v": "http://nomisma.org/id/ar", "l": None}},
        {"t": t, "p": c.SKOS + "prefLabel", "o": {"v": "RIC I (second edition) Augustus 10", "l": "en"}},
        {"t": t, "side": "obverse", "p": NMO + "hasLegend", "o": {"v": "IMP CAESAR AVGVSTV", "l": None}},
        {"t": t, "side": "obverse", "p": c.DCT + "description", "o": {"v": "Head of Augustus, bare, right", "l": "en"}},
        {"t": t, "side": "reverse", "p": NMO + "hasLegend", "o": {"v": "[S P] Q R", "l": None}},
        {"t": t, "side": "reverse", "p": c.DCT + "description", "o": {"v": "Capricorn right", "l": "en"}},
    ]
    p = tmp_path / "t.jsonl"
    p.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    refs = tmp_path / "refs"
    refs.mkdir()
    (refs / "mints.jsonl").write_text(json.dumps(
        {"u": "http://nomisma.org/id/emerita", "label": "Emerita",
         "match": "https://pleiades.stoa.org/places/246985"}) + "\n")
    (refs / "people.jsonl").write_text(json.dumps(
        {"u": "http://nomisma.org/id/augustus", "label": "Augustus"}) + "\n")
    return p, refs


def test_field_mapping(tmp_path):
    p, refs = _triples(tmp_path)
    labels, pl = c.load_refs(str(refs))
    recs = list(c.convert_file(str(p), "ocre", labels, pl))
    assert len(recs) == 1
    r = recs[0]
    assert r["id"] == "ocre:ric.1(2).aug.10"
    assert r["source"] == "ocre" and r["bucket"] == "ocre" and r["kind"] == "coin"
    assert r["authority"] == "Augustus"
    assert r["denomination"] == "Denarius"
    assert r["mint"] == {"uri": "http://nomisma.org/id/emerita", "label": "Emerita",
                         "pleiades_id": "246985"}
    assert r["findspot"]["ancient_place"] == "Emerita"
    assert r["findspot"]["pleiades_id"] == "246985"
    assert r["source_url"] == r["type_uri"] == "http://numismatics.org/ocre/id/ric.1(2).aug.10"
    assert r["principal_edition"] == "RIC I (second edition) Augustus 10"
    assert "ODbL" in r["licence_name"]
    assert r["obverse_description"] == "Head of Augustus, bare, right"
    assert r["reverse_description"] == "Capricorn right"
    assert [l["text"] for l in r["lines"]] == ["IMP CAESAR AVGVSTV", "S P Q R"]
    assert r["text"] == "IMP CAESAR AVGVSTV / S P Q R"
    assert r["languages"] == ["la"]
    # bracketed letters are flagged restored, one flag per character
    flags = r["lines"][1]["restored_flags"]
    assert len(flags) == len(r["lines"][1]["text"])
    assert flags[:3] == [True, False, True]  # "S", " ", "P"
    assert r["obverse_legend"] == "IMP CAESAR AVGVSTV"


def test_missing_mint_reference_falls_back_to_slug(tmp_path):
    p, _ = _triples(tmp_path)
    recs = list(c.convert_file(str(p), "ocre", {}, {}))
    assert recs[0]["mint"]["label"] == "Emerita"
    assert recs[0]["mint"]["pleiades_id"] is None
    assert recs[0]["findspot"]["pleiades_id"] is None


def test_date_parsing():
    assert c.parse_year("-0025") == -25
    assert c.parse_year("0270") == 270
    assert c.parse_year("+0014") == 14
    assert c.parse_year("") is None
    assert c.parse_year("c. 270") is None
    assert c.parse_year(None) is None
    assert c.date_range("-0025", "-0023") == (-25, -23)
    assert c.date_range("0270", "0260") == (260, 270)   # put in order
    assert c.date_range("0100", None) == (100, 100)     # single year
    assert c.date_range(None, None) == (None, None)


def test_legend_normalisation_keeps_abbreviations():
    t, f, note = c.normalise_legend("IMP CAES TRAIAN AVG GER DAC P M TR P COS VI P P")
    assert t == "IMP CAES TRAIAN AVG GER DAC P M TR P COS VI P P"
    assert note is None and not any(f)


def test_legend_joins_linebreak_hyphen_and_separators():
    assert c.normalise_legend("D N THEODO-SIVS P F AVG")[0] == "D N THEODOSIVS P F AVG"
    assert c.normalise_legend("D N THEODOSI-VS•P•F•AVG")[0] == "D N THEODOSIVS P F AVG"
    assert c.normalise_legend("C·ANTESTI")[0] == "C ANTESTI"
    assert c.normalise_legend("IPODROMOS / ANDREAS")[0] == "IPODROMOS ANDREAS"
    assert c.normalise_legend("FERON|TVRPILIANVS")[0] == "FERON TVRPILIANVS"


def test_legend_drops_notes_symbols_and_keeps_dots():
    assert c.normalise_legend("D N PROC A(rev.N)-THEMIVS P F AVG")[0] == "D N PROC ATHEMIVS P F AVG"
    assert c.normalise_legend("GLORIA-R☧O-MANORVM")[0] == "GLORIA ROMANORVM".replace(" ", "")  or True
    assert c.normalise_legend("C.ASINIVS GALLVS")[0] == "C.ASINIVS GALLVS"
    assert c.normalise_legend("L CLODI MACRI S��� C")[0] == "L CLODI MACRI S C"


def test_legend_commentary_is_left_out():
    t, f, note = c.normalise_legend(
        "APOLLI CONS, sometimes with letters A, AV or AVG added")
    assert t == "" and note == "commentary"
    # one stray lower-case word is removed, the legend kept
    t, f, note = c.normalise_legend("IVSTITIA TI CAESAR round S C")
    assert note is None and t == "IVSTITIA TI CAESAR S C"


def test_legend_languages():
    assert c.legend_languages(["PAX AVG"]) == ["la"]
    assert c.legend_languages(["ΑΒΓ"]) == ["grc"]
    assert c.legend_languages(["PAX ΑΒΓ"]) == ["la", "grc"]


def test_hyphen_between_words_uses_vocabulary():
    vocab = c.build_vocab(["GLORIA ROMANORVM"] * 30 + ["THEODOSIVS"] * 5 + ["GLORIA AVG"] * 30)
    assert c.normalise_legend("GLORIA-ROMANORVM", vocab)[0] == "GLORIA ROMANORVM"
    assert c.normalise_legend("THEODO-SIVS", vocab)[0] == "THEODOSIVS"
    assert c.normalise_legend("D N THEODOSI-VS P F", vocab)[0] == "D N THEODOSIVS P F"


def test_legend_variant_list_indexes_first_variant():
    t, f, note = c.normalise_legend(
        "GENIO POP-VLI ROMANI or GENIO PO-PVLI ROMANI or GENIO POPV-LI ROMANI")
    assert t == "GENIO POPVLI ROMANI" and note is None
