#!/usr/bin/env python3
"""Pausanias, Description of Greece, books 6 to 8.21, from Jones and Ormerod's Loeb volume III (Part F, 2026-10-24).

Volume III (Books VI to VIII.21: Elis II, Achaia, Arcadia), first printed 1933,
imprint "London, William Heinemann Ltd / New York, G. P. Putnam's Sons"
(MCMXXXIII on the title page). Digital Library of India scan
in.ernet.dli.2015.185436. Volumes IV and V (1935, Boeotia, Phocis) have no open
scan and are not used. Part C aligns Shilleto 1886 for the whole work, so this is
written as a separate file and the main session decides.

The English page's running header gives the region, chapter and section
("ACHAIA, xx. 6-9"), and our references are paus. 7.20.6 (book.chapter.section).
The region gives the book (Elis II 6, Achaia 7, Arcadia 8), the lower-case Roman
chapter numerals are repaired against the sequence (a chapter repeats, or
advances by one to six), the page method of align_dionysius_cary.py does the rest.
"""
import difflib
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import loeb_pages as L
from write_aligned import write_aligned

SRC = os.environ.get('TESSERAE_PAU_SRC', os.path.expanduser('~/tesserae-backups/tr_f_2026-10-24/pau'))
OUT = os.environ.get('TESSERAE_PAU_OUT', os.path.expanduser('~/tesserae-backups/tr_f_2026-10-24/final/separate'))
TESS = os.environ.get('TESSERAE_TEXTS', '/var/www/tesseraev6_flask/texts') + '/grc'
WORK = 'pausanias.description_of_greece'
SCAN = ('in.ernet.dli.2015.185436.txt', 'in.ernet.dli.2015.185436', 1933)
REGION = {'ELIS': 6, 'ACHAIA': 7, 'ARCADIA': 8}
HEAD = re.compile(r"^\W{0,3}(ELIS(?: [IJ1l]{1,3})?|AC[A-Z]{3,5}|ARC[A-Z]{3,5})\W{0,3}\s*[,.]?\s*([A-Za-z1|\u03c7\u03c0\u1f76]{1,9})\W{0,3}\s*(\d{1,2})\s*[-\u2013\u2014~]+\s*(?:([A-Za-z1|\u03c7]{1,9})\W{1,3}\s*)?(\d{1,2})\W{0,3}$")
STOP = re.compile(r'^\W*PAUSANIAS\W*[:.]?\s*DESCRIPTION OF GREECE\W*$')


def region_book(word):
    best = max(REGION, key=lambda k: difflib.SequenceMatcher(None, word, k).ratio())
    return REGION[best] if difflib.SequenceMatcher(None, word, best).ratio() >= 0.7 else None


def main():
    path = f'{TESS}/{WORK}.tess'
    src, refs3, order = {}, {}, []
    for line in open(path, encoding='utf-8'):
        m = re.match(r'^<([^>]*)>\s*(.*)$', line)
        if not m:
            continue
        ref = m.group(1).strip()
        nums = [int(x) for x in re.findall(r'\d+', ref.split()[-1])]
        if len(nums) == 3 and 6 <= nums[0] <= 8:
            refs3[tuple(nums)] = ref
            order.append(tuple(nums))
            src[ref] = m.group(2).strip()
    pages, cur = [], None
    for raw in open(f'{SRC}/{SCAN[0]}', encoding='utf-8', errors='replace'):
        s = re.sub(r'\s+', ' ', raw.strip())
        m = HEAD.match(s) if len(s) < 40 else None
        if m and region_book(m.group(1).split()[0]):
            if cur:
                pages.append(cur)
            cur = {'book': region_book(m.group(1).split()[0]), 'c1': m.group(2), 's1': L.digits(m.group(3)),
                   'c2': m.group(4) or m.group(2), 's2': L.digits(m.group(5)), 'body': []}
            continue
        if cur:
            cur['body'].append(raw)
    if cur:
        pages.append(cur)
    print('headers parsed:', len(pages))
    out, prev_b, dropped = [], None, 0
    for p in pages:
        book = p['book']
        same = prev_b is not None and prev_b[0] == book
        prev_c = prev_b[1] if same else None
        prev_s = prev_b[2] if same else None
        if p['s1'] is None or p['s2'] is None:
            dropped += 1
            continue
        c1 = L.pick_near(L.chap_values(p['c1']), prev_c, 1, 6)
        if c1 is None and same:
            # the numeral is unreadable: the sections say whether the chapter goes on
            if p['s1'] >= prev_s - 1:
                c1 = prev_c
            elif p['s1'] <= 4:
                c1 = prev_c + 1
        if c1 is None:
            dropped += 1
            continue
        c2 = L.pick_near(L.chap_values(p['c2']), c1, 0, 3)
        if c2 is None:
            c2 = c1 if p['s2'] >= p['s1'] else c1 + 1
        a, b = (c1, p['s1']), (c2, p['s2'])
        if b < a:
            if c2 == c1:
                dropped += 1
                continue
            b = (c2, p['s2'])
        text = L.page_english(p['body'], STOP, min_ratio=0.2, min_block=40)
        if not text:
            dropped += 1
            continue
        out.append({'book': book, 'a': a, 'b': b, 'text': text})
        prev_b = (book, c2, p['s2'])
    print('pages kept', len(out), 'dropped', dropped)
    units, idx, ref2u = [], {}, {}
    for p in out:
        lo, hi = (p['book'],) + p['a'], (p['book'],) + p['b']
        first = None
        for k in order:
            if lo <= k <= hi and refs3[k] not in ref2u:
                if first is None:
                    if p['text'] not in idx:
                        idx[p['text']] = len(units)
                        units.append(p['text'])
                    first = idx[p['text']]
                ref2u[refs3[k]] = first
    sub = [refs3[k] for k in order if not (k[0] == 8 and k[1] > 22)]
    pairs = [(src[r], units[i]) for r, i in ref2u.items()]
    hit, n, rr, ok, by = L.checks(pairs, 'grc')
    ur = L.unit_corr(units, ref2u, src)
    print(f'books 6 to 8.21: refs {len(sub)} paired {len(ref2u)} cov {sum(1 for r in sub if r in ref2u)/len(sub):.3f} '
          f'names {hit} (n={n}) unit-length corr {ur} refs/unit {len(ref2u)/max(1,len(units)):.1f}')
    by_book = {}
    for k in order:
        if k[0] == 8 and k[1] > 22:
            continue
        by_book.setdefault(k[0], [0, 0])
        by_book[k[0]][0] += 1
        by_book[k[0]][1] += refs3[k] in ref2u
    print('coverage by book:', {b: round(v[1] / v[0], 2) for b, v in sorted(by_book.items())})
    if not (ok or (ur is not None and ur >= 0.6)):
        print('REFUSED: checks failed')
        return 1
    write_aligned(OUT, 'grc', WORK, units, ref2u,
                  attribution='W. H. S. Jones and H. A. Ormerod (Loeb, 1933), via the Internet Archive',
                  license=L.imprint_license(),
                  sources=[{'translator': 'W. H. S. Jones and H. A. Ormerod', 'year': 1933,
                            'place': 'London and New York', 'publisher': "William Heinemann Ltd; G. P. Putnam's Sons",
                            'title': 'Pausanias, Description of Greece, vol. III (Loeb Classical Library 272)',
                            'url': 'https://archive.org/details/in.ernet.dli.2015.185436',
                            'license': 'public domain, US, copyright not renewed (renewal check 2026-10-24)'}],
                  confidence='medium', approximate=True, tess_refs=sub,
                  name_check={'name_check_hit_rate': round(hit, 3) if hit is not None else None,
                              'name_check_n': n, 'length_correlation': round(ur, 3) if ur is not None else None},
                  verified_by=by if ok else 'length correlation')
    return 0


if __name__ == '__main__':
    sys.exit(main())
