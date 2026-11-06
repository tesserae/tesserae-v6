#!/usr/bin/env python3
"""Eusebius, Church History: McGiffert's translation (Nicene and Post-Nicene
Fathers, series 2, vol. 1, 1890) aligned to texts/grc/eusebius_caesarea.historia_ecclesiastica
at CHAPTER level.

Source: the New Advent transcription (newadvent.org/fathers/2501NN.htm, one page per
book, an `<h2>Chapter N. Title.</h2>` heading above each chapter, paragraphs
opening with McGiffert's section numbers). Footnote spans and links are removed.

Why chapter level and not section: our Greek numbers sections by the Heinichen
and Schwartz scheme and McGiffert by his own, and they differ in places, so a
section-to-section pairing could be wrong while looking exact. A chapter is the
shared unit of both numberings, so every one of our references takes the English
of its whole chapter (the book heading lines 'x.0.0' have no English and stay
unpaired).

    align_eusebius_mcgiffert.py SRC_DIR OUT_DIR [--dry]
SRC_DIR holds b01.htm .. b10.htm.
"""
import os
import re
import sys

from lxml import html as LH

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from chapter_common import load_work, tail, finish, clean   # noqa: E402

src_dir, out_dir = sys.argv[1:3]
dry = '--dry' in sys.argv

english = {}          # (book, chapter) -> text
for book in range(1, 11):
    doc = LH.fromstring(open(os.path.join(src_dir, f'b{book:02d}.htm'),
                             encoding='utf-8', errors='replace').read())
    for bad in doc.xpath('//span[@class="fisk" or @class="stiki"]|//script|//div[contains(@class,"CMtag")]'):
        bad.drop_tree()
    body = doc.xpath('//div[@id="springfield2"]')[0]
    cur, buf = None, []
    for el in body:
        if el.tag == 'h2':
            if cur:
                english[cur] = clean(' '.join(buf))
            m = re.match(r'\s*Chapter\s+(\d+)\.', el.text_content())
            cur = (book, int(m.group(1))) if m else None
            buf = []
        elif el.tag == 'p' and cur:
            t = el.text_content().strip()
            if t:
                buf.append(t)
    if cur:
        english[cur] = clean(' '.join(buf))

refs, src, files = load_work('grc', 'eusebius_caesarea.historia_ecclesiastica')
units, idx, ref_to_unit = [], {}, {}
missing = set()
for r in refs:
    parts = tail(r).split('.')
    if not all(x.isdigit() for x in parts) or int(parts[1]) == 0:
        continue            # book headings and non-numbered prefaces: no English chapter
    b, c = int(parts[0]), int(parts[1])
    t = english.get((b, c))
    if not t:
        missing.add((b, c))
        continue
    if (b, c) not in idx:
        idx[(b, c)] = len(units)
        units.append(t)
    ref_to_unit[r] = idx[(b, c)]
ours = {(int(tail(r).split('.')[0]), int(tail(r).split('.')[1])) for r in refs
        if all(x.isdigit() for x in tail(r).split('.')) and int(tail(r).split('.')[1])}
print(f'English chapters {len(english)}, our chapters {len(ours)}, '
      f'English only {sorted(set(english) - ours)[:10]}, ours only {sorted(missing)[:10]}')
finish('grc', 'eusebius_caesarea.historia_ecclesiastica', units, ref_to_unit, refs, src,
       out_dir=out_dir, dry=dry, mode='chapter',
       attribution='Arthur Cushman McGiffert, in Nicene and Post-Nicene Fathers, series 2, vol. 1; '
                   'transcription by New Advent',
       license='Public domain (published 1890)',
       sources=[{'translator': 'Arthur Cushman McGiffert', 'year': 1890,
                 'place': 'New York', 'publisher': 'The Christian Literature Company',
                 'title': 'Eusebius: Church History, Life of Constantine, Oration in Praise of Constantine (NPNF series 2, vol. 1)',
                 'mode': 'chapter', 'ref_composition': ['book', 'chapter'],
                 'url': 'https://www.newadvent.org/fathers/2501.htm',
                 'pd_reason': 'published 1890'}],
       notes='Chapter-level units: every Greek section of a chapter shows the English of the whole chapter. '
             'The book heading lines (chapter 0) have no English.')
