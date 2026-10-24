#!/usr/bin/env python3
"""Grattius and Calpurnius Siculus from Duff and Duff's Minor Latin Poets, volume I (Part F, 2026-10-24).

Loeb Classical Library 284, 1934, imprint "London, William Heinemann Ltd /
Cambridge, Massachusetts, Harvard University Press". The scan is the Internet
Archive's University of Toronto copy minorlatinpoetsw00duffuoft. (Volume II,
which holds Rutilius Namatianus, Tiberianus and the Phoenix, has no open scan,
and Nemesianus is already installed from the same translators.)

The pages carry no line range in their headers, only the poet's name, so
our own Latin is the address: the scan is split into spreads (a Latin page then
its English page), each of our lines is found on a Latin page by a probe of its
opening letters (loeb_locate.py), and a line gets the English page of the spread
it stands on. A line too short to probe takes the page of the lines on both
sides when they agree. The unheaded opening pages are recovered afterwards by
repair_book_openings.py as for the Statius files.
"""
import difflib
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import loeb_pages as L
import loeb_locate as LL
from write_aligned import write_aligned

SRC = os.environ.get('TESSERAE_MLP_SRC', os.path.expanduser('~/tesserae-backups/tr_f_2026-10-24/mlp'))
OUT = os.environ.get('TESSERAE_MLP_OUT', os.path.expanduser('~/tesserae-backups/tr_f_2026-10-24/final/standalone'))
TESS = os.environ.get('TESSERAE_TEXTS', '/var/www/tesseraev6_flask/texts') + '/la'
SCAN = ('mlp1.txt', 'minorlatinpoetsw00duffuoft', 1934)
WORKS = [('grattius.cynegetica', 'Grattius, Cynegetica'), ('calpurnius_siculus.eclogae', 'Calpurnius Siculus, Eclogues')]
NAMES = re.compile(r'GRATTIUS|CALPURNIUS|SICULUS|PUBLILIUS|PISONIS|EINSIEDELN|AETNA|FLORUS|HADRIAN|MAECENATEM|PRECATIO')


def is_src_head(s):
    u = s.upper()
    return len(s) < 36 and (('MINOR' in u and 'POETS' in u) or re.search(r'CYNEGETIC|BUCOLIC|ECLOGAE?\b', u) is not None
                            and u == re.sub(r'[^A-Z ]', '', u))


HEADS = ['GRATTIUS', 'CALPURNIUS SICULUS', 'PUBLILIUS SYRUS', 'LAUS PISONIS', 'EINSIEDELN ECLOGUES', 'AETNA',
         'ELEGIAE IN MAECENATEM', 'FLORUS', 'HADRIAN']


def is_eng_head(s):
    """The English page's header is the poet's name; the scan misreads it often
    (GRAITIUS, CRATTIUS), so the match is by similarity."""
    if len(s) > 34 or not re.fullmatch(r"[A-Za-z ,.'*]+", s):
        return False
    u = re.sub(r'[^A-Z ]', '', s.upper()).strip()
    if len(u) < 5 or 'MINOR' in u:
        return False
    return max(difflib.SequenceMatcher(None, u, h).ratio() for h in HEADS) >= 0.74


def split_lost_headers(sp):
    """A spread whose English page lost its header holds both pages in `src`.

    The English begins where common English words take over: the first run of
    eight lines with a stop-word share of a quarter or more.
    """
    for x in sp:
        if x['eng'] or len(x['src']) < 50:
            continue
        lines = x['src']
        for i in range(20, len(lines) - 8):
            if L.english_ratio(' '.join(lines[i:i + 8])) >= 0.26:
                x['src'], x['eng'] = lines[:i], lines[i:]
                break


def main():
    lines = open(f'{SRC}/{SCAN[0]}', encoding='utf-8', errors='replace').read().split('\n')
    sp = LL.spreads(lines, is_src_head, is_eng_head)
    split_lost_headers(sp)
    eng = [L.page_english(x['eng'], re.compile(r'^\W*MINOR\s+LATIN\s+POETS'), min_ratio=0.2, min_block=60, cut_footnotes=True) for x in sp]
    print('spreads', len(sp))
    ok_all = True
    for stem, label in WORKS:
        path = f'{TESS}/{stem}.tess'
        src = L.source_for(path)
        order = list(src.items())
        found, missed = LL.locate(order, sp, probe=16, window=12000)
        # fill lines between two located lines on the same spread
        refs = [r for r, t in order]
        page = {r: found[r][0] for r in found}
        filled = 0
        last_i, last_p = None, None
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
        cov = len(ref2u) / len(refs)
        print(f'{stem}: refs {len(refs)} located {len(found)} filled {filled} paired {len(ref2u)} cov {cov:.3f} '
              f'names {hit} (n={n}) unit-length corr {ur} lines/unit {len(ref2u)/max(1,len(units)):.1f}')
        if not (ok or (ur is not None and ur >= 0.6)):
            print('  REFUSED: checks failed')
            ok_all = False
            continue
        write_aligned(OUT, 'la', stem, units, ref2u,
                      attribution='J. Wight Duff and Arnold M. Duff (Loeb, 1934), via the Internet Archive',
                      license=L.imprint_license(),
                      sources=[{'translator': 'J. Wight Duff and Arnold M. Duff', 'year': 1934,
                                'place': 'London and Cambridge, Mass.',
                                'publisher': 'William Heinemann Ltd; Harvard University Press',
                                'title': f'Minor Latin Poets, vol. I (Loeb Classical Library 284): {label}',
                                'url': f'https://archive.org/details/{SCAN[1]}',
                                'license': 'public domain, US, copyright not renewed (renewal check 2026-10-24)'}],
                      confidence='medium', approximate=True, tess_refs=refs,
                      name_check={'name_check_hit_rate': round(hit, 3) if hit is not None else None,
                                  'name_check_n': n,
                                  'length_correlation': round(ur, 3) if ur is not None else None},
                      verified_by=by if ok else 'length correlation')
    return 0 if ok_all else 1


if __name__ == '__main__':
    sys.exit(main())
