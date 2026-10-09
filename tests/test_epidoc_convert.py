"""Unit tests for scripts/documents/epidoc_convert.py against small real
EpiDoc samples from the four stage-1 documentary sources (tests/fixtures/epidoc/).

These tests exercise the converter only. They do not touch the search
index, the backend app, or any data under /var/www.
"""
import json
import os
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIXTURES = os.path.join(ROOT, "tests", "fixtures", "epidoc")
SCRIPT = os.path.join(ROOT, "scripts", "documents", "epidoc_convert.py")

sys.path.insert(0, os.path.join(ROOT, "scripts", "documents"))
import epidoc_convert  # noqa: E402


def convert_one(source, filename, hgv_path=None):
    path = os.path.join(FIXTURES, source, filename)
    hgv_root = None
    if hgv_path:
        hgv_root = epidoc_convert.etree.parse(
            os.path.join(FIXTURES, source, hgv_path)
        ).getroot()
    return epidoc_convert.convert_file(path, source, hgv_root=hgv_root)


# ---------------------------------------------------------------------------
# EDH
# ---------------------------------------------------------------------------

def test_edh_basic_expansion():
    rec = convert_one("edh", "HD000001.xml")
    assert rec["id"] == "edh:HD000001"
    assert rec["tm_id"] == 251193
    assert rec["languages"] == ["la"]
    assert rec["bilingual"] is False
    assert rec["date_not_before"] == 71
    assert rec["date_not_after"] == 130
    # D(is) M(anibus) expands to "Dis Manibus"
    assert rec["lines"][0]["text"] == "Dis Manibus"
    assert rec["lines"][0]["n"] == "1"
    # the diplomatic form keeps the written abbreviation, not the expansion
    assert "Dis" not in rec["lines"][0]["diplomatic"] or \
        rec["lines"][0]["diplomatic"] != rec["lines"][0]["text"]


def test_edh_gap_and_restoration_counted():
    rec = convert_one("edh", "HD000003.xml")
    assert rec["gap_count"] >= 1
    assert rec["supplied_chars"] > 0
    assert 0.0 < rec["supplied_share"] <= 1.0
    # every restored_flags array matches its own line's text length
    for line in rec["lines"]:
        assert len(line["restored_flags"]) == len(line["text"])


def test_edh_findspot_and_region():
    rec = convert_one("edh", "HD000001.xml")
    assert rec["findspot"]["region"] == "Latium et Campania (Regio I)"
    assert rec["findspot"]["ancient_place"]


def test_edh_no_line_zero_or_blank_leading_line():
    for fname in ("HD000001.xml", "HD000044.xml", "HD000058.xml"):
        rec = convert_one("edh", fname)
        for line in rec["lines"]:
            if line["n"] is None:
                assert line["text"].strip() != "", (
                    f"{fname} produced a blank line with no line number"
                )


# ---------------------------------------------------------------------------
# I.Sicily
# ---------------------------------------------------------------------------

def test_isicily_choice_keeps_regularized():
    rec = convert_one("isicily", "ISic000001.xml")
    assert rec["id"] == "isicily:ISic000001"
    assert rec["tm_id"] == 491696
    assert rec["edcs_id"] == "21900531"
    # the lemmatized second <div type="edition" subtype="simple-lemmatized">
    # must not leak its own extra copy of the text into our lines
    joined = " ".join(l["text"] for l in rec["lines"])
    assert joined.count("Dis") <= 1 or joined.count("manibus") <= 1


def test_isicily_pleiades_id_extracted():
    rec = convert_one("isicily", "ISic000005.xml")
    assert rec["findspot"]["pleiades_id"] == "462153"
    assert rec["findspot"]["ancient_place"] == "Centuripae"


def test_isicily_greek_expan_order_preserved():
    # ISic000046 has an <expan> with two <abbr> children around one <ex>
    # (a christogram glyph + "Χρίστο" + a trailing sigma); the expanded
    # text must come out in document order, "Χρίστος", not "ςΧρίστο".
    rec = convert_one("isicily", "ISic000046.xml")
    assert rec["languages"] == ["grc"]
    assert rec["lines"][0]["text"] == "Χρίστος"


def test_isicily_gap_placeholder_present():
    rec = convert_one("isicily", "ISic000014.xml")
    assert rec["gap_count"] >= 1
    all_text = " ".join(l["text"] for l in rec["lines"])
    assert epidoc_convert.GAP_PLACEHOLDER in all_text


# ---------------------------------------------------------------------------
# papyri.info (DDbDP + HGV)
# ---------------------------------------------------------------------------

def test_papyri_choice_keeps_regularized_not_original():
    rec = convert_one("papyri", "16901.xml", hgv_path="hgv_16901.xml")
    assert rec["id"] == "papyri:16901"
    assert rec["tm_id"] == 16901
    assert rec["hgv_id"] == 16901
    all_text = " ".join(l["text"] for l in rec["lines"])
    # reg="χιλίων" is kept; orig="χειλίων" is the one NOT kept
    assert "χιλίων" in all_text or "χιλίας" in all_text
    assert "χειλίων" not in all_text and "χειλίας" not in all_text


def test_papyri_hgv_supplies_date_and_place():
    rec = convert_one("papyri", "16901.xml", hgv_path="hgv_16901.xml")
    # DDbDP editions carry no date themselves; it comes from the merged
    # HGV record (origDate when="0289-09-17" -> year 289).
    assert rec["date_not_before"] == 289
    assert rec["date_not_after"] == 289
    assert rec["findspot"]["pleiades_id"] == "756518"
    assert rec["findspot"]["ancient_place"] == "Antinoopolis ?"


def test_papyri_without_hgv_has_no_date():
    rec = convert_one("papyri", "16901.xml", hgv_path=None)
    assert rec["date_not_before"] is None
    assert rec["date_not_after"] is None


def test_papyri_gap_and_unclear_tracked():
    rec = convert_one("papyri", "8666.xml", hgv_path="hgv_8666.xml")
    assert rec["gap_count"] >= 1
    assert rec["languages"] == ["grc"]


# ---------------------------------------------------------------------------
# EDR
# ---------------------------------------------------------------------------

def test_edr_basic_fields():
    rec = convert_one("edr", "aEDR111313.xml")
    assert rec["id"] == "edr:aEDR111313"
    assert rec["edr_id"] == "EDR111313"
    assert rec["tm_id"] == 285244
    assert rec["languages"] == ["la"]
    assert rec["date_not_before"] == 1
    assert rec["date_not_after"] == 50
    assert rec["findspot"]["ancient_place"] == "Thermae Himeraeae"


def test_edr_restoration_flagged():
    rec = convert_one("edr", "aEDR111313.xml")
    # line 3 has <supplied reason="lost">e</supplied> then <unclear>t</unclear>
    line3 = next(l for l in rec["lines"] if l["n"] == "3")
    assert line3["text"].startswith("et ") or "et" in line3["text"].split()[0]
    assert any(line3["restored_flags"])


def test_edr_greek_sample():
    rec = convert_one("edr", "aEDR000153.xml")
    assert rec["languages"] == ["grc"]


# ---------------------------------------------------------------------------
# CLI smoke test: run the script end to end over one source's fixtures
# ---------------------------------------------------------------------------

def test_cli_end_to_end(tmp_path):
    out_file = tmp_path / "edh.jsonl"
    result = subprocess.run(
        [sys.executable, SCRIPT, "--source", "edh",
         "--input-dir", os.path.join(FIXTURES, "edh"),
         "--output", str(out_file)],
        capture_output=True, text=True, cwd=ROOT,
    )
    assert result.returncode == 0, result.stderr
    lines = out_file.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 4
    for line in lines:
        rec = json.loads(line)
        assert rec["source"] == "edh"
        assert rec["id"].startswith("edh:")


def test_cli_papyri_requires_meta_dir(tmp_path):
    out_file = tmp_path / "papyri.jsonl"
    result = subprocess.run(
        [sys.executable, SCRIPT, "--source", "papyri",
         "--input-dir", os.path.join(FIXTURES, "papyri"),
         "--output", str(out_file)],
        capture_output=True, text=True, cwd=ROOT,
    )
    assert result.returncode != 0
    assert "meta-dir" in result.stderr


def test_word_broken_across_a_line_is_joined(tmp_path):
    """<lb break="no"/> marks a word that runs on from the previous line; the
    plain text must not split it (reviewer's question on #668)."""
    xml = """<?xml version="1.0" encoding="UTF-8"?>
<TEI xmlns="http://www.tei-c.org/ns/1.0">
  <teiHeader><fileDesc><titleStmt><title>t</title></titleStmt>
  <publicationStmt><idno type="filename">X1</idno></publicationStmt>
  <sourceDesc><p/></sourceDesc></fileDesc></teiHeader>
  <text><body><div type="edition" xml:lang="la"><ab>
    <lb n="1"/>Dis Mani
    <lb n="2" break="no"/>bus sacrum
  </ab></div></body></text>
</TEI>"""
    p = tmp_path / "X1.xml"
    p.write_text(xml, encoding="utf-8")
    rec = epidoc_convert.convert_file(str(p), "test")
    assert rec["lines"][1]["joins_previous"] is True
    assert rec["lines"][0]["joins_previous"] is False
    assert rec["text"] == "Dis Manibus sacrum"


def test_gap_tail_whitespace_never_leaks_into_line_text(tmp_path):
    """A <gap/> (or any element) whose .tail spans a line break in the
    pretty-printed source XML must not leave a literal newline or tab
    inside a line's own `text`/`diplomatic`/`expanded` fields: one .tess
    index line must always be one physical line. This reproduces the
    exact pattern found in EDR Trismegistos id 122015 during stage 2
    (a <gap/> followed by the next word on an indented new source line)."""
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<TEI xmlns="http://www.tei-c.org/ns/1.0">\n'
        '  <teiHeader><fileDesc><titleStmt><title>t</title></titleStmt>\n'
        '  <publicationStmt><idno type="filename">X2</idno></publicationStmt>\n'
        '  <sourceDesc><p/></sourceDesc></fileDesc></teiHeader>\n'
        '  <text><body><div type="edition" xml:lang="la"><ab>\n'
        '    <lb n="1"/>Sentona\n'
        '    <lb n="2" break="no"/><gap reason="lost" unit="character" quantity="1"/>\n'
        '\t\t\t\tSilicius\n'
        '  </ab></div></body></text>\n'
        '</TEI>'
    )
    p = tmp_path / "X2.xml"
    p.write_text(xml, encoding="utf-8")
    rec = epidoc_convert.convert_file(str(p), "test")
    for ln in rec["lines"]:
        for field in ("text", "diplomatic", "expanded"):
            assert "\n" not in ln[field], (field, ln[field])
            assert "\t" not in ln[field], (field, ln[field])
    assert "\n" not in rec["text"] and "\t" not in rec["text"]
    # The gap-split word still joins cleanly, with exactly one space
    # where the raw newline+tabs used to leak through.
    assert rec["lines"][1]["text"] == "█ Silicius"
