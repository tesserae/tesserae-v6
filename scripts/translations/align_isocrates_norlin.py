#!/usr/bin/env python3
"""Isocrates, the speeches Norlin translated (Loeb, vols. I and II, 1928 and
1929), aligned to texts/grc/isocrates.speeches by exact section number.

Source: Perseus's TEI of the Loeb translation, already extracted on this machine
(extracted6.json, the same file align_perseus.py reads). The installed pipeline
never reached this work because ours is one file for all twenty-one speeches
and the identity step works one file to one Perseus work.

Our references are `isoc. speeches N.M` with N the speech number and M the
section. Norlin's speeches: 1 To Demonicus, 2 To Nicocles, 3 Nicocles,
4 Panegyricus, 5 To Philip, 6 Archidamus, 7 Areopagiticus, 8 On the Peace,
12 Panathenaicus, 13 Against the Sophists, 15 Antidosis. The other ten speeches
(9, 10, 11, 14, 16 to 21) are Van Hook's Loeb of 1945, still in copyright, and
are left unpaired; the nine letters are Van Hook's too and not in our text.
Each section has its own unit. Where Perseus has no chunk for a section
(Antidosis 322 and 323 are one chunk apart) the section shares the English of
the section before it.

    align_isocrates_norlin.py OUT_DIR [--dry]
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from chapter_common import load_work, tail, finish, clean, perseus_find   # noqa: E402

out_dir = sys.argv[1]
dry = '--dry' in sys.argv
NORLIN = {'To Demonicus': 1, 'To Nicocles': 2, 'Nicocles or the Cyprians': 3,
          'Panegyricus': 4, 'To Philip': 5, 'Archidamus': 6, 'Areopagiticus': 7,
          'On the Peace': 8, 'Panathenaicus': 12, 'Against the Sophists': 13,
          'Antidosis': 15}
english = {}
for title, n in NORLIN.items():
    recs = perseus_find('Isocrates', 'Norlin', title_eq=title)
    assert len(recs) == 1 and recs[0]['meta']['year'] <= 1930, (title, len(recs))
    for ch in recs[0]['chunks']:
        sec = ch['anchors'].get('section')
        if sec and sec.isdigit():
            english[(n, int(sec))] = (english.get((n, int(sec)), '') + ' ' + ch['text']).strip()

refs, src, _ = load_work('grc', 'isocrates.speeches')
units, ref_to_unit, last = [], {}, {}
shared = 0
for r in refs:
    n, s = (int(x) for x in tail(r).split('.'))
    if n not in NORLIN.values():
        continue
    t = english.get((n, s))
    if t:
        last[n] = len(units)
        units.append(clean(t))
        ref_to_unit[r] = last[n]
    elif n in last:
        ref_to_unit[r] = last[n]
        shared += 1
print(f'sections sharing the previous English: {shared}')
finish('grc', 'isocrates.speeches', units, ref_to_unit, refs, src, out_dir=out_dir, dry=dry, mode='exact', exact=True,
       attribution='George Norlin, Isocrates, Loeb Classical Library, vols. I and II; Perseus Digital Library, Tufts University (TEI markup, CC BY-SA 4.0)',
       license='CC BY-SA 4.0 (Perseus Digital Library TEI); underlying translation is US public domain (published before 1931)',
       sources=[{'translator': 'George Norlin', 'year': 1929, 'place': 'London and New York',
                 'publisher': 'William Heinemann / G. P. Putnam\'s Sons',
                 'title': 'Isocrates, vols. I (1928) and II (1929), Loeb Classical Library',
                 'mode': 'exact', 'ref_composition': ['speech', 'section'],
                 'url': 'https://www.perseus.tufts.edu/hopper/collection?collection=Perseus:collection:Greco-Roman',
                 'pd_reason': 'published 1928 and 1929, US public domain'}],
       notes='Speeches 1 to 8, 12, 13 and 15 (Norlin). Speeches 9, 10, 11, 14 and 16 to 21 are Van Hook 1945 '
             '(in copyright) and are unpaired. '
             f'{shared} sections whose number Perseus does not mark share the English of the section before.')
