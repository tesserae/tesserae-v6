#!/usr/bin/env python3
"""Rumi, Masnavi, Books I to IV: align R. A. Nicholson's English by couplet number, page by page.

Source: the Internet Archive OCR of Nicholson, The Mathnawi of Jalalu'ddin Rumi, Gibb
Memorial Series, vol. II (translation of Books I and II, 1926) and vol. IV (Books III and IV,
1930). Public domain in the United States (published before 1931 for volume IV, 1926 for
volume II) and in the United Kingdom (Nicholson died 1945, so the United Kingdom term has
not run: see the licence note in the output). Books V and VI (1933, 1934) are not used.

Nicholson prints the English couplet by couplet and numbers every fifth couplet in the
margin, from 1 at the start of each book. The OCR loses the numbers' places: some stay at
the end of a line, most come as a column at the foot of the page. Reading them all in
order and keeping the longest rising run (about two thirds survive) gives, for each page,
the highest couplet number printed on it. A unit is then one page of English (pages without
a readable number join the next page), covering the couplets after the previous page's last
number up to this page's last number, so its edges can lie up to four couplets from the
page's real edges. The Persian text (Ganjoor, 4,013 couplets in Book I against Nicholson's
4,003, and so on) is paired by couplet number, so a further drift of up to ten couplets in
places is possible. The file is marked approximate and medium confidence.

Usage:
    align_rumi_masnavi_nicholson_books.py --vol2 OCR2.txt --vol4 OCR4.txt \
        --tess rumi.masnavi.tess --out-dir DIR [--report R.json]
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

PAGEHEAD_A = re.compile(r"^\s*(?:\d{1,3}\s+)?MATHNAWI,?\s+BOOK\s+[IVX1l]{1,4}\b\s*\d{0,3}\s*$", re.I)
PAGEHEAD_B = re.compile(r"^\s*[A-Z][A-Z0-9 ,.:;'’‘“”\"()\-—]{6,}\s+\d{1,3}\s*$")
FOOT = re.compile(
    r"^\s*(?:\d\s+)?(Literally|Or\b|i\.e\.|Lit\.|Cf\.|See\b|The text|Text\b|Read\b|Reading|MS\.|MSS\.|Cp\.|Compare)", re.I
)
# (book, first line text, line text where the next book begins or None, volume)
BOOKS = [
    (1, "Listen to the reed", "Touching this Second Book", 2),
    (2, "Touching this Second Book", None, 2),
    (3, "O Light of the Truth, Hus", "IN THE NAME OF GoD THE COMPASSIONATE, THE MERCIFUL.", 4),
    (4, "IN THE NAME OF GoD THE COMPASSIONATE, THE MERCIFUL.", None, 4),
]
MAXC = {1: 4010, 2: 3820, 3: 4820, 4: 3860}


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


def find(lines, mark, start=0):
    for i in range(start, len(lines)):
        if mark in lines[i]:
            return i
    raise SystemExit(f"mark not found: {mark!r}")


def book_units(lines, book, start_mark, end_mark, step=20):
    """Cut one book's English into units of `step` couplets.

    Margin numbers are read in order (longest rising run). Because the OCR moves them from
    their lines, each is tied only to a rough place in the text (its own line or the foot of
    its page). The place of couplet number T is then estimated from the nearest numbers by a
    local fit of text length against couplet number, which averages the displacement away."""
    a = find(lines, start_mark)
    b = find(lines, end_mark, a + 5) if end_mark else len(lines)
    mx = MAXC[book]
    text_lines, offsets, cand = [], [], []
    total = 0
    for i in range(a, b):
        raw = lines[i]
        s_ = raw.strip()
        if not s_ or PAGEHEAD_A.match(raw) or PAGEHEAD_B.match(s_):
            continue
        if re.match(r"^\d{1,4}(\s+\d{1,4})*$", s_):
            for t in s_.split():
                n = int(t)
                if n % 5 == 0 and 5 <= n <= mx:
                    cand.append((total, n))
            continue
        m = re.match(r"^(.*\S)\s+(\d{1,4})$", s_)
        if m and int(m.group(2)) % 5 == 0 and 5 <= int(m.group(2)) <= mx:
            cand.append((total, int(m.group(2))))
            s_ = m.group(1)
        if FOOT.match(s_):
            continue
        offsets.append(total)
        text_lines.append(s_)
        total += len(s_) + 1
    keep = [cand[k] for k in lis([n for _o, n in cand])]
    pos = [o for o, _n in keep]
    num = [n for _o, n in keep]

    def offset_of(T):
        k = bisect.bisect_left(num, T)
        lo, hi = max(0, k - 10), min(len(num), k + 10)
        idx = list(range(lo, hi))
        slopes = []
        for x in idx:
            for y in idx:
                if num[y] > num[x] and pos[y] > pos[x]:
                    slopes.append((pos[y] - pos[x]) / (num[y] - num[x]))
        sl = statistics.median(slopes) if slopes else (total / mx)
        est = [pos[x] + (T - num[x]) * sl for x in idx]
        return statistics.median(est)

    grid = list(range(step, mx + step, step))
    grid = [t for t in grid if t < num[-1] + step]
    cuts = [0.0] + [min(max(offset_of(t), 0.0), float(total)) for t in grid]
    cuts = [max(c, cuts[i - 1]) if i else c for i, c in enumerate(cuts)]
    units = []
    for (c0, c1), (t0, t1) in zip(zip(cuts, cuts[1:]), zip([0] + grid, grid)):
        i0 = bisect.bisect_left(offsets, c0)
        i1 = bisect.bisect_left(offsets, c1)
        if i1 <= i0:
            continue
        units.append({"first": t0 + 1, "last": t1, "text": re.sub(r"\s+", " ", " ".join(text_lines[i0:i1])).strip()})
    return units, len(keep), num[-1], 0


# Names that occur in the Persian titles of Ganjoor's sections, with the English forms Nicholson uses.
NAMES = {
    "موسی": ["Moses"], "فرعون": ["Pharaoh"], "سلیمان": ["Solomon"], "عمر": ["Umar", "'Umar", "Omar"],
    "بلال": ["Bilal"], "محمود": ["Mahmud"], "ایاز": ["Ayaz"], "مجنون": ["Majnun"], "لیلی": ["Layla", "Laila"],
    "یوسف": ["Joseph"], "عیسی": ["Jesus"], "ابراهیم": ["Abraham"], "آدم": ["Adam"], "ابلیس": ["Iblis"],
    "زید": ["Zayd"], "خلیفه": ["Caliph"], "شیخ": ["Shaykh"], "نوح": ["Noah"], "یعقوب": ["Jacob"],
    "داود": ["David"], "بایزید": ["Bayazid"], "لقمان": ["Luqman"], "هود": ["Hud"], "پیغمبر": ["Prophet"],
    "بقال": ["Greengrocer"], "طوطی": ["parrot"], "شیر": ["lion"], "خرگوش": ["hare"], "عاشق": ["lover"],
    "موش": ["mouse"], "اشتر": ["camel"], "مرغ": ["bird"], "کنیزک": ["handmaid", "slave-girl"],
    "طبیب": ["physician"], "پادشاه": ["king"],
}


def name_check(sections_path, units, ref_to_unit):
    """Share of sections whose Persian title names someone or something (NAMES) where the
    English of the units covering the section, plus one unit either side, has the English
    form. This is the proper-names check of scripts/translations/README.md, run on titles."""
    hit = tot = 0
    for sec in json.load(open(sections_path, encoding="utf-8")):
        u = ref_to_unit.get(sec["first_ref"])
        if u is None:
            continue
        found = [k for k in NAMES if k in sec["title"]]
        if not found:
            continue
        last = ref_to_unit.get(sec["last_ref"], u)
        text = " ".join(units[max(0, u - 1) : last + 2]).lower()
        tot += 1
        hit += any(any(w.lower() in text for w in NAMES[k]) for k in found)
    return hit, tot


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--vol2", required=True)
    ap.add_argument("--vol4", required=True)
    ap.add_argument("--tess", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--sections", required=True, help="rumi.masnavi.sections.json written by ganjoor_to_tess.py")
    ap.add_argument("--report")
    a = ap.parse_args()
    ocr = {2: open(a.vol2, encoding="utf-8", errors="replace").read().split("\n"),
           4: open(a.vol4, encoding="utf-8", errors="replace").read().split("\n")}
    persian = {}
    for line in open(a.tess, encoding="utf-8"):
        m = re.match(r"<(rumi\.masnavi\.(\d)\.(\d+)\.(\d))>\t(.*)", line.rstrip("\n"))
        if m:
            persian.setdefault((int(m.group(2)), int(m.group(3))), []).append((m.group(1), m.group(5)))
    couplets = {}
    for (d, c) in persian:
        couplets[d] = max(couplets.get(d, 0), c)
    units, ref_to_unit, xs, ys, report = [], {}, [], [], {}
    for book, sm, em, vol in BOOKS:
        us, nanch, last_end, tail = book_units(ocr[vol], book, sm, em)
        report[book] = {"units": len(us), "anchors_kept": nanch, "last_anchor": last_end,
                        "persian_couplets": couplets[book], "tail_chars": tail}
        for i, u in enumerate(us):
            first, last = u["first"], u["last"]
            if i == len(us) - 1:
                last = couplets[book]  # the Persian past the last number joins the last unit
            idx = len(units)
            units.append(u["text"])
            plen = 0
            for c in range(first, last + 1):
                for ref, t in persian.get((book, c), []):
                    ref_to_unit[ref] = idx
                    plen += len(t)
            xs.append(plen)
            ys.append(len(u["text"]))
    hit, ntot = name_check(a.sections, units, ref_to_unit)
    r = statistics.correlation(xs, ys)  # not a test here: the units are all about 20 couplets long
    ratios = [e / p for e, p in zip(ys, xs) if p]
    q = statistics.quantiles(ratios, n=10)
    refs = tess_refs(a.tess)
    covered = sum(1 for k in refs if k in ref_to_unit)
    print("units", len(units), "covered", covered, "of", len(refs), "names check", hit, "of", ntot, round(hit / max(ntot, 1), 3), "english/persian length deciles", [round(x, 2) for x in (q[0], q[4], q[8])])
    print(report)
    path = write_aligned(
        a.out_dir, "fa", os.path.basename(a.tess)[:-5], units, ref_to_unit,
        attribution="Reynold A. Nicholson, The Mathnawi of Jalalu'ddin Rumi, Books I to IV (London: Luzac, Gibb Memorial Series, 1926 and 1930), via the Internet Archive",
        license="Public domain in the United States (published 1926 and 1930). Nicholson died in 1945, so the term in the United Kingdom has not yet run.",
        sources=[
            {"translator": "Reynold A. Nicholson", "year": "1926", "title": "The Mathnawi of Jalalu'ddin Rumi, vol. II, translation of Books I and II",
             "url": "https://archive.org/details/mathnawiofjalalu0002unse", "source_url": "https://archive.org/details/mathnawiofjalalu0002unse",
             "publisher": "Luzac & Co., London (Gibb Memorial Series, new series IV)", "mode": "units of 20 couplets placed by the margin numbers"},
            {"translator": "Reynold A. Nicholson", "year": "1930", "title": "The Mathnawi of Jalalu'ddin Rumi, vol. IV, translation of Books III and IV",
             "url": "https://archive.org/details/mathnawiofjalalu0004unse", "source_url": "https://archive.org/details/mathnawiofjalalu0004unse",
             "publisher": "Luzac & Co., London (Gibb Memorial Series, new series IV)", "mode": "units of 20 couplets placed by the margin numbers"},
        ],
        confidence="medium", approximate=True, tess_refs=refs, verified_by="names",
        name_check={"name_check_hit_rate": round(hit / max(ntot, 1), 3), "name_check_n": ntot},
        notes=f"Books I to IV only. Units of 20 couplets: the place of each couplet number in Nicholson's text is estimated from the margin numbers the OCR kept (about two thirds), plus a drift of up to ten couplets between Nicholson's text and Ganjoor's. Names check {hit} of {ntot} section titles. Per book: {report}",
    )
    print(path)
    if a.report:
        json.dump({"units": len(units), "length_correlation": r, "coverage": covered, "refs": len(refs), "books": report}, open(a.report, "w"), indent=1)


if __name__ == "__main__":
    main()
