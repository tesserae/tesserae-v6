#!/usr/bin/env python3
"""Plato, Republic books 6 to 10, from Shorey's Loeb volume II (Part F, 2026-10-24).

Loeb Classical Library 276, first printed 1935, imprint "London, William Heinemann
Ltd / Cambridge, Massachusetts, Harvard University Press"; Internet Archive scan
republicshorey02platuoft (University of Toronto copy, a later printing: the title
page reads MCMXLII). No translation of the Republic is installed. Books 1 to 5 are
volume I (first printed 1930) and are not part of this file.

The English pages are headed only "THE REPUBLIC, BOOK VII", so, as in
align_minor_latin_poets.py, our own text is the address: each Stephanus section of
ours (pl. respublica 7.514a) is found on a Greek page by a probe of its opening
letters (Greek mode of loeb_locate.py) and takes the English page of its spread.
"""
import difflib
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import loeb_pages as L
import loeb_locate as LL
from write_aligned import write_aligned

SRC = os.environ.get('TESSERAE_REP_SRC', os.path.expanduser('~/tesserae-backups/tr_f_2026-10-24/rep'))
OUT = os.environ.get('TESSERAE_REP_OUT', os.path.expanduser('~/tesserae-backups/tr_f_2026-10-24/final/standalone'))
TESS = os.environ.get('TESSERAE_TEXTS', '/var/www/tesseraev6_flask/texts') + '/grc'
STEM = 'plato.respublica'


def is_src_head(s):
    return len(s) < 14 and re.sub(r'[^A-Z]', '', s.upper()).startswith('PLATO') and len(re.sub(r'[^A-Z]', '', s.upper())) <= 6


def is_eng_head(s):
    u = re.sub(r'[^A-Z ,]', '', s.upper()).strip()
    return len(s) < 34 and difflib.SequenceMatcher(None, re.sub(r'[ ,]+[IVXLU1l]+$', '', u), 'THE REPUBLIC, BOOK').ratio() >= 0.8 \
        and 'BOOK' in u


def main():
    LL.GREEK_MODE = True
    lines = open(f'{SRC}/republicshorey02platuoft.txt', encoding='utf-8', errors='replace').read().split('\n')
    sp = LL.spreads(lines, is_src_head, is_eng_head)
    eng = [L.page_english(x['eng'], re.compile(r'^\W*PLATO\W{0,4}$'), min_ratio=0.2, min_block=60) for x in sp]
    print('spreads', len(sp), 'with English', sum(1 for e in eng if e))
    path = f'{TESS}/{STEM}.tess'
    src = L.source_for(path)
    order = [(r, t) for r, t in src.items() if t.strip() and int(re.findall(r'\d+', r.split()[-1])[0]) >= 6]
    found, missed = LL.locate(order, sp, probe=16, window=40000)
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
    hit, n, rr, ok, by = L.checks(pairs, 'grc')
    ur = L.unit_corr(units, ref2u, src)
    print(f'books 6-10: refs {len(refs)} located {len(found)} filled {filled} paired {len(ref2u)} cov {len(ref2u)/len(refs):.3f} '
          f'names {hit} (n={n}) unit-length corr {ur} refs/unit {len(ref2u)/max(1,len(units)):.1f}')
    if not (ok or (ur is not None and ur >= 0.6)):
        print('REFUSED: checks failed')
        return 1
    write_aligned(OUT, 'grc', STEM, units, ref2u,
                  attribution='Paul Shorey (Loeb, 1935), via the Internet Archive',
                  license=L.imprint_license(),
                  sources=[{'translator': 'Paul Shorey', 'year': 1935, 'place': 'London and Cambridge, Mass.',
                            'publisher': 'William Heinemann Ltd; Harvard University Press',
                            'title': 'Plato, Republic, vol. II, books 6 to 10 (Loeb Classical Library 276)',
                            'url': 'https://archive.org/details/republicshorey02platuoft',
                            'license': 'public domain, US, copyright not renewed (renewal check 2026-10-24)'}],
                  confidence='medium', approximate=True, tess_refs=refs,
                  name_check={'name_check_hit_rate': round(hit, 3) if hit is not None else None,
                              'name_check_n': n, 'length_correlation': round(ur, 3) if ur is not None else None},
                  verified_by=by if ok else 'length correlation')
    return 0


if __name__ == '__main__':
    sys.exit(main())
