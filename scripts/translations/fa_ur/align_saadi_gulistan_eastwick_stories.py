#!/usr/bin/env python3
"""Saadi, Gulistan: align Eastwick's English (1880) to the Persian by chapter and story.

The Persian text is saadi.gulistan (Ganjoor, from Persian Wikisource): a preface (bab 0),
chapters 1 to 7 of numbered stories (hekayat) and chapter 8 of numbered maxims (hekmat),
the references being saadi.gulistan.<chapter>.<story>.<line>. Eastwick's English (Internet
Archive OCR of the 1880 second edition, which the 2026 whole-work file already used, public domain) heads each story "Story N." and each
maxim "Maxim N." and each chapter "CHAPTER N."; the OCR has lost some of the story
headings. A unit is the English between two readable headings, and it covers the Persian
stories from its own number to the one before the next readable heading, so a lost
heading merges its story into the unit before it instead of guessing a boundary.

Usage:
    align_saadi_gulistan_eastwick_stories.py --src OCR.txt --tess saadi.gulistan.tess \
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

VAL = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100}
HEAD = re.compile(r"^\W{0,6}(Story|STORY|Maxim|MAXIM)\s+([IVXLCY]+)\b\.{0,2}")


def roman(s):
    s = s.replace("Y", "V")
    n = 0
    for a, b in zip(s, s[1:] + " "):
        n += -VAL[a] if b != " " and VAL[a] < VAL.get(b, 0) else VAL[a]
    return n


def clean(lines):
    paras = re.split(r"\n\s*\n", "\n".join(lines))
    out = []
    for p in paras:
        s = re.sub(r"\s+", " ", p).strip()
        if not s or len(s) < 3:
            continue
        if re.match(r"^\d{1,3}\s+\S", s) and len(s) < 1500:
            continue  # footnote
        if re.match(r"^\W*\d+\W*$", s):
            continue
        if s.isupper() and len(s) < 70:
            continue
        letters = sum(ch.isalpha() and ord(ch) < 0x250 for ch in s)
        if len(s) > 20 and letters < 0.6 * len(s):
            continue  # Persian or Arabic text in transliteration notes
        out.append(s)
    return " ".join(out)


def english(path):
    lines = open(path, encoding="utf-8", errors="replace").read().split("\n")
    pre = next(i for i, ln in enumerate(lines) if ln.startswith("IN THE NAME OF GOD, THE MERCIFUL"))
    ch1 = next(i for i, ln in enumerate(lines) if ln.strip() == "CHAPTER I." and i > pre)
    heads = []  # (line, kind, number)
    for i in range(ch1, len(lines)):
        m = HEAD.match(lines[i].strip())
        if m and "Story" in m.group(1).title() or (m and "Maxim" in m.group(1).title()):
            heads.append((i, m.group(1).title(), roman(m.group(2))))
    return lines, pre, ch1, heads


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True)
    ap.add_argument("--tess", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--report")
    a = ap.parse_args()
    lines, pre, ch1, heads = english(a.src)
    # standalone chapter headings that the OCR kept: first occurrence of each number
    markers = {}
    for i, ln in enumerate(lines):
        m = re.match(r"^\s*CHAPTER\s+([IVX]+)\.\s*$", ln)
        if m and i >= ch1 and roman(m.group(1)) not in markers:
            markers[roman(m.group(1))] = i
    # chapter numbering by resets of the story number and by the kept chapter headings;
    # chapter 8 is the Maxim run
    seq, chap, prev = [], 1, 0
    for i, kind, n in heads:
        if kind == "Maxim":
            chap = 8
        elif n <= prev:
            chap += 1
        chap = max(chap, max([c for c, ml in markers.items() if ml < i], default=1))
        if kind == "Story" and n <= prev and chap == 8:
            continue
        prev = n if kind == "Story" else 0
        seq.append((i, chap, n))
    # Persian side: stories per chapter
    persian = {}
    order = []
    for line in open(a.tess, encoding="utf-8"):
        m = re.match(r"<(saadi\.gulistan\.(\d+)\.(\d+)\.(\d+))>\t(.*)", line.rstrip("\n"))
        if m:
            persian.setdefault((int(m.group(2)), int(m.group(3))), []).append((m.group(1), m.group(5)))
            order.append(m.group(1))
    maxstory = {}
    for c, s in persian:
        maxstory[c] = max(maxstory.get(c, 0), s)
    # keep headings that fit the Persian counts and rise within their chapter
    good, last = [], {}
    for i, c, n in seq:
        if c in maxstory and 1 <= n <= maxstory[c] and n > last.get(c, 0):
            good.append((i, c, n))
            last[c] = n
    def chapter_lines(c):
        starts = markers.get(c)
        if starts is None:
            first = [i for i, cc, n in good if cc == c]
            starts = (first[0] - 3) if first else None
        nxt = [markers.get(cc) or next((i - 3 for i, c2, n in good if c2 == cc), None) for cc in range(c + 1, 9)]
        nxt = [x for x in nxt if x]
        if nxt:
            end = min(nxt)
        else:
            lastheads = [i for i, cc, n in good if cc == c]
            end = (lastheads[-1] + 150) if lastheads else len(lines)
        return starts, end

    def story_units(c):
        """[(first_story, last_story, text)] for chapter c from the readable headings."""
        out = []
        mine = [(i, n) for i, cc, n in good if cc == c]
        cs, ce = chapter_lines(c)
        for idx, (i, n) in enumerate(mine):
            nxt = mine[idx + 1] if idx + 1 < len(mine) else None
            end_line = nxt[0] if nxt else ce
            first_story = 1 if idx == 0 else n
            last_story = (nxt[1] - 1) if nxt else maxstory[c]
            start_line = cs if idx == 0 else i + 1
            out.append((first_story, last_story, clean(lines[start_line:end_line])))
        return out

    units, ref_to_unit, xs, ys = [], {}, [], []
    units.append(clean(lines[pre + 1 : ch1]))
    for k, ln in persian.get((0, 1), []):
        ref_to_unit[k] = 0
    chapter_mode = {}
    for c in sorted(maxstory):
        if c == 0:
            continue
        su = story_units(c)
        pl = [sum(len(t) for s in range(a_, b_ + 1) for _k, t in persian.get((c, s), [])) for a_, b_, _x in su]
        el = [len(x) for _a, _b, x in su]
        r_c = statistics.correlation(pl, el) if len(su) > 2 and len(set(pl)) > 1 else 0.0
        med = statistics.median([e / p for e, p in zip(el, pl) if p]) if pl else 1
        worst = max([max(e / p, p / e) / max(med, 1 / med) for e, p in zip(el, pl) if p and e] or [1])
        if r_c >= 0.8 and worst < 6:
            chapter_mode[c] = ("story", round(r_c, 3))
            for a_, b_, text in su:
                u = len(units)
                units.append(text)
                plen = 0
                for s_ in range(a_, b_ + 1):
                    for k, t in persian.get((c, s_), []):
                        ref_to_unit[k] = u
                        plen += len(t)
                xs.append(plen)
                ys.append(len(text))
        else:
            cs, ce = chapter_lines(c)
            text = clean(lines[cs:ce])
            u = len(units)
            units.append(text)
            plen = 0
            for s_ in range(1, maxstory[c] + 1):
                for k, t in persian.get((c, s_), []):
                    ref_to_unit[k] = u
                    plen += len(t)
            xs.append(plen)
            ys.append(len(text))
            chapter_mode[c] = ("chapter", round(r_c, 3))
    print("chapter modes", chapter_mode)
    r = statistics.correlation(xs, ys) if len(xs) > 2 else 0.0
    refs = tess_refs(a.tess)
    covered = sum(1 for k in refs if k in ref_to_unit)
    print("headings read", len(good), "of", sum(maxstory.values()) - 0, "persian stories; units", len(units),
          "coverage", covered, "of", len(refs), "length correlation", round(r, 3))
    path = write_aligned(
        a.out_dir, "fa", os.path.basename(a.tess)[:-5], units, ref_to_unit,
        attribution="Edward B. Eastwick, The Gulistan, or Rose-Garden, of Shekh Muslihu'd-din Sadi of Shiraz (London: Trübner & Co., 2nd ed., 1880), via the Internet Archive",
        license="Public domain (published 1880)",
        sources=[{
            "translator": "Edward B. Eastwick", "year": "1880",
            "title": "The Gulistan, or Rose-Garden",
            "url": "https://archive.org/details/TheGulistanOrRose-GardenOfShekhMuslihud-dinSadiOfShiraz-EdwardB.Eastwick",
            "source_url": "https://archive.org/details/TheGulistanOrRose-GardenOfShekhMuslihud-dinSadiOfShiraz-EdwardB.Eastwick",
            "publisher": "Trübner & Co., London (second edition)", "mode": "story by story where the OCR kept the heading",
        }],
        confidence="medium", approximate=True, tess_refs=refs, verified_by="length_correlation",
        notes=f"Chapters whose story headings read cleanly are aligned story by story, the others as a whole chapter: {chapter_mode}. Length correlation of all units {r:.3f}.",
    )
    print(path)
    if a.report:
        json.dump({"good": good, "units": len(units), "length_correlation": r, "coverage": covered, "refs": len(refs)}, open(a.report, "w"), indent=1)


if __name__ == "__main__":
    main()
