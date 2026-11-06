#!/usr/bin/env python3
# ruff: noqa: E741  (the corpus lines are called `l` in a dozen throwaway loops, as in the other scripts here)
"""Two Latin prose works, chapter by chapter:

  apuleius.apologia and apuleius.florida   H. E. Butler, The Apologia and Florida of Apuleius of Madaura
                                            (Oxford: Clarendon Press, 1909), Project Gutenberg 26294
  eutropius.breviarium                      J. S. Watson, Justin, Cornelius Nepos and Eutropius (Bohn's
                                            Classical Library, 1853), Internet Archive OCR (justincorneliusn00watsuoft)

Butler numbers the chapters of the Apologia (1 to 103) and the Florida (1 to 23) in
the text, exactly as our references do, so the pairing is by number, and the book's
footnote section (printed after each work) is cut off. (De Deo Socratis is not in Butler's volume and is not paired.)

Watson's Eutropius numbers chapters with roman numerals at the head of each paragraph, in
ten books, with footnotes interleaved. The OCR damages some numerals and loses the heading of
Book II, so the chapters are read as a chain (the next numeral, or one of the next three) and
the next book opens when a chapter I follows a book's last chapters; the chapter counts per book
(20, 28, 23, 27, 9, 25, 23, 23, 28, 18) of our own text decide where a book ends, and a book whose chain
does not reach its own count is not written.

    align_apuleius_eutropius.py SRC_DIR OUT_DIR [--dry]
SRC_DIR holds pg26294.txt and eutropius.txt.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from chapter_common import (load_work, tail, finish, clean, dehyphenate, roman_ocr, _is_running_head, drop_footnotes)

src_dir, out_dir = sys.argv[1:3]
dry = '--dry' in sys.argv

# ---- Apuleius, Butler ----------------------------------------------------------------------------
lines = open(os.path.join(src_dir, 'pg26294.txt'), encoding='utf-8', errors='replace').read().split('\n')
starts = [i for i, l in enumerate(lines) if l.strip() in ('THE APOLOGIA', 'THE FLORIDA')]
print('Butler headings:', [(i, lines[i].strip()) for i in starts])
# the translation of the Apologia opens at the second 'THE APOLOGIA' line after the contents; the notes
# sections repeat the heading, so each work's text is the stretch from its first heading after the contents
# to the next heading
apol_a = next(i for i in starts if lines[i].strip() == 'THE APOLOGIA' and i > 300)
flor_a = next((i for i in starts if lines[i].strip() == 'THE FLORIDA' and i > apol_a), None)
apol_b = next(i for i in starts if i > apol_a and lines[i].strip() != 'THE APOLOGIA' or lines[i].strip() == 'THE APOLOGIA' and i > apol_a + 200)
text_ap = lines[apol_a + 1:(flor_a if flor_a else apol_b)]
text_fl = lines[flor_a + 1:next(i for i in starts if i > flor_a)] if flor_a else []


def numbered(textlines, last):
    """Paragraphs opening `N. text` with N counting 1, 2, 3 ..., up to `last`."""
    out, cur, buf = {}, 0, []
    for ln in textlines:
        s = ln.strip()
        m = re.match(r'^(\d{1,3})\.\s+(\S.*)$', s)
        if m and int(m.group(1)) == cur + 1 and cur + 1 <= last:
            if cur:
                out[cur] = clean(' '.join(buf))
            cur, buf = cur + 1, [m.group(2)]
        elif cur and s:
            buf.append(s)
    if cur:
        out[cur] = clean(' '.join(buf))
    return out


for stem, textlines, prefix in (('apuleius.apologia', text_ap, 'apul.apol.'), ('apuleius.florida', text_fl, 'apul.fl.')):
    refs, src, _ = load_work('la', stem)
    last = max(int(tail(r)) for r in refs if tail(r).isdigit())
    eng = numbered(textlines, last)
    # drop a bracketed footnote number like [6] (clean() does) and anything after the work's last chapter
    print(f'{stem}: English chapters {len(eng)} of {last}')
    units, ref_to_unit = [], {}
    for r in refs:
        c = tail(r)
        if c.isdigit() and int(c) in eng:
            ref_to_unit[r] = len(units)
            units.append(eng[int(c)])
    if len(eng) == last:
        finish('la', stem, units, ref_to_unit, refs, src, out_dir=out_dir, dry=dry, mode='exact', exact=True,
               attribution='Harold Edgeworth Butler, The Apologia and Florida of Apuleius of Madaura (Oxford: Clarendon Press, 1909); Project Gutenberg eBook 26294',
               license='Public domain (published 1909)',
               sources=[{'translator': 'Harold Edgeworth Butler', 'year': 1909, 'place': 'Oxford', 'publisher': 'Clarendon Press',
                         'title': 'The Apologia and Florida of Apuleius of Madaura', 'mode': 'exact', 'ref_composition': ['chapter'],
                         'url': 'https://www.gutenberg.org/ebooks/26294', 'pd_reason': 'published 1909'}],
               notes='One unit per chapter, numbered as in our text.')

# ---- Eutropius, Watson ---------------------------------------------------------------------------
refs, src, _ = load_work('la', 'eutropius.breviarium')
count = {}
for r in refs:
    p = tail(r).split('.')
    if p[0].isdigit() and p[1].isdigit():
        count[int(p[0])] = max(count.get(int(p[0]), 0), int(p[1]))
lines = open(os.path.join(src_dir, 'eutropius.txt'), encoding='utf-8', errors='replace').read().split('\n')
a = next(i for i, l in enumerate(lines) if re.match(r'^\s*BOOK\s+I\.\s*$', l) and i > 22000)
end = next(i for i in range(26538, len(lines)) if re.match(r'^\s*(THE\s+END|END\s+OF|INDEX|NOTES)', lines[i]) or i > 27300)
MARK = re.compile(r'^\W{0,2}([IVXLivxl1U]{1,8})[.,]\s+(\S.*)$')
english, book, chap = {}, 1, 0
buf, cur = [], None
irregular = []
HEADING = re.compile(r'^\s*BOOK\s+([IVXL]+)\.?[\s\-^\d]*$')
headings = {i: roman_ocr(HEADING.match(lines[i]).group(1)) for i in range(a + 1, end) if HEADING.match(lines[i])}
print('Watson book headings found:', sorted(headings.values()))
for pos, ln in enumerate(lines[a + 1:end], start=a + 1):
    if pos in headings and headings[pos] and headings[pos] != book:
        if cur:
            english[cur] = buf
        book, chap, cur, buf = headings[pos], 0, None, []
        continue
    if _is_running_head(ln):
        continue
    s = ln.rstrip()
    m = MARK.match(s)
    n = None
    if m and re.match(r'^[\u2014\u2013-]', m.group(2).lstrip()):
        m = None                      # an entry of a book's table of contents ('VII.\u2014 XXIII.')
    if m:
        tok = m.group(1).upper().replace('1', 'I').replace('U', 'V')
        v = roman_ocr(tok)
        if v is not None and tok[0].isupper() or (m.group(1).upper() == m.group(1)):
            nxt = next((headings[i] for i in sorted(headings) if i > pos), None)
            if v == 1 and chap >= max(1, count.get(book, 0) - 2) and book < max(count) and nxt != book + 1:
                book, chap, n = book + 1, 1, 1             # the heading of this book was lost in the OCR
            elif v == 1 and chap == 0:
                chap, n = 1, 1
            elif v is not None and chap < v <= chap + 3 and v <= count.get(book, 0):
                if v != chap + 1:
                    irregular.append((book, v))
                chap, n = v, v
    if n is not None:
        if cur:
            english[cur] = buf
        cur, buf = (book, chap), [m.group(2)]
        continue
    if cur and s.strip():
        buf.append(s)
if cur:
    english[cur] = buf
english = {k: clean(dehyphenate('\n'.join(drop_footnotes(v)))) for k, v in english.items()}
found = {b: max((c for (bb, c) in english if bb == b), default=0) for b in count}
print('eutropius: chapters read per book (last numeral) vs ours:', {b: (found[b], count[b]) for b in sorted(count)}, 'irregular', len(irregular))
units, idx, ref_to_unit = [], {}, {}
for r in refs:
    p = tail(r).split('.')
    if not (p[0].isdigit() and p[1].isdigit()):
        continue
    b, c = int(p[0]), int(p[1])
    if found.get(b, 0) < count[b] - 2:
        continue                                  # a book whose chain fell short is not written
    t = english.get((b, c))
    if not t:
        # a chapter whose numeral the OCR lost sits inside the chapter before it
        prev = max((cc for (bb, cc) in english if bb == b and cc < c), default=None)
        t = english.get((b, prev)) if prev else None
        k = (b, prev)
    else:
        k = (b, c)
    if not t or len(t) < 40:
        continue
    if k not in idx:
        idx[k] = len(units)
        units.append(t)
    ref_to_unit[r] = idx[k]
finish('la', 'eutropius.breviarium', units, ref_to_unit, refs, src, out_dir=out_dir, dry=dry, mode='chapter',
       attribution='John Selby Watson, Justin, Cornelius Nepos and Eutropius (Bohn\'s Classical Library, 1853); scans at the Internet Archive',
       license='Public domain (published 1853)',
       sources=[{'translator': 'John Selby Watson', 'year': 1853, 'place': 'London', 'publisher': 'Henry G. Bohn',
                 'title': 'Justin, Cornelius Nepos, and Eutropius, literally translated', 'mode': 'chapter',
                 'ref_composition': ['book', 'chapter'], 'url': 'https://archive.org/details/justincorneliusn00watsuoft',
                 'pd_reason': 'published 1853'}],
       notes='Chapter-level units. A chapter whose numeral the OCR lost shares the unit of the chapter before it (its text is in it). '
             'The dedication (praef) is unpaired.')
