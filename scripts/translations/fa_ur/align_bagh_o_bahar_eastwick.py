#!/usr/bin/env python3
"""Mir Amman, Bagh o Bahar: align Edward B. Eastwick's English (1852) to the Persian-script Urdu by section.

Source: Internet Archive OCR of Eastwick's translation (Hertford 1852, public domain). The
Urdu text (Urdu Wikisource, via ur_wikisource) has seven sections: the opening praise, the
reason for the translation, the beginning of the tale, and the four darwesh's stories. Each
section opens on a sentence that can be found in the English ("When the turn came to the
second Darwesh to relate his tale", "The third darwesh sate down", "The fourth fakir began"),
so the English is cut at those sentences and the units pair with the sections in order.
The OCR carries the translator's notes in the page feet; paragraphs that open with a note
mark are dropped, the running heads too.

Usage:
    align_bagh_o_bahar_eastwick.py --src OCR.txt --tess mir_amman.bagh_o_bahar.tess --out-dir DIR [--report R.json]
"""

import argparse
import json
import os
import re
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from write_aligned import tess_refs, write_aligned  # noqa: E402

# Text at which each section's English begins, in order (found by substring on one line).
MARKS = [
    "God be praised ! what a Creator is He",
    "In the first place, this sinful",
    "BEGINNING OF THE STORY.",
    "All replied, “O S",
    "When the turn came to the second Darwesh",
    "The third darwesh sate down",
    "The fourth fakir began",
]
END_MARK = "CONCLUSION OF THE BOOK."


def clean(lines):
    paras = re.split(r"\n\s*\n", "\n".join(lines))
    out = []
    for p in paras:
        s = re.sub(r"\s+", " ", p).strip()
        if not s:
            continue
        if s.isupper() or re.match(r"^[A-Z .,'’\-]{4,40}\d{0,3}\.?$", s):
            continue  # running head
        if re.match(r"^[\^*†‡§]|^\d{1,3}\s", s) and len(s) < 900:
            continue  # translator's note
        if re.match(r"^Note \d+", s):
            continue
        out.append(s)
    return " ".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True)
    ap.add_argument("--tess", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--report")
    a = ap.parse_args()
    L = open(a.src, encoding="utf-8", errors="replace").read().split("\n")
    pos, at = [], 380
    for mk in MARKS:
        i = next(j for j in range(at, len(L)) if mk in L[j])
        pos.append(i)
        at = i + 1
    # the first mark of "All replied" opens the first darwesh's tale one line later; the
    # sentence "First do you yourself be pleased to commence" is its last line
    end = next(j for j in range(pos[-1], len(L)) if END_MARK in L[j])
    pos2 = pos[:3] + [pos[3] + 6] + pos[4:]
    edges = pos2 + [end]
    units = [clean(L[a:b]) for a, b in zip(edges, edges[1:])]
    sections = {}
    for line in open(a.tess, encoding="utf-8"):
        m = re.match(r"<(mir_amman\.bagh_o_bahar\.(\d+)\.(\d+))>\t(.*)", line.rstrip("\n"))
        if m:
            sections.setdefault(int(m.group(2)), []).append((m.group(1), m.group(4)))
    assert sorted(sections) == list(range(1, 8)), sorted(sections)
    ref_to_unit, xs, ys = {}, [], []
    for s in range(1, 8):
        for ref, _t in sections[s]:
            ref_to_unit[ref] = s - 1
        xs.append(sum(len(t) for _r, t in sections[s]))
        ys.append(len(units[s - 1]))
    r = statistics.correlation(xs, ys)
    ratios = [round(y / x, 2) for x, y in zip(xs, ys)]
    print("units", len(units), "length correlation", round(r, 3), "english/urdu characters per section", ratios)
    refs = tess_refs(a.tess)
    path = write_aligned(
        a.out_dir, "ur", os.path.basename(a.tess)[:-5], units, ref_to_unit,
        attribution="Edward B. Eastwick, Bagh o Bahar, or The Garden and the Spring (Hertford: Stephen Austin, 1852), via the Internet Archive",
        license="Public domain (published 1852)",
        sources=[{
            "translator": "Edward B. Eastwick", "year": "1852",
            "title": "The Bagh o Bahar, or The Garden and the Spring",
            "url": "https://archive.org/details/in.ernet.dli.2015.81938",
            "source_url": "https://archive.org/details/in.ernet.dli.2015.81938",
            "publisher": "Stephen Austin, Hertford", "mode": "one unit per section of the Urdu",
        }],
        confidence="high", approximate=False, tess_refs=refs, verified_by="length_correlation",
        notes=f"Seven units, one per section of the Urdu, cut at sentences found in both texts. Length correlation of the seven pairs {r:.3f}; English to Urdu characters per section {ratios}.",
    )
    print(path)
    if a.report:
        json.dump({"edges": edges, "length_correlation": r, "ratios": ratios}, open(a.report, "w"), indent=1)


if __name__ == "__main__":
    main()
