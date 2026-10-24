#!/usr/bin/env python3
"""Silius Italicus, Punica books 9 to 17, from Duff's Loeb volume II (Part F, 2026-10-24).

Loeb Classical Library 278, first printed 1934, imprint "London, William
Heinemann Ltd / Cambridge, Massachusetts, Harvard University Press". The scan is
the Internet Archive's University of Toronto copy punicasi02siliuoft (the 1961
printing, the scan's own copyright page says "First printed 1934, Reprinted 1938,
1950, 1961"). Books 9 to 17 now have A. S. Kline's translation, which is free
for non-commercial use only, and the project's rule is public domain first, so
this is written as a separate file and the main session decides the swap
(merge_unit_sources.py lays it over the installed file when it does).

Every English page carries the running header "PUNICA, IX. 17-44", the exact
Latin line range, so this is the Statius method (align_statius.py) with the shared
parts in loeb_pages.py.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import loeb_pages as L
from write_aligned import write_aligned

SRC = os.environ.get('TESSERAE_SILIUS_SRC', os.path.expanduser('~/tesserae-backups/tr_f_2026-10-24/sil'))
OUT = os.environ.get('TESSERAE_SILIUS_OUT', os.path.expanduser('~/tesserae-backups/tr_f_2026-10-24/final/separate'))
TESS = os.environ.get('TESSERAE_TEXTS', '/var/www/tesseraev6_flask/texts') + '/la'
WORK = 'silius_italicus.punica'
HEAD = re.compile(r'PUNICA\s*[,.]\s*([IVXLU1l|]{1,6})\s*[.,]?\s+(' + L.NUM + r')\s*[-–—]+\s*(' + L.NUM + r')')
STOP = re.compile(r'^\W*SILIUS ITALICUS\W*$')


def main():
    path = f'{TESS}/{WORK}.tess'
    refs = L.load_refs(path, 2)
    src = L.source_for(path)
    pages, cur = [], None
    for raw in open(f'{SRC}/s2.txt', encoding='utf-8', errors='replace'):
        m = HEAD.search(raw)
        if m and len(raw.strip()) < 40:
            if cur:
                pages.append(cur)
            cur = {'num': L.roman_in(m.group(1), 9, 17), 'start': L.digits(m.group(2)),
                   'end': L.digits(m.group(3)), 'body': []}
            continue
        if cur:
            cur['body'].append(raw)
    if cur:
        pages.append(cur)
    print('headers parsed:', len(pages))
    book, last_start, ok_pages = 9, None, []
    for p in pages:
        s0, e0, n = p['start'], p['end'], p['num']
        if s0 is None or e0 is None:
            continue
        if n in (book, book + 1) and n != book and last_start is not None and s0 < last_start - 60:
            book = n
        elif n != book and last_start is not None and s0 < last_start - 150 and book < 17:
            book += 1
        last_start = s0
        p['book'] = book
        p['text'] = L.page_english(p['body'], STOP, min_ratio=0.2, min_block=40, cut_footnotes=True)
        if p['text']:
            ok_pages.append(p)
    ok_pages, fixed, dropped, trimmed = L.contiguity_repair(ok_pages, 8, 60, lambda p: p['book'])
    print(f'pages kept {len(ok_pages)} repaired {fixed} dropped {dropped} trimmed {trimmed}')
    mp = [((lambda ln, b=p['book']: (b, ln)), p['start'], p['end'], p['text']) for p in ok_pages]
    units, ref2u = L.build_units(mp, refs)
    sub = [r for k, r in refs.items() if 9 <= k[0] <= 17]
    pairs = [(src.get(r, ''), units[i]) for r, i in ref2u.items()]
    hit, n, rr, ok, by = L.checks(pairs, 'la')
    cov = sum(1 for r in sub if r in ref2u) / len(sub)
    print(f'books 9-17: refs {len(sub)} paired {len(ref2u)} cov {cov:.3f} names {hit} (n={n}) corr {rr} '
          f'lines/unit {len(ref2u)/len(units):.1f}')
    by_book = {}
    for k, r in refs.items():
        if 9 <= k[0] <= 17:
            by_book.setdefault(k[0], [0, 0])
            by_book[k[0]][0] += 1
            by_book[k[0]][1] += r in ref2u
    print('coverage by book:', {b: round(v[1] / v[0], 2) for b, v in sorted(by_book.items())})
    if not ok:
        print('REFUSED: checks failed')
        return 1
    write_aligned(OUT, 'la', WORK, units, ref2u,
                  attribution='J. D. Duff (Loeb, 1934), via the Internet Archive',
                  license=L.imprint_license(),
                  sources=[{'translator': 'J. D. Duff', 'year': 1934, 'place': 'London and Cambridge, Mass.',
                            'publisher': 'William Heinemann Ltd; Harvard University Press',
                            'title': 'Silius Italicus, Punica, vol. II, books 9 to 17 (Loeb Classical Library 278)',
                            'url': 'https://archive.org/details/punicasi02siliuoft',
                            'license': 'public domain, US, copyright not renewed (renewal check 2026-10-24)'}],
                  confidence='medium', approximate=True, tess_refs=sub,
                  name_check={'name_check_hit_rate': round(hit, 3) if hit is not None else None,
                              'name_check_n': n, 'length_correlation': round(rr, 3) if rr is not None else None},
                  verified_by=by)
    return 0


if __name__ == '__main__':
    sys.exit(main())
