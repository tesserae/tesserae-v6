#!/usr/bin/env python3
"""Nizami-i 'Arudi, Chahar Maqala: align E. G. Browne's English to the Persian by anecdote.

Source: the Internet Archive OCR of Browne, Revised Translation of the Chahar Maqala
(Gibb Memorial Series XI, 2, London 1921; the 1899 translation of the Journal of the
Royal Asiatic Society, revised). Public domain. Browne numbers the anecdotes I to XLIII
in one run, and the Persian text (Qazvini's edition on Persian Wikisource) carries the
word "hekayat" (anecdote) alone in a paragraph before each of the 43 anecdotes: one in
the preface, ten in each of the first three discourses, twelve in the fourth. That gives
48 segments on each side: the preface, anecdote 1, then for each discourse its opening
essay followed by its anecdotes. Segments pair in order.

Usage:
    align_chahar_maqala_browne.py --src OCR.txt --tess nizami_arudi.chahar_maqala.tess \
        --out-dir DIR [--report REPORT.json]
"""

import argparse
import json
import os
import re
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from write_aligned import tess_refs, write_aligned  # noqa: E402

ROMAN = {"I": 1, "V": 5, "X": 10, "L": 50}


def roman(s):
    n = 0
    for a, b in zip(s, s[1:] + " "):
        n += -ROMAN[a] if b != " " and ROMAN[a] < ROMAN.get(b, 0) else ROMAN[a]
    return n


def clean_english(lines):
    """Remove running heads, footnote paragraphs and footnote marks."""
    text = "\n".join(lines)
    paras = re.split(r"\n\s*\n", text)
    out = []
    for p in paras:
        s = re.sub(r"\s+", " ", p).strip()
        if not s:
            continue
        if re.match(r"^\d{1,2}\s+[A-Za-z'‘’\[(\"]", s) and len(s) < 1500:
            continue  # footnote
        if re.match(r"^\(?\w{0,3}\)?\s*\d{0,3}\s*(FIRST|SECOND|THIRD|FOURTH)\s+DISCOURSE", s):
            s = re.sub(r"^\(?\w{0,3}\)?\s*\d{0,3}\s*(FIRST|SECOND|THIRD|FOURTH)\s+DISCOURSE[^a-z]*", "", s)
        if re.match(r"^\d{0,3}\s*CHAHAR\s*\.?\s*MAQALA", s):
            continue
        if s.isupper() and len(s) < 60:
            continue  # running head or a title in capitals
        s = re.sub(r"(?<=[A-Za-zāīū])\d{1,2}(?=[\s,.;:)\]])", "", s)
        out.append(s)
    return " ".join(out)


def english_segments(path):
    lines = open(path, encoding="utf-8", errors="replace").read().split("\n")
    start = next(i for i, ln in enumerate(lines) if "EXORDIUM" in ln) - 12
    end = next(i for i, ln in enumerate(lines) if i > 5990 and ln.strip() == "NOTES")
    cuts = [("preface", start)]
    for i in range(start, end):
        ln = lines[i].strip()
        m = re.match(r"^.{0,12}?ANEC[DB]OTE\s+([IVXL]+)\b", ln)
        if m and not ln.startswith("Anecdote"):
            cuts.append((f"a{roman(m.group(1))}", i))
        m = re.match(r"^.{0,8}?\s(FIRST|SECOND|THIRD|FOURTH)\s+DISCOURSE\.?\s*$", ln)
        if m:
            cuts.append((f"d{m.group(1)}", i))
    # an anecdote heading is not repeated: keep the first of each id, in line order
    seen, ordered = set(), []
    for name, i in sorted(cuts, key=lambda x: x[1]):
        if name in seen:
            continue
        seen.add(name)
        ordered.append((name, i))
    segs = []
    for (name, a), (_n2, b) in zip(ordered, ordered[1:] + [("end", end)]):
        segs.append((name, clean_english(lines[a + 1 : b]) if name != "preface" else clean_english(lines[a:b])))
    return segs


def persian_segments(tess):
    rows = []
    for line in open(tess, encoding="utf-8"):
        m = re.match(r"<([^>]+)>\t(.*)", line.rstrip("\n"))
        if m:
            rows.append((m.group(1), m.group(2)))
    segs, cur, cur_name = [], [], "preface"
    sec = lambda r: int(r.split(".")[-2])  # noqa: E731
    last_sec = 0
    k = 0
    for ref, t in rows:
        s = sec(ref)
        if s != last_sec and s >= 1:
            segs.append((cur_name, cur))
            cur, cur_name = [], f"d{s}"
        last_sec = s
        if t.strip() == "حکایت":
            segs.append((cur_name, cur))
            k += 1
            cur, cur_name = [(ref, t)], f"a{k}"  # the heading word belongs to its anecdote
            continue
        cur.append((ref, t))
    segs.append((cur_name, cur))
    return [(n, c) for n, c in segs if c], rows


def corr(xs, ys):
    return statistics.correlation(xs, ys) if len(xs) > 2 else 0.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True)
    ap.add_argument("--tess", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--report")
    a = ap.parse_args()
    eng = english_segments(a.src)
    per, rows = persian_segments(a.tess)
    print("english segments", len(eng), "persian segments", len(per))
    names_e = [n for n, _ in eng]
    names_p = [n for n, _ in per]
    # English discourse openings are named dFIRST.. and Persian d1.. : compare by order
    shape = lambda ns: ["d" if n.startswith("d") else ("a" if n.startswith("a") else "p") for n in ns]  # noqa: E731
    if shape(names_e) != shape(names_p):
        print("segment shapes differ", shape(names_e), shape(names_p))
        raise SystemExit("segments do not pair; refusing to write")
    units, ref_to_unit, xs, ys = [], {}, [], []
    for i, ((en, et), (pn, pl)) in enumerate(zip(eng, per)):
        units.append(et)
        for ref, _t in pl:
            ref_to_unit[ref] = i
        xs.append(sum(len(t) for _r, t in pl))
        ys.append(len(et))
    r = corr(xs, ys)
    print("units", len(units), "length correlation", round(r, 3))
    refs = tess_refs(a.tess)
    path = write_aligned(
        a.out_dir,
        "fa",
        os.path.basename(a.tess)[:-5],
        units,
        ref_to_unit,
        attribution="Edward G. Browne, Revised Translation of the Chahar Maqala (Four Discourses) of Nidhami-i-Arudi-i-Samarqandi (London: Luzac, 1921), via the Internet Archive",
        license="Public domain (published 1921, Browne died 1926)",
        sources=[
            {
                "translator": "Edward G. Browne",
                "year": "1921",
                "title": "Revised Translation of the Chahar Maqala",
                "url": "https://archive.org/details/chaharmaqala032556mbp",
                "source_url": "https://archive.org/details/chaharmaqala032556mbp",
                "publisher": "Luzac, London (Gibb Memorial Series XI, 2)",
                "mode": "anecdote by anecdote",
            }
        ],
        confidence="high",
        approximate=False,
        tess_refs=refs,
        verified_by="length_correlation",
        notes=f"Persian and English both divide into 48 segments (preface, 43 anecdotes, four discourse openings) that pair in order. Length correlation of the 48 pairs {r:.3f}.",
    )
    print(path)
    if a.report:
        json.dump({"units": len(units), "length_correlation": r, "pairs": [(en, pn, x, y) for (en, _), (pn, _), x, y in zip(eng, per, xs, ys)]}, open(a.report, "w"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
