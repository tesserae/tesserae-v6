#!/usr/bin/env python3
# ruff: noqa: E741  (the corpus lines are called `l` in a dozen throwaway loops, as in the other scripts here)
"""Maximus of Tyre, Dissertations: Thomas Taylor's translation (London, 1804)
aligned to texts/grc/maximus_of_tyre.dialexeis at DISSERTATION level.

THE NUMBERING DIFFERS. Taylor translated the Davies edition and numbers the forty-one
dissertations in its order, and our Greek (Hobein's Teubner order) numbers them
differently. Pairing number to number would have put the wrong English beside every
dissertation while looking complete. The concordance below was found by comparing
proper names between each of our 41 Greek dissertations and each of Taylor's 41
English ones (every Greek dissertation against every English one), by the ratio of
English to Greek length, and then confirmed by reading the opening of every Greek
dissertation beside the opening and title of the English it was given (about 36 of
the 41 were read one by one, the rest sit inside runs that were). The result is a
bijection: ours 11 to 29 are Taylor 1 to 19, ours 36 to 41 are Taylor 20 to 25,
ours 8 to 10 are Taylor 26 to 28, and the rest are listed in CONCORDANCE.

Source: Internet Archive OCR (bub_gb_YcYfAAAAMAAJ, both volumes). Taylor numbers
the forty-one dissertations and nothing finer, and our references are
dissertation.chapter.letter, so each dissertation is one unit shown beside all of
its Greek lines (about 48 lines per unit). The OCR damages the numerals (XL as XI,
XXXVI as XXXVII), so the walk counts headings in order and checks that exactly
forty-one are found. Taylor's footnotes, set at the foot of his pages, are
dropped with the footnote-block rule of chapter_common.py where they start with a
mark; the end of the first volume and 'FINIS' close their dissertations.

    align_maximus_taylor.py SRC_FILE OUT_DIR [--dry]
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from chapter_common import load_work, tail, finish, dehyphenate, drop_footnotes, clean   # noqa: E402

src_file, out_dir = sys.argv[1:3]
dry = '--dry' in sys.argv
lines = open(src_file, encoding='utf-8', errors='replace').read().split('\n')
HEAD = re.compile(r'^.{0,8}?\s*DISSERTATION\s+[IVXLl1UVvFf ]{1,10}[.,]?\W{0,4}[xXV]?\s*$')
stops = [i for i, l in enumerate(lines) if re.match(r'^\s*(ADDITIONAL\s+NOTES|END\s+OF\s+THE\s+FIRST\s+VOLUME|FINIS)\b', l)]
heads = [i for i, l in enumerate(lines) if HEAD.match(l) and 'DISSERTATIONS' not in l]
print(f'headings found {len(heads)} (expect 41), stops {stops}')
assert len(heads) == 41, len(heads)
english = {}
for k, a in enumerate(heads):
    b = heads[k + 1] if k + 1 < len(heads) else len(lines)
    cut = [s for s in stops if a < s < b]
    if cut:
        b = cut[0]
    seg = lines[a + 1:b]
    # a volume title page ('DISSERTATIONS' ... ) can sit inside the range of dissertation 20 and 21: drop it
    seg = [l for l in seg if not re.match(r'^\s*Digitized by', l)]
    english[k + 1] = clean(dehyphenate('\n'.join(drop_footnotes(seg))))
# our dissertation (Hobein order) -> Taylor's dissertation number (Davies order)
CONCORDANCE = {1: 36, 2: 38, 3: 39, 4: 29, 5: 30, 6: 40, 7: 41, 8: 26, 9: 27, 10: 28,
               30: 31, 31: 32, 32: 33, 33: 34, 34: 35, 35: 37}
CONCORDANCE.update({k: k - 10 for k in range(11, 30)})
CONCORDANCE.update({k: k - 16 for k in range(36, 42)})
assert sorted(CONCORDANCE.values()) == list(range(1, 42))
refs, src, _ = load_work('grc', 'maximus_of_tyre.dialexeis')
units, ref_to_unit = [], {}
idx = {}
for r in refs:
    d = CONCORDANCE[int(tail(r).split('.')[0])]
    if d in english:
        if d not in idx:
            idx[d] = len(units)
            units.append(english[d])
        ref_to_unit[r] = idx[d]
finish('grc', 'maximus_of_tyre.dialexeis', units, ref_to_unit, refs, src, out_dir=out_dir, dry=dry, mode='dissertation',
       attribution='Thomas Taylor, The Dissertations of Maximus Tyrius (London, 1804); scans at the Internet Archive',
       license='Public domain (published 1804)',
       sources=[{'translator': 'Thomas Taylor', 'year': 1804, 'place': 'London', 'publisher': 'C. Whittingham',
                 'title': 'The Dissertations of Maximus Tyrius, translated from the Greek, 2 vols.',
                 'mode': 'dissertation', 'ref_composition': ['dissertation'],
                 'url': 'https://archive.org/details/bub_gb_YcYfAAAAMAAJ', 'pd_reason': 'published 1804'}],
       notes='One unit per dissertation (41), paired through a concordance between Taylor\'s order and ours (see the script header); every Greek line of a dissertation shows the English of the whole dissertation. '
             'Taylor\'s translation is free in places and carries his own notes; the OCR leaves some of them in the text.')
