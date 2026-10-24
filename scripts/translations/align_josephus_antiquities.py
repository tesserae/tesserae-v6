#!/usr/bin/env python3
"""Josephus, Jewish Antiquities books 5 to 17, from the Loeb volumes of 1934 to 1963 (Part F, 2026-10-24).

Volumes V (Thackeray and Marcus, books 5 to 8, 1934), VI (Thackeray and Marcus,
9 to 11, 1937), VII (Marcus, 12 to 14, 1943) and VIII (Marcus and Wikgren, 15 to
17, 1963), imprint "Cambridge, Massachusetts, Harvard University Press / London,
William Heinemann Ltd". Scans loeb-281, loeb-326, loeb-365, loeb-410 on the
Internet Archive.

Our references are Niese's continuous section numbers (j. aj. 5.97) and the
Loeb's English page header gives that range ("JEWISH ANTIQUITIES, V. 93-97"; the
"(2)" markers inside the English are chapter-relative and are not used). So this
is the Statius page method with the shared parts in loeb_pages.py: the book from
the numeral (the current book or the next), the section span from the header, a
misread digit repaired by the page's own plausible length, a section shared by
two pages given to the page where it begins.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import loeb_pages as L
from write_aligned import write_aligned

SRC = os.environ.get('TESSERAE_JOSEPHUS_SRC', os.path.expanduser('~/tesserae-backups/tr_f_2026-10-24/jos'))
OUT = os.environ.get('TESSERAE_JOSEPHUS_OUT', os.path.expanduser('~/tesserae-backups/tr_f_2026-10-24/final/partial'))
TESS = os.environ.get('TESSERAE_TEXTS', '/var/www/tesseraev6_flask/texts') + '/grc'
WORK = 'flavius_josephus.antiquitates_judaicae'
VOLS = [  # (file, archive id, first published, translators, first book, last book)
    ('loeb-281.txt', 'loeb-281', 1934, 'H. St. J. Thackeray and Ralph Marcus', 5, 8),
    ('loeb-326.txt', 'loeb-326', 1937, 'Ralph Marcus', 9, 11),
    ('loeb-365.txt', 'loeb-365', 1943, 'Ralph Marcus', 12, 14),
    ('loeb-410.txt', 'loeb-410', 1963, 'Ralph Marcus and Allen Wikgren', 15, 17),
]
HEAD = re.compile(r'ANTIQUITIES\W{0,3}\s*([IVXLl1|]{1,6})\W{1,3}\s*([0-9OolISB]{1,3})\s*[-–—]+\s*([0-9OolISB]{1,3})')
STOP = re.compile(r'^\W*JOSEPHUS\W*$|^\W*JEWISH ANTIQUITIES\W*$')
MARK = re.compile(r'\(\s*(\d{1,3})\s*\)')


def pages(path):
    out, cur = [], None
    for raw in open(path, encoding='utf-8', errors='replace'):
        s = raw.strip()
        m = HEAD.search(s)
        if m and len(s) < 48:
            if cur:
                out.append(cur)
            cur = {'num': m.group(1), 's': L.digits(m.group(2)), 'e': L.digits(m.group(3)), 'body': []}
            continue
        if cur:
            cur['body'].append(raw)
    if cur:
        out.append(cur)
    return out


def sections_for_volume(path, lo, hi):
    """[(book, start, end, English)] for one volume's pages, repaired and in order."""
    pgs = pages(path)
    book, last_s, out = None, None, []
    for p in pgs:
        s0, e0 = p['s'], p['e']
        if s0 is None or e0 is None or e0 < s0:
            continue
        hb = L.roman_in(p['num'], lo, hi)
        if book is None:
            if hb is None:
                continue
            book = hb
        elif hb in (book, book + 1) and hb != book and last_s is not None and s0 < last_s - 20:
            book = hb
        elif hb is None and last_s is not None and s0 < last_s - 40 and book < hi:
            book += 1
        last_s = s0
        text = L.page_english(p['body'], STOP, min_ratio=0.2, min_block=40)
        out.append({'book': book, 'start': s0, 'end': e0, 'text': text})
    pages_, fixed, dropped, trimmed = L.contiguity_repair([p for p in out if p['text']], 1, 40, lambda p: p['book'])
    print(f'    {os.path.basename(path)}: headers {len(pgs)} kept {len(pages_)} repaired {fixed} dropped {dropped} trimmed {trimmed}')
    return pages_


def main():
    path = f'{TESS}/{WORK}.tess'
    refs = L.load_refs(path, 2)
    src = L.source_for(path)
    units, idx, ref2u, usrc = [], {}, {}, []
    used = []
    for fn, vid, yr, tr, lo, hi in VOLS:
        pg = sections_for_volume(f'{SRC}/{fn}', lo, hi)
        n_sec = 0
        for p in pg:
            t = p['text']
            if t not in idx:
                idx[t] = len(units)
                units.append(t)
                usrc.append(vid)
            for sct in range(p['start'], p['end'] + 1):
                ref = refs.get((p['book'], sct))
                if ref and ref not in ref2u:
                    ref2u[ref] = idx[t]
                    n_sec += 1
        print(f'  {fn}: sections paired {n_sec}')
        if n_sec > 50:
            used.append((fn, vid, yr, tr))
    pairs = [(src.get(r, ''), units[i]) for r, i in ref2u.items()]
    hit, n, r, ok, by = L.checks(pairs, 'grc')
    ur = L.unit_corr(units, ref2u, src)
    cov_all = len(ref2u) / len(refs)
    sub = [r for r in refs.values() if 5 <= int(re.findall(r'\d+', r)[-2]) <= 17]
    cov = sum(1 for r in sub if r in ref2u) / len(sub)
    print(f'books 5-17: refs {len(sub)} paired {sum(1 for r in sub if r in ref2u)} cov {cov:.3f} (whole work {cov_all:.3f}) '
          f'names {hit} (n={n}) corr per ref {r} unit-length corr {ur} refs/unit {len(ref2u)/len(units):.2f}')
    by_book = {}
    for ref in sub:
        b = int(re.findall(r'\d+', ref)[-2])
        by_book.setdefault(b, [0, 0])
        by_book[b][0] += 1
        by_book[b][1] += ref in ref2u
    print('coverage by book:', {b: round(v[1] / v[0], 2) for b, v in sorted(by_book.items())})
    if not ((hit is not None and hit >= 0.25) or (ur is not None and ur >= 0.6)):
        print('REFUSED: checks failed')
        return 1
    vids = [vid for fn, vid, yr, tr in used]
    srcs = [{'translator': tr, 'year': yr, 'place': 'London and Cambridge, Mass.',
             'publisher': 'William Heinemann Ltd; Harvard University Press',
             'title': f'Josephus, Jewish Antiquities (Loeb Classical Library), {vid}',
             'url': f'https://archive.org/details/{vid}',
             'license': 'public domain, US, copyright not renewed (renewal check 2026-10-24)'}
            for fn, vid, yr, tr in used]
    write_aligned(OUT, 'grc', WORK, units, ref2u,
                  attribution='H. St. J. Thackeray, Ralph Marcus and Allen Wikgren (Loeb, 1934 to 1963), via the Internet Archive',
                  license=L.imprint_license(), sources=srcs, confidence='high', approximate=False,
                  tess_refs=sub,
                  name_check={'name_check_hit_rate': round(hit, 3) if hit is not None else None,
                              'name_check_n': n,
                              'length_correlation': round(ur, 3) if ur is not None else None,
                              'unit_sources': [vids.index(v) if v in vids else 0 for v in usrc]},
                  verified_by=by)
    return 0


if __name__ == '__main__':
    sys.exit(main())
