#!/usr/bin/env python3
"""Demosthenes, On the Crown (18), On the Embassy (19) and Against Leptines (20):
C. A. Vince 1926 (the first two) and J. H. Vince 1930 (Leptines), Loeb Classical
Library, aligned to texts/grc/demosthenes.on_the_crown, .on_the_false_embassy and
.against_leptines by exact section number.

Source: Perseus's TEI of the Loeb translations, already extracted on this machine
(extracted6.json). align_perseus.py gave On the Embassy a single unit for all 338
sections because Perseus numbers them in one run, so these three are redone one
unit per section. Where Perseus has no chunk for a section (the English runs two
Greek sections together) the section shares the English of the one before it.

The other speeches Vince and Murray translated for the Loeb after 1930 (1935, 1936,
1939) are in copyright and are not used.

    align_demosthenes_vince.py OUT_DIR [--dry]
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from chapter_common import load_work, tail, finish, clean, perseus_find   # noqa: E402

out_dir = sys.argv[1]
dry = '--dry' in sys.argv
WORKS = [('demosthenes.on_the_crown', 'On the Crown', 'Charles Anthony Vince', 1926, 18),
         ('demosthenes.on_the_false_embassy', 'On the Embassy', 'Charles Anthony Vince', 1926, 19),
         ('demosthenes.against_leptines', 'Against Leptines', 'James Herbert Vince', 1930, 20)]
for stem, title, translator, year, num in WORKS:
    recs = perseus_find('Demosthenes', translator.split()[-1], title_eq=title)
    recs = [r for r in recs if translator in r['meta']['translator']]
    assert len(recs) == 1 and recs[0]['meta']['year'] <= 1930, (title, len(recs))
    english = {}
    for ch in recs[0]['chunks']:
        s = ch['anchors'].get('section')
        if s and s.isdigit():
            english[int(s)] = (english.get(int(s), '') + ' ' + ch['text']).strip()
    refs, src, _ = load_work('grc', stem)
    units, ref_to_unit, last, shared = [], {}, None, 0
    for r in refs:
        n, s = (int(x) for x in tail(r).split('.'))
        t = english.get(s)
        if t:
            last = len(units)
            units.append(clean(t))
            ref_to_unit[r] = last
        elif last is not None:
            ref_to_unit[r] = last
            shared += 1
    finish('grc', stem, units, ref_to_unit, refs, src, out_dir=out_dir, dry=dry, mode='exact', exact=True,
           attribution=f'{translator}, Demosthenes, Loeb Classical Library ({year}); Perseus Digital Library, Tufts University (TEI markup, CC BY-SA 4.0)',
           license='CC BY-SA 4.0 (Perseus Digital Library TEI); underlying translation is US public domain (published before 1931)',
           sources=[{'translator': translator, 'year': year, 'place': 'London and Cambridge, MA',
                     'publisher': 'William Heinemann / Harvard University Press',
                     'title': f'Demosthenes, {title} (Loeb Classical Library)',
                     'mode': 'exact', 'ref_composition': ['section'],
                     'url': 'https://www.perseus.tufts.edu/',
                     'pd_reason': f'published {year}, US public domain'}],
           notes=f'One unit per section. {shared} sections whose number Perseus does not mark share the English of the section before.')
