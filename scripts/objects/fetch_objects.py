#!/usr/bin/env python3
"""Fetch museum catalogue records for the Objects collection.

    python -I scripts/objects/fetch_objects.py --museum cleveland --out DIR
    python -I scripts/objects/fetch_objects.py --museum chicago --archive DIR/artic-api-data.tar.bz2 --out DIR
    python -I scripts/objects/fetch_objects.py --museum smithsonian --raw DIR/raw --out DIR

Each run writes DIR/records.jsonl, one raw museum record per line, and stops.
build_objects_db.py reads those files. Nothing here is committed data.

cleveland     The Cleveland Museum of Art open access API (CC0), department
              "Greek and Roman Art", every record, no key.
chicago       The Art Institute of Chicago data dump (artic-api-data.tar.bz2),
              department "Arts of Greece, Rome, and Byzantium". The archive is
              downloaded first (--download) or already in place (--archive).
              Records are read from the archive in one pass, never unpacked.
              Byzantine and coin material is left out here (coins are the Coins
              collection), and records of other cultures are left out.
smithsonian   Smithsonian Open Access (CC0). The public API key allows ten
              requests an hour, so the records come from the same data in the
              open-access bucket (--raw: a folder of unit/NN.txt files, fetched
              with --download). Records whose culture, title, type or place
              names a Greek, Roman or Etruscan object are kept (the National
              Museum of Natural History Anthropology department, which holds the
              Greek vase notes of Shirley Schwarz and the Roman lamp cards).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tarfile
import time
import urllib.parse
import urllib.request

CLEVELAND_API = "https://openaccess-api.clevelandart.org/api/artworks/"
CLEVELAND_DEPT = "Greek and Roman Art"
CHICAGO_DUMP = "https://artic-api-data.s3.amazonaws.com/artic-api-data.tar.bz2"
CHICAGO_DEPT = "Arts of Greece, Rome, and Byzantium"
SI_BUCKET = "https://smithsonian-open-access.s3-us-west-2.amazonaws.com/metadata/edan"
SI_UNITS = ("nmnhanthro",)

CHICAGO_DROP = re.compile(r"byzantin|coptic|early christian|islamic|medieval|sasanian|sassanian|"
                          r"umayyad|abbasid|crusader", re.I)
CHICAGO_FAR = re.compile(r"iran|khorasan|iraq|afghanistan|turkmenistan|uzbekistan|pakistan|india|"
                         r"china|nishapur|samarra|rayy", re.I)
CHICAGO_LAST_YEAR = 400   # the department runs on into Byzantium: nothing dated after this is kept
SI_KEEP = re.compile(r"\b(greek|greece|roman|rome|etruscan|etruria|attic|athenian|corinthian|"
                     r"hellenistic|apulian|boeotian)\b", re.I)


def http_json(url, retries=4):
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "tesserae-objects-fetch/1.0"})
            with urllib.request.urlopen(req, timeout=120) as r:  # nosec B310
                return json.loads(r.read())
        except Exception as e:  # network errors are retried, then raised
            if i == retries - 1:
                raise
            print(f"retry {url}: {e}", file=sys.stderr)
            time.sleep(5 * (i + 1))


def fetch_cleveland(out):
    n = skip = 0
    path = os.path.join(out, "records.jsonl")
    with open(path, "w", encoding="utf-8") as f:
        while True:
            q = urllib.parse.urlencode({"department": CLEVELAND_DEPT, "limit": 100, "skip": skip})
            page = http_json(f"{CLEVELAND_API}?{q}")
            data = page.get("data") or []
            for rec in data:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                n += 1
            total = (page.get("info") or {}).get("total", 0)
            skip += 100
            if not data or skip >= total:
                break
    print(f"cleveland: {n} records fetched", file=sys.stderr)
    return n


def chicago_wanted(rec):
    """True for the Greek, Roman and Etruscan objects of the department.

    The department is "Arts of Greece, Rome, and Byzantium", so the test leaves
    out what does not belong rather than listing every Greek place name: coins
    (the Coins collection), anything Byzantine, Coptic, Islamic or medieval,
    anything dated after 400 CE, and places far to the east."""
    if rec.get("department_title") != CHICAGO_DEPT:
        return False
    blob = " ".join(str(x) for x in [rec.get("place_of_origin"), rec.get("classification_title"),
                                     " ".join(rec.get("classification_titles") or []),
                                     rec.get("title"), rec.get("date_display"),
                                     rec.get("style_title")] if x)
    if rec.get("artwork_type_title") == "Coin" or re.search(r"\bcoins?\b|\bmedal", blob, re.I):
        return False
    if CHICAGO_DROP.search(blob) or CHICAGO_FAR.search(str(rec.get("place_of_origin") or "")):
        return False
    start = rec.get("date_start")
    if isinstance(start, int) and start > CHICAGO_LAST_YEAR:
        return False
    return True


def fetch_chicago(out, archive, download):
    if download:
        print(f"downloading {CHICAGO_DUMP}", file=sys.stderr)
        urllib.request.urlretrieve(CHICAGO_DUMP, archive)  # nosec B310
    seen = kept = 0
    with tarfile.open(archive, "r:bz2") as t, \
            open(os.path.join(out, "records.jsonl"), "w", encoding="utf-8") as f:
        for m in t:
            if not (m.isfile() and "/json/artworks/" in m.name and m.name.endswith(".json")):
                continue
            rec = json.load(t.extractfile(m))
            if rec.get("department_title") != CHICAGO_DEPT:
                continue
            seen += 1
            rec["_in_scope"] = chicago_wanted(rec)
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            kept += rec["_in_scope"]
    print(f"chicago: {seen} records in the department, {kept} Greek, Roman or Etruscan "
          f"(the rest marked _in_scope false)", file=sys.stderr)
    return seen


SI_DROP = re.compile(r"islamic|muslim|egyptian|byzantin|coptic", re.I)


def si_fields(rec):
    """The text that says what an object is: culture, title, object type and place."""
    c = rec.get("content") or {}
    ft = c.get("freetext") or {}
    bits = [rec.get("title")]
    for key in ("culture", "place", "objectType"):
        for item in ft.get(key) or []:
            bits.append(item.get("content") if isinstance(item, dict) else item)
    bits += (c.get("indexedStructured") or {}).get("culture") or []
    return " ".join(str(b) for b in bits if b)


def si_wanted(rec):
    """A Greek, Roman or Etruscan object: the words appear in its culture, title,
    type or place, and nothing marks it Islamic, Egyptian or Byzantine."""
    text = si_fields(rec)
    if not SI_KEEP.search(text):
        return False
    return not SI_DROP.search(text) or re.search(r"\b(roman|greek|greco|etruscan)\b", text, re.I) and \
        not re.search(r"islamic|muslim", text, re.I)


def fetch_smithsonian(out, raw, download, units):
    if download:
        for u in units:
            d = os.path.join(raw, u)
            os.makedirs(d, exist_ok=True)
            idx = urllib.request.urlopen(f"{SI_BUCKET}/{u}/index.txt").read().decode().split()  # nosec B310
            for url in idx:
                dest = os.path.join(d, os.path.basename(url))
                if not os.path.exists(dest):
                    urllib.request.urlretrieve(url, dest)  # nosec B310
    seen = kept = 0
    with open(os.path.join(out, "records.jsonl"), "w", encoding="utf-8") as f:
        for u in units:
            d = os.path.join(raw, u)
            for name in sorted(os.listdir(d)):
                with open(os.path.join(d, name), encoding="utf-8") as src:
                    for line in src:
                        if not line.strip():
                            continue
                        seen += 1
                        rec = json.loads(line)
                        if si_wanted(rec):
                            rec["_unit"] = u
                            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                            kept += 1
    print(f"smithsonian: {seen} records read, {kept} name a Greek, Roman or Etruscan object", file=sys.stderr)
    return kept


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--museum", required=True, choices=["cleveland", "chicago", "smithsonian"])
    ap.add_argument("--out", required=True, help="a fresh folder under ~/tesserae-backups/sources/archaeology/")
    ap.add_argument("--archive", help="chicago: path of artic-api-data.tar.bz2")
    ap.add_argument("--raw", help="smithsonian: folder of unit/NN.txt files")
    ap.add_argument("--units", default=",".join(SI_UNITS))
    ap.add_argument("--download", action="store_true", help="fetch the dump or bucket files first")
    args = ap.parse_args(argv)
    os.makedirs(args.out, exist_ok=True)
    if args.museum == "cleveland":
        fetch_cleveland(args.out)
    elif args.museum == "chicago":
        fetch_chicago(args.out, args.archive or os.path.join(args.out, "artic-api-data.tar.bz2"), args.download)
    else:
        fetch_smithsonian(args.out, args.raw or os.path.join(args.out, "raw"), args.download,
                          args.units.split(","))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
