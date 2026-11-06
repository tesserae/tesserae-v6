#!/usr/bin/env python3
# ruff: noqa: E741  (the corpus lines are called `l` in a dozen throwaway loops, as in the other scripts here)
"""Arrian, Anabasis of Alexander: E. J. Chinnock's translation (London, 1884)
aligned to texts/grc/arrian.anabasis at CHAPTER level.

Source: Project Gutenberg 46976 (`BOOK I.` and `CHAPTER I.` headings, footnotes
gathered after the text). Chinnock's chapter divisions are the standard ones: the
chapter counts per book (29, 27, 30, 30, 29, 30, 30) equal those of our Greek, so
every Greek section takes the English of its chapter. Chinnock prints no section
numbers. Book 1's proem (our 1.0.x, Arrian's preface) is not in the translation
and stays unpaired.

    align_arrian_chinnock.py SRC_FILE OUT_DIR [--dry]
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from chapter_common import load_work, tail, finish, parse_headed   # noqa: E402

src_file, out_dir = sys.argv[1:3]
dry = '--dry' in sys.argv
lines = open(src_file, encoding='utf-8', errors='replace').read().split('\n')
first = next(i for i, l in enumerate(lines) if re.match(r'^BOOK I\.\s*$', l) and i > 500)
stop = next(i for i, l in enumerate(lines) if l.startswith('FOOTNOTES:'))
english = parse_headed(lines, re.compile(r'^BOOK ([IVX]+)\.\s*$'),
                       re.compile(r'^CHAPTER ([IVXL]+)\.\s*$'), first, stop)
# the italic one-line chapter heading under each CHAPTER line is a title, not text: drop it
english = {k: re.sub(r'^[A-Z][A-Z .,;:—\'’-]{6,}?\.\s+(?=[A-Z][a-z])', '', v) for k, v in english.items()}
refs, src, _ = load_work('grc', 'arrian.anabasis')
units, idx, ref_to_unit = [], {}, {}
for r in refs:
    b, c, s = (int(x) for x in tail(r).split('.'))
    t = english.get((b, c))
    if not t or c == 0:
        continue
    if (b, c) not in idx:
        idx[(b, c)] = len(units)
        units.append(t)
    ref_to_unit[r] = idx[(b, c)]
print(f'English chapters {len(english)}')
finish('grc', 'arrian.anabasis', units, ref_to_unit, refs, src, out_dir=out_dir, dry=dry, mode='chapter',
       attribution='E. J. Chinnock, The Anabasis of Alexander (London, 1884); Project Gutenberg eBook 46976',
       license='Public domain (published 1884)',
       sources=[{'translator': 'Edward James Chinnock', 'year': 1884, 'place': 'London',
                 'publisher': 'Hodder and Stoughton',
                 'title': 'The Anabasis of Alexander; or, The History of the Wars and Conquests of Alexander the Great',
                 'mode': 'chapter', 'ref_composition': ['book', 'chapter'],
                 'url': 'https://www.gutenberg.org/ebooks/46976', 'pd_reason': 'published 1884'}],
       notes='Chapter-level units. The proem (1.0.x) has no English in this translation.')
