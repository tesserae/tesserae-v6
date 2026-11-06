#!/usr/bin/env python3
"""Ennius, Annales, from Warmington's Remains of Old Latin, volume I (Part F, 2026-10-24).

Loeb Classical Library 294, 1935, imprint "London, William Heinemann Ltd /
Cambridge, Massachusetts, Harvard University Press"; Internet Archive scan
remainsofoldlati01warmuoft (University of Toronto copy). Warmington numbers
fragments (Vahlen's order, "2-3" and so on) and our file numbers verse lines, so
the fragment numbers cannot be the address. Our own Latin is, as in
align_minor_latin_poets.py: the scan is split into spreads (a Latin page headed
ENNIUS, then its English page headed ANNALS), each of our lines is found on a Latin
page by a probe of its opening letters, and a line takes the English page of its
spread. The English page holds Warmington's translation with his testimonia, so
a unit is a page of fragments, not a line. Lines whose text Warmington prints
differently go unpaired.
"""
import difflib
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import loeb_pages as L
import loeb_locate as LL
from write_aligned import write_aligned

SRC = os.environ.get('TESSERAE_WAR_SRC', os.path.expanduser('~/tesserae-backups/tr_f_2026-10-24/war'))
OUT = os.environ.get('TESSERAE_WAR_OUT', os.path.expanduser('~/tesserae-backups/tr_f_2026-10-24/final/standalone'))
TESS = os.environ.get('TESSERAE_TEXTS', '/var/www/tesseraev6_flask/texts') + '/la'
STEM = 'ennius.annales'


def is_src_head(s):
    return re.sub(r'[^A-Z]', '', s.upper()) in ('ENNIUS', 'ENNIVS', 'ENNIUS') and len(s) < 14


def is_eng_head(s):
    u = re.sub(r'[^A-Z ]', '', s.upper()).strip()
    return len(s) < 20 and len(u) >= 5 and difflib.SequenceMatcher(None, u, 'ANNALS').ratio() >= 0.8


def main():
    lines = open(f'{SRC}/w1.txt', encoding='utf-8', errors='replace').read().split('\n')
    sp = LL.spreads(lines, is_src_head, is_eng_head)
    eng = [L.page_english(x['eng'], re.compile(r'^\W*ENNIUS\W*$'), min_ratio=0.15, min_block=60) for x in sp]
    path = f'{TESS}/{STEM}.tess'
    src = L.source_for(path)
    order = [(r, t) for r, t in src.items() if t.strip()]
    found, missed = LL.locate(order, sp, probe=14, window=15000)
    refs = [r for r, t in order]
    page = {r: found[r][0] for r in found}
    last_i, last_p, filled = None, None, 0
    for i, r in enumerate(refs):
        if r in page:
            if last_i is not None and last_p == page[r]:
                for j in range(last_i + 1, i):
                    if refs[j] not in page:
                        page[refs[j]] = last_p
                        filled += 1
            last_i, last_p = i, page[r]
    units, idx, ref2u = [], {}, {}
    for r in refs:
        if r in page and eng[page[r]]:
            t = eng[page[r]]
            if t not in idx:
                idx[t] = len(units)
                units.append(t)
            ref2u[r] = idx[t]
    pairs = [(src[r], units[i]) for r, i in ref2u.items()]
    hit, n, rr, ok, by = L.checks(pairs, 'la')
    ur = L.unit_corr(units, ref2u, src)
    print(f'spreads {len(sp)} refs {len(refs)} located {len(found)} filled {filled} paired {len(ref2u)} '
          f'cov {len(ref2u)/len(refs):.3f} names {hit} (n={n}) unit-length corr {ur} lines/unit {len(ref2u)/max(1,len(units)):.1f}')
    if len(found) / len(refs) < 0.5:
        # Warmington prints the fragments in his own order and readings: too few of our
        # lines are found on a page for the pages in between to be filled honestly
        print(f'REFUSED: only {len(found)} of {len(refs)} lines were found on a page (under half)')
        return 1
    if not (ok or (ur is not None and ur >= 0.6)):
        print('REFUSED: checks failed')
        return 1
    write_aligned(OUT, 'la', STEM, units, ref2u,
                  attribution='E. H. Warmington (Loeb, 1935), via the Internet Archive',
                  license=L.imprint_license(),
                  sources=[{'translator': 'E. H. Warmington', 'year': 1935, 'place': 'London and Cambridge, Mass.',
                            'publisher': 'William Heinemann Ltd; Harvard University Press',
                            'title': 'Remains of Old Latin, vol. I: Ennius and Caecilius (Loeb Classical Library 294)',
                            'url': 'https://archive.org/details/remainsofoldlati01warmuoft',
                            'license': 'public domain, US, copyright not renewed (renewal check 2026-10-24)'}],
                  confidence='low', approximate=True, tess_refs=refs,
                  name_check={'name_check_hit_rate': round(hit, 3) if hit is not None else None,
                              'name_check_n': n, 'length_correlation': round(ur, 3) if ur is not None else None},
                  verified_by=by if ok else 'length correlation')
    return 0


if __name__ == '__main__':
    sys.exit(main())
