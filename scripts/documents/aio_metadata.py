#!/usr/bin/env python3
"""Add the Attic Inscriptions Online documents to a COPY of metadata.db.

Reads the JSONL that aio_convert.py writes and inserts one `documents` row and
the `display` rows (translation with the translator's name) per inscription.
Rows of source 'aio' already in the copy are deleted first, so the script can
be run again. Never run it against the production file: the output path must
differ from the input path and may not be under /var/www.

Usage:
    aio_metadata.py AIO_JSONL METADATA_DB_COPY
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from aio_convert import (  # noqa: E402
    BBAW_LICENCE_NAME, BBAW_LICENCE_URL, BBAW_NAME, LICENCE_NAME, LICENCE_URL, PHI_LICENCE_NAME,
    SOURCE, SOURCE_NAME, phi_credit_name,
)
from extract_metadata import DOCUMENTS_COLUMNS  # noqa: E402


def credit_name(translators: str) -> str:
    return f"{SOURCE_NAME}, translation by {translators}" if translators else SOURCE_NAME


def document_row(rec: dict) -> dict:
    a = rec["aio"]
    fs = rec.get("findspot") or {}
    types = ", ".join(a.get("inscription_types") or []) or None
    row = {c: None for c in DOCUMENTS_COLUMNS}
    row.update({
        "id": rec["id"],
        "collection": "documents",
        "source": SOURCE,
        "licence_name": LICENCE_NAME,
        "licence_url": LICENCE_URL,
        "source_name": credit_name(a.get("translators")),
        "source_url": a["url"],
        "principal_edition": a.get("edition"),
        "text_type_label": types, "text_type_native": types,
        "object_type_label": a.get("monument_type"),
        "object_type_native": a.get("monument_type"),
        "date_not_before": rec.get("date_not_before"),
        "date_not_after": rec.get("date_not_after"),
        "ancient_place": fs.get("ancient_place"),
        "region": fs.get("region"),
        "pleiades_id": fs.get("pleiades_id"),
        "languages": ",".join(rec.get("languages") or ["grc"]),
        "bilingual": 1 if rec.get("bilingual") else 0,
    })
    if a.get("greek_source") == "bbaw":
        # The Greek is the Berlin edition's (primary credit), the translation AIO's (secondary).
        row.update({
            "licence_name": BBAW_LICENCE_NAME, "licence_url": BBAW_LICENCE_URL,
            "source_name": f"Greek text: {BBAW_NAME}",
            "source_url": a.get("bbaw_url"),
            "licence_name_secondary": LICENCE_NAME, "licence_url_secondary": LICENCE_URL,
            "source_name_secondary": f"Translation: {SOURCE_NAME} ({a['translators']})" if a.get("translators") else f"Translation: {SOURCE_NAME}",
            "source_url_secondary": a["url"],
        })
    if a.get("greek_source") == "phi":
        # The Greek is PHI's, used with permission for indexing and search only (primary credit),
        # the translation AIO's (secondary). The licence name has no link: there is no public licence.
        row.update({
            "licence_name": PHI_LICENCE_NAME, "licence_url": None,
            "source_name": phi_credit_name(a["phi_number"]),
            "source_url": a.get("phi_url"),
            "licence_name_secondary": LICENCE_NAME, "licence_url_secondary": LICENCE_URL,
            "source_name_secondary": f"Translation: {SOURCE_NAME} ({a['translators']})" if a.get("translators") else f"Translation: {SOURCE_NAME}",
            "source_url_secondary": a["url"],
        })
    return row


def display_rows(rec: dict) -> list:
    a = rec["aio"]
    rows = []
    if a.get("translation"):
        text = a["translation"]
        if a.get("translators"):
            text += f" (Translation by {a['translators']}, Attic Inscriptions Online.)"
        rows.append((rec["id"], "translation", text))
    return rows


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("jsonl")
    ap.add_argument("db")
    ap.add_argument("--tess", action="append", default=[],
                    help="a .tess file written by write_document_tess.py: only documents "
                         "with a line in it get a row (one inscription has no usable text)")
    a = ap.parse_args(argv)
    if os.path.realpath(a.db).startswith("/var/www"):
        print("refusing to write under /var/www", file=sys.stderr)
        return 2
    written = None
    if a.tess:
        written = set()
        for p in a.tess:
            with open(p, encoding="utf-8") as f:
                for ln in f:
                    if ln.startswith("<"):
                        written.add(ln[1:ln.index(">")].split(" ", 1)[0])
    conn = sqlite3.connect(a.db)
    conn.execute("DELETE FROM display WHERE id IN (SELECT id FROM documents WHERE source = ?)", (SOURCE,))
    conn.execute("DELETE FROM documents WHERE source = ?", (SOURCE,))
    sql = (f"INSERT INTO documents ({', '.join(DOCUMENTS_COLUMNS)}) VALUES "
           f"({', '.join('?' for _ in DOCUMENTS_COLUMNS)})")
    n = nd = 0
    skipped = []
    with open(a.jsonl, encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            rec = json.loads(line)
            if written is not None and rec["id"] not in written:
                skipped.append(rec["id"])
                continue
            row = document_row(rec)
            conn.execute(sql, [row[c] for c in DOCUMENTS_COLUMNS])
            n += 1
            for d in display_rows(rec):
                conn.execute("INSERT INTO display (id, field, value) VALUES (?, ?, ?)", d)
                nd += 1
    conn.commit()
    conn.close()
    print(f"inserted {n} documents and {nd} display rows into {a.db}; "
          f"left out (no indexed text): {skipped}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
