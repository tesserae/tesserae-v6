#!/usr/bin/env python3
"""Polyaenus, Stratagems, in R. Shepherd's translation of 1793.

Source: Internet Archive bim_eighteenth-century_polynuss-stratagems-of_polyaenus-of-lampsacus_1793
(OCR text of the 1793 printing, London: George Nicol). Only this 1793 text is used.
The Attalus revision may carry its editor's rights, so none of its wording is used
here, and its chapter lists were not needed.

WHY THE CHAPTER NUMBERS ARE NOT USED

Shepherd divides each book into chapters, one general each, in the order of the
Greek. His printed numerals are garbled by the scan and, where they can be read,
do not always agree with the numbering of our Greek (a first version that numbered
his chapters by their numerals paired "Thibron" with a chapter about Mnasippidas,
found by reading five passages). What does agree is the ORDER of the generals, and
each chapter head names its general ("THEMISTOCLES.").

METHOD: THE ORDER OF THE NAMED GENERALS

Within each book the English blocks (one per head) and our Greek chapters are two
ordered lists. A block can pair with a chapter only if the general's name in the
head matches a capitalised name in the first section of the chapter (the canonical
forms of proper_names.py: a three-letter prefix, a consonant skeleton, or a close
letter ratio). The pairing is the longest order-preserving set of such matches (a
longest common subsequence), so one false or missing match cannot shift the rest.
A block pairs with its matched chapter and, when the next block is matched too, with
the chapters between the two (a head the scan lost leaves its chapter inside the
block before it, which is then one coarse unit, not a wrong one). Blocks whose head
name cannot be read, or matches no chapter, stay unpaired. Chapters of our Greek that
no matched block reaches stay unpaired. The book openings (the emperors' address) are
never paired.

Precision is chosen over coverage on purpose: wrong English beside right Greek is
invisible to the reader who needs the English.
"""
import difflib
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import loeb_common as C
import proper_names as V

SRC_FILE = os.path.join(C.SRC,
                        'bim_eighteenth-century_polynuss-stratagems-of_polyaenus-of-lampsacus_1793.txt')
# 0-based line index where each book begins in the scan
STARTS = {1: 3108, 2: 6597, 3: 10180, 4: 12413, 5: 15480, 6: 18646, 7: 21804, 8: 25394}
END = 29000
HEAD = re.compile(r'^\W{0,3}"?\*?\s*C\s?H\s?A\s?P\b')
GREEK_CAPS = ('ΑΒΓΔΕΖΗΘΙΚΛΜΝΞΟΠ'
              'ΡΣΤΥΦΧΨΩἈἉἘἙἨἩἸἹ'
              'ὈὉὨὩᾈᾉᾘᾙᾨᾩ')


def heading_name(raw, i):
    """The general's name printed under (or after) a chapter head, spaces the scan
    put inside it removed. Empty when no clean all-capitals line is found."""
    for j in range(i, min(i + 4, len(raw))):
        t = raw[j]
        if j == i:
            t = re.sub(r'^\W{0,3}"?\*?\s*C\s?H\s?A\s?P\b\W*(?:[IVXLivxl1]{1,8}[.,:;]\s*)?', '', t)
        t = re.sub(r'[^A-Za-z]', '', t.strip())
        if len(t) >= 4 and t.upper() == t and not re.fullmatch(r'[IVXL]+', t):
            return t
    return ''


def greek_names(text):
    return [w for w in re.findall(r'[Ͱ-Ͽἀ-῿]+', text)
            if len(w) > 2 and w[0] in GREEK_CAPS][:8]


def name_match(eng_name, words):
    if not eng_name:
        return False
    c = V.canon(eng_name)
    if len(c) < 3:
        return False
    for w in words:
        g = V.canon(w)
        if len(g) < 3:
            continue
        if g[:3] == c[:3] or (V.skel(g)[:3] == V.skel(c)[:3] and len(V.skel(c)) >= 3) or \
                difflib.SequenceMatcher(None, g, c).ratio() >= 0.7:
            return True
    return False


def lcs_pairs(match, nb, nc):
    """Longest order-preserving set of (block, chapter) pairs with match[i][j]."""
    best = [[0] * (nc + 1) for _ in range(nb + 1)]
    for i in range(nb - 1, -1, -1):
        for j in range(nc - 1, -1, -1):
            best[i][j] = max(best[i + 1][j], best[i][j + 1],
                             best[i + 1][j + 1] + 1 if match[i][j] else 0)
    pairs, i, j = [], 0, 0
    while i < nb and j < nc:
        if match[i][j] and best[i][j] == best[i + 1][j + 1] + 1:
            pairs.append((i, j))
            i += 1
            j += 1
        elif best[i + 1][j] >= best[i][j + 1]:
            i += 1
        else:
            j += 1
    return pairs


def clean_lines(lines):
    keep = []
    for ln in lines:
        t = ln.replace('ſ', 's')
        t = re.sub(r'[ \t]+', ' ', t).strip()
        if not t:
            keep.append('')
            continue
        letters = sum(c.isalpha() for c in t)
        if letters < 4 or letters < 0.55 * len(t):
            continue
        if re.match(r'^(STRATAGEMS? OF WAR|POLYAENUS|POLYANUS|BOOK\b|CHAP\b)', t, re.I) and len(t) < 40:
            continue
        keep.append(t)
    return keep


def main():
    raw = open(SRC_FILE, encoding='utf-8', errors='replace').read().split('\n')
    tl = C.load_tess(os.path.join(C.TEXTS, 'grc', 'polyaenus.strategemata.tess'))
    chap_refs = {}
    src_of = {}
    for ref, t in tl:
        src_of.setdefault(ref, t)
        m = re.search(r'(\d+)\.(\d+)(?:\.(\d+))?\s*$', ref)
        if m:
            chap_refs.setdefault((int(m.group(1)), int(m.group(2))), []).append(ref)
    mapping = {}
    total_blocks = total_matched = 0
    for b in range(1, 9):
        lo, hi = STARTS[b], STARTS.get(b + 1, END)
        idx = [i for i in range(lo, hi) if HEAD.match(raw[i])]
        if not idx:
            print(f'book {b}: no chapter heads found')
            continue
        lead = ' '.join(raw[lo:idx[0]])[:1200]
        lead_is_chapter = not (re.search(r'ADDRESS|PROOEMIUM|PROEMIUM|PREFATORY|Antoninus|majesties', lead, re.I)
                               or idx[0] - lo < 8)
        starts = ([lo] if lead_is_chapter else []) + idx
        names = []
        for s in starts:
            names.append(heading_name(raw, s) if HEAD.match(raw[s]) else heading_name(raw, s + 1))
        chapters = sorted(c for (bb, c) in chap_refs if bb == b)
        cwords = {c: greek_names(src_of[chap_refs[(b, c)][0]]) for c in chapters}
        match = [[name_match(names[i], cwords[chapters[j]]) for j in range(len(chapters))]
                 for i in range(len(starts))]
        pairs = lcs_pairs(match, len(starts), len(chapters))
        pj = {i: j for i, j in pairs}
        total_blocks += len(starts)
        total_matched += len(pairs)
        print(f'book {b}: {len(starts)} blocks, {len(chapters)} of our chapters, {len(pairs)} matched by name')
        for i, s in enumerate(starts):
            if i not in pj:
                continue
            e = starts[i + 1] if i + 1 < len(starts) else hi
            block = clean_lines(raw[s + (1 if HEAD.match(raw[s]) else 0):e])
            text = C.clean_english(C.strip_footnotes(block))
            if len(text) < 60:
                continue
            j = pj[i]
            j_end = pj[i + 1] - 1 if (i + 1) in pj else j
            for jj in range(j, j_end + 1):
                for ref in chap_refs.get((b, chapters[jj]), []):
                    mapping.setdefault(ref, text)
    print(f"blocks {total_blocks}, matched by general's name {total_matched}")
    source = {'translator': 'R. Shepherd', 'year': 1793, 'place': 'London', 'publisher': 'George Nicol',
              'title': "Polyaenus's Stratagems of War, translated from the original Greek",
              'license': 'public domain', 'mode': 'chapter', 'ref_composition': ['book', 'chapter'],
              'url': 'https://archive.org/details/bim_eighteenth-century_polynuss-stratagems-of_polyaenus-of-lampsacus_1793',
              'source_url': 'https://archive.org/details/bim_eighteenth-century_polynuss-stratagems-of_polyaenus-of-lampsacus_1793'}
    row = C.finish('polyaenus.strategemata', 'grc', tl, mapping, source,
                   'Public domain: published 1793 (London: George Nicol), the 1793 text only.',
                   'Internet Archive')
    C.save_report('polyaenus', [row])


if __name__ == '__main__':
    main()
