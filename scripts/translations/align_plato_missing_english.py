#!/usr/bin/env python3
"""Plato works of texts/grc that had no translation file: Alcibiades I and II, Lovers (Lamb, Loeb 1927) and the
Epistles (Bury, Loeb 1929), aligned by Stephanus section to the Perseus TEI (Part G, 2026-10-25).

Our references are `pl. alcibiades 1.103a`, `plat. Lovers.132a` and `pl. epistles 1.309a` (letter, Stephanus
section). Perseus anchors its English by the same Stephanus sections (and letter number for the Epistles).
Both volumes were published 1930 or earlier, so no renewal check applies. Jowett (1871, 1892) is not needed:
Perseus has a Loeb text of all four.

    align_plato_missing_english.py OUT_DIR [--dry]
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from g_common import load_work, tail, finish, perseus_record, stephanus_text, pair_by_key, source_dict, license_for   # noqa: E402

LAMB = 'Walter Rangeley Maitland Lamb'
WORKS = [  # stem, Perseus title, translator part, key is (letter, section)?
    ('plato.alcibiades_1', 'Alcibiades 1', 'Lamb', False, 'Alcibiades I', 1927),
    ('plato.alcibiades_2', 'Alcibiades 2', 'Lamb', False, 'Alcibiades II', 1927),
    ('plato.lovers', 'Lovers', 'Lamb', False, 'Lovers', 1927),
    ('plato.epistles', 'Letters', 'Bury', True, 'Epistles', 1929),
]


def _letter_key(r):
    return int(tail(r).split('.', 1)[0]), tail(r).split('.', 1)[1]


def _letter_group(r):
    return _letter_key(r)[0]


def _dialogue_key(r):
    return r.rsplit('.', 1)[1]


def main():
    out_dir = sys.argv[1]
    dry = '--dry' in sys.argv
    for stem, ptitle, trpart, letters, title, year in WORKS:
        rec = perseus_record('Plato', ptitle, trpart)
        assert rec['meta']['year'] == year and year <= 1930
        refs, src, _ = load_work('grc', stem)
        if letters:
            english = {(int(k[0]), k[1]): t for k, t in stephanus_text(rec, group=lambda a: a.get('letter')).items()}
            key, group = _letter_key, _letter_group
        else:
            english = {k[1]: t for k, t in stephanus_text(rec).items()}
            key, group = _dialogue_key, None
        units, r2u, shared = pair_by_key(refs, key, english, share_previous=False, group_of_ref=group)
        translator = rec['meta']['translator']
        translator = LAMB if 'Maitland Lamb' in translator else translator
        t = f'Plato, {title} (Loeb Classical Library, Plato in Twelve Volumes)'
        kw = dict(out_dir=out_dir, dry=dry, mode='exact', exact=True,
               attribution=f'{translator}, {t}; Perseus Digital Library, Tufts University (TEI markup, CC BY-SA 4.0)',
               license=license_for(year),
               sources=[source_dict(translator, year, t, 'https://www.perseus.tufts.edu/',
                                    ref_composition=(['letter'] if letters else []) + ['stephanus section'],
                                    scan='by date (published ' + str(year) + '), no title page read')],
               notes=f'One unit per Stephanus section, from Perseus "{ptitle}" ({rec["meta"].get("source_file", "")}). '
                     f'{len(refs) - len(r2u)} references of ours have no section of that number in Perseus and stay unpaired.')
        res = finish('grc', stem, units, r2u, refs, src, **kw)
        if not res['accepted']:
            # Held for reading, not for installing: both checks abstain or fall short (fewer than 20 names, length
            # correlation under 0.8), so the file goes to review/ with the lower name floor stated in verified_by.
            kw['out_dir'] = os.path.join(out_dir, 'review')
            res = finish('grc', stem, units, r2u, refs, src, min_names=8,
                         extra_evidence='HELD: the name check had fewer than 20 names to test and the length correlation '
                                        'is under 0.8; the pairing rests on the exact Stephanus section numbers and on reading',
                         **kw)
            print(f'  -> {stem} written to review/ only')


if __name__ == '__main__':
    main()
