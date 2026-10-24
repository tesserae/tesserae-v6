#!/usr/bin/env python3
"""Remove the placeholder papyri from a Greek documents index and its metadata.

papyri.info has about six thousand records whose only text is the sentence
"This text has not been added to papyri.info yet." They have no words, so
they never match a search, but they show up in Browse lists and counts, and a
reader who opens one sees no text. This script finds every document whose
whole indexed text is that sentence (or empty apart from it) and removes it
from every table of both files that is keyed by a document id.

Usage:
    remove_placeholder_documents.py INDEX_DB METADATA_DB [--dry-run]

Tables and what happens to them:
  INDEX_DB  lines          rows of the document deleted (key: text_id, ref)
            postings       rows of those lines deleted (key: text_id, ref)
            doc_meta       row of the document deleted (key: doc_id)
            texts          line_count lowered by the deleted lines, row kept
            lemma_doc_freq recomputed (same SQL as build_inverted_index.py)
                           only if a posting was deleted, else untouched
  METADATA  documents      row deleted (key: id)
            display        rows deleted (key: id)

The script edits the two files in place, so run it on copies. It refuses a
path under /var/www. It is idempotent. Before and after it prints, per table,
the row count and an order-independent hash of every row that is not removed,
and stops with exit code 2 if any of those hashes changed.
"""
from __future__ import annotations

import argparse
import hashlib
import os
import re
import sqlite3
import sys

PLACEHOLDER = "This text has not been added to papyri.info yet."
_WS = re.compile(r"\s+")


def is_placeholder_text(joined: str) -> bool:
    """True when the folded text is the placeholder, repeated or not, and
    nothing else."""
    folded = _WS.sub(" ", joined).strip()
    if PLACEHOLDER not in folded:
        return False
    return folded.replace(PLACEHOLDER, "").strip() == ""


def _guard(path: str) -> None:
    if os.path.realpath(path).startswith("/var/www"):
        raise SystemExit(f"refusing {path}: resolves under /var/www, run on a copy")
    if not os.path.isfile(path):
        raise SystemExit(f"no such file: {path}")


def find_placeholder_docs(conn: sqlite3.Connection):
    """Return (doc_ids, line_keys): the set of document ids and the list of
    (text_id, ref) of every line of those documents."""
    docs: dict[tuple[int, str], list] = {}
    for text_id, ref, content in conn.execute(
            "SELECT text_id, ref, content FROM lines ORDER BY rowid"):
        doc_id = ref.split(" ", 1)[0]
        d = docs.setdefault((text_id, doc_id), [[], []])
        d[0].append(content or "")
        d[1].append(ref)
    doc_ids: set[str] = set()
    line_keys: list[tuple[int, str]] = []
    for (text_id, doc_id), (contents, refs) in docs.items():
        if is_placeholder_text(" ".join(contents)):
            doc_ids.add(doc_id)
            line_keys.extend((text_id, r) for r in refs)
    return doc_ids, line_keys


def _row_hash(row) -> int:
    h = hashlib.sha256(repr(row).encode("utf-8")).digest()
    return int.from_bytes(h[:8], "big")


def table_fingerprint(conn, sql: str, params=()) -> tuple[int, int]:
    n = 0
    acc = 0
    for row in conn.execute(sql, params):
        n += 1
        acc = (acc + _row_hash(row)) & 0xFFFFFFFFFFFFFFFF
    return n, acc


def fingerprints(idx, meta, doc_ids, line_keys) -> dict:
    """Fingerprint of every row that stays, per table."""
    removed_lines = set(line_keys)
    out = {}
    out["lines"] = table_fingerprint_filtered(
        idx, "SELECT text_id, ref, content, lemmas, tokens FROM lines",
        lambda r: (r[0], r[1]) not in removed_lines)
    out["postings"] = table_fingerprint_filtered(
        idx, "SELECT lemma, text_id, ref, positions FROM postings",
        lambda r: (r[1], r[2]) not in removed_lines)
    out["doc_meta"] = table_fingerprint_filtered(
        idx, "SELECT doc_id, text_id, first_ref, last_ref FROM doc_meta",
        lambda r: r[0] not in doc_ids)
    out["texts (without line_count)"] = table_fingerprint(
        idx, "SELECT text_id, filename, author, title FROM texts")
    out["lemma_doc_freq"] = table_fingerprint(
        idx, "SELECT lemma, df FROM lemma_doc_freq")
    out["documents"] = table_fingerprint_filtered(
        meta, "SELECT * FROM documents", lambda r: r[0] not in doc_ids)
    out["display"] = table_fingerprint_filtered(
        meta, "SELECT id, field, value FROM display", lambda r: r[0] not in doc_ids)
    return out


def table_fingerprint_filtered(conn, sql, keep) -> tuple[int, int]:
    n = 0
    acc = 0
    for row in conn.execute(sql):
        if keep(row):
            n += 1
            acc = (acc + _row_hash(row)) & 0xFFFFFFFFFFFFFFFF
    return n, acc


def counts(idx, meta) -> dict:
    q = lambda c, s: c.execute(s).fetchone()[0]  # noqa: E731
    return {
        "texts": q(idx, "SELECT COUNT(*) FROM texts"),
        "texts.sum(line_count)": q(idx, "SELECT COALESCE(SUM(line_count),0) FROM texts"),
        "lines": q(idx, "SELECT COUNT(*) FROM lines"),
        "postings": q(idx, "SELECT COUNT(*) FROM postings"),
        "doc_meta": q(idx, "SELECT COUNT(*) FROM doc_meta"),
        "lemma_doc_freq": q(idx, "SELECT COUNT(*) FROM lemma_doc_freq"),
        "documents": q(meta, "SELECT COUNT(*) FROM documents"),
        "documents distinct ids": q(meta, "SELECT COUNT(DISTINCT id) FROM documents"),
        "display": q(meta, "SELECT COUNT(*) FROM display"),
        "display distinct ids": q(meta, "SELECT COUNT(DISTINCT id) FROM display"),
    }


def rebuild_lemma_doc_freq(idx) -> None:
    base = ("CASE WHEN instr(t.filename,'.part.')>0 "
            "THEN substr(t.filename,1,instr(t.filename,'.part.')-1)||'.tess' "
            "ELSE t.filename END")
    idx.execute("DROP TABLE IF EXISTS lemma_doc_freq")
    idx.execute("CREATE TABLE lemma_doc_freq (lemma TEXT PRIMARY KEY, df INTEGER)")
    idx.execute(
        "INSERT INTO lemma_doc_freq (lemma, df) "  # nosec B608
        f"SELECT p.lemma, COUNT(DISTINCT {base}) "
        "FROM postings p JOIN texts t ON p.text_id = t.text_id GROUP BY p.lemma")


def remove(idx, meta, doc_ids, line_keys) -> dict:
    per_text: dict[int, int] = {}
    for text_id, _ref in line_keys:
        per_text[text_id] = per_text.get(text_id, 0) + 1
    postings_removed = 0
    for text_id, ref in line_keys:
        cur = idx.execute(
            "DELETE FROM postings WHERE text_id = ? AND ref = ?", (text_id, ref))
        postings_removed += cur.rowcount
        idx.execute("DELETE FROM lines WHERE text_id = ? AND ref = ?", (text_id, ref))
    for d in doc_ids:
        idx.execute("DELETE FROM doc_meta WHERE doc_id = ?", (d,))
    for text_id, n in per_text.items():
        idx.execute(
            "UPDATE texts SET line_count = line_count - ? WHERE text_id = ?", (n, text_id))
    if postings_removed:
        rebuild_lemma_doc_freq(idx)
    for d in doc_ids:
        meta.execute("DELETE FROM documents WHERE id = ?", (d,))
        meta.execute("DELETE FROM display WHERE id = ?", (d,))
    idx.commit()
    meta.commit()
    return {"postings_removed": postings_removed}


def print_counts(label: str, c: dict) -> None:
    print(f"-- {label}")
    for k, v in c.items():
        print(f"   {k:28s} {v:>12,}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("index_db")
    ap.add_argument("metadata_db")
    ap.add_argument("--dry-run", action="store_true",
                    help="report what would be removed, change nothing")
    a = ap.parse_args(argv)
    _guard(a.index_db)
    _guard(a.metadata_db)

    if a.dry_run:
        idx = sqlite3.connect(f"file:{a.index_db}?mode=ro", uri=True)
        meta = sqlite3.connect(f"file:{a.metadata_db}?mode=ro", uri=True)
    else:
        idx = sqlite3.connect(a.index_db)
        meta = sqlite3.connect(a.metadata_db)

    doc_ids, line_keys = find_placeholder_docs(idx)
    in_meta = 0
    for i in range(0, len(doc_ids), 500):
        chunk = list(doc_ids)[i:i + 500]
        in_meta += meta.execute(
            "SELECT COUNT(*) FROM documents WHERE id IN (%s)" % ",".join("?" * len(chunk)),
            chunk).fetchone()[0]
    print(f"placeholder documents found: {len(doc_ids):,} distinct ids, "
          f"{len(line_keys):,} lines, {in_meta:,} with a documents row")
    before = counts(idx, meta)
    print_counts("before", before)
    if a.dry_run:
        print("dry run: nothing changed")
        return 0
    if not doc_ids:
        print("nothing to remove (already clean)")
        print("integrity_check:", idx.execute("PRAGMA integrity_check").fetchone()[0],
              meta.execute("PRAGMA integrity_check").fetchone()[0])
        return 0

    fp_before = fingerprints(idx, meta, doc_ids, line_keys)
    info = remove(idx, meta, doc_ids, line_keys)
    after = counts(idx, meta)
    print_counts("after", after)
    print(f"postings removed: {info['postings_removed']:,}")
    fp_after = fingerprints(idx, meta, set(), [])
    bad = 0
    print("-- hash of every kept row (rows, hash), before against after")
    for k in fp_before:
        same = fp_before[k] == fp_after[k]
        bad += not same
        print(f"   {k:28s} {fp_before[k][0]:>10,} {fp_before[k][1]:016x} "
              f"{'identical' if same else 'CHANGED ' + str(fp_after[k])}")
    left = find_placeholder_docs(idx)[0]
    print(f"placeholder documents left: {len(left)}")
    print("integrity_check:", idx.execute("PRAGMA integrity_check").fetchone()[0],
          meta.execute("PRAGMA integrity_check").fetchone()[0])
    return 2 if bad or left else 0


if __name__ == "__main__":
    sys.exit(main())
