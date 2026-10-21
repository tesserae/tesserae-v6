"""Tests for the Attic Inscriptions Online (AIO) converter, metadata rows and
overlap check. No network and no corpus data: small hand-written records in
the form the AIO API returns them."""
import base64
import json
import os
import sqlite3
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts", "documents"))

import aio_convert as ac  # noqa: E402
import aio_metadata as am  # noqa: E402
import aio_overlap as ao  # noqa: E402
from extract_metadata import create_schema  # noqa: E402


def b64(xml: str) -> str:
    return base64.b64encode(xml.encode("utf-8")).decode("ascii")


GREEK = b64(
    '<body xmlns:xml="http://www.w3.org/XML/1998/namespace">'
    '<div xml:lang="grc" type="edition" xml:space="preserve"><div n="1" type="textpart"><ab>'
    '<lb/><note type="inline">(394/3)</note>ἔδοξεν τῆι <supplied reason="lost">βου'
    '<lb break="no"/>λῆι</supplied> καὶ τῶι δήμωι<lb/>Κινησίας εἶπε'
    '<lb/><gap reason="lost" quantity="1" unit="line"/>'
    '</ab></div></div></body>')

TRANSLATION = b64(
    '<body xmlns:xml="http://www.w3.org/XML/1998/namespace"><div xml:lang="en" type="translation">'
    '<div n="1" type="textpart"><p><lb/><note type="inline">Relief</note><note type="footnote">1</note>'
    '<lb/>The Council and People decided.<note type="footnote">2</note> Kinesias '
    '<supplied reason="lost">proposed</supplied><gap reason="illegible" extent="unknown" unit="character"/>'
    '</p></div></div></body>')

RAW = {
    "url": "www.atticinscriptions.com/inscription/IGII2/18", "aio_key": "AIO_798",
    "references": [{"source": "IGII2", "reference": "18", "is_translation_source": True},
                   {"source": "SEG", "reference": "61.36"}],
    "translation_title": "Honours for <i>Dionysios</i>, 394/3 BC",
    "translation_epidoc": TRANSLATION, "translators": ["Stephen Lambert", "P. J.  Rhodes"],
    "IPR": "Creative Commons", "greek_epidoc": GREEK,
}

PAGE_HTML = '''
<h3 id="ins_title">Honours</h3>
<span id="ins_source"><i>IG</i> II<sup>2</sup> 18 </span>
<span id="ins_date"> Date:
    394/3 BC
</span>
<div class="ins_alt_source" ><b><a href="/browse/bysource/IGII2/"><i>IG</i> II<sup>2</sup> 18 (Translated text)</a></b></div>
<div class="ins_alt_source" ><a href="/browse/bysource/SEG/"><i>SEG</i> 61.36</a></div>
<div class="ins_type_info" >
Monument type: Stele
</div>
<div class="ins_type_info" >
Inscription type:
Decree (People),
Honorific
</div>
<div class="ins_type_info" >
Findspot: Athens (Agora) <a href="http://pleiades.stoa.org/places/579885"><span></span></a>
</div>
'''


def test_epidoc_is_decoded_from_base64_and_moved_into_the_tei_namespace():
    root = ac.decode_epidoc(GREEK)
    assert root.tag.startswith("{http://www.tei-c.org/ns/1.0}")
    assert any(el.get("type") == "edition" for el in root.iter(ac.qn("div")))


def test_malformed_epidoc_is_recovered_and_noted():
    notes = []
    root = ac.decode_epidoc(b64("<body><div><p>text</div></body>"), notes)
    assert root is not None and notes and "recovered" in notes[0]


def test_greek_lines_drop_notes_keep_restorations_and_join_broken_words():
    lines, langs, counts = ac.greek_lines(GREEK)
    assert langs == ["grc"]
    texts = [ln["text"] for ln in lines]
    assert "(394/3)" not in " ".join(texts)
    assert texts[0] == "ἔδοξεν τῆι βουλῆι καὶ τῶι δήμωι" or texts[0].startswith("ἔδοξεν τῆι βου")
    joined = ac.join_lines(lines)
    assert "βουλῆι" in joined
    assert counts["supplied_chars"] > 0
    first = lines[0]
    assert any(first["restored_flags"])  # the supplied letters are flagged restored


def test_translation_text_drops_footnotes_keeps_inline_notes_and_brackets():
    text = ac.translation_text(TRANSLATION)
    assert text.startswith("(Relief)")
    assert "The Council and People decided." in text
    assert "1" not in text.replace("(Relief)", "")
    assert "[proposed]" in text and ". . ." in text


def test_translators_are_joined_with_and_and_spaces_collapsed():
    assert ac.translators_of(RAW) == "Stephen Lambert and P. J. Rhodes"
    assert ac.translators_of({"translators": ["A B", "C D", "E F"]}) == "A B, C D and E F"


def test_page_gives_edition_as_aio_shows_it_with_exponents_flattened():
    page = ac.parse_page(PAGE_HTML)
    assert page["edition"] == "IG II2 18"
    assert page["date_text"] == "394/3 BC"
    assert page["monument_type"] == "Stele"
    assert page["inscription_types"] == ["Decree (People)", "Honorific"]
    assert page["findspot"] == "Athens"
    assert page["pleiades_id"] == "579885"
    assert page["references"] == ["IG II2 18", "SEG 61.36"]


def test_edition_is_never_the_aio_number():
    own = {"edition": "AIO 1049", "references": ["AIO 1049", "SEG 28.46", "IG I3 363"]}
    assert ac.choose_edition(own, None) == ("IG I3 363", "reference-IG")
    seg_only = {"edition": "AIUK 4.6 (BM, Funerary Monuments) no. 1",
                "references": ["AIUK 4.6 (BM, Funerary Monuments) no. 1", "SEG 28.46"]}
    assert ac.choose_edition(seg_only, None) == ("SEG 28.46", "reference-SEG")
    nothing = {"edition": "AIUK 7 (Chatsworth) no. 3", "references": ["AIUK 7 (Chatsworth) no. 3"]}
    assert ac.choose_edition(nothing, None) == ("AIUK 7 (Chatsworth) no. 3", "heading-own-number")
    assert ac.choose_edition(ac.parse_page(PAGE_HTML), None) == ("IG II2 18", "heading")


def test_dates_are_parsed_to_signed_years():
    assert ac.parse_date("394/3 BC") == (-394, -393)
    assert ac.parse_date("After 378/7 BC") == (-378, None)
    assert ac.parse_date("27 BC – 14 AD") == (-27, 14)
    assert ac.parse_date("Late v - early iv BC") == (-434, -367)
    assert ac.parse_date("Imperial period") == (None, None)
    assert ac.parse_date("A: 450-430 BC? B: ca. 18 AD") == (None, None)


def test_record_has_aio_id_and_the_fields_the_pipeline_reads():
    rec = ac.build_record(RAW, "IGII2", "18", ac.parse_page(PAGE_HTML), [])
    assert rec["id"] == "aio:IGII2_18" and "/" not in rec["id"]
    assert rec["source"] == "aio" and rec["languages"] == ["grc"]
    assert (rec["date_not_before"], rec["date_not_after"]) == (-394, -393)
    assert rec["findspot"]["ancient_place"] == "Athens"
    assert rec["aio"]["url"] == "https://www.atticinscriptions.com/inscription/IGII2/18"
    assert rec["title"] == "Honours for Dionysios, 394/3 BC"
    assert rec["lines"] and rec["text"]


def test_record_without_greek_is_skipped():
    raw = dict(RAW)
    del raw["greek_epidoc"]
    assert ac.build_record(raw, "IGII2", "18", None, []) is None


def test_credit_line_names_aio_translator_license_and_page(tmp_path):
    rec = ac.build_record(RAW, "IGII2", "18", ac.parse_page(PAGE_HTML), [])
    row = am.document_row(rec)
    assert row["source_name"] == "Attic Inscriptions Online, translation by Stephen Lambert and P. J. Rhodes"
    assert row["source_url"] == "https://www.atticinscriptions.com/inscription/IGII2/18"
    assert row["licence_name"] == "CC BY-SA 3.0"
    assert row["licence_url"] == "https://creativecommons.org/licenses/by-sa/3.0/"
    assert row["principal_edition"] == "IG II2 18"
    assert row["text_type_label"] == "Decree (People), Honorific"
    assert row["object_type_label"] == "Stele"
    assert row["pleiades_id"] == "579885"
    assert row["source"] == "aio" and row["collection"] == "documents"
    disp = am.display_rows(rec)
    assert disp[0][1] == "translation"
    assert "Translation by Stephen Lambert and P. J. Rhodes" in disp[0][2]


def test_metadata_script_inserts_rows_and_can_run_twice(tmp_path):
    rec = ac.build_record(RAW, "IGII2", "18", ac.parse_page(PAGE_HTML), [])
    jl = tmp_path / "aio.jsonl"
    jl.write_text(json.dumps(rec, ensure_ascii=False) + "\n", encoding="utf-8")
    tess = tmp_path / "aio.tess"
    tess.write_text("<aio:IGII2_18 1>\tἔδοξεν\n", encoding="utf-8")
    db = tmp_path / "meta.db"
    conn = sqlite3.connect(db)
    create_schema(conn)
    conn.commit()
    conn.close()
    for _ in range(2):
        assert am.main([str(jl), str(db), "--tess", str(tess)]) == 0
    conn = sqlite3.connect(db)
    assert conn.execute("SELECT COUNT(*) FROM documents WHERE source='aio'").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM display WHERE id='aio:IGII2_18'").fetchone()[0] == 1


def test_metadata_script_refuses_the_production_folder():
    assert am.main(["x.jsonl", "/var/www/tesseraev6_flask/data/documents/metadata.db"]) == 2


def test_overlap_keys_match_the_other_sources_spelling_of_the_same_edition():
    assert ao.key_aio("IG II2 1967") == ao.key_existing("IG 02 (2. Aufl.) 01967.")
    assert ao.key_aio("SEG 21.498") == ao.key_existing("SEG 21, 0498.")
    assert ao.key_aio("IG XII 5 1277") is None
    assert ao.key_existing("IG 12, 05, p. 191.") is None


# ---- Berlin IG digital edition (CC BY 4.0) -------------------------------

BBAW_XML = '''<?xml version="1.0" encoding="UTF-8"?>
<TEI xmlns="http://www.tei-c.org/ns/1.0"><teiHeader><fileDesc><publicationStmt>
<idno type="URI">https://telota.bbaw.de/ig/digitale-edition/inschrift/IG II_III³ 4, 1563</idno>
<availability><licence target="https://creativecommons.org/licenses/by/4.0/legalcode">CC BY 4.0</licence></availability>
</publicationStmt></fileDesc></teiHeader><text><body>
<div type="edition"><ab><lb n="1"/><hi rend="smallit">vacat</hi>[. . . . λ]ογισταῖς <hi rend="sup">17</hi>̣Π[ολιά]δι χρε̣μάτ‒<lb n="2"/>ων ἀνέθηκ(εν) ὁ δῆμος ․․․․ v <hi rend="italic">h</hi>
<lb n="3"/>[––]</ab></div>
<div type="translation" xml:lang="DE"><ab>nicht verwenden</ab></div></body></text></TEI>'''.encode("utf-8")


def test_berlin_text_brackets_gaps_and_line_end_hyphen():
    lines = ac.bbaw_lines(BBAW_XML)
    texts = [ln["text"] for ln in lines]
    assert texts[0].startswith(ac.GAP + " λογισταῖς Πολιάδι χρεμάτ")
    assert "vacat" not in " ".join(texts) and "17" not in " ".join(texts)
    assert lines[1]["joins_previous"] is True
    assert "ἀνέθηκεν" in texts[1] and "nicht" not in " ".join(texts)
    # brackets are not in the text, the letters they held are flagged restored
    assert "[" not in texts[0] and "]" not in texts[0]
    flags0 = lines[0]["restored_flags"]
    assert flags0[texts[0].index("λ")] is True
    assert flags0[texts[0].index("Π")] is False and flags0[texts[0].index("ολιά")] is True
    # the all-dots-and-dashes line is one gap
    assert texts[-1] == ac.GAP
    # a lone Latin "v" and italic "h" do not survive
    assert " v" not in texts[1] and "h" not in texts[1]


def test_berlin_licence_is_checked_and_page_link_built():
    root = ac.bbaw_parse(BBAW_XML)
    assert ac.bbaw_licence_ok(root)
    assert not ac.bbaw_licence_ok(ac.bbaw_parse(BBAW_XML.replace(b"by/4.0", b"by-nc/4.0")))
    assert ac.bbaw_page_url(root) == (
        "https://telota.bbaw.de/ig/digitale-edition/inschrift/IG%20II_III%C2%B3%204,%201563")


def test_record_with_berlin_greek_credits_both_sources():
    raw = dict(RAW)
    del raw["greek_epidoc"]
    rec = ac.build_record_bbaw(raw, "IGII34", "1563", ac.parse_page(PAGE_HTML), [BBAW_XML], [])
    assert rec["id"] == "aio:IGII34_1563" and rec["lines"] and rec["aio"]["greek_source"] == "bbaw"
    row = am.document_row(rec)
    assert row["source_name"] == "Greek text: Inscriptiones Graecae, Berlin-Brandenburg Academy of Sciences and Humanities"
    assert row["source_url"].startswith("https://telota.bbaw.de/ig/digitale-edition/inschrift/")
    assert (row["licence_name"], row["licence_url"]) == ("CC BY 4.0", "https://creativecommons.org/licenses/by/4.0/")
    assert row["source_name_secondary"] == "Translation: Attic Inscriptions Online (Stephen Lambert and P. J. Rhodes)"
    assert row["source_url_secondary"] == "https://www.atticinscriptions.com/inscription/IGII34/1563"
    assert (row["licence_name_secondary"], row["licence_url_secondary"]) == (
        "CC BY-SA 3.0", "https://creativecommons.org/licenses/by-sa/3.0/")
    assert row["principal_edition"] == "IG II2 18"


# ---- one row per document, broken words rejoined, region -------------------

import write_document_tess as wdt  # noqa: E402


def test_aio_document_is_one_row_with_ref_equal_to_its_id_even_when_long(tmp_path):
    raw = dict(RAW)
    rec = ac.build_record(raw, "IGII2", "18", ac.parse_page(PAGE_HTML), [])
    rec["lines"] = rec["lines"] * 8   # more lines than the short-document threshold
    jl = tmp_path / "aio.jsonl"
    jl.write_text(json.dumps(rec, ensure_ascii=False) + "\n", encoding="utf-8")
    out = tmp_path / "texts"
    wdt.process_corpus(str(jl), str(out), all_short=True)
    files = list((out / "grc").glob("*.tess"))
    assert len(files) == 1 and files[0].name == "aio__attica.tess"
    rows = files[0].read_text(encoding="utf-8").splitlines()
    assert len(rows) == 1
    ref, text = rows[0].split("\t", 1)
    assert ref == "<aio:IGII2_18>" and " / " in text


def test_word_broken_across_a_line_end_is_rejoined_without_separator(tmp_path):
    lines, _, _ = ac.greek_lines(GREEK)
    assert lines[1]["joins_previous"] is True       # <lb break="no"/> inside the supplied word
    rec = {"id": "aio:T_1", "source": "aio", "languages": ["grc"], "lines": lines,
           "findspot": {"region": "Attica"}, "date_not_before": None}
    text, restored, _, _ = wdt.build_short_doc_unit(rec)
    assert "βουλῆι" in text.split(" ")                # whole word, not 'βου' / 'λῆι'
    assert "βου /" not in text
    # the rejoined word's supplied letters are still flagged restored
    toks = text.split(" ")
    assert toks.index("βουλῆι") in restored


def test_berlin_hyphenated_word_is_rejoined_too():
    lines = ac.bbaw_lines(BBAW_XML)
    rec = {"id": "aio:T_2", "source": "aio", "languages": ["grc"], "lines": lines,
           "findspot": {"region": "Attica"}, "date_not_before": None}
    text, _, _, _ = wdt.build_short_doc_unit(rec)
    assert "χρεμάτων" in text.split(" ")


def test_every_aio_document_has_region_attica():
    rec = ac.build_record(RAW, "IGII2", "18", ac.parse_page(PAGE_HTML), [])
    assert rec["findspot"]["region"] == "Attica"
    assert am.document_row(rec)["region"] == "Attica"


def test_berlin_en_dash_after_a_letter_at_a_line_end_marks_a_broken_word():
    xml = BBAW_XML.replace("χρεμάτων".encode(), b"x") if False else (
        '<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body><div type="edition"><ab>'
        '<lb n="1"/>ἐπὶ τῆς δος ὀγδόης πρυτανεί]–<lb n="2"/>ας, ἧι Διόδοτος [Ἀνθεστηρι]–'
        '<lb n="3"/>ῶνος<lb n="4"/>Προξε[ν– – – –<lb n="5"/>– – – –</ab></div></body></text></TEI>').encode("utf-8")
    lines = ac.bbaw_lines(xml)
    assert lines[1]["joins_previous"] is True and lines[2]["joins_previous"] is True
    assert lines[3]["joins_previous"] is False
    rec = {"id": "aio:T_3", "source": "aio", "languages": ["grc"], "lines": lines,
           "findspot": {"region": "Attica"}, "date_not_before": None}
    text, _, _, _ = wdt.build_short_doc_unit(rec)
    toks = text.split(" ")
    assert "πρυτανείας," in toks and "Ἀνθεστηριῶνος" in toks
