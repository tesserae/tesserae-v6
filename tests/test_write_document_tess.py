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


# ---------------------------------------------------------------------------
# gap_before in the restored-word sidecar (where the stone has a gap)
# ---------------------------------------------------------------------------

def test_short_doc_gap_positions_leading_middle_trailing():
    # "[---]uf [---][IIvir(i)] (duoviri) [---]" in one line, then a gap-only line, then text.
    rec = _rec("edr:G1", "edr", [
        _line(1, f"{GAP}uf IIviri {GAP} (duoviri) {GAP}"),
        _line(2, f"{GAP}"),
        _line(3, "ob honorem"),
    ])
    text, _r, _f, _g = build_short_doc_unit(rec)
    assert text == "uf IIviri (duoviri) / ob honorem"
    from scripts.documents.write_document_tess import build_short_doc_unit_gaps
    gap_before = build_short_doc_unit_gaps(rec)[-1]["gap_before"]
    # Counted in the index's token list (the "/" is not a token there):
    # before "uf" (0), before "(duoviri)" (2), and, for the end of line 1 and
    # for the gap-only line after it, before "ob" (3), once.
    assert gap_before == [0, 2, 3]


def test_gap_inside_a_word_marks_the_position_between_the_fragments():
    rec = _rec("edr:G2", "edr", [_line(1, f"Ca{GAP}nio Octavio")])
    from scripts.documents.write_document_tess import build_short_doc_unit_gaps
    text, _r, fragment, _g, extra = build_short_doc_unit_gaps(rec)
    gap_before = extra["gap_before"]
    assert text == "Ca nio Octavio"
    assert fragment == [0, 1]
    assert gap_before == [1]


def test_gap_only_document_is_still_skipped():
    rec = _rec("edr:G3", "edr", [_line(1, f"{GAP}{GAP}")])
    from scripts.documents.write_document_tess import build_short_doc_unit_gaps
    assert build_short_doc_unit_gaps(rec)[0] is None


def test_long_doc_lines_carry_their_own_gap_positions():
    from scripts.documents.write_document_tess import build_long_doc_lines_gaps
    rec = _rec("edr:G4", "edr", [_line(1, f"{GAP} aaa bbb"), _line(2, f"ccc {GAP}"), _line(3, "ddd")])
    lines, _ = build_long_doc_lines_gaps(rec)
    assert [(n, g["gap_before"]) for n, _t, _r, _f, g in lines] == [(1, [0]), (2, [1]), (3, [])]
    # the four-item form callers already use is unchanged
    old, _ = build_long_doc_lines(rec)
    assert all(len(x) == 4 for x in old)


def test_sidecar_file_has_gap_before_for_every_line(tmp_path):
    src = tmp_path / "merged.jsonl"
    recs = [_rec("edr:G5", "edr", [_line(1, f"{GAP}uf IIviri")], region="Roma"),
            _rec("edr:G6", "edr", [_line(1, "plain words here")], region="Roma")]
    src.write_text("\n".join(json.dumps(r) for r in recs) + "\n", encoding="utf-8")
    out = tmp_path / "out"
    process_corpus(str(src), str(out))
    rows = []
    for name in os.listdir(out / "la"):
        if name.endswith(".restored_words.jsonl"):
            rows += [json.loads(x) for x in (out / "la" / name).read_text(encoding="utf-8").splitlines()]
    by_ref = {r["ref"]: r for r in rows}
    assert by_ref["edr:G5"]["gap_before"] == [0]
    assert by_ref["edr:G6"]["gap_before"] == []
    assert by_ref["edr:G5"]["restored"] == [] and "fragment" in by_ref["edr:G5"]


def test_index_token_rule_matches_the_index_builders_tokenizers():
    from scripts.build_inverted_index import tokenize_greek_fast, tokenize_latin_fast
    from scripts.documents.write_document_tess import _makes_index_token
    for w in ["Lucius", "/", "12", "IIviri", "(duoviri)", "·", "Aug.", "VIvir", "iuvenis", "-", ":(%1000)"]:
        assert _makes_index_token(w, "la") == bool(tokenize_latin_fast(w)), w
    for w in ["Ἀθηναῖοι", "/", "12", "·", "καὶ", "(βουλή)", "αβ-γδ"]:
        assert _makes_index_token(w, "grc") == bool(tokenize_greek_fast(w)), w


def test_gap_positions_follow_the_index_token_list_across_slashes():
    from scripts.documents.write_document_tess import build_short_doc_unit_gaps
    # "alpha / beta █ gamma": the written stream is alpha / beta gamma (the "/"
    # is position 1) but the index holds alpha beta gamma, so the gap before
    # "gamma" is index 2, not stream position 3.
    rec = _rec("edr:G7", "edr", [_line(1, "alpha"), _line(2, f"beta {GAP} gamma")])
    text, _r, _f, _g, extra = build_short_doc_unit_gaps(rec)
    gap_before = extra["gap_before"]
    assert text == "alpha / beta gamma"
    assert gap_before == [2]


# ---------------------------------------------------------------------------
# gloss_indices in the sidecar (an editor's gloss on a word already written out)
# ---------------------------------------------------------------------------

def _gloss_line(n, text, gloss_spans):
    ln = _line(n, text)
    flags = [False] * len(text)
    for a, b in gloss_spans:
        for i in range(a, b):
            flags[i] = True
    ln["gloss_flags"] = flags
    return ln


def test_gloss_tokens_are_flagged_in_the_index_token_space():
    from scripts.documents.write_document_tess import build_short_doc_unit_gaps
    # "alpha / IIviri (duoviri) 12 (tria milia)": the "/" and "12" are not index tokens
    t = "IIviri (duoviri) 12 (tria milia)"
    a = t.index("(duoviri)")
    b = t.index("(tria")
    rec = _rec("edr:L1", "edr", [_line(1, "alpha"),
                                 _gloss_line(2, t, [(a, a + 9), (b, b + 12)])])
    text, _r, _f, _g, extra = build_short_doc_unit_gaps(rec)
    assert text == "alpha / IIviri (duoviri) 12 (tria milia)"
    # index tokens: alpha iiuiri duouiri tria milia (the "12" and "/" are not tokens)
    assert extra["gloss_indices"] == [2, 3, 4]


def test_gloss_flags_follow_a_joined_line_and_a_line_without_gloss():
    from scripts.documents.write_document_tess import build_short_doc_unit_gaps
    first = _line(1, "Aug")
    second = _gloss_line(2, "(usti)", [(0, 6)])
    second["joins_previous"] = True
    rec = _rec("edr:L2", "edr", [first, second])
    text, _r, _f, _g, extra = build_short_doc_unit_gaps(rec)
    assert text == "Aug(usti)"
    # the joined word is six characters of gloss in nine: a majority, so it is a gloss token
    assert extra["gloss_indices"] == [0]
    rec2 = _rec("edr:L3", "edr", [_line(1, "plain words")])
    assert build_short_doc_unit_gaps(rec2)[-1]["gloss_indices"] == []


def test_sidecar_file_has_gloss_indices(tmp_path):
    src = tmp_path / "merged.jsonl"
    t = "uf IIviri (duoviri)"
    a = t.index("(")
    recs = [_rec("edr:L4", "edr", [_gloss_line(1, t, [(a, len(t))])], region="Roma"),
            _rec("edr:L5", "edr", [_line(1, "plain words here")], region="Roma")]
    src.write_text("\n".join(json.dumps(r) for r in recs) + "\n", encoding="utf-8")
    out = tmp_path / "out"
    process_corpus(str(src), str(out))
    rows = {}
    for name in os.listdir(out / "la"):
        if name.endswith(".restored_words.jsonl"):
            for x in (out / "la" / name).read_text(encoding="utf-8").splitlines():
                r = json.loads(x)
                rows[r["ref"]] = r
    assert rows["edr:L4"]["gloss_indices"] == [2]
    assert rows["edr:L5"]["gloss_indices"] == []
