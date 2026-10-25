#!/usr/bin/env python3
"""Saadi, Bustan: align H. Wilberforce Clarke's English (1879) to the Persian by couplet number.

Clarke's prose translation (Internet Archive OCR of the Calcutta 1879 edition, public domain)
renders each couplet in two short lines and numbers every fifth couplet in the margin,
counting from 1 in each chapter. The OCR keeps about two thirds of the numbers, at the start
of their line. For each chapter the script takes the longest rising run of readable numbers,
cuts the English at them into units of at least MIN_COUPLETS couplets, and pairs each unit
with the Persian couplets of the same numbers. Clarke's couplet count differs from the
Ganjoor text by a few percent in places (Clarke follows another edition and notes omissions),
so Clarke's numbers are scaled to the Persian chapter's couplet count before pairing. The
file is marked approximate. Chapter 0 is the invocation, chapters 1 to 10 the ten books.

Usage:
    align_saadi_bustan_clarke.py --src OCR.txt --tess saadi.bustan.tess --out-dir DIR [--report R.json]
"""

import argparse
import bisect
import json
import os
import re
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from write_aligned import tess_refs, write_aligned  # noqa: E402

ANCHOR = re.compile(r"^\s*(\d{1,4})\s{1,6}(\S.*)$")
SKIP = re.compile(r"BUSTAN|BUST\s*AN|SA.?DI|\[|chap|CHAP|couplets?\s+\d|Ikd", re.I)
# Line numbers (0-based) in the OCR text where each chapter's English begins; 0 is the invocation.
STARTS = [(0, 330), (1, 1593), (2, 6660), (3, 9018), (4, 11147), (5, 13610), (6, 14553), (7, 15374), (8, 17393), (9, 18582), (10, 20057)]
END_LINE = 20700
MIN_COUPLETS = 40


def lis(vals):
    tails, idx, prev = [], [], [-1] * len(vals)
    for i, v in enumerate(vals):
        j = bisect.bisect_left(tails, v)
        if j == len(tails):
            tails.append(v)
            idx.append(i)
        else:
            tails[j] = v
            idx[j] = i
        prev[i] = idx[j - 1] if j > 0 else -1
    out, k = [], idx[-1] if idx else -1
    while k >= 0:
        out.append(k)
        k = prev[k]
    return out[::-1]


def clean_lines(lines, anchor_lines):
    out = []
    for i, ln in lines:
        s = ln.strip()
        if not s or SKIP.search(s) and i not in anchor_lines:
            continue
        if re.match(r"^\d{1,4}$", s):
            continue
        if i not in anchor_lines and re.match(r"^\d{1,3}\s+\S", s):
            continue  # footnote line
        s = re.sub(r"^\d{1,4}\s{1,6}", "", s) if i in anchor_lines else s
        out.append(s)
    return re.sub(r"\s+", " ", " ".join(out)).strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True)
    ap.add_argument("--tess", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--report")
    a = ap.parse_args()
    L = open(a.src, encoding="utf-8", errors="replace").read().split("\n")
    couplets = {}
    ref_by_couplet = {}
    for line in open(a.tess, encoding="utf-8"):
        m = re.match(r"<(saadi\.bustan\.(\d+)\.(\d+)\.(\d))>\t(.*)", line.rstrip("\n"))
        if m:
            c, k = int(m.group(2)), int(m.group(3))
            couplets[c] = max(couplets.get(c, 0), k)
            ref_by_couplet.setdefault((c, k), []).append((m.group(1), m.group(5)))
    units, ref_to_unit, xs, ys, report = [], {}, [], [], {}
    bounds = [b for _c, b in STARTS] + [END_LINE]
    for (c, a0), b0 in zip(STARTS, bounds[1:]):
        g = couplets[c]
        cand = []
        for i in range(a0, b0):
            m = ANCHOR.match(L[i])
            if m and not SKIP.search(L[i]):
                n = int(m.group(1))
                if (n % 5 == 0 or n == 1) and n <= int(g * 1.15) + 5:
                    cand.append((i, n))
        keep = [cand[k] for k in lis([n for _i, n in cand])]
        if not keep:
            raise SystemExit(f"chapter {c}: no readable numbers")
        top = keep[-1][1] + 2
        scale = g / top
        anchor_lines = {i for i, _n in keep}
        # cut points: anchors at least MIN_COUPLETS after the previous cut
        cuts = [(a0, 1)]
        for i, n in keep:
            if n - cuts[-1][1] >= MIN_COUPLETS:
                cuts.append((i, n))
        # the English after the last readable number runs on for a few couplets; the rest of
        # the chapter's pages (end notes, the next chapter's heading) is not translation
        tail_end = min(b0, keep[-1][0] + 45)
        bounds_c = cuts + [(tail_end, top + 1)]
        for (la, na), (lb, nb) in zip(bounds_c, bounds_c[1:]):
            text = clean_lines([(i, L[i]) for i in range(la, lb)], anchor_lines)
            if len(text) < 20:
                continue
            first = max(1, round((na - 1) * scale) + 1) if na > 1 else 1
            last = g if lb >= tail_end else min(g, round((nb - 1) * scale))
            u = len(units)
            units.append(text)
            plen = 0
            for k in range(first, last + 1):
                for ref, t in ref_by_couplet.get((c, k), []):
                    ref_to_unit[ref] = u
                    plen += len(t)
            xs.append(plen)
            ys.append(len(text))
        report[c] = {"anchors": len(keep), "last_anchor": keep[-1][1], "persian_couplets": g, "scale": round(scale, 3)}
    r = statistics.correlation(xs, ys)
    refs = tess_refs(a.tess)
    covered = sum(1 for k in refs if k in ref_to_unit)
    print("units", len(units), "coverage", covered, "of", len(refs), "length correlation", round(r, 3))
    print(report)
    path = write_aligned(
        a.out_dir, "fa", os.path.basename(a.tess)[:-5], units, ref_to_unit,
        attribution="H. Wilberforce Clarke, The Bustan by Shaikh Muslihu-d-din Sa'di Shirazi (Calcutta: Thacker, Spink, 1879), via the Internet Archive",
        license="Public domain (published 1879)",
        sources=[{
            "translator": "H. Wilberforce Clarke", "year": "1879",
            "title": "The Bustan by Shaikh Muslihu-d-din Sa'di Shirazi",
            "url": "https://archive.org/details/bstnbyshaikh00sadiuoft",
            "source_url": "https://archive.org/details/bstnbyshaikh00sadiuoft",
            "publisher": "Thacker, Spink and Co., Calcutta", "mode": "couplet numbers read from the margin, scaled per chapter",
        }],
        confidence="medium", approximate=True, tess_refs=refs, verified_by="length_correlation",
        notes=f"Units of at least {MIN_COUPLETS} couplets between margin numbers the OCR kept, paired with the Persian couplets after scaling Clarke's numbering to the chapter's couplet count. Length correlation {r:.3f}. Per chapter: {report}",
    )
    print(path)
    if a.report:
        json.dump({"units": len(units), "length_correlation": r, "coverage": covered, "refs": len(refs), "chapters": report}, open(a.report, "w"), indent=1)


if __name__ == "__main__":
    main()
