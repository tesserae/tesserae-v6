"""Tests for the Packard Humanities Institute (PHI) Greek of Attic Inscriptions
Online (AIO) documents: the converter's PHI branch, the credit rows, and the
guards that keep such a text to indexing and search. Everything here is a
made-up record in the form PHI's API returns. No PHI text is in this file."""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts", "documents"))

import aio_convert as ac  # noqa: E402
import aio_metadata as am  # noqa: E402
import backend.documents as docs  # noqa: E402
from backend.app import app  # noqa: E402
from scripts.documents.build_documents_index import build_one_language  # noqa: E402
from scripts.documents.write_document_tess import process_corpus  # noqa: E402

from test_aio_convert import PAGE_HTML, RAW  # noqa: E402


def _lines(*contents):
    return [{"number": i + 1, "content": c} for i, c in enumerate(contents)]


PHI_RECORD = {
    "phi": "999999", "book": "IG II²", "reference": "1", "site": "Athens",
    "date_text": "s. IV a.", "not_before": "-400", "not_after": "-301",
    "text": {"lines": _lines(
        "[ἔδοξεν τῆι βου]λῆι καὶ τῶι δή-",
        "μωι. {αν} vacat — c.10-11 —",
        "  Σωκράτης Ἀθη<ν>αῖος ․․5․․ (ἀναγρά)ψαι ∶ΙΙ∶",
        "[— — — — —] lacuna",
    )},
}


def test_phi_lines_brackets_gaps_and_surplus_letters():
    lines = ac.phi_lines(PHI_RECORD["text"]["lines"])
    assert lines[0]["text"] == "ἔδοξεν τῆι βουλῆι καὶ τῶι δή"
    flags = lines[0]["restored_flags"]
    assert flags[:14] == [True] * 14 and flags[14] is False
    assert lines[1]["text"] == "μωι. " + ac.GAP
    assert lines[1]["joins_previous"] is True
    assert "{" not in lines[1]["text"] and "αν" not in lines[1]["text"]
    assert lines[2]["text"] == "Σωκράτης Ἀθηναῖος " + ac.GAP + " ἀναγράψαι ΙΙ"
    assert lines[-1]["text"] == ac.GAP


def test_phi_word_broken_at_a_line_end_is_rejoined_in_the_running_text():
    lines = ac.phi_lines(PHI_RECORD["text"]["lines"][:2])
    assert "δήμωι" in ac.join_lines(lines)


def test_phi_hyphen_before_a_gap_stays_and_before_a_letter_joins():
    lines = ac.phi_lines(_lines("καὶ τῶι-", "— — —", "ἔδοξεν τῆι-", "[ἡ βου]λή"))
    assert lines[0]["text"].endswith("-")
    assert lines[2]["text"] == "ἔδοξεν τῆι" and lines[3]["joins_previous"] is True
    assert not lines[1]["joins_previous"]


def test_phi_latin_remarks_and_words_are_left_out():
    lines = ac.phi_lines(_lines("vacat", "in corona (1-7): ἔδοξεν", "Imp(eratori) Caes(ari) ἡ βουλή"))
    assert [ln["text"] for ln in lines] == ["ἔδοξεν", "ἡ βουλή"]


def test_record_with_phi_greek_credits_phi_and_aio():
    raw = dict(RAW)
    del raw["greek_epidoc"]
    rec = ac.build_record_phi(raw, "IGII2", "18", ac.parse_page(PAGE_HTML), PHI_RECORD, "999999", [])
    assert rec["id"] == "aio:IGII2_18" and rec["lines"] and rec["aio"]["greek_source"] == "phi"
    row = am.document_row(rec)
    assert row["source_name"] == ("Greek text: PHI Greek Inscriptions, The Packard Humanities Institute (PHI 999999)")
    assert row["source_url"] == "https://epigraphy.packhum.org/text/999999"
    assert row["licence_name"] == docs.INDEXING_ONLY_LICENCE and row["licence_url"] is None
    assert row["source_name_secondary"] == "Translation: Attic Inscriptions Online (Stephen Lambert and P. J. Rhodes)"
    assert row["source_url_secondary"] == "https://www.atticinscriptions.com/inscription/IGII2/18"
    assert (row["licence_name_secondary"], row["licence_url_secondary"]) == (
        "CC BY-SA 3.0", "https://creativecommons.org/licenses/by-sa/3.0/")
    assert rec["findspot"]["region"] == "Attica"


def test_date_and_findspot_come_from_aio_page_else_from_phi():
    raw = dict(RAW)
    del raw["greek_epidoc"]
    from_page = ac.build_record_phi(raw, "IGII2", "18", ac.parse_page(PAGE_HTML), PHI_RECORD, "999999", [])
    assert (from_page["date_not_before"], from_page["date_not_after"]) == (-394, -393)
    assert from_page["findspot"]["ancient_place"] == "Athens"
    no_page = ac.build_record_phi(raw, "IGII2", "18", None, PHI_RECORD, "999999", [])
    assert (no_page["date_not_before"], no_page["date_not_after"]) == (-400, -301)
    assert no_page["findspot"]["ancient_place"] == "Athens"
    assert no_page["aio"]["date_from_phi"] is True


def test_converter_main_pairs_translations_without_greek_with_phi(tmp_path):
    raw_dir, html_dir, phi_dir = tmp_path / "raw", tmp_path / "html", tmp_path / "phi"
    for d in (raw_dir, html_dir, phi_dir):
        d.mkdir()
    raw = dict(RAW)
    del raw["greek_epidoc"]
    (raw_dir / "IGII2__18.json").write_text(json.dumps(raw), encoding="utf-8")
    (html_dir / "IGII2__18.html").write_text(PAGE_HTML, encoding="utf-8")
    (phi_dir / "999999.json").write_text(json.dumps(PHI_RECORD), encoding="utf-8")
    (tmp_path / "list.json").write_text(json.dumps([{"aio": "IGII2/18", "phi": "999999"}]), encoding="utf-8")
    out = tmp_path / "out.jsonl"
    assert ac.main([str(raw_dir), str(html_dir), str(out), "--phi-dir", str(phi_dir),
                    "--phi-list", str(tmp_path / "list.json")]) == 0
    recs = [json.loads(ln) for ln in out.read_text(encoding="utf-8").splitlines()]
    assert [r["id"] for r in recs] == ["aio:IGII2_18"] and recs[0]["aio"]["greek_source"] == "phi"
    # without the PHI folder the same translation has no Greek and is not written
    out2 = tmp_path / "out2.jsonl"
    ac.main([str(raw_dir), str(html_dir), str(out2)])
    assert out2.read_text(encoding="utf-8") == ""


def test_the_licence_name_is_the_same_in_the_converter_and_the_backend():
    assert ac.PHI_LICENCE_NAME == docs.INDEXING_ONLY_LICENCE


# ---- the guards -----------------------------------------------------------

@pytest.fixture
def phi_documents_env(tmp_path, monkeypatch):
    import sqlite3
    rec = ac.build_record_phi(
        {k: v for k, v in RAW.items() if k != "greek_epidoc"}, "IGII2", "18",
        ac.parse_page(PAGE_HTML), PHI_RECORD, "999999", [])
    other = ac.build_record(RAW, "IGII2", "19", ac.parse_page(PAGE_HTML), [])
    corpus = tmp_path / "corpus.jsonl"
    with open(corpus, "w", encoding="utf-8") as f:
        for r in (rec, other):
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    texts_root = str(tmp_path / "texts_documents")
    process_corpus(str(corpus), texts_root, all_short=True)
    index_dir = str(tmp_path / "inverted_index")
    build_one_language("grc", texts_root, index_dir, str(tmp_path / "cache"), str(tmp_path / "scratch"),
                       fast_greek=True, verbose=False)
    meta = str(tmp_path / "metadata.db")
    from extract_metadata import create_schema
    conn = sqlite3.connect(meta)
    create_schema(conn)
    for r in (rec, other):
        row = am.document_row(r)
        cols = list(row)
        conn.execute(f"INSERT INTO documents ({', '.join(cols)}) VALUES ({', '.join('?' for _ in cols)})",  # nosec B608
                     [row[c] for c in cols])
    conn.commit()
    conn.close()
    monkeypatch.setenv("TESSERAE_DOCUMENTS", "1")
    monkeypatch.setenv("TESSERAE_DOCUMENTS_INDEX_DIR", index_dir)
    monkeypatch.setenv("TESSERAE_DOCUMENTS_META", meta)
    monkeypatch.setenv("TESSERAE_DOCUMENTS_RESTORED_DIR", str(tmp_path / "restored"))
    docs.reset_caches()
    yield
    docs.reset_caches()


def test_phi_document_page_shows_the_text_and_credit_but_is_marked_indexing_only(phi_documents_env):
    r = app.test_client().get("/api/documents/aio:IGII2_18?language=grc")
    assert r.status_code == 200
    data = r.get_json()
    assert data["indexing_only"] is True
    assert "δήμωι" in " ".join(ln["text"] for ln in data["lines"])
    assert data["credit"]["source_name"].startswith("Greek text: PHI Greek Inscriptions")
    assert data["credit"]["source_url"] == "https://epigraphy.packhum.org/text/999999"
    assert data["credit"]["source_name_secondary"].startswith("Translation: Attic Inscriptions Online")
    assert r.headers["X-Robots-Tag"] == "noindex, noarchive"
    assert "no-store" in r.headers["Cache-Control"]


def test_aio_own_greek_document_carries_no_indexing_only_mark(phi_documents_env):
    r = app.test_client().get("/api/documents/aio:IGII2_19?language=grc")
    assert r.status_code == 200
    assert "indexing_only" not in r.get_json()
    assert "X-Robots-Tag" not in r.headers
    assert docs.is_indexing_only("aio:IGII2_18") and not docs.is_indexing_only("aio:IGII2_19")


def test_no_documents_route_is_a_download_and_the_connector_does_not_serve_the_page():
    rules = [r.rule for r in app.url_map.iter_rules() if "document" in r.rule]
    assert rules
    assert not [r for r in rules if any(w in r for w in ("download", "export", "csv", "bulk", "zip"))]
    from backend.blueprints.mcp_manifest import MANIFEST as manifest
    assert manifest["/api/documents/<doc_id>"].get("site_only") is True
    assert manifest["/api/documents/browse"].get("site_only") is True


def test_the_public_bundle_leaves_out_the_documents_index():
    root = os.path.join(os.path.dirname(__file__), "..")
    text = open(os.path.join(root, "scripts", "ops", "public_bundle_exclusions.json"), encoding="utf-8").read()
    assert "data/inverted_index/{lang}_documents_index.db" in text
