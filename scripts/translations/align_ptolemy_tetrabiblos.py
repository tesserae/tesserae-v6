#!/usr/bin/env python3
"""Ptolemy, Tetrabiblos, from Robbins's Loeb of 1940 (Part F, 2026-10-24).

Loeb Classical Library 350 (Manetho and Ptolemy: Tetrabiblos), first printed 1940,
imprint "Cambridge, Massachusetts, Harvard University Press / London, William
Heinemann Ltd". The scan is the Internet Archive upload
L350ManethoHistoryOfEgyptPtolemyTetrabiblos (the 1964 printing: the copyright page
says "First printed 1940, reprinted 1943, 1956, 1964").

The English page's running header gives book and chapter ("TETRABIBLOS I. 4-5"),
and our references are book.chapter.section[.part], so the alignment is by
chapter: a unit is the English of every page headed with that chapter, and a
page headed with two chapters belongs to both. Header numerals are repaired by
sequence (a chapter may repeat, advance by one or two, or start over at the next
book). A page whose header lost its numbers is left out.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import loeb_pages as L
from write_aligned import write_aligned

SRC = os.environ.get('TESSERAE_PTOL_SRC', os.path.expanduser('~/tesserae-backups/tr_f_2026-10-24/ptol'))
OUT = os.environ.get('TESSERAE_PTOL_OUT', os.path.expanduser('~/tesserae-backups/tr_f_2026-10-24/final/standalone'))
TESS = os.environ.get('TESSERAE_TEXTS', '/var/www/tesseraev6_flask/texts') + '/grc'
STEM = 'claudius_ptolemaeus.apotelesmatica_tetrabiblos'
HEAD = re.compile(r'TETRABIBLOS\W{0,3}\s*([IVXLlT1|]{1,5})\W{1,3}\s*([0-9OolISB]{1,3})(?:\s*[-–—]+\s*([0-9OolISB]{1,3}))?\W{0,3}$')
STOP = re.compile(r'^\W*PTOLEMY\W*$|^\W*(TETRABIBLOS|TRIMSTISE)\W*$')


def main():
    path = f'{TESS}/{STEM}.tess'
    refs = {}
    src = L.source_for(path)
    for r in src:
        nums = re.findall(r'\d+', r.split()[-1])
        if len(nums) >= 2:
            refs.setdefault((int(nums[0]), int(nums[1])), []).append(r)
    pages, cur = [], None
    for raw in open(f'{SRC}/t.txt', encoding='utf-8', errors='replace'):
        s = re.sub(r'\s+', ' ', raw.strip())
        m = HEAD.search(s)
        if m and len(s) < 36:
            if cur:
                pages.append(cur)
            cur = {'num': m.group(1), 'c1': L.digits(m.group(2)), 'c2': L.digits(m.group(3)) if m.group(3) else None,
                   'body': []}
            continue
        if cur:
            cur['body'].append(raw)
    if cur:
        pages.append(cur)
    print('headers parsed:', len(pages))
    book, prev, chap_text, kept = None, None, {}, 0
    for p in pages:
        c1, c2 = p['c1'], p['c2'] or p['c1']
        hb = L.roman_in(p['num'], 1, 4)
        if c1 is None or c2 is None or c2 < c1:
            continue
        if book is None:
            book = hb or 1
        elif prev is not None and not (prev <= c1 <= prev + 2):
            if hb == book + 1 and c1 <= 2 and prev >= 5:
                book += 1
            else:
                continue            # not in sequence: a misread numeral
        elif prev is not None and hb == book + 1 and c1 <= 2 and prev >= 5:
            book += 1
        if c2 - c1 > 2:
            continue
        text = L.page_english(p['body'], STOP, min_ratio=0.2, min_block=40)
        if not text:
            continue
        for c in range(c1, c2 + 1):
            chap_text.setdefault((book, c), []).append(text)
        prev = c2
        kept += 1
    print('pages kept:', kept, 'chapters with text:', len(chap_text))
    units, idx, ref2u = [], {}, {}
    for key, texts in chap_text.items():
        t = ' '.join(texts)
        if t not in idx:
            idx[t] = len(units)
            units.append(t)
        for r in refs.get(key, []):
            ref2u[r] = idx[t]
    all_refs = [r for rs in refs.values() for r in rs]
    pairs = [(src[r], units[i]) for r, i in ref2u.items()]
    hit, n, rr, ok, by = L.checks(pairs, 'grc')
    ur = L.unit_corr(units, ref2u, src)
    cov = len(ref2u) / len(all_refs)
    print(f'refs {len(all_refs)} paired {len(ref2u)} cov {cov:.3f} names {hit} (n={n}) unit-length corr {ur} '
          f'refs/unit {len(ref2u)/max(1,len(units)):.1f}')
    by_book = {}
    for (b, c), rs in refs.items():
        by_book.setdefault(b, [0, 0])
        by_book[b][0] += len(rs)
        by_book[b][1] += sum(1 for r in rs if r in ref2u)
    print('coverage by book:', {b: round(v[1] / v[0], 2) for b, v in sorted(by_book.items())})
    if not (ok or (ur is not None and ur >= 0.6)):
        print('REFUSED: checks failed')
        return 1
    write_aligned(OUT, 'grc', STEM, units, ref2u,
                  attribution='F. E. Robbins (Loeb, 1940), via the Internet Archive',
                  license=L.imprint_license(),
                  sources=[{'translator': 'F. E. Robbins', 'year': 1940, 'place': 'London and Cambridge, Mass.',
                            'publisher': 'William Heinemann Ltd; Harvard University Press',
                            'title': 'Manetho; Ptolemy, Tetrabiblos (Loeb Classical Library 350)',
                            'url': 'https://archive.org/details/L350ManethoHistoryOfEgyptPtolemyTetrabiblos',
                            'license': 'public domain, US, copyright not renewed (renewal check 2026-10-24)'}],
                  confidence='medium', approximate=True, tess_refs=all_refs,
                  name_check={'name_check_hit_rate': round(hit, 3) if hit is not None else None,
                              'name_check_n': n, 'length_correlation': round(ur, 3) if ur is not None else None},
                  verified_by=by if ok else 'length correlation')
    return 0


if __name__ == '__main__':
    sys.exit(main())
