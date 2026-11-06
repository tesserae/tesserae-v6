#!/usr/bin/env python3
# ruff: noqa: E741  (the corpus lines are called `l` in a dozen throwaway loops, as in the other scripts here)
"""Celsus, De Medicina: James Greive's translation, A Translation of Celsus's Eight Books of
Medicine (London, 1756), aligned to texts/la/celsus.de_medicina at CHAPTER level.

Source: Project Gutenberg 64207 (`CHAP. I.` headings; the eight books restart the numbering at
I). The books are told apart by the restart of the numerals, and the result is checked: the
chapter count of every book must equal ours (ours has the numbered chapters 1 to 10, 1 to 33, 1 to 27,
1 to 32, 1 to 28, 1 to 19, 1 to 33 and 1 to 25, plus the prefaces `pr`, which Greive prints as the opening of
the book and which share the unit of the book's first chapter) or the book is not written. Footnotes are
cut where Gutenberg sets them apart.

    align_celsus_greive.py SRC_FILE OUT_DIR [--dry]
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from chapter_common import load_work, tail, finish, clean, dehyphenate, roman_to_int   # noqa: E402

src_file, out_dir = sys.argv[1:3]
dry = '--dry' in sys.argv
lines = open(src_file, encoding='utf-8', errors='replace').read().split('\n')
refs, src, _ = load_work('la', 'celsus.de_medicina')
count = {}
for r in refs:
    p = tail(r).split('.')
    if p[0].isdigit() and p[1].isdigit():
        count[int(p[0])] = max(count.get(int(p[0]), 0), int(p[1]))
first = next(i for i, l in enumerate(lines) if re.match(r'^CHAP\. I\.\s*$', l))
stop = next((i for i, l in enumerate(lines) if re.match(r'^\*\*\* END OF', l)), len(lines))
book, chap, cur, buf, english = 1, 0, None, [], {}
for ln in lines[first:stop]:
    m = re.match(r'^CHAP\. ([IVXL]+)\.\s*$', ln)
    if m:
        v = roman_to_int(m.group(1))
        if cur:
            english[cur] = buf
        if v == 1 and chap > 1:
            book += 1
        chap, cur, buf = v, (book, v), []
        continue
    if cur and not re.match(r'^\s*\[Footnote', ln):
        buf.append(ln.strip())
english = {k: clean(dehyphenate('\n'.join(v))) for k, v in english.items()}
found = {b: max((c for (bb, c) in english if bb == b), default=0) for b in range(1, 9)}
print('chapters per book, English vs ours:', {b: (found[b], count.get(b)) for b in range(1, 9)})
units, idx, ref_to_unit = [], {}, {}
for r in refs:
    p = tail(r).split('.')
    if not p[0].isdigit() or found.get(int(p[0])) != count.get(int(p[0])):
        continue
    b = int(p[0])
    c = int(p[1]) if p[1].isdigit() else 1                    # a preface shares the first chapter's unit
    t = english.get((b, c))
    if not t:
        continue
    if (b, c) not in idx:
        idx[(b, c)] = len(units)
        units.append(t)
    ref_to_unit[r] = idx[(b, c)]
finish('la', 'celsus.de_medicina', units, ref_to_unit, refs, src, out_dir=out_dir, dry=dry, mode='chapter',
       attribution='James Greive, A Translation of Celsus\'s Eight Books of Medicine (London, 1756); Project Gutenberg eBook 64207',
       license='Public domain (published 1756)',
       sources=[{'translator': 'James Greive', 'year': 1756, 'place': 'London', 'publisher': 'D. Wilson and T. Durham',
                 'title': 'A Translation of Celsus\'s Eight Books of Medicine', 'mode': 'chapter', 'ref_composition': ['book', 'chapter'],
                 'url': 'https://www.gutenberg.org/ebooks/64207', 'pd_reason': 'published 1756'}],
       notes='Chapter-level units; the eighteenth-century English of Greive keeps his own chapter notes in places. A book preface shares the unit of the first chapter.')
