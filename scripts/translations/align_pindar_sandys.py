#!/usr/bin/env python3
"""Pindar's Odes, from Sir John Sandys' Loeb of 1915.

Source: Internet Archive bwb_P7-ACW-840 (OCR text), US public domain by
publication date (London: Heinemann; New York: Putnam, 1915).

METHOD: THE RUNNING HEAD, AS IN align_statius.py

Each English page after the first of an ode is headed with the collection, the
ode and the Greek lines it renders: "OLYMPIAN ODES I 18-40". The first English
page of an ode carries no range (its lines run from 1 to the line before the
next page's start), and its ode is named by the head of the Greek page that
opens the ode ("OLYMPIAN I"). Our references are collection.ode.line and the
printed ranges are in the same line numbers, which is verified, not assumed:
the last printed range of every ode is compared with the line count of our text,
and an ode whose numbering disagrees is skipped and reported.

OCR damage to heads is the usual kind (digits read as letters: "1os-116",
"ss-71"). Digit-like letters are mapped back inside the number fields only, a
page whose span is implausible is repaired from contiguity or dropped, and a
page that cannot be made plausible leaves its lines unpaired.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import loeb_common as C

SRC_FILE = os.path.join(C.SRC, 'bwb_P7-ACW-840.txt')
COLL = {'OLYMPIAN': 'o', 'PYTHIAN': 'p', 'NEMEAN': 'n', 'ISTHMIAN': 'i'}
ROMAN = {'I': 1, 'V': 5, 'X': 10, 'L': 50}
DIGIT = str.maketrans({'o': '0', 'O': '0', 's': '5', 'S': '5', 'l': '1', 'I': '1', 'g': '9', 'B': '8'})

NUM = r'[0-9osSlIgBtO]{1,5}'
RANGE = re.compile(r'^\W{0,3}(OLYMPIAN|PYTHIAN|NEMEAN|ISTHMIAN)\s+ODES\s+([IVXL1]{1,6})\s+(' + NUM +
                   r')\s*[-–—~]\s*(' + NUM + r')\s*\W*$')
OPEN = re.compile(r'^\W{0,3}(OLYMPIAN|PYTHIAN|NEMEAN|ISTHMIAN)\s+([IVXL1]{1,6})\s*\W*$')
ODES_HEAD = re.compile(r'^\W{0,3}THE\s+(OLYMPIAN|PYTHIAN|NEMEAN|ISTHMIAN)\s+ODES')
FOR_HEAD = re.compile(r'^\W{0,3}[IVXL]+\s*\.\s*[—–-]+\s*FOR\b')
GREEK_PAGE = re.compile(r'^\W{0,3}PINDAR\W*$')
MIN_SPAN, MAX_SPAN = 2, 70


def roman(s):
    s = s.replace('1', 'I')
    total, prev = 0, 0
    for ch in reversed(s):
        v = ROMAN.get(ch, 0)
        total += v if v >= prev else -v
        prev = max(prev, v)
    return total


def num(s):
    s = s.lstrip('t')
    s = s.translate(DIGIT)
    return int(s) if s.isdigit() else None


def upper_block(block):
    t = ' '.join(block)
    letters = [c for c in t if c.isalpha()]
    return bool(letters) and sum(1 for c in letters if c.isupper()) / len(letters) > 0.6


def english_after(raw, start, stop, opener=False):
    body = []
    for j in range(start, stop):
        if GREEK_PAGE.match(raw[j]):
            break
        body.append(raw[j])
    if opener:
        # drop the ode's title lines (all capitals) before the first prose
        blocks, cur = [], []
        for ln in body:
            if ln.strip():
                cur.append(ln)
            elif cur:
                blocks.append(cur)
                cur = []
        if cur:
            blocks.append(cur)
        while blocks and upper_block(blocks[0]):
            blocks.pop(0)
        body = [ln for b in blocks for ln in (b + [''])]
    return C.clean_english(C.strip_footnotes(body))


def parse():
    raw = open(SRC_FILE, encoding='utf-8', errors='replace').read().split('\n')
    ev = []
    for i, line in enumerate(raw):
        m = RANGE.match(line)
        if m:
            a, b = num(m.group(3)), num(m.group(4))
            ev.append((i, 'range', COLL[m.group(1)], roman(m.group(2)), a, b))
            continue
        m = OPEN.match(line)
        if m and roman(m.group(2)):
            ev.append((i, 'open', COLL[m.group(1)], roman(m.group(2)), None, None))
    return raw, ev


def build():
    raw, ev = parse()
    pages, fixed, dropped = [], 0, 0
    for k, (i, kind, coll, ode, a, b) in enumerate(ev):
        nxt = ev[k + 1][0] if k + 1 < len(ev) else len(raw)
        if kind == 'open':
            # the English opener lies after the last "THE ... ODES" or "-FOR" head
            # inside this ode's own Greek opening, up to the next range head
            seg_end = nxt
            cut = None
            for j in range(i + 1, seg_end):
                if ODES_HEAD.match(raw[j]) or FOR_HEAD.match(raw[j]):
                    cut = j
            if cut is None:
                continue
            # skip any further all-caps title lines directly under the head
            text = english_after(raw, cut + 1, seg_end, opener=True)
            pages.append([coll, ode, 'open', None, text])
        else:
            text = english_after(raw, i + 1, nxt)
            pages.append([coll, ode, 'range', (a, b), text])
    # resolve spans per ode in order
    out = []
    by_ode = {}
    for p in pages:
        by_ode.setdefault((p[0], p[1]), []).append(p)
    for (coll, ode), plist in by_ode.items():
        prev_end = None
        for p in plist:
            if p[2] == 'open':
                firsts = [q[3][0] for q in plist if q[2] == 'range' and q[3][0]]
                if firsts and 3 <= firsts[0] - 1 <= 40:
                    out.append((coll, ode, 1, firsts[0] - 1, p[4]))
                    prev_end = firsts[0] - 1
                else:
                    dropped += 1
                continue
            a, b = p[3]
            if a is None or b is None:
                dropped += 1
                continue
            span = b - a + 1
            if not (MIN_SPAN <= span <= MAX_SPAN) or (prev_end is not None and a > prev_end + 30):
                if prev_end is not None and MIN_SPAN <= b - (prev_end + 1) + 1 <= MAX_SPAN:
                    a = prev_end + 1
                    fixed += 1
                else:
                    dropped += 1
                    continue
            if prev_end is not None and a <= prev_end:
                a = prev_end + 1
                if a > b:
                    dropped += 1
                    continue
            out.append((coll, ode, a, b, p[4]))
            prev_end = b
    return out, fixed, dropped, len(pages)


def main():
    out, fixed, dropped, n = build()
    print(f'pages parsed: {n}   kept: {len(out)}   repaired: {fixed}   dropped: {dropped}')
    tl = C.load_tess(os.path.join(C.TEXTS, 'grc', 'pindar.odes.tess'))
    lines, ode_len = {}, {}
    for ref, _ in tl:
        m = re.search(r'pind\.\s*([a-z])\.\s*(\d+)\.(\d+)\s*$', ref)
        if m:
            key = (m.group(1), int(m.group(2)), int(m.group(3)))
            lines[key] = ref
            ode_len[(key[0], key[1])] = max(ode_len.get((key[0], key[1]), 0), key[2])
    # does the printed numbering agree with ours?
    top = {}
    for coll, ode, a, b, _ in out:
        top[(coll, ode)] = max(top.get((coll, ode), 0), b)
    skip = set()
    for key, t in sorted(top.items()):
        ll = ode_len.get(key)
        if ll is None or t > ll + 2 or t < 0.8 * ll:
            print(f'    ode {key[0]}.{key[1]}: printed lines run to {t}, ours to {ll}: SKIPPED (numbering differs or pages lost)')
            skip.add(key)
    mapping = {}
    for coll, ode, a, b, text in out:
        if (coll, ode) in skip or not text:
            continue
        for ln in range(a, b + 1):
            ref = lines.get((coll, ode, ln))
            if ref and ref not in mapping:
                mapping[ref] = text
    source = {'translator': 'John Sandys', 'year': 1915, 'place': 'London and New York',
              'publisher': "William Heinemann / G. P. Putnam's Sons",
              'title': 'The Odes of Pindar, including the principal fragments (Loeb Classical Library 56)',
              'license': 'public domain', 'mode': 'page', 'ref_composition': ['ode', 'line range'],
              'url': 'https://archive.org/details/bwb_P7-ACW-840',
              'source_url': 'https://archive.org/details/bwb_P7-ACW-840'}
    row = C.finish('pindar.odes', 'grc', tl, mapping, source,
                   'Public domain in the United States: published 1915 (John Sandys, Loeb Classical Library).',
                   'Internet Archive', clean_notes=True)
    row['skipped_odes'] = sorted('%s.%d' % k for k in skip)
    C.save_report('pindar', [row])


if __name__ == '__main__':
    main()
