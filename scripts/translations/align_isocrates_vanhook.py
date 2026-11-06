#!/usr/bin/env python3
"""Isocrates, speeches 9, 10, 11, 14 and 16 to 21 and the nine letters, from Van Hook's Loeb vol. III (1945),
aligned by section to the Perseus TEI (Part G, 2026-10-25).

Our references are `isoc. speeches N.S` (speech N, section S) and `isoc. letters N.S`. Speeches 1 to 8, 12, 13
and 15 are Norlin's (Loeb vols. I and II, 1928 and 1929) and are already installed in grc__isocrates.speeches.json.
This script writes a standalone file for the Van Hook speeches (speeches.vanhook) and one for the letters, and
`--merge PRODUCTION_FILE` then lays the Van Hook speeches over the installed file with
merge_translation_files.py so every installed unit stays and each source carries its own license.

    align_isocrates_vanhook.py OUT_DIR [--dry]
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from g_common import (load_work, tail, finish, perseus_record, section_text, pair_by_key, source_dict,   # noqa: E402
                      license_for, VOLUMES)

TR = 'Larue Van Hook'
SPEECHES = {9: 'Evagoras', 10: 'Helen', 11: 'Busiris', 14: 'Plataicus', 16: 'Concerning the Team of Horses',
            17: 'Trapeziticus', 18: 'Against Callimachus', 19: 'Aegineticus', 20: 'Against Lochites', 21: 'Against Euthynus'}
LETTERS = {1: 'Letter 1. To Dionysius', 2: 'Letter 2. To Philip, I', 3: 'Letter 3. To Philip, II', 4: 'Letter 4. To Antipater',
           5: 'Letter 5. To Alexander', 6: 'Letter 6. To the Children of Jason', 7: 'Letter 7. To Timotheus',
           8: 'Letter 8. To the Rulers of the Mytilenaeans', 9: 'Letter 9. To Archidamus'}


def build(stem, titles, out_dir, dry, name):
    v = VOLUMES['iso3']
    refs, src, _ = load_work('grc', stem)
    english = {}
    for n, title in titles.items():
        rec = perseus_record('Isocrates', title, TR)
        assert rec['meta']['year'] == v['year']
        for s, t in section_text(rec).items():
            english[(n, s)] = t
    mine = [r for r in refs if int(tail(r).split('.')[0]) in titles]
    key = lambda r: tuple(int(x) for x in tail(r).split('.'))                   # noqa: E731
    units, r2u, shared = pair_by_key(mine, key, english, group_of_ref=lambda r: key(r)[0])
    # coverage is measured against the whole work only for the speeches this script covers
    rec_out = finish('grc', stem, units, r2u, mine, {r: src[r] for r in mine}, out_dir=out_dir, dry=dry, mode='exact', exact=True,
                     attribution=f'{TR}, {v["title"]}; Perseus Digital Library, Tufts University (TEI markup, CC BY-SA 4.0)',
                     license=license_for(v['year']),
                     sources=[source_dict(TR, v['year'], v['title'], 'https://www.perseus.tufts.edu/',
                                          ref_composition=['speech', 'section'], scan=v['scan'])],
                     notes=f'{name}. One unit per section. {shared} sections whose number Perseus does not mark share the '
                           'English of the section before.')
    if rec_out['accepted'] and not dry:
        # finish() names the file after the stem and counts coverage against `mine`; record the whole-work figure too
        p = os.path.join(out_dir, f'grc__{stem}.json')
        d = json.load(open(p))
        d['n_tess_refs'] = len(refs)
        d['coverage'] = round(len(r2u) / len(refs), 4)
        json.dump(d, open(p, 'w'), ensure_ascii=False)
    return rec_out


def main():
    out_dir = sys.argv[1]
    dry = '--dry' in sys.argv
    os.makedirs(out_dir, exist_ok=True)
    a = build('isocrates.speeches', SPEECHES, os.path.join(out_dir, 'vanhook_only'), dry, 'Speeches 9, 10, 11, 14, 16 to 21 (Van Hook)')
    b = build('isocrates.letters', LETTERS, out_dir, dry, 'Letters 1 to 9 (Van Hook)')
    print('accepted:', a['accepted'], b['accepted'])


if __name__ == '__main__':
    main()
