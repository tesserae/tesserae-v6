#!/usr/bin/env python3
"""Build data/objects/objects.sqlite from the museum records fetch_objects.py wrote.

    python -I scripts/objects/build_objects_db.py \\
        --cleveland DIR --chicago DIR --smithsonian DIR --out data/objects/objects.sqlite

Each DIR holds a records.jsonl. One row per object: id (museum code and
accession), museum, title, object_type, culture, date_text, date_start,
date_end (signed years, -500 is 500 BCE), material, place_text, description
(the curator's text), short_text (tombstone or label), inscription_text,
image_url, object_url, licence, credit, and search_text (title, description,
short text and inscription, lower-cased, diacritics removed) with an FTS5 index.

An object is kept only when it has a description or a note of at least
MIN_TEXT characters. Coins are left out (they are the Coins collection). The
count fetched, kept and dropped for each museum, and the median description
length, are printed and written beside the database as objects_build_report.json.
The database is written to a temporary file and moved into place when complete.

Data files are not committed. See docs/DATA_OPERATIONS.md for the steps.
"""
from __future__ import annotations

import argparse
import html
import json
import os
import re
import sqlite3
import statistics
import sys
import unicodedata

MIN_TEXT = 40

COLUMNS = [
    ("id", "TEXT NOT NULL UNIQUE"),
    ("museum", "TEXT NOT NULL"),
    ("title", "TEXT"),
    ("object_type", "TEXT"),
    ("culture", "TEXT"),
    ("date_text", "TEXT"),
    ("date_start", "INTEGER"),
    ("date_end", "INTEGER"),
    ("material", "TEXT"),
    ("place_text", "TEXT"),
    ("description", "TEXT"),
    ("short_text", "TEXT"),
    ("inscription_text", "TEXT"),
    ("image_url", "TEXT"),
    ("object_url", "TEXT"),
    ("licence", "TEXT"),
    ("credit", "TEXT"),
    ("search_text", "TEXT"),
]
INDEXED = ("museum", "object_type", "culture", "material", "date_start", "date_end")

MUSEUM_NAMES = {
    "cleveland": "Cleveland Museum of Art",
    "chicago": "Art Institute of Chicago",
    "smithsonian": "Smithsonian Institution",
}
SI_UNIT_NAMES = {
    "NMNHANTHRO": "Smithsonian National Museum of Natural History, Department of Anthropology",
}
LICENCES = {
    "cleveland": "CC0",
    "chicago": "Catalogue record CC0, description CC BY 4.0",
    "smithsonian": "CC0",
}


def fold(text):
    """Lower-case and strip diacritics (Greek accents, macrons) for matching."""
    if not text:
        return ""
    d = unicodedata.normalize("NFD", str(text))
    d = "".join(ch for ch in d if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", d.lower()).strip()


def clean(text):
    """Plain text from a museum field: markup removed, entities decoded, spaces tidied."""
    if text is None:
        return None
    t = re.sub(r"<\s*(br|/p|/li)\s*/?>", "\n", str(text), flags=re.I)
    t = re.sub(r"<[^>]+>", "", t)
    t = html.unescape(t)
    t = re.sub(r"[ \t\r\f\v]+", " ", t)
    t = re.sub(r"\n\s*\n+", "\n\n", t)
    return t.strip() or None


def as_int(v):
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return None


def join_list(v, sep="; "):
    if isinstance(v, (list, tuple)):
        parts = [clean(x) for x in v if x]
        return sep.join(p for p in parts if p) or None
    return clean(v)


# -- Cleveland ----------------------------------------------------------------

def cleveland_row(r):
    if r.get("type") == "Coins":
        return None, "coin"
    if r.get("share_license_status") != "CC0":
        return None, "licence is not CC0"
    inscr = []
    for i in r.get("inscriptions") or []:
        if isinstance(i, dict) and i.get("inscription"):
            inscr.append(clean(i["inscription"]))
            if i.get("inscription_translation"):
                inscr.append(clean(i["inscription_translation"]))
    web = ((r.get("images") or {}).get("web") or {}).get("url")
    credit = "Cleveland Museum of Art"
    if r.get("creditline"):
        credit += ", " + clean(r["creditline"])
    credit += ". Catalogue record and image CC0."
    return {
        "id": "cma:" + str(r["accession_number"]),
        "museum": "cleveland",
        "title": clean(r.get("title")),
        "object_type": clean(r.get("type")),
        "culture": join_list(r.get("culture")),
        "date_text": clean(r.get("creation_date")),
        "date_start": as_int(r.get("creation_date_earliest")),
        "date_end": as_int(r.get("creation_date_latest")),
        "material": clean(r.get("technique")),
        "place_text": clean(r.get("find_spot")),
        "description": clean(r.get("description")),
        "short_text": clean(r.get("tombstone")),
        "inscription_text": "; ".join(inscr) or None,
        "image_url": web,
        "object_url": r.get("url"),
        "licence": LICENCES["cleveland"],
        "credit": credit,
    }, None


# -- Art Institute of Chicago -------------------------------------------------

def chicago_row(r):
    if r.get("_in_scope") is False:
        return None, "outside Greek, Roman or Etruscan (coin, Byzantine, later or far east)"
    art = r.get("id")
    image = None
    if r.get("is_public_domain") and r.get("image_id"):
        image = f"https://www.artic.edu/iiif/2/{r['image_id']}/full/843,/0/default.jpg"
    credit = "Art Institute of Chicago"
    if r.get("credit_line"):
        credit += ", " + clean(r["credit_line"])
    credit += ". Catalogue record CC0, description CC BY 4.0."
    return {
        "id": "aic:" + str(r.get("main_reference_number") or art),
        "museum": "chicago",
        "title": clean(r.get("title")),
        "object_type": clean(r.get("artwork_type_title")),
        "culture": clean(r.get("style_title")) or clean(r.get("place_of_origin")),
        "date_text": clean(r.get("date_display")),
        "date_start": as_int(r.get("date_start")),
        "date_end": as_int(r.get("date_end")),
        "material": clean(r.get("medium_display")),
        "place_text": clean(r.get("place_of_origin")),
        "description": clean(r.get("description")),
        "short_text": clean(r.get("short_description")),
        "inscription_text": clean(r.get("inscriptions")),
        "image_url": image,
        "object_url": f"https://www.artic.edu/artworks/{art}",
        "licence": LICENCES["chicago"],
        "credit": credit,
    }, None


# -- Smithsonian Open Access --------------------------------------------------

SI_SKIP_LABELS = {"Record Last Modified", "Specimen Count", "Accession Date"}
# A note that only points to a publication or says how a label was filed says
# nothing about the object.
SI_CITATION = re.compile(r"^(described in|published in|illustrated in|see |barcoded|this object was barcoded|"
                         r"catalogued as|formerly |old number)", re.I)
BC = r"(?:B\.?\s?C\.?(?:E\.?)?|BCE)"
AD = r"(?:A\.?\s?D\.?|CE)"


def si_note(rec):
    notes = ((rec.get("content") or {}).get("freetext") or {}).get("notes") or []
    keep = []
    for n in notes:
        text = clean(n.get("content")) if isinstance(n, dict) else clean(n)
        label = n.get("label") if isinstance(n, dict) else ""
        if not text or label in SI_SKIP_LABELS or SI_CITATION.match(text):
            continue
        keep.append(text)
    return " ".join(keep) or None


def si_dates(text):
    """(start, end) signed years from a phrase like 'ca. 475-410 B.C.' or '5th century BC'."""
    if not text:
        return None, None
    m = re.search(rf"(\d{{3,4}})\s*[-–]\s*(\d{{3,4}})\s*{BC}", text, re.I)
    if m:
        return -int(m.group(1)), -int(m.group(2))
    m = re.search(rf"(\d{{3,4}})\s*{BC}", text, re.I)
    if m:
        return -int(m.group(1)), -int(m.group(1))
    m = re.search(rf"(\d{{1,2}})(?:st|nd|rd|th)\s+century\s*{BC}", text, re.I)
    if m:
        c = int(m.group(1))
        return -(c * 100), -((c - 1) * 100 + 1)
    m = re.search(rf"(\d{{1,2}})(?:st|nd|rd|th)\s+century\s*{AD}", text, re.I)
    if m:
        c = int(m.group(1))
        return (c - 1) * 100 + 1, c * 100
    return None, None


def si_values(rec, key):
    ft = ((rec.get("content") or {}).get("freetext") or {}).get(key) or []
    return [clean(x.get("content")) for x in ft if isinstance(x, dict) and x.get("content")]


def smithsonian_row(r):
    note = si_note(r)
    # Some cast-gem notes say the description is copied from the Beazley Archive,
    # whose text is under another copyright than the museum's CC0 record.
    if note and re.search(r"description is copied from", note, re.I):
        return None, "note copied from another institution's database"
    c = r.get("content") or {}
    dnr = c.get("descriptiveNonRepeating") or {}
    media = ((dnr.get("online_media") or {}).get("media")) or []
    image = None
    for m in media:
        if m.get("type") == "Images" and (m.get("usage") or {}).get("access") == "CC0" and m.get("content"):
            image = m["content"]
            break
    unit = r.get("unitCode") or r.get("_unit", "").upper()
    ident = si_values(r, "identifier")
    acc = next((i for i in ident if i), None) or dnr.get("record_ID")
    usnm = [i for f in ((c.get("freetext") or {}).get("identifier") or []) for i in [f]
            if f.get("label") in ("USNM Number", "Object number", "Accession number")]
    acc = (usnm[0]["content"] if usnm else acc) or r.get("id")
    cultures = si_values(r, "culture") or (c.get("indexedStructured") or {}).get("culture") or []
    # The accession date is not the object's date: the object's date lives in the note or the title.
    d0, d1 = si_dates(" ".join(filter(None, [clean(r.get("title")), note])))
    if (dnr.get("metadata_usage") or {}).get("access") != "CC0":
        return None, "licence is not CC0"
    return {
        "id": "si:" + str(acc),
        "museum": "smithsonian",
        "title": clean(r.get("title") or (dnr.get("title") or {}).get("content")),
        "object_type": join_list(si_values(r, "objectType")),
        "culture": join_list(cultures),
        "date_text": None,
        "date_start": d0,
        "date_end": d1,
        "material": join_list(si_values(r, "physicalDescription")),
        "place_text": join_list(si_values(r, "place")),
        "description": note,
        "short_text": None,
        "inscription_text": None,
        "image_url": image,
        "object_url": dnr.get("record_link") or dnr.get("guid"),
        "licence": LICENCES["smithsonian"],
        "credit": f"{SI_UNIT_NAMES.get(unit, 'Smithsonian Institution')}. Catalogue record and image CC0.",
    }, None


ROW_FUNCS = {"cleveland": cleveland_row, "chicago": chicago_row, "smithsonian": smithsonian_row}


def finish(row):
    row["search_text"] = fold(" ".join(row[k] for k in
                                       ("title", "description", "short_text", "inscription_text") if row.get(k)))
    return row


def text_length(row):
    return len(row.get("description") or "")


def build(inputs, out_path):
    """inputs: {museum: path of records.jsonl}. Returns (total, report)."""
    tmp = out_path + ".building"
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    if os.path.exists(tmp):
        os.remove(tmp)
    con = sqlite3.connect(tmp)
    cols = ", ".join(f"{n} {t}" for n, t in COLUMNS)
    con.execute(f"CREATE TABLE objects (n INTEGER PRIMARY KEY, {cols})")  # nosec B608 -- fixed column list defined above
    names = [n for n, _ in COLUMNS]
    ins = f"INSERT OR IGNORE INTO objects ({', '.join(names)}) VALUES ({', '.join('?' * len(names))})"  # nosec B608 -- fixed column list
    report = {}
    for museum, path in inputs.items():
        rep = {"fetched": 0, "kept": 0, "dropped": 0, "dropped_because": {}, "lengths": []}
        seen = set()
        with open(path, encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                rep["fetched"] += 1
                row, why = ROW_FUNCS[museum](json.loads(line))
                if row is None:
                    rep["dropped_because"][why] = rep["dropped_because"].get(why, 0) + 1
                    continue
                if text_length(row) < MIN_TEXT:
                    rep["dropped_because"]["no description of 40 characters"] = \
                        rep["dropped_because"].get("no description of 40 characters", 0) + 1
                    continue
                if row["id"] in seen:
                    rep["dropped_because"]["repeated accession number"] = \
                        rep["dropped_because"].get("repeated accession number", 0) + 1
                    continue
                seen.add(row["id"])
                row = finish(row)
                con.execute(ins, [row[n] for n in names])
                rep["kept"] += 1
                rep["lengths"].append(text_length(row))
        rep["dropped"] = rep["fetched"] - rep["kept"]
        rep["median_description_chars"] = int(statistics.median(rep["lengths"])) if rep["lengths"] else None
        del rep["lengths"]
        report[museum] = rep
    con.execute("CREATE VIRTUAL TABLE objects_fts USING fts5(search_text, content='objects', "
                "content_rowid='n', tokenize='unicode61 remove_diacritics 2')")
    con.execute("INSERT INTO objects_fts(rowid, search_text) SELECT n, search_text FROM objects")
    con.execute("INSERT INTO objects_fts(objects_fts) VALUES ('optimize')")
    for c in INDEXED:
        con.execute(f"CREATE INDEX objects_{c} ON objects ({c})")  # nosec B608 -- fixed names above
    con.commit()
    total = con.execute("SELECT COUNT(*) FROM objects").fetchone()[0]
    con.execute("VACUUM")
    con.close()
    os.replace(tmp, out_path)
    return total, report


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    for m in MUSEUM_NAMES:
        ap.add_argument(f"--{m}", help=f"folder holding {m} records.jsonl")
    ap.add_argument("--out", default="data/objects/objects.sqlite")
    args = ap.parse_args(argv)
    inputs = {m: os.path.join(getattr(args, m), "records.jsonl") for m in MUSEUM_NAMES if getattr(args, m)}
    if not inputs:
        ap.error("give at least one museum folder")
    total, report = build(inputs, args.out)
    with open(os.path.join(os.path.dirname(os.path.abspath(args.out)), "objects_build_report.json"), "w") as f:
        json.dump(report, f, indent=1)
    print(json.dumps(report, indent=1), file=sys.stderr)
    print(f"wrote {args.out}: {total} objects", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
