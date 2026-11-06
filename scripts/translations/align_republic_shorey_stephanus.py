#!/usr/bin/env python3
"""Plato, Republic, books 1 to 10, from Shorey's Loeb (vol. I 1930, books 1 to 5, and vol. II 1935, books
6 to 10), aligned by Stephanus page and section to the Perseus TEI (Part G, 2026-10-25).

Our references are `pl. respublica B.NNNx` (book, Stephanus page and section letter). Perseus anchors its
English by the same pair, so each of our references takes the English of its own section: the finest unit the
text has. This replaces the page-spread method of Part F (align_republic_shorey.py, length correlation 0.11),
which had to find each section on a scanned page.

The file has two sources, each with its own license, and `unit_sources` (0 = vol. I, 1 = vol. II) for every
unit, so the Reader credits the volume whose words are on the screen.

    align_republic_shorey_stephanus.py OUT_DIR [--dry]
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from g_common import load_work, tail, finish, perseus_record, stephanus_text, pair_by_key, source_dict, license_for   # noqa: E402
import proper_names as V                                                                                         # noqa: E402

STEM = 'plato.respublica'


def main():
    out_dir = sys.argv[1]
    dry = '--dry' in sys.argv
    rec = perseus_record('Plato', 'Republic', 'Shorey')
    english = stephanus_text(rec, group=lambda a: a.get('book'))
    # our tail is "B.NNNx"; Perseus keys are (book, "NNNx")
    refs, src, _ = load_work('grc', STEM)
    key = lambda r: tuple(tail(r).split('.', 1))                                    # noqa: E731
    english = {(str(b), s): t for (b, s), t in english.items()}
    units, r2u, shared = pair_by_key(refs, key, english, share_previous=False)
    # book of each unit, for unit_sources and the per-volume figures
    book_of_unit = {}
    for r, u in r2u.items():
        book_of_unit[u] = int(tail(r).split('.')[0])
    unit_sources = [0 if book_of_unit[u] <= 5 else 1 for u in range(len(units))]
    for vol, rng in ((1, range(1, 6)), (2, range(6, 11))):
        rr = [r for r in refs if int(tail(r).split('.')[0]) in rng]
        got = [r for r in rr if r in r2u]
        hit, n = V.score([(src[r], units[r2u[r]]) for r in got], 'grc', sample=800)
        print(f'vol {vol}: {len(got)}/{len(rr)} references paired, names {hit} on {n}')
    vol1 = source_dict('Paul Shorey', 1930, 'Plato, The Republic, vol. I, books 1 to 5 (Loeb Classical Library)',
                       'https://www.perseus.tufts.edu/', ref_composition=['book', 'stephanus section'],
                       scan='https://archive.org/details/republicshorey01platuoft (a printing of MCMXXXVII; first published 1930; the Perseus TEI '
                            'is the source of the text)')
    vol2 = source_dict('Paul Shorey', 1935, 'Plato, The Republic, vol. II, books 6 to 10 (Loeb Classical Library)',
                       'https://www.perseus.tufts.edu/', ref_composition=['book', 'stephanus section'],
                       scan='https://archive.org/details/republicshorey02platuoft (University of Toronto copy, a later printing, title page MCMXLII; '
                            'London William Heinemann Ltd, Cambridge, Massachusetts Harvard University Press; read in Part F)')
    rec_out = finish(
        'grc', STEM, units, r2u, refs, src, out_dir=out_dir, dry=dry, mode='exact', exact=True,
        attribution='Paul Shorey, Plato: The Republic, Loeb Classical Library, vol. I (1930) and vol. II (1935); Perseus Digital Library, '
                    'Tufts University (TEI markup, CC BY-SA 4.0)',
        license=license_for(1930) + ' / ' + license_for(1935),
        sources=[vol1, vol2],
        notes='One unit per Stephanus section. Books 1 to 5 are Shorey vol. I (1930), books 6 to 10 vol. II (1935); '
              f'{len(refs) - len(r2u)} references of ours have no section of that number in Perseus and stay unpaired.')
    if rec_out['accepted'] and not dry:
        path = os.path.join(out_dir, f'grc__{STEM}.json')
        d = json.load(open(path))
        d['unit_sources'] = unit_sources
        json.dump(d, open(path, 'w'), ensure_ascii=False)
        print('unit_sources added:', len(unit_sources), 'from vol I:', unit_sources.count(0), 'from vol II:', unit_sources.count(1))


if __name__ == '__main__':
    main()
