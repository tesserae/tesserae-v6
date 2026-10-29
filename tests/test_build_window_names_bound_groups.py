"""Coptic names found inside bound groups (scripts/corpus/build_window_names.py).

Coptic writes a preposition, an article and a name as one written word
(ⲉⲧⲃⲉⲧϩⲓⲉⲣⲟⲩⲥⲁⲗⲏⲙ), so a surface match against the name set misses the name.
Coptic Scriptorium's parse splits the word into its parts, and the part that is
the name is tagged PROPN. These tests use a toy syntax db and a toy passage
index, no live data.
"""

import importlib.util
import json
import os
import sqlite3
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
_SPEC = importlib.util.spec_from_file_location(
    "build_window_names",
    os.path.join(ROOT, "scripts", "corpus", "build_window_names.py"),
)
bwn = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(bwn)

JER = "ϩⲓⲉⲣⲟⲩⲥⲁⲗⲏⲙ"  # Jerusalem
ISR = "ⲓⲥⲣⲁⲏⲗ"  # Israel


def _syntax_db(path):
    con = sqlite3.connect(path)
    con.execute(
        "create table texts (text_id integer primary key, filename text unique not null)"
    )
    con.execute(
        "create table syntax (text_id integer not null, ref text not null, tokens text, "
        "lemmas text, upos text, heads text, deprels text, feats text, primary key (text_id, ref))"
    )
    con.execute("insert into texts values (1, 'toy.amos.tess')")
    rows = [
        # line 1: the name is a separate token inside the bound group ⲉⲧⲃⲉⲧ+ϩⲓⲉⲣⲟⲩⲥⲁⲗⲏⲙ
        ("toy.amos.1", ["ⲉⲧⲃⲉ", "ⲧ", JER], ["ADP", "DET", "PROPN"]),
        # line 2: the written word is ⲛ+ⲓⲥⲣⲁⲏⲗ
        ("toy.amos.2", ["ⲛ", ISR], ["ADP", "PROPN"]),
        # line 3: a second use of each, so both clear min_total=2
        ("toy.amos.3", ["ⲉ", JER, "ⲙⲛ", ISR], ["ADP", "PROPN", "ADP", "PROPN"]),
        # line 4: no name
        ("toy.amos.4", ["ⲁⲩⲱ", "ⲡⲉϫⲉ"], ["CCONJ", "VERB"]),
    ]
    for ref, toks, ups in rows:
        con.execute(
            "insert into syntax values (1, ?, ?, ?, ?, ?, ?, ?)",
            (
                ref,
                json.dumps(toks),
                json.dumps(toks),
                json.dumps(ups),
                "[]",
                "[]",
                "[]",
            ),
        )
    con.commit()
    con.close()


def _passage_index(idx):
    os.makedirs(idx, exist_ok=True)
    con = sqlite3.connect(os.path.join(idx, "window_texts.db"))
    con.execute(
        "create table window_texts (id text primary key, language text, work text, "
        "ref_start text, ref_end text, text text)"
    )
    con.execute("create table lines (work text, ord integer, ref text, text text)")
    lines = [
        ("toy.amos", 0, "toy.amos.1", "ⲉⲧⲃⲉⲧ" + JER),
        ("toy.amos", 1, "toy.amos.2", "ⲛ" + ISR),
        ("toy.amos", 2, "toy.amos.3", "ⲉ" + JER + " ⲙⲛ" + ISR),
        ("toy.amos", 3, "toy.amos.4", "ⲁⲩⲱ ⲡⲉϫⲉ"),
    ]
    con.executemany("insert into lines values (?,?,?,?)", lines)
    wins = [
        ("toy.amos:a", "cop", "toy.amos", "toy.amos.1", "toy.amos.2"),
        ("toy.amos:b", "cop", "toy.amos", "toy.amos.4", "toy.amos.4"),
    ]
    for wid, lang, work, rs, re_ in wins:
        text = "\n".join(t for (_, _, r, t) in lines if rs <= r <= re_)
        con.execute(
            "insert into window_texts values (?,?,?,?,?,?)",
            (wid, lang, work, rs, re_, text),
        )
    con.commit()
    con.close()


def test_propn_by_line_reads_the_parse_parts(tmp_path):
    db = str(tmp_path / "syntax_coptic.db")
    _syntax_db(db)
    got = bwn.syntax_coptic_propn_by_line(db, lambda t: t)
    assert got == {
        "toy.amos": {"toy.amos.1": [JER], "toy.amos.2": [ISR], "toy.amos.3": [JER, ISR]}
    }


def test_window_line_refs_is_inclusive_and_tolerates_unknown_refs():
    refs = ["a.1", "a.2", "a.3"]
    lbw = {"a": (refs, {"a.1": 0, "a.2": 1, "a.3": 2})}
    assert bwn.window_line_refs(lbw, "a", "a.1", "a.2") == ["a.1", "a.2"]
    assert bwn.window_line_refs(lbw, "a", "zzz", "a.2") == []
    assert bwn.window_line_refs(lbw, "missing", "a.1", "a.2") == []


def test_names_from_parse_keeps_only_purity_set_names():
    got = bwn.names_from_parse(["r1", "r2"], {"r1": ["x", "y"], "r2": ["y"]}, {"x"})
    assert got == {"x": "x"}


def test_bound_group_name_is_found_where_the_surface_match_is_not(tmp_path):
    syn = str(tmp_path / "syntax_coptic.db")
    _syntax_db(syn)
    idx = str(tmp_path / "idx")
    _passage_index(idx)
    names = bwn.propn_purity_set(
        bwn.syntax_coptic_pairs(syn, bwn.normalize_coptic), min_total=2, min_rate=0.85
    )
    assert bwn.normalize_coptic(JER) in names and bwn.normalize_coptic(ISR) in names
    propn = bwn.syntax_coptic_propn_by_line(syn, bwn.normalize_coptic)
    con = sqlite3.connect(os.path.join(idx, "window_texts.db"))
    pairs = list(bwn.coptic_window_pairs(con, names, propn))
    by_win = {}
    for wid, k, _form in pairs:
        by_win.setdefault(wid, set()).add(k)
    # the surface match alone finds nothing: no written word equals a name
    orig, norm = bwn.tokenize_coptic(
        con.execute("select text from window_texts where id='toy.amos:a'").fetchone()[0]
    )
    assert bwn.names_in_window(orig, norm, names) == {}
    # the parse finds both
    assert by_win["toy.amos:a"] == {
        bwn.normalize_coptic(JER),
        bwn.normalize_coptic(ISR),
    }
    # a window of the nameless line gets nothing
    assert "toy.amos:b" not in by_win


def test_surface_match_is_kept_in_the_union(tmp_path):
    syn = str(tmp_path / "syntax_coptic.db")
    _syntax_db(syn)
    con = sqlite3.connect(":memory:")
    con.execute(
        "create table window_texts (id text, language text, work text, ref_start text, ref_end text, text text)"
    )
    con.execute("create table lines (work text, ord integer, ref text, text text)")
    # a window whose text holds the name as a whole written word and whose work has no parse rows
    con.execute(
        "insert into window_texts values ('w:1','cop','other.work','o.1','o.1',?)",
        (JER + " ⲁⲩⲱ",),
    )
    con.execute("insert into lines values ('other.work',0,'o.1',?)", (JER + " ⲁⲩⲱ",))
    names = {bwn.normalize_coptic(JER)}
    pairs = list(bwn.coptic_window_pairs(con, names, {}))
    assert [(w, k) for w, k, _ in pairs] == [("w:1", bwn.normalize_coptic(JER))]


def test_rebuild_coptic_only_leaves_other_languages_byte_identical(tmp_path):
    syn = str(tmp_path / "syntax_coptic.db")
    _syntax_db(syn)
    idx = str(tmp_path / "idx")
    _passage_index(idx)
    con = sqlite3.connect(os.path.join(idx, "window_texts.db"))
    con.execute(
        "insert into window_texts values ('la:1','la','virgil.aen','v.1','v.1','Roma')"
    )
    con.commit()
    con.close()
    live = str(tmp_path / "live.db")
    c = sqlite3.connect(live)
    c.execute("create table window_names (id text, k text, form text)")
    c.execute("create table name_df (k text primary key, df integer)")
    c.execute("create table meta (key text, value text)")
    c.execute("insert into window_names values ('la:1','roma','Roma')")
    c.execute("insert into name_df values ('roma', 1)")
    c.execute("insert into meta values ('windows_cop', '2')")
    c.commit()
    c.close()
    out = str(tmp_path / "out.db")
    old_n, new_n = bwn.rebuild_coptic_only(live, out, idx_dir=idx, syntax_db=syn)
    assert (old_n, new_n) == (0, 2)
    o = sqlite3.connect(out)
    assert o.execute("select * from window_names where id='la:1'").fetchall() == [
        ("la:1", "roma", "Roma")
    ]
    assert o.execute("select df from name_df where k='roma'").fetchone() == (1,)
    k = bwn.normalize_coptic(JER)
    assert o.execute("select df from name_df where k=?", (k,)).fetchone() == (1,)
    assert o.execute("pragma integrity_check").fetchone() == ("ok",)
