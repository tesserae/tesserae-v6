#!/usr/bin/env python3
# ruff: noqa: E741  (the corpus lines are called `l` in a dozen throwaway loops, as in the other scripts here)
"""Cicero: the Verrines (Yonge, Bohn 1851), De Oratore and Brutus (J. S. Watson,
Bohn 1860, in 'Cicero on Oratory and Orators') and De Fato (Yonge, Bohn 1853),
aligned to texts/la/cicero.in_verrem, .de_oratore, .brutus and .de_fato.

Sources: Internet Archive OCR of the Bohn volumes (orationsofmarcus01ciceuoft,
ciceroonoratorya00ciceuoft, treatisescicero00ciceuoft). The OCR is rough, so the
chapter walk is the tolerant one of align_cicero_treatises.py (split_chapters:
roman numerals that must chain 1, 2, 3 and may skip at most two lost markers).

KEYS, AND THE HONESTY LINE (as in align_cicero_treatises.py). Yonge and Watson
number CHAPTERS (the roman numerals of the old editions) and our references number
SECTIONS (the modern paragraph numbers), except for Brutus, where our 97 lines ARE
the 97 chapters. For Brutus the alignment is exact. For the others each section
is allocated to a chapter by cumulative text length inside its book (chapter
boundaries fall where the running share of the Latin equals the running share of
the English), the files are marked approximate, and a book whose chapter chain
breaks is refused rather than guessed at.

    align_cicero_yonge_watson.py SRC_DIR OUT_DIR [--dry]
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from align_cicero_treatises import allocate                       # noqa: E402
from chapter_common import load_work, tail, finish, split_chapters_fuzzy   # noqa: E402

src_dir, out_dir = sys.argv[1:3]
dry = '--dry' in sys.argv


def norm(l):
    return re.sub(r'\s+', ' ', l).strip()


def load(fn):
    return open(os.path.join(src_dir, fn), encoding='utf-8', errors='replace').read().split('\n')


def find(lines, pat, after=0):
    for i in range(after, len(lines)):
        if re.match(pat, norm(lines[i])):
            return i
    raise ValueError(f'heading not found: {pat}')


def region(lines, starts, end):
    """Cut `lines` into [(label, slice)] at the heading patterns in `starts`
    (searched in order), the last one ending at the `end` pattern."""
    idx, at = [], 0
    for label, pat in starts:
        at = find(lines, pat, at + 1 if idx else 0)
        idx.append((label, at))
    stop = find(lines, end, idx[-1][1] + 1)
    out = []
    for k, (label, a) in enumerate(idx):
        b = idx[k + 1][1] if k + 1 < len(idx) else stop
        out.append((label, lines[a + 1:b]))
    return out


SRC_VERRES = ('orationsofmarcus01ciceuoft.txt',
              [((1, 1), r'^THE FIRST ORATION AGAINST VERRES'),
               ((2, 1), r'^THE FIRST BOOK OF THE SECOND PLEADING'),
               ((2, 2), r'^THE SECOND BOOK O[FP] THE SECOND PLEADING'),
               ((2, 3), r'^THE THIRD BOOK OF THE SECOND PLEADING'),
               ((2, 4), r'^THE FOURTH BOOK OF THE SECOND PLEADING'),
               ((2, 5), r'^TH[ER] FIFTH BOOK OF THE SECOND PLEADING')], r'^END OF VOL\. I')
SRC_ORATORE = ('ciceroonoratorya00ciceuoft.txt',
               [(1, r'^BOOK I\.'), (2, r'^BOOK II\.'), (3, r'^BOOK Ill?\.')],
               r'^END OF .{0,3}DE ORATORE')

JOBS = []


def work(stem, prefix, regions, mode, source, notes=''):
    JOBS.append((stem, prefix, regions, mode, source, notes))


# the Verrines
fn, starts, end = SRC_VERRES
work('cicero.in_verrem', 'ver', region(load(fn), starts, end), 'sections',
     {'translator': 'Charles Duke Yonge', 'year': 1851, 'place': 'London', 'publisher': 'Henry G. Bohn',
      'title': 'The Orations of Marcus Tullius Cicero, literally translated, vol. 1 (Bohn\'s Classical Library)',
      'url': 'https://archive.org/details/orationsofmarcus01ciceuoft'})
# De Oratore
fn, starts, end = SRC_ORATORE
work('cicero.de_oratore', 'orat', region(load(fn), starts, end), 'sections',
     {'translator': 'John Selby Watson', 'year': 1860, 'place': 'London', 'publisher': 'Henry G. Bohn',
      'title': 'Cicero on Oratory and Orators (Bohn\'s Classical Library)',
      'url': 'https://archive.org/details/ciceroonoratorya00ciceuoft'})
# Brutus: exact, chapters are our references
lines = load('ciceroonoratorya00ciceuoft.txt')
a = find(lines, r'^REMARKS ON EMINENT ORATORS\.$', 14000)
b = find(lines, r'^INDEX\.', a + 200)
work('cicero.brutus', 'brut', [('', lines[a + 1:b])], 'chapters',
     {'translator': 'John Selby Watson', 'year': 1860, 'place': 'London', 'publisher': 'Henry G. Bohn',
      'title': 'Cicero on Oratory and Orators (Bohn\'s Classical Library)',
      'url': 'https://archive.org/details/ciceroonoratorya00ciceuoft'})
# De Fato
lines = load('treatisescicero00ciceuoft.txt')
a = find(lines, r'^ON FATE\.$', 14000)
b = find(lines, r'^ON THE COMMONWEALTH\.$', a + 100)
work('cicero.de_fato', 'fat', [('', lines[a + 1:b])], 'sections',
     {'translator': 'Charles Duke Yonge', 'year': 1853, 'place': 'London', 'publisher': 'Henry G. Bohn',
      'title': 'The Treatises of M. T. Cicero: On the Nature of the Gods, On Divination, On Fate, ... (Bohn\'s Classical Library)',
      'url': 'https://archive.org/details/treatisescicero00ciceuoft'},
     notes='The commencement of the treatise is lost in the Latin and the translation; no section is paired before the first chapter.')

for stem, prefix, regions, mode, source, notes in JOBS:
    refs, src, _ = load_work('la', stem)
    by_book = {}
    for r in refs:
        parts = tail(r).split('.')
        if not all(p.isdigit() for p in parts):
            continue
        if stem == 'cicero.in_verrem':
            key, sec = (int(parts[0]), int(parts[1])), int(parts[2])
        elif stem == 'cicero.de_oratore':
            key, sec = int(parts[0]), int(parts[1])
        else:
            key, sec = '', int(parts[-1])
        by_book.setdefault(key, []).append((sec, r))
    units, idx, ref_to_unit, refused = [], {}, {}, []
    for label, rlines in regions:
        chapters, ok = split_chapters_fuzzy(rlines)
        secs = by_book.get(label)
        if not secs:
            continue
        if not ok or len(chapters) < 3:
            refused.append((label, len(chapters)))
            continue
        if mode == 'chapters':
            by_ch = {n: t for n, t in chapters}
            shared = 0
            last = None
            for sec, r in sorted(secs):
                t = by_ch.get(sec)
                if t:
                    if sec not in idx:
                        idx[sec] = len(units)
                        units.append(t)
                    last = idx[sec]
                    ref_to_unit[r] = last
                elif last is not None and sec <= chapters[-1][0]:
                    ref_to_unit[r] = last          # marker lost in the OCR: its text sits in the chapter before
                    shared += 1
            notes += f' {shared} chapters whose numeral the scan lost share the unit of the chapter before (their text is in it).'
            print(f'{stem}: {len(chapters)} chapters read, last numeral {chapters[-1][0]}')
        else:
            alloc = allocate(chapters, sorted((s, len(src[r])) for s, r in secs))
            for sec, r in secs:
                if sec in alloc:
                    ck = (label, alloc[sec])
                    if ck not in idx:
                        idx[ck] = len(units)
                        units.append(chapters[alloc[sec]][1])
                    ref_to_unit[r] = idx[ck]
            print(f'{stem} {label}: {len(chapters)} chapters (last numeral {chapters[-1][0]}) over {len(secs)} sections')
    if refused:
        print(f'{stem}: REFUSED books {refused}')
    if not units:
        continue
    exact = mode == 'chapters'
    finish('la', stem, units, ref_to_unit, refs, src, out_dir=out_dir, dry=dry,
           mode='exact' if exact else 'proportional', exact=exact,
           attribution=f"{source['translator']} ({source['publisher']}, {source['year']}); scans at the Internet Archive",
           license=f"Public domain (published {source['year']})",
           sources=[dict(source, mode='exact' if exact else 'proportional',
                         ref_composition=['book', 'chapter'], pd_reason=f"published {source['year']}")],
           notes=('Sections are allocated to the translator\'s chapters by cumulative text length inside each book; '
                  'the unit is one chapter. ' if not exact else 'Our references are the translator\'s chapters. ') + notes
           + (f' Refused books: {refused}.' if refused else ''))
