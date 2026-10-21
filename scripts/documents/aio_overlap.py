#!/usr/bin/env python3
"""Report AIO inscriptions that the documents collection already holds, by
edition number (IG and SEG, the corpora that AIO and the other sources share).

Reads the AIO JSONL and a metadata.db (read-only). An AIO document counts as
already held when ANY edition it cites (its heading or any reference on its
AIO page) equals the principal edition of a document from another source.

Usage:  aio_overlap.py AIO_JSONL METADATA_DB [--out OVERLAP_JSON]
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3

ROMAN = {1: "I", 2: "II", 3: "III", 4: "IV", 5: "V", 7: "VII", 9: "IX", 10: "X", 11: "XI", 12: "XII", 13: "XIII", 14: "XIV"}


def key_aio(ref: str):
    ref = ref.strip()
    m = re.match(r"^SEG (\d+)\.(\w+)", ref)
    if m:
        return ("SEG", int(m.group(1)), re.sub(r"^0+", "", m.group(2)))
    m = re.match(r"^IG (I|II)(\d) ([\dA-Za-z. ]+)", ref)  # the Attic corpora only
    if m:
        nums = tuple(re.sub(r"^0+(?=\d)", "", t) for t in re.findall(r"\d+[a-z]?", m.group(3)))
        if nums:
            return ("IG", m.group(1) + (m.group(2) or ""), nums[:2] if m.group(1) == "II" and m.group(2) == "3" else nums[:1])
    return None


def key_existing(pe: str):
    pe = pe.strip()
    m = re.match(r"^SEG (\d+), 0*(\w+)", pe)
    if m:
        return ("SEG", int(m.group(1)), m.group(2))
    m = re.match(r"^IG (\d+)(?: \((\d)\. Aufl\.\))?[ ,]+([\d, ]+[a-z]?)", pe)
    if m:
        vol = ROMAN.get(int(m.group(1)))
        if vol not in ("I", "II") or not m.group(2):
            return None
        nums = tuple(re.sub(r"^0+(?=\d)", "", t) for t in re.findall(r"\d+[a-z]?", m.group(3)))
        if not nums:
            return None
        return ("IG", vol + (m.group(2) or ""), nums[-2:] if m.group(1) == "02" and m.group(2) == "3" else nums[-1:])
    return None


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("jsonl")
    ap.add_argument("db")
    ap.add_argument("--out", default=None)
    a = ap.parse_args(argv)
    conn = sqlite3.connect(f"file:{a.db}?mode=ro", uri=True)
    existing = {}
    for did, src, pe, lang in conn.execute(
            "SELECT id, source, principal_edition, languages FROM documents "
            "WHERE source != 'aio' AND principal_edition IS NOT NULL"):
        k = key_existing(pe)
        if k:
            existing.setdefault(k, []).append((did, src, pe))
    pairs = []
    n_docs = 0
    for line in open(a.jsonl, encoding="utf-8"):
        rec = json.loads(line)
        n_docs += 1
        cited = [rec["aio"]["edition"]] + list(rec["aio"].get("references") or [])
        hits = {}
        for r in cited:
            k = key_aio(r or "")
            if k and k in existing:
                for e in existing[k]:
                    hits[e[0]] = (r, e)
        for eid, (r, e) in hits.items():
            pairs.append({"aio": rec["id"], "aio_edition": rec["aio"]["edition"], "matched_reference": r,
                          "existing": e[0], "existing_source": e[1], "existing_edition": e[2]})
    out = {"aio_documents": n_docs, "existing_keys_indexed": len(existing),
           "pairs": pairs, "aio_documents_with_a_match": len({p["aio"] for p in pairs})}
    if a.out:
        json.dump(out, open(a.out, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    print(json.dumps({k: v for k, v in out.items() if k != "pairs"}))
    for p in pairs[:15]:
        print(p)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
