#!/usr/bin/env python3
"""Josephus, Life (Vita): Thackeray's Loeb of 1926 (volume 1, public domain), aligned
by the running heads of its English pages.

WHY. The installed alignment gives 76 of the corpus's 430 references an English
unit (Whiston, from Perseus). The corpus numbers the Life in Niese's SMALL sections,
1 to 430. Whiston numbers it in 76 large sections. The installed file pairs Whiston's
section n with Niese's section n for n = 1 to 76, which is the wrong English beside
the Greek for most of them (Niese's section 76 is nowhere near Whiston's), and it covers
nothing from 77 on. This replaces it.

HOW. Every English page of Thackeray's Loeb carries a running head naming the small
sections that begin on it ("THE LIFE, 4-11"), the same numbers our references use.
The English between that head and the next Greek page's head ("JOSEPHUS") is the
page, and every reference from a to b takes it. The first page has no such head (the
Life opens on it) and holds sections 1 to 3. A section that begins on one page and
runs on to the next takes the page on which it begins.

THREE SCANS. OCR damages the heads of some pages in each scan, so the three
archive.org scans are read and, for each range of sections, the first scan in which
its head reads cleanly supplies the page. A head is accepted only if it continues the
chain of the heads before it (a at most one past the previous b, b between a and
a+14), which rejects numerals the OCR misread ("188-145" for "138-145").

CHECKS. Names (Greek section against its page, using the same name test as every other
alignment) and the share of the 430 references covered. Length correlation is not
meaningful (pages hold 5 to 7 sections whatever their length).

Usage:
    python align_josephus_vita.py --scans A.txt B.txt C.txt \\
        --tess texts/grc/flavius_josephus.josephi_vita.tess --out OUT.json
"""
import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import proper_names as V  # noqa: E402

HEAD = re.compile(r'^\s*THE LIFE[,. ]+(\d{1,3})\s*[-—–.]+\s*(\d{1,3})\s*$')
GREEK_HEAD = re.compile(r'^\s*(JOSEPHUS|IOSHUOY BIO.*)\s*$')
FOOT = re.compile(r'^\s*(?:\d{1,2}|[a-eA-E]|[§*])\s+(?:See|Or|Cf|i\.e|Lit|The|So|Text|MSS|Niese|Probably|Probable|Perhaps|A\.|B\.|Ap\.)\b')


def pages_of(path):
    lines = open(path, encoding='utf-8', errors='ignore').read().split('\n')
    heads = [(i, int(m.group(1)), int(m.group(2))) for i, lx in enumerate(lines)
             if (m := HEAD.match(lx))]
    out = {}
    prev_b = None
    for k, (i, a, b) in enumerate(heads):
        ok = a <= b <= a + 14 and (prev_b is None or prev_b <= a <= prev_b + 1)
        if not ok:
            continue
        prev_b = b
        end = len(lines)
        for j in range(i + 1, len(lines)):
            if GREEK_HEAD.match(lines[j]) or HEAD.match(lines[j]):
                end = j
                break
        out[(a, b)] = clean_page(lines[i + 1:end])
    # the first page: from "(1)" of the English to the next Greek head
    for i, lx in enumerate(lines):
        if re.match(r"^\s*['‘’]?\s*\(1\)\s+My family", lx):
            end = len(lines)
            for j in range(i + 1, len(lines)):
                if GREEK_HEAD.match(lines[j]) or HEAD.match(lines[j]):
                    end = j
                    break
            out[(1, 3)] = clean_page(lines[i:end])
            break
    return out


def clean_page(lines):
    keep = []
    for lx in lines:
        if FOOT.match(lx):
            break
        keep.append(lx)
    text = ' '.join(x.strip() for x in keep if x.strip())
    text = re.sub(r'(\w)- (\w)', r'\1\2', text)
    return re.sub(r'\s+', ' ', text).strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--scans', nargs='+', required=True)
    ap.add_argument('--tess', required=True)
    ap.add_argument('--out', required=True)
    args = ap.parse_args()

    pages = {}
    used = {}
    for n, path in enumerate(args.scans):
        for key, text in pages_of(path).items():
            if key not in pages and len(text) > 200:
                pages[key] = text
                used[key] = os.path.basename(path)
    print('pages with a clean head:', len(pages), ' by scan:',
          {s: sum(1 for v in used.values() if v == s) for s in set(used.values())})

    refs = []
    for line in open(args.tess, encoding='utf-8', errors='ignore'):
        m = re.match(r'<(j\. vit\. (\d+))>\s*(.*)', line)
        if m:
            refs.append((m.group(1), int(m.group(2)), m.group(3)))
    ranges = sorted(pages)
    units, unit_of, ref_to_unit = [], {}, {}
    for ref, n, greek in refs:
        page = next((k for k in ranges if k[0] <= n <= k[1]), None)
        if page is None:
            continue
        if page not in unit_of:
            unit_of[page] = len(units)
            units.append(pages[page])
        ref_to_unit[ref] = unit_of[page]
    missing = [n for _, n, _ in refs if f'j. vit. {n}' not in ref_to_unit]
    pairs = []
    by_unit = {}
    for ref, n, g in refs:
        if ref in ref_to_unit:
            by_unit.setdefault(ref_to_unit[ref], []).append(g)
    for u, gs in by_unit.items():
        pairs.append((' '.join(gs), units[u]))
    score = V.score(pairs, 'grc', sample=500)
    out = {
        'tess_work': 'grc/flavius_josephus.josephi_vita', 'language': 'grc',
        'n_tess_refs': len(refs), 'n_translated': len(ref_to_unit),
        'coverage': round(len(ref_to_unit) / len(refs), 4),
        'mean_source_lines_per_translation_unit': round(len(ref_to_unit) / len(units), 2),
        'alignment_confidence': 'high' if len(ref_to_unit) / len(refs) >= 0.95 and score[0] >= 0.5 else 'medium',
        'name_check_hit_rate': score[0], 'name_check_n': score[1], 'verified_by': 'names',
        'sources': [{
            'translator': 'H. St. J. Thackeray', 'year': 1926,
            'title': 'Josephus, Vol. 1: The Life, Against Apion (Loeb Classical Library 186)',
            'publisher': "William Heinemann / G. P. Putnam's Sons",
            'mode': 'page', 'ref_composition': ['section'],
            'source_url': 'https://archive.org/details/josephuswithengl01joseuoft',
        }],
        'license': 'Public domain in the United States (first published 1926).',
        'attribution': 'H. St. J. Thackeray (1926), Loeb Classical Library, via the Internet Archive',
        'n_units_stored': len(units), 'units': units, 'ref_to_unit': ref_to_unit,
    }
    json.dump(out, open(args.out, 'w', encoding='utf-8'), ensure_ascii=False)
    print(f'refs {len(refs)} translated {len(ref_to_unit)} coverage {out["coverage"]:.4f} units {len(units)} '
          f'refs per unit {out["mean_source_lines_per_translation_unit"]} names {score}')
    print('uncovered sections:', missing)


if __name__ == '__main__':
    main()
