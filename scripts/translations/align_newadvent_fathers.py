#!/usr/bin/env python3
"""Five Greek works of the Fathers whose public-domain English (the Ante-Nicene and
Nicene and Post-Nicene Fathers series, 1869 to 1895) is on New Advent, aligned to
our works by number:

  clement_of_alexandria.protrepticus      Exhortation to the Heathen, 12 chapters (Wilson, ANF 2, 1869)
  clement_of_alexandria.paedagogus        The Instructor, 3 books and their chapters (Wilson, ANF 2, 1869)
  clement_of_alexandria.quis_dives_salvetur  Who is the Rich Man that shall be Saved, 42 sections (Wilson, 1869)
  basil_of_caesarea.epistulae             Letters (Blomfield Jackson, NPNF 2.8, 1895), letter by letter
  gregory_of_nazianzus.theological_orations  Orations 27 to 31 (Browne and Swallow, NPNF 2.7, 1894), section by section

Source: newadvent.org/fathers/<number>.htm, fetched at one request a second. The
pages mark chapters (`Chapter N.`), sections (a roman numeral opening a paragraph)
and letters (`Letter N`), and carry footnotes in spans that are removed. Where the
translator's count of chapters or sections per work (or the oration) differs from ours the
work is refused, since a shift of one would put the wrong English beside right Greek.
Basil's NPNF volume prints 325 of the 366 letters of the Benedictine order that our
text numbers, so the other letters stay unpaired.

    align_newadvent_fathers.py SRC_DIR OUT_DIR [--dry]
SRC_DIR holds clem/, basil/ and greg/ (the fetched pages).
"""
import glob
import os
import re
import sys

from lxml import html as LH

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from chapter_common import load_work, tail, finish, clean, roman_to_int, end_merge_map   # noqa: E402

src_dir, out_dir = sys.argv[1:3]
dry = '--dry' in sys.argv


def page_paras(path):
    """-> (h1 text, [(tag, text)] of h2 and p in the body, without the site furniture)."""
    doc = LH.fromstring(open(path, encoding='utf-8', errors='replace').read())
    for bad in doc.xpath('//span[@class="fisk" or @class="stiki"]|//script|//div[contains(@class,"CMtag")]'):
        bad.drop_tree()
    body = doc.xpath('//div[@id="springfield2"]')[0]
    h1 = ''
    out = []
    for el in body:
        if el.tag == 'h1':
            h1 = re.sub(r'\s+', ' ', el.text_content()).strip()
        elif el.tag in ('h2', 'p'):
            t = re.sub(r'\s+', ' ', el.text_content()).strip()
            if not t or t.startswith('Please help support') or t.startswith('BY CLEMENT') or t.startswith('ST. BASIL') \
                    or t.startswith('(The Instructor)'):
                continue
            out.append((el.tag, t))
    return h1, out


def numbered_sections(paras):
    """Paragraphs opening with a roman numeral and a point (`IV. text`) open section IV; paragraphs without one
    continue the section before. Returns {n: text}; None if the numerals do not chain 1, 2, 3 ..."""
    secs, cur, buf = {}, None, []
    for tag, t in paras:
        if tag != 'p':
            continue
        m = re.match(r'^([IVXL]+)\.\s+(.*)$', t)
        n = roman_to_int(m.group(1)) if m else None
        if n is not None and (cur is None and n == 1 or cur is not None and cur < n <= cur + 3):
            if cur is not None:
                secs[cur] = clean(' '.join(buf))
            cur, buf = n, [m.group(2)]
        elif cur is not None:
            buf.append(t)
    if cur is not None:
        secs[cur] = clean(' '.join(buf))
    ok = bool(secs) and all(b > a for a, b in zip(sorted(secs), sorted(secs)[1:]))
    return secs, ok


def write(stem, units, ref_to_unit, refs, src, translator, year, place, publisher, title, url, series, notes):
    finish('grc', stem, units, ref_to_unit, refs, src, out_dir=out_dir, dry=dry, mode='exact', exact=True,
           attribution=f'{translator}, {title}, {series} ({year}); text from New Advent',
           license=f'Public domain (published {year})',
           sources=[{'translator': translator, 'year': year, 'place': place, 'publisher': publisher,
                     'title': f'{title} ({series})', 'mode': 'exact', 'url': url, 'pd_reason': f'published {year}'}],
           notes=notes)


# ---- Clement, Protrepticus: one page per chapter -------------------------------------------------
refs, src, _ = load_work('grc', 'clement_of_alexandria.protrepticus')
chap = {}
for k in range(1, 13):
    h1, ps = page_paras(os.path.join(src_dir, 'clem', f'0208{k:02d}.htm'))
    chap[k] = clean(' '.join(t for tag, t in ps if tag == 'p'))
units, ref_to_unit = [], {}
for r in refs:
    c = int(tail(r).split('.')[0])
    if chap.get(c):
        ref_to_unit[r] = c - 1
units = [chap[k] for k in range(1, 13)]
ours = {int(tail(r).split('.')[0]) for r in refs}
print('protrepticus: our chapters', sorted(ours), 'English chapters', sorted(chap))
if ours == set(chap):
    write('clement_of_alexandria.protrepticus', units, ref_to_unit, refs, src, 'William Wilson', 1869, 'Edinburgh', 'T. and T. Clark',
          'Exhortation to the Heathen', 'https://www.newadvent.org/fathers/0208.htm', 'Ante-Nicene Fathers, vol. 2',
          'One unit per chapter (12).')

# ---- Clement, Paedagogus: three pages (books), chapters under h2 ----------------------------------
refs, src, _ = load_work('grc', 'clement_of_alexandria.paedagogus')
eng = {}
for b in (1, 2, 3):
    h1, ps = page_paras(os.path.join(src_dir, 'clem', f'0209{b}.htm'))
    cur, buf = None, []
    for tag, t in ps:
        m = re.match(r'^Chapter (\d+)\.', t) if tag == 'h2' else None
        if m:
            if cur:
                eng[(b, cur)] = clean(' '.join(buf))
            cur, buf = int(m.group(1)), []
        elif cur and tag == 'p':
            buf.append(t)
    if cur:
        eng[(b, cur)] = clean(' '.join(buf))
ours = {}
for r in refs:
    p = tail(r).split('.')
    if p[0].isdigit() and p[1].isdigit():
        ours[int(p[0])] = max(ours.get(int(p[0]), 0), int(p[1]))
en = {b: max(c for (bb, c) in eng if bb == b) for b in (1, 2, 3)}
print('paedagogus: our chapters per book', ours, 'English', en)
merge = {}                          # (book, our chapter) -> English chapters
okp = True
for b in (1, 2, 3):
    if ours[b] == en[b]:
        for c in range(1, ours[b] + 1):
            merge[(b, c)] = [c]
        continue
    gl = {}
    for r in refs:
        p = tail(r).split('.')
        if p[0].isdigit() and int(p[0]) == b and p[1].isdigit():
            gl[int(p[1])] = gl.get(int(p[1]), 0) + len(src[r])
    chs = sorted(gl)
    mp = end_merge_map([gl[c] for c in chs], [len(eng[(b, c)]) for c in range(1, en[b] + 1)])
    if mp is None:
        print(f'   paedagogus book {b}: the chapters do not pair one to one up to the end: refused')
        okp = False
        continue
    for i, c in enumerate(chs):
        merge[(b, c)] = [j + 1 for j in mp[i]]
    print(f'   paedagogus book {b}: English {en[b]} chapters against our {ours[b]}; the last Greek chapter takes English {merge[(b, chs[-1])]}')
if okp:
    units, idx, r2u = [], {}, {}
    for r in refs:
        p = tail(r).split('.')
        if p[0].isdigit() and p[1].isdigit() and (int(p[0]), int(p[1])) in merge:
            b, c = int(p[0]), int(p[1])
            parts = tuple(merge[(b, c)])
            if (b, parts) not in idx:
                idx[(b, parts)] = len(units)
                units.append(' '.join(eng[(b, j)] for j in parts))
            r2u[r] = idx[(b, parts)]
    write('clement_of_alexandria.paedagogus', units, r2u, refs, src, 'William Wilson', 1869, 'Edinburgh', 'T. and T. Clark',
          'The Instructor (Paedagogus)', 'https://www.newadvent.org/fathers/0209.htm', 'Ante-Nicene Fathers, vol. 2',
          'One unit per chapter. The chapter summaries that open each book (our `argument` lines) have no English counterpart and stay unpaired.')

# ---- Clement, Quis dives salvetur: one page, sections I to XLII ----------------------------------
refs, src, _ = load_work('grc', 'clement_of_alexandria.quis_dives_salvetur')
h1, ps = page_paras(os.path.join(src_dir, 'clem', '0207.htm'))
secs, ok = numbered_sections(ps)
ours = {int(tail(r).split('.')[0]) for r in refs if tail(r).split('.')[0].isdigit()}
print('quis dives: our sections', max(ours), 'English sections', max(secs) if secs else None, 'chain ok', ok)
if ok and max(secs) == max(ours):
    units, idx, r2u = [], {}, {}
    for r in refs:
        c = tail(r).split('.')[0]
        if c.isdigit() and int(c) in secs:
            if int(c) not in idx:
                idx[int(c)] = len(units)
                units.append(secs[int(c)])
            r2u[r] = idx[int(c)]
    write('clement_of_alexandria.quis_dives_salvetur', units, r2u, refs, src, 'William Wilson', 1869, 'Edinburgh', 'T. and T. Clark',
          'Who is the Rich Man that shall be Saved?', 'https://www.newadvent.org/fathers/0207.htm', 'Ante-Nicene Fathers, vol. 2',
          'One unit per section (42).')

# ---- Basil, Letters -------------------------------------------------------------------------------
refs, src, _ = load_work('grc', 'basil_of_caesarea.epistulae')
letters = {}
for path in sorted(glob.glob(os.path.join(src_dir, 'basil', '*.htm'))):
    h1, ps = page_paras(path)
    m = re.match(r'Letter (\d+)', h1)
    if m:
        letters[int(m.group(1))] = clean(' '.join(t for tag, t in ps if tag == 'p'))
units, idx, r2u = [], {}, {}
for r in refs:
    n = tail(r)
    if n.isdigit() and int(n) in letters and len(letters[int(n)]) > 60:
        idx[int(n)] = len(units)
        units.append(letters[int(n)])
        r2u[r] = idx[int(n)]
print(f'basil: {len(letters)} English letters, {len(r2u)} of {len(refs)} of ours paired')
write('basil_of_caesarea.epistulae', units, r2u, refs, src, 'Blomfield Jackson', 1895, 'New York', 'The Christian Literature Company',
      'Letters', 'https://www.newadvent.org/fathers/3202.htm', 'Nicene and Post-Nicene Fathers, series 2, vol. 8',
      'One unit per letter. The NPNF volume prints 325 of the 366 letters of the Benedictine order; the rest are unpaired. '
      'Basil\'s letters carry the same number in the translation and in our Greek.')

# ---- Gregory of Nazianzus, Theological Orations (Orations 27 to 31) -----------------------------
refs, src, _ = load_work('grc', 'gregory_of_nazianzus.theological_orations')
eng = {}
for i, n in enumerate(range(310227, 310232), start=1):
    h1, ps = page_paras(os.path.join(src_dir, 'greg', f'{n}.htm'))
    secs, ok = numbered_sections(ps)
    if not ok:
        print(f'gregory oration {i}: section numerals do not chain ({sorted(secs)[:5]}...)')
    for s, t in secs.items():
        eng[(i, s)] = t
ours = {}
for r in refs:
    p = tail(r).split('.')
    if p[0].isdigit() and len(p) > 1 and p[1].isdigit():
        ours[int(p[0])] = max(ours.get(int(p[0]), 0), int(p[1]))
en = {i: max((s for (ii, s) in eng if ii == i), default=0) for i in range(1, 6)}
print('gregory English sections per oration (numerals read):', {i: sorted(s for (ii, s) in eng if ii == i)[-3:] for i in range(1, 6)})
print('gregory: our sections per oration', ours, 'English', en)
merge, okg = {}, True
for i in range(1, 6):
    secs_i = sorted(s for (ii, s) in eng if ii == i)
    if not secs_i:
        okg = False
        continue
    if ours[i] == en[i]:
        # a section whose numeral the page lost shares the text of the section before (it is inside it)
        for c in range(1, ours[i] + 1):
            merge[(i, c)] = [c if (i, c) in eng else max(s for s in secs_i if s < c)]
        continue
    gl = {}
    for r in refs:
        p = tail(r).split('.')
        if p[0].isdigit() and int(p[0]) == i and len(p) > 1 and p[1].isdigit():
            gl[int(p[1])] = gl.get(int(p[1]), 0) + len(src[r])
    chs = sorted(gl)
    mp = end_merge_map([gl[c] for c in chs], [len(eng[(i, s)]) for s in secs_i])
    if mp is None:
        print(f'   gregory oration {i}: sections do not pair one to one up to the end: refused')
        okg = False
        continue
    for k, c in enumerate(chs):
        merge[(i, c)] = [secs_i[j] for j in mp[k]]
    print(f'   gregory oration {i}: English {len(secs_i)} sections against our {ours[i]}; the last Greek section takes English {merge[(i, chs[-1])]}')
if okg:
    units, idx, r2u = [], {}, {}
    for r in refs:
        p = tail(r).split('.')
        if p[0].isdigit() and len(p) > 1 and p[1].isdigit() and (int(p[0]), int(p[1])) in merge:
            i, c = int(p[0]), int(p[1])
            parts = tuple(merge[(i, c)])
            if (i, parts) not in idx:
                idx[(i, parts)] = len(units)
                units.append(' '.join(eng[(i, j)] for j in parts))
            r2u[r] = idx[(i, parts)]
    write('gregory_of_nazianzus.theological_orations', units, r2u, refs, src, 'Charles Gordon Browne and James Edward Swallow', 1894,
          'New York', 'The Christian Literature Company', 'The Theological Orations (Orations 27 to 31)',
          'https://www.newadvent.org/fathers/3102.htm', 'Nicene and Post-Nicene Fathers, series 2, vol. 7', 'One unit per section.')
