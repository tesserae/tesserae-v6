#!/usr/bin/env python3
"""Prudentius from H. J. Thomson's Loeb volumes of 1949 and 1953 (Part F, 2026-10-24).

Volume I (1949: Apotheosis, Hamartigenia, Psychomachia, Contra Symmachum I,
besides the Cathemerinon, which is installed from Pope and left alone) and
volume II (1953: Contra Symmachum II, Peristephanon, Dittochaeon, Epilogus),
imprint "London, William Heinemann Ltd / Cambridge, Massachusetts, Harvard
University Press", Internet Archive scans prudentiuswithen01pruduoft and
prudentius00pruduoft (University of Toronto copies).

The pages carry no line range, only a title ("CROWNS OF MARTYRDOM, X"), so, as in
align_minor_latin_poets.py, our own Latin is the address: the scan is split into
spreads, each of our lines is found on a Latin page by a probe of its opening
letters (loeb_locate.py), and a line takes the English page of its spread.
"""
import difflib
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import loeb_pages as L
import loeb_locate as LL
from write_aligned import write_aligned

SRC = os.environ.get('TESSERAE_PRU_SRC', os.path.expanduser('~/tesserae-backups/tr_f_2026-10-24/pru'))
OUT = os.environ.get('TESSERAE_PRU_OUT', os.path.expanduser('~/tesserae-backups/tr_f_2026-10-24/final/standalone'))
TESS = os.environ.get('TESSERAE_TEXTS', '/var/www/tesseraev6_flask/texts') + '/la'
HEADS = ['CROWNS OF MARTYRDOM', 'SCENES FROM HISTORY', 'A REPLY TO ADDRESS OF SYMMACHUS', 'THE DIVINITY OF CHRIST',
         'THE ORIGIN OF SIN', 'THE FIGHT FOR MANSOUL', 'THE DAILY ROUND', 'EPILOGUE']
# (scan, archive id, first published, [(work stem, book filter or None)])
VOLS = [
    ('p1b.txt', 'prudentiuswithen01pruduoft', 1949,
     [('prudentius.apotheosis', None), ('prudentius.hamartigenia', None), ('prudentius.psychomachia', None),
      ('prudentius.contra_symmachum', 1)]),
    ('p1.txt', 'prudentius00pruduoft', 1953,
     [('prudentius.contra_symmachum', 2), ('prudentius.peristephanon', None), ('prudentius.dittochaeon', None),
      ('prudentius.epilogus', None)]),
]


LATIN_TITLES = ['PSYCHOMACHIA', 'HAMARTIGENIA', 'APOTHEOSIS', 'PERISTEPHANON LIBER', 'EPILOGUS', 'CATHEMERINON',
                'CONTRA ORATIONEM SYMMACHI LIBER', 'TITULI HISTORIARUM DITTOCHAEON']


def is_src_head(s):
    """A Latin page: the running head PRUDENTIUS, or the poem's own Latin title on its opening page."""
    if len(s) > 48:
        return False
    u = re.sub(r'[^A-Z ]', '', s.upper()).strip()
    if re.sub(r'[^A-Z]', '', u) in ('PRUDENTIUS', 'PRUDENTIU', 'PRUDENTIVS'):
        return True
    return len(u) >= 9 and max(difflib.SequenceMatcher(None, u, h).ratio() for h in LATIN_TITLES) >= 0.85


def is_eng_head(s):
    if len(s) > 45 or not re.fullmatch(r"[A-Za-z ,.'*0-9]+", s):
        return False
    u = re.sub(r',?\s*[IVXLl1|]+\.?\s*$', '', re.sub(r'[^A-Za-z ,]', '', s.upper())).strip()
    if len(u) < 8:
        return False
    return max(difflib.SequenceMatcher(None, u, h).ratio() for h in HEADS) >= 0.8


def split_lost_headers(sp):
    for x in sp:
        if x['eng'] or len(x['src']) < 50:
            continue
        lines = x['src']
        for i in range(20, len(lines) - 8):
            if L.english_ratio(' '.join(lines[i:i + 8])) >= 0.26:
                x['src'], x['eng'] = lines[:i], lines[i:]
                break


def main():
    got = {}      # work stem -> {ref: english page text}
    for fn, vid, yr, works in VOLS:
        lines = open(f'{SRC}/{fn}', encoding='utf-8', errors='replace').read().split('\n')
        sp = LL.spreads(lines, is_src_head, is_eng_head)
        split_lost_headers(sp)
        eng = [L.page_english(x['eng'], re.compile(r'^\W*PRUDENTIUS\W*$'), min_ratio=0.2, min_block=60, cut_footnotes=True) for x in sp]
        order, owner = [], {}
        for stem, book in works:
            src = L.source_for(f'{TESS}/{stem}.tess')
            for r, t in src.items():
                if not t.strip():
                    continue
                if book is not None and not re.search(r'sym\. %d\.' % book, r):
                    continue
                order.append((r, t))
                owner[r] = stem
        found, missed = LL.locate(order, sp, probe=16, window=12000)
        page = {r: found[r][0] for r in found}
        refs = [r for r, t in order]
        last_i, last_p, filled = None, None, 0
        for i, r in enumerate(refs):
            if r in page:
                if last_i is not None and last_p == page[r]:
                    for j in range(last_i + 1, i):
                        if refs[j] not in page:
                            page[refs[j]] = last_p
                            filled += 1
                last_i, last_p = i, page[r]
        print(f'{fn}: spreads {len(sp)} refs {len(order)} located {len(found)} filled {filled}')
        for r in refs:
            if r in page and eng[page[r]]:
                got.setdefault(owner[r], {})[r] = (eng[page[r]], vid, yr)
    for stem in sorted(got):
        path = f'{TESS}/{stem}.tess'
        src = L.source_for(path)
        refs = list(src)
        # the contra_symmachum file holds books 1 and 2, paired from two volumes
        units, idx, ref2u, usrc = [], {}, {}, []
        for r, (t, vid, yr) in got[stem].items():
            if t not in idx:
                idx[t] = len(units)
                units.append(t)
                usrc.append(vid)
            ref2u[r] = idx[t]
        vids = sorted(set(usrc), key=usrc.index)
        pairs = [(src[r], units[i]) for r, i in ref2u.items()]
        hit, n, rr, ok, by = L.checks(pairs, 'la')
        ur = L.unit_corr(units, ref2u, src)
        cov = len(ref2u) / len(refs)
        print(f'{stem}: refs {len(refs)} paired {len(ref2u)} cov {cov:.3f} names {hit} (n={n}) '
              f'unit-length corr {ur} lines/unit {len(ref2u)/max(1,len(units)):.1f}')
        if not (ok or (ur is not None and ur >= 0.6)):
            print('  REFUSED: checks failed')
            continue
        ss = [{'translator': 'H. J. Thomson', 'year': dict((v, y) for f, v, y, w in VOLS)[v],
               'place': 'London and Cambridge, Mass.', 'publisher': 'William Heinemann Ltd; Harvard University Press',
               'title': 'Prudentius (Loeb Classical Library), vol. %s' % ('I' if v == 'prudentiuswithen01pruduoft' else 'II'),
               'url': f'https://archive.org/details/{v}',
               'license': 'public domain, US, copyright not renewed (renewal check 2026-10-24)'} for v in vids]
        write_aligned(OUT, 'la', stem, units, ref2u,
                      attribution='H. J. Thomson (Loeb, 1949 and 1953), via the Internet Archive',
                      license=L.imprint_license(), sources=ss, confidence='medium', approximate=True,
                      tess_refs=refs,
                      name_check={'name_check_hit_rate': round(hit, 3) if hit is not None else None,
                                  'name_check_n': n, 'length_correlation': round(ur, 3) if ur is not None else None,
                                  'unit_sources': [vids.index(v) for v in usrc]},
                      verified_by=by if ok else 'length correlation')
    return 0


if __name__ == '__main__':
    sys.exit(main())
