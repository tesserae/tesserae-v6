#!/usr/bin/env python3
# ruff: noqa: E741  (the corpus lines are called `l` in a dozen throwaway loops, as in the other scripts here)
"""Cassiodorus, Variae: Thomas Hodgkin's CONDENSED translation, The Letters of
Cassiodorus (London, 1886), aligned to texts/la/cassiodorus.variae at LETTER level.

HODGKIN'S BOOK IS A CONDENSED TRANSLATION, NOT A COMPLETE ONE. He renders the more
important letters nearly in full, summarizes the others in his own words, and
omits the Preface's rhetoric and some formulae. Every unit written here is
therefore Hodgkin's condensed rendering of the letter, and the file says so in
`sources`, in `notes` and in `short_attribution` (the same word is meant for the
Reader and the Sources page to show, so that nobody reads it as a full text).

Source: Internet Archive OCR (lettersofcassiod00cassuoft), the translation part of
the volume, which opens each letter with a heading ('2. KING THEODORIC TO THEON,
VIR SUBLIMIS.') in his own numbering, the numbering of Mommsen's edition and of
ours. The OCR garbles numerals (i for 1, ii for 11) and loses some headings, so a
letter is opened by a heading line whose numeral is, in order, within eight of the
one expected, or whose numeral is unreadable but whose text reads 'X TO Y'. A
letter whose heading is lost has its text merged into the letter before and its own
references are left unpaired. Footnote blocks (Latin quotations under the text) and
running heads are dropped.

    align_cassiodorus_hodgkin.py SRC_FILE OUT_DIR [--dry]
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from chapter_common import load_work, tail, finish, clean, roman_ocr, dehyphenate   # noqa: E402

src_file, out_dir = sys.argv[1:3]
dry = '--dry' in sys.argv
lines = open(src_file, encoding='utf-8', errors='replace').read().split('\n')
start = next(i for i, l in enumerate(lines) if re.match(r'^BOOK\s+I\.?\s*$', l) and i > 5000)
BOOK = re.compile(r'^\s*BOOK\s+([IVXL]+)\.?\s*$')
HEAD = re.compile(r"^\s*([A-Za-z0-9]{1,9})[.,]\s+([A-Z][A-Z \-',.;:()]{8,})$")
FOOT = re.compile(r"^\s*['‘’]?\d{1,2}\s+['‘’“]")
RUNNING = re.compile(r'^\s*(\d+\s+)?Cassiodori\s+Variae\.?\s*(\d+)?\s*$|^\s*\d+\s*$|^\s*Cassiodori\b')

refs, src, _ = load_work('la', 'cassiodorus.variae')
nlet = {}
for r in refs:
    p = tail(r).split('.')
    if p[0].isdigit() and p[1].isdigit():
        nlet[int(p[0])] = max(nlet.get(int(p[0]), 0), int(p[1]))

english, book, last_heading_line, last = {}, 0, -999, 0
cur, buf, skipping, irregular = None, [], False, []
for i in range(start, len(lines)):
    ln = lines[i]
    mb = BOOK.match(ln)
    if mb and i - last_heading_line > 200 and book < 12:
        if cur:
            english[cur] = buf
        book, last, cur, buf, last_heading_line = book + 1, 0, None, [], i
        continue
    if re.match(r'^\s*(INDEX|APPENDIX)\b', ln) and book == 12 and i > last_heading_line + 500:
        break
    mh = HEAD.match(ln)
    if mh and book:
        tok, title = mh.group(1), mh.group(2)
        if tok.isdigit():
            n = int(tok)
        else:
            n = roman_ocr(tok) if tok.isalpha() else None
        looks = ' TO ' in title or title.startswith('THE KING')
        ok = looks and ((n is not None and last < n <= last + 8) or n is None)
        if ok:
            if n is None:
                n = last + 1
            if n != last + 1:
                irregular.append((book, n, f'{n - last - 1} heading(s) before it lost'))
            if cur:
                english[cur] = buf
            cur, buf, last, skipping = (book, n), [], n, False
            continue
    if cur is None:
        continue
    if not ln.strip():
        skipping = False
        buf.append(ln)
        continue
    if RUNNING.match(ln):
        continue
    if FOOT.match(ln):
        skipping = True
    if skipping:
        continue
    buf.append(ln)
if cur:
    english[cur] = buf
english = {k: clean(dehyphenate('\n'.join(v))) for k, v in english.items()}
got = {}
for (b, n) in english:
    got[b] = got.get(b, 0) + 1
print('letters found per book (ours):', {b: (got.get(b, 0), nlet.get(b)) for b in sorted(nlet)})
units, idx, ref_to_unit = [], {}, {}
for r in refs:
    p = tail(r).split('.')
    if not (p[0].isdigit() and p[1].isdigit()):
        continue
    k = (int(p[0]), int(p[1]))
    t = english.get(k)
    if not t or len(t) < 80:
        continue
    if k not in idx:
        idx[k] = len(units)
        units.append(t)
    ref_to_unit[r] = idx[k]
finish('la', 'cassiodorus.variae', units, ref_to_unit, refs, src, out_dir=out_dir, dry=dry, mode='letter',
       attribution='Thomas Hodgkin, The Letters of Cassiodorus, being a condensed translation of the Variae Epistolae (London, 1886): CONDENSED translation; scans at the Internet Archive',
       license='Public domain (published 1886)',
       sources=[{'translator': 'Thomas Hodgkin', 'year': 1886, 'place': 'London', 'publisher': 'Henry Frowde',
                 'title': 'The Letters of Cassiodorus, being a condensed translation of the Variae Epistolae of Magnus Aurelius Cassiodorus Senator',
                 'condensed': True, 'short_attribution': 'T. Hodgkin (1886), condensed translation',
                 'mode': 'letter', 'ref_composition': ['book', 'letter'],
                 'url': 'https://archive.org/details/lettersofcassiod00cassuoft', 'pd_reason': 'published 1886'}],
       notes='CONDENSED TRANSLATION: Hodgkin renders the important letters nearly in full and summarizes the rest in his own words, '
             'so a unit is his condensed rendering of the letter, not a complete translation. Letters whose heading the OCR lost are unpaired. '
             f'{len(irregular)} headings were placed with a gap in the numbering.')
