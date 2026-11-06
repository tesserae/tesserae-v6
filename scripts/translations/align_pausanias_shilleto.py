#!/usr/bin/env python3
"""Pausanias, Description of Greece: A. R. Shilleto's translation (Bohn's
Classical Library, 2 vols., London, 1886) aligned to
texts/grc/pausanias.description_of_greece at CHAPTER level.

Source: the Internet Archive OCR of both volumes (pausaniasdescrip01pausuoft,
books 1 to 6, and pausaniasdescrip00pausiala, books 7 to 10). Shilleto prints
`CHAPTER <roman numeral>` above each chapter and does not number sections, so a
chapter is the finest unit the English gives (our Greek numbers sections inside
each chapter, which all take the English of their chapter).

The OCR garbles about a tenth of the numerals (Y for V, XTII for XIII, LITE for
LIII), so the walk does not trust them: the chapter counts of our own text
(book 1 has 44, book 2 has 38, and so on) give the expected next chapter, a
parsed numeral is used only to notice a heading the OCR lost (a jump), and a
chapter heading read after the last chapter of a book opens the next book.
Footnote blocks, running heads and page numbers are dropped and words split at a
line end are rejoined.

    align_pausanias_shilleto.py SRC_DIR OUT_DIR [--dry]
SRC_DIR holds the two OCR text files.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from chapter_common import (load_work, tail, finish, roman_ocr, dehyphenate,   # noqa: E402
                            drop_footnotes, clean)

src_dir, out_dir = sys.argv[1:3]
dry = '--dry' in sys.argv

refs, src, _ = load_work('grc', 'pausanias.description_of_greece')
nchap = {}
for r in refs:
    b, c, s = (int(x) for x in tail(r).split('.'))
    nchap[b] = max(nchap.get(b, 0), c)

HEAD = re.compile(r'^\s*C[HI]+A[PF]T\w*\s+([A-Za-z0-9 ]{1,9})[.,]?\s*$')
RUNNING = re.compile(r'^\s*((\d+\s+)?PAUSANIA\S*\s*\d*|BOOK\s+[IVXLY]+\b[^a-z]{0,30})\s*$')
PAGE = re.compile(r'^\s*\d{1,3}\s*$')

english = {}
b, c = 1, 0
irregular = []
for fn in ('pausaniasdescrip01pausuoft.txt', 'pausaniasdescrip00pausiala.txt'):
    lines = open(os.path.join(src_dir, fn), encoding='utf-8', errors='replace').read().split('\n')
    cur, buf = None, []
    started = False
    for ln in lines:
        if re.match(r'^\s*(END\s+OF\s+VOL|INDEX\.?\s*$)', ln):
            break                       # the text of the volume ends here
        m = HEAD.match(ln)
        if m:
            if cur:
                english[cur] = buf
            p = roman_ocr(m.group(1))
            if p == 1 and c >= 3:
                b, c = b + 1, 1                       # numeral 1 after a run of chapters: next book
            elif p is not None and c + 1 <= p <= c + 3 and p <= nchap.get(b, 0):
                if p != c + 1:
                    irregular.append((f'{b}.{p}', f'{p - c - 1} heading(s) lost before it'))
                c = p
            else:
                if p != c + 1:
                    irregular.append((f'{b}.{c + 1}', f'numeral read as {p}, placed by sequence'))
                c += 1
                if c > nchap.get(b, 0):
                    b, c = b + 1, 1
                    irregular.append((f'{b}.1', 'book opened by overflow of the previous count'))
            cur, buf = (b, c), []
            started = True
        elif cur:
            if PAGE.match(ln) or RUNNING.match(ln):
                continue
            buf.append(ln)
    if cur:
        english[cur] = buf

total = sum(nchap.values())
print(f'chapters read {len(english)} of {total} expected; last chapter reached {b}.{c}; irregular headings {len(irregular)}')
for x in irregular[:25]:
    print('  ', x)

units, idx, ref_to_unit = [], {}, {}
for r in refs:
    bk, ch, s = (int(x) for x in tail(r).split('.'))
    lines = english.get((bk, ch))
    if not lines:
        continue
    if (bk, ch) not in idx:
        txt = clean(dehyphenate('\n'.join(drop_footnotes(lines))))
        if len(txt) < 40:
            continue
        idx[(bk, ch)] = len(units)
        units.append(txt)
    ref_to_unit[r] = idx[(bk, ch)]
finish('grc', 'pausanias.description_of_greece', units, ref_to_unit, refs, src, out_dir=out_dir, dry=dry,
       mode='chapter',
       attribution='A. R. Shilleto, Pausanias\' Description of Greece (Bohn\'s Classical Library, 1886); scans at the Internet Archive',
       license='Public domain (published 1886)',
       sources=[{'translator': 'Arthur Richard Shilleto', 'year': 1886, 'place': 'London',
                 'publisher': 'George Bell and Sons (Bohn\'s Classical Library)',
                 'title': 'Pausanias\' Description of Greece, translated into English with notes and index, 2 vols.',
                 'mode': 'chapter', 'ref_composition': ['book', 'chapter'],
                 'url': 'https://archive.org/details/pausaniasdescrip01pausuoft and https://archive.org/details/pausaniasdescrip00pausiala',
                 'pd_reason': 'published 1886'}],
       notes='Chapter-level units: every Greek section of a chapter shows the English of the whole chapter. '
             f'{len(irregular)} chapter headings had OCR-damaged numerals and were placed by sequence.')
