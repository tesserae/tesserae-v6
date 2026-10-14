#!/usr/bin/env python3
"""Build data/coins/coins.sqlite from the converter's JSONL.

    python -I scripts/coins/convert_ocre.py --ocre ... --crro ... --refs ... --output coins.jsonl
    python -I scripts/coins/build_coins_db.py --input coins.jsonl --out data/coins/coins.sqlite

One row per coin type (OCRE and CRRO records from nomisma.org, ODbL), the
columns the Coins page and /api/coins read, and an FTS5 index over
`search_text` (legends plus descriptions, lower-cased, diacritics removed).
The database is written to a temporary file next to --out and moved into
place when it is complete, so a half-built file is never read.

Data files are not committed. See docs/DATA_OPERATIONS.md for the steps.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import sys
import unicodedata

COLUMNS = [
    ("id", "TEXT NOT NULL UNIQUE"),
    ("source", "TEXT NOT NULL"),
    ("uri", "TEXT"),
    ("title", "TEXT"),
    ("authority", "TEXT"),
    ("issuer", "TEXT"),
    ("portrait", "TEXT"),
    ("mint", "TEXT"),
    ("mint_pleiades_id", "TEXT"),
    ("region", "TEXT"),
    ("denomination", "TEXT"),
    ("material", "TEXT"),
    ("date_start", "INTEGER"),
    ("date_end", "INTEGER"),
    ("obverse_legend", "TEXT"),
    ("reverse_legend", "TEXT"),
    ("obverse_description", "TEXT"),
    ("reverse_description", "TEXT"),
    ("search_text", "TEXT"),
]
INDEXED = ("source", "authority", "mint", "denomination", "material", "date_start", "date_end")


# Latin look-alike capitals inside a Greek word (BAΣΙΛΕΩΣ with a Latin B and A)
# are read as Greek, as scripts/coins/convert_ocre.py does for the legend lines.
_LATIN_TO_GREEK = {"A": "\u0391", "B": "\u0392", "E": "\u0395", "Z": "\u0396", "H": "\u0397",
                   "I": "\u0399", "K": "\u039a", "M": "\u039c", "N": "\u039d", "O": "\u039f",
                   "P": "\u03a1", "T": "\u03a4", "Y": "\u03a5", "X": "\u03a7"}


def unmix_scripts(text):
    def fix(m):
        w = m.group(0)
        if any(unicodedata.name(ch, "").startswith("GREEK") for ch in w):
            return "".join(_LATIN_TO_GREEK.get(ch, ch) for ch in w)
        return w
    return re.sub(r"\S+", fix, text)


def fold(text):
    """Lower-case and strip diacritics (Greek accents, macrons) for matching."""
    if not text:
        return ""
    d = unicodedata.normalize("NFD", unmix_scripts(str(text)))
    d = "".join(ch for ch in d if not unicodedata.combining(ch)).lower()
    # final and lunate sigma fold to the ordinary one (same rule as
    # backend/blueprints/coins.py fold), so a legend typed with any is found
    d = d.replace("\u03c2", "\u03c3").replace("\u03f2", "\u03c3")
    return re.sub(r"\s+", " ", d).strip()


def row_from_record(rec):
    mint = rec.get("mint") or {}
    parts = [rec.get("obverse_legend"), rec.get("reverse_legend"),
             rec.get("obverse_description"), rec.get("reverse_description")]
    return {
        "id": rec["id"],
        "source": rec["source"],
        "uri": rec.get("type_uri") or rec.get("source_url"),
        "title": rec.get("title"),
        "authority": rec.get("authority"),
        "issuer": rec.get("issuer"),
        "portrait": rec.get("portrait"),
        "mint": mint.get("label"),
        "mint_pleiades_id": mint.get("pleiades_id"),
        "region": rec.get("region"),
        "denomination": rec.get("denomination"),
        "material": rec.get("material"),
        "date_start": rec.get("date_not_before"),
        "date_end": rec.get("date_not_after"),
        "obverse_legend": rec.get("obverse_legend"),
        "reverse_legend": rec.get("reverse_legend"),
        "obverse_description": rec.get("obverse_description"),
        "reverse_description": rec.get("reverse_description"),
        "search_text": fold(" ".join(p for p in parts if p)),
    }


def build(input_path, out_path):
    tmp = out_path + ".building"
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    if os.path.exists(tmp):
        os.remove(tmp)
    con = sqlite3.connect(tmp)
    cols = ", ".join(f"{n} {t}" for n, t in COLUMNS)
    con.execute(f"CREATE TABLE coins (n INTEGER PRIMARY KEY, {cols})")  # nosec B608 -- fixed column list defined above
    names = [n for n, _ in COLUMNS]
    ins = f"INSERT INTO coins ({', '.join(names)}) VALUES ({', '.join('?' * len(names))})"  # nosec B608 -- fixed column list
    counts = {}
    with open(input_path, encoding="utf-8") as f:
        batch = []
        for line in f:
            if not line.strip():
                continue
            r = row_from_record(json.loads(line))
            counts[r["source"]] = counts.get(r["source"], 0) + 1
            batch.append([r[n] for n in names])
            if len(batch) >= 5000:
                con.executemany(ins, batch)
                batch = []
        if batch:
            con.executemany(ins, batch)
    con.execute("CREATE VIRTUAL TABLE coins_fts USING fts5(search_text, content='coins', "
                "content_rowid='n', tokenize='unicode61 remove_diacritics 2')")
    con.execute("INSERT INTO coins_fts(rowid, search_text) SELECT n, search_text FROM coins")
    con.execute("INSERT INTO coins_fts(coins_fts) VALUES ('optimize')")
    for c in INDEXED:
        con.execute(f"CREATE INDEX coins_{c} ON coins ({c})")  # nosec B608 -- fixed names above
    con.commit()
    total = con.execute("SELECT COUNT(*) FROM coins").fetchone()[0]
    con.execute("VACUUM")
    con.close()
    os.replace(tmp, out_path)
    return total, counts


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--input", required=True, help="converter JSONL (convert_ocre.py output)")
    ap.add_argument("--out", default="data/coins/coins.sqlite")
    args = ap.parse_args(argv)
    total, counts = build(args.input, args.out)
    print(f"wrote {args.out}: {total} types {counts}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
