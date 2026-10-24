"""Tests for scripts/documents/remove_placeholder_documents.py on a small
synthetic index and metadata pair (hand-built tables with the same columns the
real build writes)."""
import os
import sqlite3
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scripts.documents import remove_placeholder_documents as rpd  # noqa: E402

P = rpd.PLACEHOLDER


def _build(tmp_path, with_postings_for_placeholder=False):
    idx_path = str(tmp_path / "grc_documents_index.db")
    meta_path = str(tmp_path / "metadata.db")
    c = sqlite3.connect(idx_path)
    c.executescript("""
    CREATE TABLE texts (text_id INTEGER PRIMARY KEY, filename TEXT UNIQUE, author TEXT, title TEXT, line_count INTEGER);
    CREATE TABLE postings (lemma TEXT, text_id INTEGER, ref TEXT, positions TEXT);
    CREATE TABLE lines (text_id INTEGER, ref TEXT, content TEXT, lemmas TEXT, tokens TEXT, PRIMARY KEY (text_id, ref));
    CREATE TABLE lemma_doc_freq (lemma TEXT PRIMARY KEY, df INTEGER);
    CREATE TABLE doc_meta (doc_id TEXT PRIMARY KEY, text_id INTEGER, first_ref TEXT, last_ref TEXT);
    """)
    c.execute("INSERT INTO texts VALUES (1,'papyri__a.tess','papyri__a','',5)")
    c.execute("INSERT INTO texts VALUES (2,'papyri__b.tess','papyri__b','',1)")
    rows = [
        (1, "papyri:1", P),
        (1, "papyri:2", "καλως ποιησεις"),
        (1, "papyri:3 1", "καλως"),
        (1, "papyri:3 2", P),  # a real document with a placeholder line: kept
        (1, "papyri:4", " " + P + "  "),
        (2, "papyri:5", P),
    ]
    for t, ref, content in rows:
        c.execute("INSERT INTO lines VALUES (?,?,?,?,?)", (t, ref, content, "[]", "[]"))
        c.execute("INSERT OR REPLACE INTO doc_meta VALUES (?,?,?,?)",
                  (ref.split(" ")[0], t, ref, ref))
    c.execute("INSERT INTO postings VALUES ('καλως',1,'papyri:2','[0]')")
    c.execute("INSERT INTO postings VALUES ('καλως',1,'papyri:3 1','[0]')")
    c.execute("INSERT INTO postings VALUES ('ποιεω',1,'papyri:2','[1]')")
    if with_postings_for_placeholder:
        c.execute("INSERT INTO postings VALUES ('οὐδεν',2,'papyri:5','[0]')")
        c.execute("INSERT INTO postings VALUES ('καλως',2,'papyri:5','[0]')")
    c.execute("INSERT INTO lemma_doc_freq VALUES ('καλως',1)")
    c.execute("INSERT INTO lemma_doc_freq VALUES ('ποιεω',1)")
    c.commit()
    c.close()
    m = sqlite3.connect(meta_path)
    m.executescript("""
    CREATE TABLE documents (id TEXT PRIMARY KEY, collection TEXT, source TEXT);
    CREATE TABLE display (id TEXT, field TEXT, value TEXT);
    """)
    for i in ("papyri:1", "papyri:2", "papyri:3", "papyri:4", "papyri:5"):
        m.execute("INSERT INTO documents VALUES (?,?,?)", (i, "papyri", "papyri"))
        m.execute("INSERT INTO display VALUES (?,?,?)", (i, "museum", "M " + i))
    m.commit()
    m.close()
    return idx_path, meta_path


def _ids(path, sql):
    c = sqlite3.connect(path)
    try:
        return sorted(r[0] for r in c.execute(sql))
    finally:
        c.close()


def test_is_placeholder_text():
    assert rpd.is_placeholder_text(P)
    assert rpd.is_placeholder_text("  " + P + "\n")
    assert rpd.is_placeholder_text(P + " " + P)
    assert not rpd.is_placeholder_text("")
    assert not rpd.is_placeholder_text("καλως")
    assert not rpd.is_placeholder_text(P + " καλως")


def test_removes_only_placeholder_documents(tmp_path, capsys):
    idx, meta = _build(tmp_path)
    assert rpd.main([idx, meta]) == 0
    assert _ids(idx, "SELECT ref FROM lines") == ["papyri:2", "papyri:3 1", "papyri:3 2"]
    assert _ids(idx, "SELECT doc_id FROM doc_meta") == ["papyri:2", "papyri:3"]
    assert _ids(meta, "SELECT id FROM documents") == ["papyri:2", "papyri:3"]
    assert _ids(meta, "SELECT DISTINCT id FROM display") == ["papyri:2", "papyri:3"]
    assert _ids(idx, "SELECT line_count FROM texts ORDER BY text_id") == [0, 3]
    out = capsys.readouterr().out
    assert "3 distinct ids" in out
    assert "CHANGED" not in out
    assert "integrity_check: ok ok" in out


def test_idempotent(tmp_path, capsys):
    idx, meta = _build(tmp_path)
    assert rpd.main([idx, meta]) == 0
    before = (_ids(idx, "SELECT ref FROM lines"), _ids(meta, "SELECT id FROM documents"),
              _ids(idx, "SELECT line_count FROM texts ORDER BY text_id"))
    capsys.readouterr()
    assert rpd.main([idx, meta]) == 0
    assert "already clean" in capsys.readouterr().out
    assert before == (_ids(idx, "SELECT ref FROM lines"), _ids(meta, "SELECT id FROM documents"),
                      _ids(idx, "SELECT line_count FROM texts ORDER BY text_id"))


def test_dry_run_changes_nothing(tmp_path, capsys):
    idx, meta = _build(tmp_path)
    h = (os.path.getsize(idx), _ids(idx, "SELECT ref FROM lines"))
    assert rpd.main([idx, meta, "--dry-run"]) == 0
    assert h == (os.path.getsize(idx), _ids(idx, "SELECT ref FROM lines"))
    assert "3 distinct ids" in capsys.readouterr().out
    assert _ids(meta, "SELECT id FROM documents") == [f"papyri:{i}" for i in range(1, 6)]


def test_postings_and_doc_freq_follow(tmp_path):
    idx, meta = _build(tmp_path, with_postings_for_placeholder=True)
    assert rpd.main([idx, meta]) == 0
    assert _ids(idx, "SELECT DISTINCT ref FROM postings") == ["papyri:2", "papyri:3 1"]
    c = sqlite3.connect(idx)
    df = dict(c.execute("SELECT lemma, df FROM lemma_doc_freq"))
    c.close()
    # text 2 is gone from the postings, so only papyri__a.tess has these lemmas
    assert df == {"καλως": 1, "ποιεω": 1}


def test_refuses_production_path():
    with pytest.raises(SystemExit):
        rpd._guard("/var/www/tesseraev6_flask/data/documents/metadata.db")
