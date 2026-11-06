#!/usr/bin/env python3
"""Nonnus, Dionysiaca, from Rouse's Loeb of 1940 and 1942 (Part F, 2026-10-24).

Three volumes on the Internet Archive (dionysiaca01nonnuoft, 02, 03), imprint
"Cambridge, Massachusetts, Harvard University Press / London, William Heinemann
Ltd", 1940, 1940, 1942. No renewal was found in the NYPL cce-renewals data
(research/translations/2026-10-24_renewal_check). Every English page carries the
running header "DIONYSIACA, XVII. 321-350", the exact Greek line range, so this
is the Statius method (align_statius.py) with the shared parts in loeb_pages.py.

Book numbers in a header are misread often ("IL", "IIT", "UL"), so the book comes
from the numeral when it reads and is one of the current book or the next, and
from the line numbers (a start that falls below the last start means a new book)
when it does not. Page spans are 10 to 45 lines in this poem.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import loeb_pages as L
from write_aligned import write_aligned

SRC = os.environ.get('TESSERAE_NONNUS_SRC',
                     os.path.expanduser('~/tesserae-backups/tr_f_2026-10-24'))
OUT = os.environ.get('TESSERAE_NONNUS_OUT',
                     os.path.expanduser('~/tesserae-backups/tr_f_2026-10-24/final/standalone'))
TESS = os.environ.get('TESSERAE_TEXTS', '/var/www/tesseraev6_flask/texts') + '/grc'
VOLS = [('nonnus01.txt', 'dionysiaca01nonnuoft', 1940),
        ('nonnus02.txt', 'dionysiaca02nonnuoft', 1940),
        ('nonnus03.txt', 'dionysiaca03nonnuoft', 1942)]
HEAD = re.compile(r'DIONYSIACA\s*[,.]\s*([IVXLUT1l|]{1,8})\s*[.,]?\s+(' + L.NUM +
                  r')\s*[-–^~]+\s*(' + L.NUM + r')')
STOP = re.compile(r'^\W*NONNOS\W*$|NOTES? (ON|TO)|ADDITIONAL NOTE')


def parse(path, vol):
    pages, cur = [], None
    for raw in open(path, encoding='utf-8', errors='replace'):
        m = HEAD.search(raw)
        if m and len(raw.strip()) < 40:
            if cur:
                pages.append(cur)
            cur = {'num': L.roman_in(m.group(1), 1, 48), 'start': L.digits(m.group(2)),
                   'end': L.digits(m.group(3)), 'body': [], 'vol': vol}
            continue
        if cur:
            cur['body'].append(raw)
    if cur:
        pages.append(cur)
    return pages


def assign_books(pages):
    """Book from the numeral when plausible, else from the line numbers."""
    book, last_start, out = 0, None, []
    for p in pages:
        s, e = p['start'], p['end']
        if s is None or e is None:
            continue
        n = p['num']
        if book == 0:
            book = 1
        elif n == book + 1 and s < last_start:
            book = n
        elif n != book and last_start is not None and s < last_start - 100:
            book += 1
        p = dict(p, book=book)
        last_start = s
        out.append(p)
    return out


def main():
    refs = L.load_refs(f'{TESS}/nonnus_of_panopolis.dionysiaca.tess', 2)
    src = L.source_for(f'{TESS}/nonnus_of_panopolis.dionysiaca.tess')
    pages = []
    for fn, vol, yr in VOLS:
        pages += parse(f'{SRC}/{fn}', vol)
    print('headers parsed:', len(pages))
    pages = assign_books(pages)
    for p in pages:
        p['text'] = L.page_english(p['body'], STOP, cut_footnotes=True)
    # Each volume must vouch for itself: volume 1's scan has lost about half its
    # pages and many words on the rest (names 0.16 against 0.76 and 0.60), and a
    # page of English with words missing is worse than no page.
    good = set()
    for fn, vol, yr in VOLS:
        pairs = []
        for p in pages:
            if p['vol'] == vol and p['text']:
                for ln in range(p['start'], p['end'] + 1):
                    r = refs.get((p['book'], ln))
                    if r:
                        pairs.append((src[r], p['text']))
        h, n = L.V.score(pairs, 'grc', sample=300)
        print(f'  {vol}: pages {sum(1 for p in pages if p["vol"] == vol)} names {h} (n={n})')
        if h is not None and h >= 0.30:
            good.add(vol)
    pages = [p for p in pages if p['vol'] in good]
    pages, fixed, dropped, trimmed = L.contiguity_repair(
        pages, 8, 48, lambda p: p['book'])
    pages = [p for p in pages if len(p['text']) > 80]
    print(f'pages kept {len(pages)}  repaired {fixed}  dropped {dropped}  trimmed {trimmed}')
    mp = [((lambda ln, b=p['book']: (b, ln)), p['start'], p['end'], p['text']) for p in pages]
    units, ref2u = L.build_units(mp, refs)
    pairs = [(src.get(r, ''), units[i]) for r, i in ref2u.items()]
    hit, n, r, ok, by = L.checks(pairs, 'grc')
    cov = len(ref2u) / len(refs)
    per = round(len(ref2u) / len(units), 1)
    print(f'refs {len(refs)} paired {len(ref2u)} cov {cov:.3f} names {hit} (n={n}) '
          f'corr {r} lines/unit {per} ok={ok} by={by}')
    bybook = {}
    for ref in refs.values():
        b = int(re.findall(r'\d+', ref)[-2])
        bybook.setdefault(b, [0, 0])
        bybook[b][0] += 1
        bybook[b][1] += ref in ref2u
    print('coverage by book:', {b: round(v[1] / v[0], 2) for b, v in sorted(bybook.items())})
    if not ok:
        print('REFUSED: checks failed')
        return 1
    srcs = [{'translator': 'W. H. D. Rouse', 'year': y, 'place': 'London and Cambridge, Mass.',
             'publisher': 'William Heinemann Ltd; Harvard University Press',
             'title': 'Nonnos, Dionysiaca (Loeb Classical Library, vol. %d)' % (i + 1),
             'url': f'https://archive.org/details/{v}',
             'license': 'public domain, US, copyright not renewed (renewal check 2026-10-24)'}
            for i, (fn, v, y) in enumerate(VOLS) if v in good]
    path = write_aligned(OUT, 'grc', 'nonnus_of_panopolis.dionysiaca', units, ref2u,
                         attribution='W. H. D. Rouse (Loeb, 1940 and 1942), via the Internet Archive',
                         license=L.imprint_license(), sources=srcs, confidence='medium',
                         approximate=True, tess_refs=list(refs.values()),
                         name_check={'name_check_hit_rate': round(hit, 3) if hit is not None else None,
                                     'name_check_n': n,
                                     'length_correlation': round(r, 3) if r is not None else None},
                         verified_by=by)
    print('wrote', path)
    return 0


if __name__ == '__main__':
    sys.exit(main())
