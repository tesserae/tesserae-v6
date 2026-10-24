#!/usr/bin/env python3
"""Dionysius of Halicarnassus, Roman Antiquities, from Cary's Loeb of 1937 to 1950 (Part F, 2026-10-24).

Seven volumes, "on the basis of the version of Edward Spelman" (Cary revised
Spelman, so this is a different text from the Spelman 1758 alignment of Part C
and is written as its own file), imprint "Cambridge, Massachusetts, Harvard
University Press / London, William Heinemann Ltd". Scans from the Internet Archive:
the University of Toronto copies of volumes 1, 3, 4, 5, 6, 7 and the Digital Library
of India copy of volume 2. Several are later printings (the scans say which).

The English page's running header is already in our reference form:
"BOOK V. 4, 2-5, 2" is chapter 4 section 2 to chapter 5 section 2, and our
references are dion_hal. ant_rom 5.4.2. So this is the Statius page method with
the shared parts in loeb_pages.py: the book from the numeral (the current book or
the next), the span from the header, a misread digit repaired against the
neighbouring pages, a section shared by two pages given to the page where it
begins. Books 12 to 20 survive only in excerpts and are covered as far as the
headers read.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import loeb_pages as L
from write_aligned import write_aligned

SRC = os.environ.get('TESSERAE_DIONYSIUS_SRC', os.path.expanduser('~/tesserae-backups/tr_f_2026-10-24/dio'))
OUT = os.environ.get('TESSERAE_DIONYSIUS_OUT', os.path.expanduser('~/tesserae-backups/tr_f_2026-10-24/final/standalone'))
TESS = os.environ.get('TESSERAE_TEXTS', '/var/www/tesseraev6_flask/texts') + '/grc'
WORK = 'dionysius_halicarnassensis.antiquitates_romanae'
VOLS = [  # (file, archive id, first published, first book, last book)
    ('d01.txt', 'romanantiquities01dionuoft', 1937, 1, 2),
    ('d02dli.txt', 'in.ernet.dli.2015.185208', 1939, 3, 4),
    ('d03.txt', 'romanantiquities03dionuoft', 1940, 5, 6),
    ('d04.txt', 'romanantiquities04dionuoft', 1943, 6, 7),
    ('d05.txt', 'romanantiquities05dionuoft', 1945, 8, 9),
    ('d06.txt', 'romanantiquities06dionuoft', 1947, 9, 10),
    ('d07.txt', 'romanantiquities07dionuoft', 1950, 11, 20),
]
HEAD = re.compile(r'^\W{0,3}BOOK\s+([IVXLU1l|]{1,8})\b\W*(.*)$')
NUMS = re.compile(r'[0-9OolISB]{1,3}')
STOP = re.compile(r'^\W*DIONYSIUS OF HALICARNASSUS\W*$|^\W*ROMAN ANTIQUITIES\W*$')


def parse(path, lo, hi):
    pages, cur = [], None
    for raw in open(path, encoding='utf-8', errors='replace'):
        s = raw.strip()
        m = HEAD.match(s)
        if m and len(s) < 40 and any(c.isdigit() for c in m.group(2)):
            nums = [L.digits(x) for x in NUMS.findall(m.group(2))]
            if cur:
                pages.append(cur)
            cur = {'num': m.group(1), 'n': nums, 'body': []}
            continue
        if cur:
            cur['body'].append(raw)
    if cur:
        pages.append(cur)
    out = []
    for p in pages:
        n = p['n']
        if any(x is None for x in n):
            continue
        if len(n) == 3:
            a, b = (n[0], n[1]), (n[0], n[2])
        elif len(n) == 4:
            a, b = (n[0], n[1]), (n[2], n[3])
        else:
            continue
        if b < a or max(a[1], b[1]) > 45 or max(a[0], b[0]) > 120:
            continue          # no chapter has 45 sections: a misread or a contents line
        out.append({'num': p['num'], 'a': a, 'b': b, 'body': p['body']})
    return out


def resolve(pages, lo, hi):
    """Assign books and repair spans by neighbouring pages."""
    book, prev_b, out = None, None, []
    dropped = fixed = run = 0
    for p in pages:
        a, b = p['a'], p['b']
        if book is None:
            book = lo          # a volume opens with its first book
        elif prev_b is not None and a[0] + 5 < prev_b[0] and a[0] <= 4 and book < hi:
            # the chapter numbers start over: the next book begins
            book += 1
            prev_b = None
        if prev_b is not None and a < prev_b:
            # earlier than the last page ended: a misread start, or a page that goes
            # back. A sane page that ends after the last one is believed from the
            # last end on, anything else is dropped. A page that jumps FORWARD is
            # kept as printed (the scan lost the pages between).
            if b >= prev_b and b[0] - prev_b[0] <= 3:
                a = prev_b
                fixed += 1
                run = 0
            else:
                dropped += 1
                run += 1
                if run >= 3:
                    prev_b, run = None, 0      # three in a row: the memory, not the pages, is wrong
                continue
        if b[0] - a[0] > 3 or b < a:
            dropped += 1
            continue
        out.append({'book': book, 'a': a, 'b': b, 'body': p['body']})
        prev_b = b
    return out, fixed, dropped


def main():
    path = f'{TESS}/{WORK}.tess'
    refs3 = {}
    order = []
    src = {}
    for line in open(path, encoding='utf-8'):
        m = re.match(r'^<([^>]*)>\s*(.*)$', line)
        if not m:
            continue
        ref = m.group(1).strip()
        nums = [int(x) for x in re.findall(r'\d+', ref)[-3:]]
        if len(nums) == 3:
            refs3[tuple(nums)] = ref
            order.append(tuple(nums))
            src[ref] = m.group(2).strip()
    units, idx, ref2u, usrc = [], {}, {}, []
    used = []
    for fn, vid, yr, lo, hi in VOLS:
        pgs, fixed, dropped = resolve(parse(f'{SRC}/{fn}', lo, hi), lo, hi)
        n_ref = 0
        # a page covers refs from its start to its end, inclusive; shared ones stay with the earlier page
        for p in pgs:
            lo_k, hi_k = (p['book'],) + p['a'], (p['book'],) + p['b']
            text = L.page_english(p['body'], STOP, min_ratio=0.2, min_block=40)
            if not text:
                continue
            first = None
            for k in order:
                if lo_k <= k <= hi_k and refs3[k] not in ref2u:
                    if first is None:
                        if text not in idx:
                            idx[text] = len(units)
                            units.append(text)
                            usrc.append(vid)
                        first = idx[text]
                    ref2u[refs3[k]] = first
                    n_ref += 1
        print(f'  {fn}: pages {len(pgs)} (repaired {fixed}, dropped {dropped}) refs paired {n_ref}')
        if n_ref > 30:
            used.append((fn, vid, yr))
    pairs = [(src.get(r, ''), units[i]) for r, i in ref2u.items()]
    hit, n, r, ok, by = L.checks(pairs, 'grc')
    ur = L.unit_corr(units, ref2u, src)
    cov = len(ref2u) / len(refs3)
    print(f'refs {len(refs3)} paired {len(ref2u)} cov {cov:.3f} names {hit} (n={n}) unit-length corr {ur} refs/unit {len(ref2u)/max(1,len(units)):.2f}')
    by_book = {}
    for k, ref in refs3.items():
        by_book.setdefault(k[0], [0, 0])
        by_book[k[0]][0] += 1
        by_book[k[0]][1] += ref in ref2u
    print('coverage by book:', {b: round(v[1] / v[0], 2) for b, v in sorted(by_book.items())})
    if not ((hit is not None and hit >= 0.25) or (ur is not None and ur >= 0.6)):
        print('REFUSED: checks failed')
        return 1
    vids = [v for fn, v, y in used]
    srcs = [{'translator': 'Earnest Cary, on the basis of the version of Edward Spelman', 'year': yr,
             'place': 'London and Cambridge, Mass.', 'publisher': 'William Heinemann Ltd; Harvard University Press',
             'title': 'Dionysius of Halicarnassus, Roman Antiquities (Loeb Classical Library), vol. %d' % (i + 1),
             'url': f'https://archive.org/details/{vid}',
             'license': 'public domain, US, copyright not renewed (renewal check 2026-10-24)'}
            for i, (fn, vid, yr) in enumerate(used)]
    write_aligned(OUT, 'grc', WORK, units, ref2u,
                  attribution='Earnest Cary (Loeb, 1937 to 1950), via the Internet Archive',
                  license=L.imprint_license(), sources=srcs, confidence='medium', approximate=True,
                  tess_refs=list(refs3.values()),
                  name_check={'name_check_hit_rate': round(hit, 3) if hit is not None else None,
                              'name_check_n': n,
                              'length_correlation': round(ur, 3) if ur is not None else None,
                              'unit_sources': [vids.index(v) if v in vids else 0 for v in usrc]},
                  verified_by=by)
    return 0


if __name__ == '__main__':
    sys.exit(main())
