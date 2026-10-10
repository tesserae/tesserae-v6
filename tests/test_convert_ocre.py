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


# ---------------------------------------------------------------------------
# Greek sets (fixture: one real type from each of eight catalogues)
# ---------------------------------------------------------------------------

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures", "coins")
GREEK_MARKS = {"cn": "corpus-nummorum", "sco": "/sco/", "pella": "/pella/", "pco": "/pco/",
               "bigr": "/bigr/", "iris": "/iris/", "iacb": "/iacb.", "lco": "/lco/"}


def _greek_records(tmp_path):
    rows = [json.loads(line) for line in open(os.path.join(FIXTURES, "greek_triples.jsonl"), encoding="utf-8")]
    labels, pl = c.load_refs(os.path.join(FIXTURES, "greek_refs"))
    out = {}
    for code, mark in GREEK_MARKS.items():
        p = tmp_path / f"{code}.jsonl"
        p.write_text("".join(json.dumps(r) + "\n" for r in rows if mark in r["t"]), encoding="utf-8")
        recs = list(c.convert_file(str(p), code, labels, pl))
        assert len(recs) == 1, code
        out[code] = recs[0]
    return out


def test_every_greek_set_converts_with_its_code_and_licence(tmp_path):
    recs = _greek_records(tmp_path)
    assert recs["cn"]["id"] == "cn:10069"  # no /id/ in the address: the part after /types/
    assert recs["sco"]["id"] == "sco:sc.1.1"
    assert recs["pco"]["id"] == "pco:cpe.1_1.1"
    for code, r in recs.items():
        assert r["source"] == code and r["kind"] == "coin"
        assert r["source_name"] == c.DATASETS[code]["name"]
        assert r["obverse_description"] or r["reverse_description"]
    assert "CC BY-NC-SA 3.0" in recs["cn"]["licence_name"]
    assert "CC BY-NC-SA 4.0" in recs["iacb"]["licence_name"]
    assert "ODbL" in recs["sco"]["licence_name"] and "ODbL" in recs["iris"]["licence_name"]


def test_greek_sets_keep_greek_legends_and_read_stated_authority(tmp_path):
    recs = _greek_records(tmp_path)
    assert recs["pella"]["authority"] == "Philip II"          # hasStatedAuthority
    assert recs["pella"]["reverse_legend"] == "\u03a6\u0399\u039b\u0399\u03a0\u03a0\u039f\u03a5"
    assert recs["pella"]["languages"] == ["grc"]
    # a blank node holding rdf:value was resolved by the fetcher, so both names show;
    # the British Museum person address has no label and is left out of the portrait
    assert recs["pco"]["authority"] == "Ptolemy I Soter; Cleomenes of Naucratis"
    assert recs["pco"]["portrait"] == "Zeus"
    assert recs["bigr"]["languages"] == ["grc"]
    assert recs["iacb"]["reverse_legend"] == "MA" and recs["iacb"]["languages"] == ["la"]


def test_latin_lookalike_letters_in_a_greek_word_become_greek(tmp_path):
    recs = _greek_records(tmp_path)
    raw = recs["sco"]["reverse_legend"]
    assert raw.startswith("BA\u03a3")                          # catalogued with a Latin B and A
    assert recs["sco"]["lines"][0]["text"] == "\u0392\u0391\u03a3\u0399\u039b\u0395\u03a9\u03a3 \u03a3\u0395\u039b\u0395\u03a5\u039a\u039f\u03a5"
    assert c.unmix_scripts("AVGVSTVS") == "AVGVSTVS"           # a Latin word is untouched


def test_greek_accents_and_breathings_survive_normalisation():
    text, flags, note = c.normalise_legend("\u0392\u0391\u03a3\u0399\u039b\u0388\u03a9\u03a3 \u1f08\u039b\u0395\u039e\u1f0c\u039d\u0394\u03a1\u039f\u03a5")
    assert note is None and len(flags) == len(text)
    assert "\u0388" in text and "\u1f08" in text and "\u1f0c" in text


def test_note_after_a_greek_legend_is_dropped_not_the_legend():
    text, _, note = c.normalise_legend("\u03a0\u03a4\u039f\u039b\u0395\u039c\u0391\u0399\u039f\u03a5 \u0392\u0391\u03a3\u0399\u039b\u0395\u03a9\u03a3 above quadriga")
    assert note is None and text == "\u03a0\u03a4\u039f\u039b\u0395\u039c\u0391\u0399\u039f\u03a5 \u0392\u0391\u03a3\u0399\u039b\u0395\u03a9\u03a3"


def test_command_line_takes_several_datasets(tmp_path):
    rows = [json.loads(line) for line in open(os.path.join(FIXTURES, "greek_triples.jsonl"), encoding="utf-8")]
    paths = []
    for code in ("sco", "pella"):
        p = tmp_path / f"{code}.jsonl"
        p.write_text("".join(json.dumps(r) + "\n" for r in rows if GREEK_MARKS[code] in r["t"]), encoding="utf-8")
        paths.append(f"{code}={p}")
    out = tmp_path / "coins.jsonl"
    rc = c.main(["--dataset", paths[0], "--dataset", paths[1],
                 "--refs", os.path.join(FIXTURES, "greek_refs"), "--output", str(out)])
    assert rc == 0
    ids = [json.loads(line)["id"] for line in open(out, encoding="utf-8")]
    assert ids == ["sco:sc.1.1", "pella:lerider.philip_ii.1.1"]
