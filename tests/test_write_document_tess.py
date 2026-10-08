"""Tests for scripts/documents/write_document_tess.py, using small inline
fixtures (no network, no corpus data)."""
import json
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scripts.corpus.validate_tess import check as validate_tess_check
from scripts.documents.restoration_tokens import GAP_PLACEHOLDER as GAP
from scripts.documents.write_document_tess import (
    assign_language,
    build_long_doc_lines,
    build_short_doc_unit,
    doc_id_of,
    process_corpus,
)

# The same regex backend/text_processor.py's process_file uses to read an
# existing .tess file (copied literally here, the way index_layout.py's own
# TESS_LINE_RE does, to self-check against the real loader's own rule).
PROCESS_FILE_RE = re.compile(r'^<([^>]+)>\s*(.+)$')


def _flags(text, restored_spans=()):
    flags = [False] * len(text)
    for start, end in restored_spans:
        for i in range(start, end):
            flags[i] = True
    return flags


def _line(n, text, restored_spans=()):
    return {"n": str(n), "text": text, "diplomatic": text,
            "restored_flags": _flags(text, restored_spans), "joins_previous": False}


def _rec(doc_id, source, lines, languages=("la",), region=None, date_not_before=None):
    return {
        "id": doc_id, "source": source, "tm_id": 1,
        "languages": list(languages),
        "findspot": {"region": region},
        "date_not_before": date_not_before,
        "lines": lines,
    }


def test_assign_language_pure_la_or_grc_only():
    assert assign_language(_rec("edh:X", "edh", [], languages=("la",))) == "la"
    assert assign_language(_rec("edh:X", "edh", [], languages=("grc",))) == "grc"
    assert assign_language(_rec("edh:X", "edh", [], languages=("la,grc",))) is None
    assert assign_language(_rec("edh:X", "edh", [], languages=("cop",))) is None
    assert assign_language(_rec("edh:X", "edh", [], languages=())) is None


def test_doc_id_of_uses_the_merged_corpus_id_field_unchanged():
    rec = _rec("papyri:290109", "papyri", [])
    assert doc_id_of(rec) == "papyri:290109"


def test_short_doc_joins_lines_with_slash_and_drops_pure_gap_token():
    rec = _rec("edh:HD000001", "edh", [
        _line(1, "Quintus Etuvius"),
        _line(2, f"Vol{GAP}Capreolus"),
    ])
    text, restored_idx, fragment_idx, gaps = build_short_doc_unit(rec)
    # "Vol█Capreolus" splits into two fragment pieces at the gap.
    assert text == "Quintus Etuvius / Vol Capreolus"
    assert GAP not in text
    assert fragment_idx  # the split pieces are flagged
    assert gaps == 1  # the one gap character is still dropped and counted,
    # even though it split a token into fragments rather than being its own
    # all-gap token


def test_pure_gap_token_dropped_and_counted():
    rec = _rec("edh:HD000002", "edh", [
        _line(1, f"dedit {GAP}{GAP} Sentonae"),
    ])
    text, restored_idx, fragment_idx, gaps = build_short_doc_unit(rec)
    assert GAP not in text
    assert text == "dedit Sentonae"
    assert gaps == 2  # both gap characters counted


def test_restored_word_marked_and_indexed():
    # "filius" entirely supplied by the editor (restored=True).
    rec = _rec("edh:HD000003", "edh", [
        _line(1, "Sexti filius", restored_spans=[(6, 12)]),
    ])
    text, restored_idx, fragment_idx, gaps = build_short_doc_unit(rec)
    tokens = text.split(" ")
    assert tokens[1] == "filius"
    assert restored_idx == [1]
    assert fragment_idx == []


def test_long_doc_line_numbers_are_array_position_not_n_field():
    # "n" repeats (e.g. a bilingual two-column inscription); position must
    # still be unique.
    lines = [_line("1", f"line a {i}") for i in range(1, 13)]
    rec = _rec("merged:1", "edh+edr", lines)
    doc_lines, gaps = build_long_doc_lines(rec)
    assert [ln[0] for ln in doc_lines] == list(range(1, 13))


def _write_corpus(tmp_path, records):
    path = os.path.join(tmp_path, "merged_corpus.jsonl")
    with open(path, "w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return path


def test_short_and_long_documents_pack_into_the_same_bucket_file(tmp_path):
    short_lines = [_line(1, "Dis Manibus"), _line(2, "Euhodia")]
    long_lines = [_line(i, f"verse {i}") for i in range(1, 13)]
    records = [
        _rec("edh:SHORT1", "edh", short_lines, region="Dalmatia"),
        _rec("edh:LONG1", "edh", long_lines, region="Dalmatia"),
    ]
    input_path = _write_corpus(tmp_path, records)
    out_root = os.path.join(tmp_path, "texts_documents")
    result = process_corpus(input_path, out_root)
    assert not result["regex_failures"]

    tess_path = os.path.join(out_root, "la", "edh__dalmatia.tess")
    assert os.path.exists(tess_path)
    with open(tess_path, encoding="utf-8") as f:
        lines = [ln.rstrip("\n") for ln in f if ln.strip()]
    # 1 short-doc line + 12 long-doc lines in ONE packed file.
    assert len(lines) == 13
    assert lines[0] == "<edh:SHORT1>\tDis Manibus / Euhodia"
    assert lines[1].startswith("<edh:LONG1 1>\t")
    assert lines[-1].startswith("<edh:LONG1 12>\t")


def test_ref_syntax_round_trips_through_both_tess_parsers(tmp_path):
    records = [
        _rec("edh:SHORT1", "edh", [_line(1, "Dis Manibus")], region="Dalmatia"),
        _rec("edh:LONG1", "edh", [_line(i, f"verse {i}") for i in range(1, 13)],
             region="Dalmatia"),
    ]
    input_path = _write_corpus(tmp_path, records)
    out_root = os.path.join(tmp_path, "texts_documents")
    process_corpus(input_path, out_root)
    tess_path = os.path.join(out_root, "la", "edh__dalmatia.tess")

    with open(tess_path, encoding="utf-8") as f:
        for raw in f:
            raw = raw.rstrip("\n")
            assert PROCESS_FILE_RE.match(raw), f"text_processor regex failed: {raw!r}"

    # validate_tess.py's own checker (literal tab, duplicate/monotonic refs).
    assert validate_tess_check(tess_path) is True


def test_bilingual_and_other_language_documents_are_skipped(tmp_path):
    records = [
        _rec("edh:BILINGUAL", "edh", [_line(1, "both scripts")], languages=("la,grc",)),
        _rec("edh:COPTIC", "edh", [_line(1, "coptic text")], languages=("cop",)),
        _rec("edh:LATIN", "edh", [_line(1, "Dis Manibus")], languages=("la",)),
    ]
    input_path = _write_corpus(tmp_path, records)
    out_root = os.path.join(tmp_path, "texts_documents")
    result = process_corpus(input_path, out_root)
    assert result["by_lang"]["la"]["documents"] == 1
    assert sum(result["skipped_other_language"].values()) == 2


def test_fully_gapped_document_is_skipped_not_written_empty(tmp_path):
    records = [
        _rec("edh:ALLGAP", "edh", [_line(1, GAP * 5)]),
        _rec("edh:LATIN", "edh", [_line(1, "Dis Manibus")]),
    ]
    input_path = _write_corpus(tmp_path, records)
    out_root = os.path.join(tmp_path, "texts_documents")
    result = process_corpus(input_path, out_root)
    assert result["empty_skipped"]["la"] == 1
    assert result["by_lang"]["la"]["documents"] == 1


def test_literary_index_and_backend_are_never_imported_or_touched():
    import ast
    import scripts.documents.write_document_tess as wdt
    src = open(wdt.__file__, encoding="utf-8").read()
    assert "data/inverted_index" not in src
    tree = ast.parse(src)
    imported_names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_names.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_names.add(node.module.split(".")[0])
    assert "backend" not in imported_names
