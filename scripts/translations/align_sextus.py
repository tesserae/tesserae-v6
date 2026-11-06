#!/usr/bin/env python3
"""Sextus Empiricus from Bury's Loeb volumes of 1933 to 1949 (Part F, 2026-10-24).

Three of the four volumes have an open scan on the Internet Archive:
  volume 1, Outlines of Pyrrhonism (1933, London Heinemann / New York Putnam),
  volume 2, Against the Logicians (1935, London Heinemann / Cambridge, Mass.
  Harvard University Press),
  volume 4, Against the Professors (1949, Harvard University Press / Heinemann).
Volume 3 (Against the Physicists and the Ethicists, Adversus mathematicos 9 to 11) is
a lending copy only and is not used.

The English page's running header gives the continuous section numbers
("OUTLINES OF PYRRHONISM, I. 7-10"; "AGAINST THE LOGICIANS, I. 114-117"), which
are the numbers our references end in. The Loeb counts Against the Logicians as
books I and II and the Professors as I to VI, ours are adversus mathematicos
7, 8 and 1 to 6, so the book is mapped. Pages are repaired and shared sections
given as in align_josephus_antiquities.py.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import loeb_pages as L
from write_aligned import write_aligned

SRC = os.environ.get('TESSERAE_SEXTUS_SRC', os.path.expanduser('~/tesserae-backups/tr_f_2026-10-24/sex'))
OUT = os.environ.get('TESSERAE_SEXTUS_OUT', os.path.expanduser('~/tesserae-backups/tr_f_2026-10-24/final/standalone'))
TESS = os.environ.get('TESSERAE_TEXTS', '/var/www/tesseraev6_flask/texts') + '/grc'
# (scan, archive id, first published, head words, work, loeb book -> our book, our file)
VOLS = [
    ('in.ernet.dli.2015.183761.txt', 'in.ernet.dli.2015.183761', 1933, 'OUTLINES OF PYRRHONISM', 'ph', {1: 1, 2: 2, 3: 3}),
    ('in.ernet.dli.2015.183448.txt', 'in.ernet.dli.2015.183448', 1935, 'AGAINST THE LOGICIANS', 'am', {1: 7, 2: 8}),
    ('sextusempiricus_201912.txt', 'sextusempiricus_201912', 1949, 'AGAINST THE PROFESSORS', 'am', {1: 1, 2: 2, 3: 3, 4: 4, 5: 5, 6: 6}),
]
STOP = re.compile(r'^\W*SEXTUS\W+[EU]MPIRICUS\W*$|^\W*(OUTLINES OF PYRRHONISM|AGAINST THE [A-Z]+)\W*$')
FILES = {'ph': 'sextus_empiricus.pyrrhoniae_hypotyposes', 'am': 'sextus_empiricus.adversus_mathematicos'}


def parse(path, words):
    head = re.compile(r'^\W{0,3}' + words.replace(' ', r'\s+') + r'\W{0,3}\s*([IVXLl1|]{1,4})\W{1,3}\s*([0-9OolISB]{1,3})\s*[-–—]+\s*([0-9OolISB]{1,3})\W{0,3}$', re.I)
    pages, cur = [], None
    for raw in open(path, encoding='utf-8', errors='replace'):
        s = raw.strip()
        m = head.match(s)
        if m:
            if cur:
                pages.append(cur)
            cur = {'num': m.group(1), 's': L.digits(m.group(2)), 'e': L.digits(m.group(3)), 'body': []}
            continue
        if cur:
            cur['body'].append(raw)
    if cur:
        pages.append(cur)
    return pages


def resolve(pages, bookmap):
    hi = max(bookmap)
    book, last_s, out = 1, None, []
    for p in pages:
        s0, e0 = p['s'], p['e']
        if s0 is None or e0 is None or e0 < s0:
            continue
        hb = L.roman_in(p['num'], 1, hi)
        if last_s is not None and s0 < last_s - 20 and book < hi and hb in (book + 1, None):
            book += 1
        elif last_s is not None and hb == book + 1 and s0 <= 12 and last_s > 20:
            book += 1
        last_s = s0
        text = L.page_english(p['body'], STOP, min_ratio=0.2, min_block=40)
        if text:
            out.append({'book': book, 'start': s0, 'end': e0, 'text': text})
    return L.contiguity_repair(out, 1, 45, lambda p: p['book'])


def main():
    units, idx, ref2u, usrc = [], {}, {}, []
    srcs_text, allrefs, used = {}, {}, []
    for fn, vid, yr, words, kind, bookmap in VOLS:
        tpath = f'{TESS}/{FILES[kind]}.tess'
        refs = {}
        for line in open(tpath, encoding='utf-8'):
            m = re.match(r'^<([^>]*)>\s*(.*)$', line)
            if not m:
                continue
            ref = m.group(1).strip().split()[-1] if ' ' in m.group(1) else m.group(1)
            nums = re.findall(r'\d+', m.group(1).split()[-1])
            if 'toc' in m.group(1) or 'endnote' in m.group(1) or len(nums) < 2:
                allrefs[m.group(1).strip()] = None
                continue
            key = (int(nums[0]), int(nums[-1]))
            refs[key] = m.group(1).strip()
            srcs_text[m.group(1).strip()] = m.group(2).strip()
            allrefs[m.group(1).strip()] = key
        pgs, fixed, dropped, trimmed = resolve(parse(f'{SRC}/{fn}', words), bookmap)
        n_ref = 0
        for p in pgs:
            ob = bookmap.get(p['book'])
            if ob is None:
                continue
            first = None
            for sct in range(p['start'], p['end'] + 1):
                ref = refs.get((ob, sct))
                if ref and ref not in ref2u:
                    if first is None:
                        if p['text'] not in idx:
                            idx[p['text']] = len(units)
                            units.append(p['text'])
                            usrc.append(vid)
                        first = idx[p['text']]
                    ref2u[ref] = first
                    n_ref += 1
        print(f'  {fn}: pages {len(pgs)} repaired {fixed} dropped {dropped} refs paired {n_ref}')
        if n_ref > 30:
            used.append((fn, vid, yr, kind))
    # one file per work
    for kind, stem in FILES.items():
        wrefs = [r for r in allrefs if r.split()[0] == stem or r.startswith(stem)]
        got = {r: i for r, i in ref2u.items() if r in set(wrefs)}
        real = [r for r in wrefs if allrefs[r] is not None]
        if not got:
            print(kind, 'nothing paired')
            continue
        # compact this work's units
        u2, remap, ref2 = [], {}, {}
        for r, i in got.items():
            if i not in remap:
                remap[i] = len(u2)
                u2.append(units[i])
            ref2[r] = remap[i]
        pairs = [(srcs_text.get(r, ''), u2[i]) for r, i in ref2.items()]
        hit, n, rr, ok, by = L.checks(pairs, 'grc')
        ur = L.unit_corr(u2, ref2, srcs_text)
        print(f'{stem}: refs {len(wrefs)} (translatable {len(real)}) paired {len(ref2)} cov {len(ref2)/len(real):.3f} '
              f'names {hit} (n={n}) unit-length corr {ur} refs/unit {len(ref2)/len(u2):.2f}')
        by_book = {}
        for r in real:
            b = allrefs[r][0]
            by_book.setdefault(b, [0, 0])
            by_book[b][0] += 1
            by_book[b][1] += r in ref2
        print('  coverage by book:', {b: round(v[1] / v[0], 2) for b, v in sorted(by_book.items())})
        if not ((hit is not None and hit >= 0.25) or (ur is not None and ur >= 0.6)):
            print('  REFUSED: checks failed')
            continue
        vol_srcs = [u for u in used if u[3] == kind]
        vids = [u[1] for u in vol_srcs]
        # per-unit source: the volume each unit came from
        inv = {i: usrc[i] for i in remap}
        us = [vids.index(inv[old]) if inv[old] in vids else 0 for old, new in sorted(remap.items(), key=lambda kv: kv[1])]
        srcs = [{'translator': 'R. G. Bury', 'year': yr,
                 'place': ('London and New York' if yr == 1933 else 'London and Cambridge, Mass.'),
                 'publisher': ('William Heinemann Ltd; G. P. Putnam\'s Sons' if yr == 1933
                               else 'William Heinemann Ltd; Harvard University Press'),
                 'title': 'Sextus Empiricus (Loeb Classical Library), ' + {'ph': 'Outlines of Pyrrhonism', 'am': 'Against the Logicians / Against the Professors'}[k],
                 'url': f'https://archive.org/details/{vid}',
                 'license': 'public domain, US, copyright not renewed (renewal check 2026-10-24)'}
                for fn, vid, yr, k in vol_srcs]
        write_aligned(OUT, 'grc', stem, u2, ref2,
                      attribution='R. G. Bury (Loeb, 1933 to 1949), via the Internet Archive',
                      license=L.imprint_license(), sources=srcs, confidence='medium', approximate=True,
                      tess_refs=real,
                      name_check={'name_check_hit_rate': round(hit, 3) if hit is not None else None,
                                  'name_check_n': n,
                                  'length_correlation': round(ur, 3) if ur is not None else None,
                                  'unit_sources': us},
                      verified_by=by)
    return 0


if __name__ == '__main__':
    sys.exit(main())
