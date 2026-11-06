#!/usr/bin/env python3
"""Pliny the Elder, Natural History, from the Loeb volumes of 1938 to 1963 (Part F, 2026-10-24).

Ten volumes: Rackham (1, 2, 3, 4, 5, 9), W. H. S. Jones (6, 7, 8) and Eichholz
(10), imprint "Cambridge, Massachusetts, Harvard University Press / London,
William Heinemann Ltd". Scans from the Internet Archive (the Loeb uploads
natural-history-in-ten-volumes.-vol.-N-..., the University of Toronto copies
naturalhistory0Nplinuoft and the Digital Library of India copies of volumes 2 and 6;
for each volume the scan that lets the most of our references be found is used).
Several are later printings of the original (the copyright pages say which).

Our references are Mayhoff-style chapters (plin. nat. 10.65), the running headers
carry chapter and section numerals in lower-case Roman that the OCR misreads
badly ("BOOK VIII. xvi. 40-xvii. 42"), so the numerals are not used. The Latin on
the facing page is the address instead (loeb_locate.py): the scan is split into
spreads (a Latin page, then its English page), each reference of ours is found on a
Latin page by a probe of its opening letters, walked in order so a probe can only be
found after the previous reference, and a reference takes the English pages from
the one under its opening to the one under the opening of the next reference
(the last of them only when the next reference starts below the top of its page).
A unit is therefore one to a few Loeb pages, and neighbouring chapters on the same
page share a unit. Book 1 (the table of contents and list of sources) has no
English text to match and is left unpaired.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import loeb_locate as LL
import loeb_pages as L
from write_aligned import write_aligned

SRC = os.environ.get('TESSERAE_PLINY_SRC', os.path.expanduser('~/tesserae-backups/tr_f_2026-10-24/pliny'))
OUT = os.environ.get('TESSERAE_PLINY_OUT', os.path.expanduser('~/tesserae-backups/tr_f_2026-10-24/final/partial'))
TESS = os.environ.get('TESSERAE_TEXTS', '/var/www/tesseraev6_flask/texts') + '/la'
WORK = 'pliny_the_elder.naturalis_historia'
# (file, archive id, first published, translator)
# (volume, first published, translator, [(scan file, archive id), ...]) in order of preference tried;
# the scan that locates the most of our references is used for that volume.
VOLS = [
    (1, 1938, 'H. Rackham', [('v1.txt', 'natural-history-in-ten-volumes.-vol.-1-praefatio-libri-i-ii-loeb-330')]),
    (2, 1942, 'H. Rackham', [('u2.txt', 'naturalhistory02plinuoft'), ('v2.txt', 'in.gov.ignca.13446')]),
    (3, 1940, 'H. Rackham', [('v3.txt', 'natural-history-in-ten-volumes.-vol.-3-libri-viii-xi-loeb-353'), ('u3.txt', 'naturalhistory03plinuoft')]),
    (4, 1945, 'H. Rackham', [('v4.txt', 'natural-history-in-ten-volumes.-vol.-4-libri-xii-xvi-loeb-370'), ('u4.txt', 'naturalhistory04plinuoft')]),
    (5, 1950, 'H. Rackham', [('v5.txt', 'natural-history-in-ten-volumes.-vol.-5-libri-xvii-xix-loeb-371')]),
    (6, 1951, 'W. H. S. Jones', [('u6.txt', 'naturalhistory06plinuoft'), ('v6.txt', 'in.gov.ignca.13448')]),
    (7, 1956, 'W. H. S. Jones', [('v7.txt', 'natural-history-in-ten-volumes.-vol.-7-libri-xxiv-xxvii-loeb-393'), ('u7.txt', 'naturalhistory07plinuoft')]),
    (8, 1963, 'W. H. S. Jones', [('v8.txt', 'natural-history-in-ten-volumes.-vol.-8-libri-xxviii-xxxii-loeb-418'), ('u8.txt', 'naturalhistory08plinuoft')]),
    (9, 1952, 'H. Rackham', [('v9.txt', 'natural-history-in-ten-volumes.-vol.-9-libri-xxxiii-xxxv-loeb-394'), ('u9.txt', 'naturalhistory09plinuoft')]),
    (10, 1962, 'D. E. Eichholz', [('v10.txt', 'natural-history-in-ten-volumes.-vol.-10-libri-xxxvi-xxxvii-loeb-419')]),
]



def is_src_head(s):
    u = s.upper()
    return len(s) < 36 and 'NATURAL' in u and 'HISTORY' in u and re.sub(r'^[\W_]+', '', u)[:1] in ('P', 'N')


def is_title(s):
    return bool(re.fullmatch(r'\W*BOOK\s+[IVXLlU1]+\W*', s))


def is_eng_head(s):
    return len(s) < 50 and bool(re.match(r'^\W{0,3}BOOK\s+[IVXLlU1]+\b', s)) and any(c.isdigit() for c in s)


def main():
    path = f'{TESS}/{WORK}.tess'
    refs = L.load_refs(path, 2)
    src = L.source_for(path)
    order = [(r, t) for r, t in src.items() if t.strip()]     # file order
    ref2u, units, idx, usrc = {}, [], {}, []
    chosen = {}
    for vol, yr, tr, cands in VOLS:
        best = None
        for fn, vid in cands:
            if not os.path.exists(f'{SRC}/{fn}'):
                continue
            lines = open(f'{SRC}/{fn}', encoding='utf-8', errors='replace').read().split('\n')
            sp = LL.spreads(lines, is_src_head, is_eng_head, is_title)
            found, missed = LL.locate(order, sp)
            print(f'  vol {vol} {fn}: spreads {len(sp)} refs located {len(found)}')
            if best is None or len(found) > len(best[3]):
                best = (fn, vid, sp, found)
        if best is None:
            continue
        fn, vid, sp, found = best
        chosen[vol] = (vid, len(found))
        eng = [L.page_english(x['eng'], re.compile(r'^\W*(PLINY|PUNY|PLIKY)\W*:?\s*NATURAL'), min_ratio=0.22, min_block=60)
               for x in sp]
        got = sorted(found.items(), key=lambda kv: (kv[1][0], kv[1][1]))
        for n, (ref, (pg, frac)) in enumerate(got):
            if ref in ref2u:
                continue
            if n + 1 < len(got):
                q, qf = got[n + 1][1]
                end = q if qf > 0.12 else q - 1
            else:
                end = pg
            end = min(max(end, pg), pg + 6)
            text = ' '.join(t for t in eng[pg:end + 1] if t).strip()
            if not text:
                continue
            if text not in idx:
                idx[text] = len(units)
                units.append(text)
                usrc.append(vol)
            ref2u[ref] = idx[text]
    pairs = [(src.get(r, ''), units[i]) for r, i in ref2u.items()]
    hit, n, r, ok, by = L.checks(pairs, 'la')
    ur = L.unit_corr(units, ref2u, src)
    cov = len(ref2u) / len(refs)
    per = round(len(ref2u) / len(units), 1)
    print(f'refs {len(refs)} paired {len(ref2u)} cov {cov:.3f} names {hit} (n={n}) unit-length corr {ur} refs/unit {per}')
    by_book = {}
    for ref in refs.values():
        b = ref.split()[-1].split('.')[0]
        by_book.setdefault(b, [0, 0])
        by_book[b][0] += 1
        by_book[b][1] += ref in ref2u
    print('coverage by book:', {b: round(v[1] / v[0], 2) for b, v in by_book.items()})
    if not (ok or (ur is not None and ur >= 0.8)):
        print('REFUSED')
        return 1
    vols_used = [vol for vol, yr, tr, c in VOLS if vol in chosen and chosen[vol][1] > 20]
    srcs = [{'translator': tr, 'year': yr, 'place': 'London and Cambridge, Mass.',
             'publisher': 'William Heinemann Ltd; Harvard University Press',
             'title': f'Pliny, Natural History, vol. {vol} (Loeb Classical Library)',
             'url': f'https://archive.org/details/{chosen[vol][0]}',
             'license': 'public domain, US, copyright not renewed (renewal check 2026-10-24)'}
            for vol, yr, tr, c in VOLS if vol in chosen and chosen[vol][1] > 20]
    write_aligned(OUT, 'la', WORK, units, ref2u,
                  attribution='H. Rackham, W. H. S. Jones and D. E. Eichholz (Loeb, 1938 to 1963), via the Internet Archive',
                  license=L.imprint_license(), sources=srcs, confidence='medium', approximate=True,
                  tess_refs=list(refs.values()),
                  name_check={'name_check_hit_rate': round(hit, 3) if hit is not None else None,
                              'name_check_n': n, 'length_correlation': round(ur, 3) if ur is not None else None,
                              'unit_sources': [vols_used.index(v) if v in vols_used else 0 for v in usrc]},
                  verified_by=by if ok else 'length correlation')
    return 0


if __name__ == '__main__':
    sys.exit(main())
