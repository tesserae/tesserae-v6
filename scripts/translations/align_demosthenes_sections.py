#!/usr/bin/env python3
"""Demosthenes by section (Part G, 2026-10-25): every speech of our corpus except On the Crown, On the
Embassy and Against Leptines (section-level since Part C), aligned section by section to the Perseus TEI
of the Loeb translations: J. H. Vince (1930, 1935), A. T. Murray (1936, 1939), N. W. and N. J. DeWitt (1949).

Our references are `dem. N.S` (speech N, section S), `dem. ex. D.S` (Exordia) and `dem. L. N.S` (Letters);
Perseus anchors its English by the same numbers. A speech whose Perseus section numbers do not reach our
sections shares the English of the section before (counted in the notes). A speech that fails both checks
of chapter_common.finish() is NOT written and is listed; the held Kennedy whole-speech file of Part C stands
for it (copied by `--fallback-dir`).

    align_demosthenes_sections.py OUT_DIR [--only stem,stem] [--dry] [--fallback-dir DIR_OF_KENNEDY_FILES]
"""
import json
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from g_common import (load_work, tail, finish, perseus_record, section_text, pair_by_key, source_dict,   # noqa: E402
                      license_for, VOLUMES)

# our oration number -> (Perseus title, translator part, volume key)
P = 'James Herbert Vince'
M = 'Augustus Taber Murray'
ORATIONS = {
    1: ('First Olynthiac', P, 'dem1'), 2: ('Second Olynthiac', P, 'dem1'), 3: ('Third Olynthiac', P, 'dem1'),
    4: ('First Philippic', P, 'dem1'), 5: ('On the Peace', P, 'dem1'), 6: ('Second Philippic', P, 'dem1'),
    7: ('On Halonnesus', P, 'dem1'), 8: ('On the Chersonese', P, 'dem1'), 9: ('Third Philippic', P, 'dem1'),
    10: ('Fourth Philippic', P, 'dem1'), 11: ('Answer to Philip’s Letter', P, 'dem1'), 12: ('Philip’s Letter', P, 'dem1'),
    13: ('On Organization', P, 'dem1'), 14: ('On the Navy-Boards', P, 'dem1'), 15: ('For the Liberty of the Rhodians', P, 'dem1'),
    16: ('For the People of Megalopolis', P, 'dem1'), 17: ('On the Treaty with Alexander', P, 'dem1'),
    21: ('Against Meidias', P, 'dem3'), 22: ('Against Androtion', P, 'dem3'), 23: ('Against Aristocrates', P, 'dem3'),
    24: ('Against Timocrates', P, 'dem3'), 25: ('Against Aristogeiton I', P, 'dem3'), 26: ('Against Aristogeiton II', P, 'dem3'),
    27: ('Against Aphobus I', M, 'dem4'), 28: ('Against Aphobus II', M, 'dem4'), 29: ('Against Aphobus III', M, 'dem4'),
    30: ('Against Onetor I', M, 'dem4'), 31: ('Against Onetor II', M, 'dem4'), 32: ('Against Zenothemis', M, 'dem4'),
    33: ('Against Apaturius', M, 'dem4'), 34: ('Against Phormio', M, 'dem4'), 35: ('Against Lacritus', M, 'dem4'),
    36: ('For Phormio', M, 'dem4'), 37: ('Against Pantaenetus', M, 'dem4'), 38: ('Against Nausimachus and Xenopeithes', M, 'dem4'),
    39: ('Against Boeotus I', M, 'dem4'), 40: ('Against Boeotus II', M, 'dem4'),
    41: ('Against Spudias', M, 'dem5'), 42: ('Against Phaenippus', M, 'dem5'), 43: ('Against Macartatus', M, 'dem5'),
    44: ('Against Leochares', M, 'dem5'), 45: ('Apollodorus Against Stephanus I', M, 'dem5'),
    46: ('Apollodorus Against Stephanus II', M, 'dem5'), 47: ('Against Evergus And Mnesibulus', M, 'dem5'),
    48: ('Against Olympiodorus', M, 'dem5'), 49: ('Apollodorus Against Timotheus', M, 'dem5'),
    50: ('Apollodorus Against Polycles', M, 'dem6'), 51: ('On The Trierarchic Crown', M, 'dem6'),
    52: ('Apollodorus Against Callipus', M, 'dem6'), 53: ('Apollodorus Against Nicostratus', M, 'dem6'),
    54: ('Against Conon', M, 'dem6'), 55: ('Against Callicles', M, 'dem6'), 56: ('Against Dionysodorus', M, 'dem6'),
    57: ('Against Eubulides', M, 'dem6'), 58: ('Against Theocrines', M, 'dem6'), 59: ('Apollodorus Against Neaera', M, 'dem6'),
    60: ('The Funeral Speech', 'Norman W. DeWitt', 'dem7'), 61: ('The Erotic Essay', 'Norman W. DeWitt', 'dem7'),
}
DONE_AT_SECTION_LEVEL = {'demosthenes.on_the_crown', 'demosthenes.on_the_false_embassy', 'demosthenes.against_leptines'}
SPECIAL = {'demosthenes.exordia': ('Exordia', 'Norman W. DeWitt', 'dem7', ('div', 'section')),
           'demosthenes.letters': ('Letters', 'Norman W. DeWitt', 'dem7', ('letter', 'section'))}
TRANSLATOR_FULL = {'dem7': 'Norman W. DeWitt and Norman J. DeWitt'}


def _parts(r):
    return tuple(int(x) for x in tail(r).split('.'))


def _first(r):
    return _parts(r)[0]


def _section(r):
    return int(tail(r).split('.')[1])


def speech_number(refs):
    return int(tail(refs[0]).split('.')[0])


def main():
    args = sys.argv[1:]
    out_dir = args[0]
    dry = '--dry' in args
    only = set(args[args.index('--only') + 1].split(',')) if '--only' in args else None
    fallback = args[args.index('--fallback-dir') + 1] if '--fallback-dir' in args else None
    stems = sorted(f[:-5] for f in os.listdir(os.path.join(os.environ.get('TESSERAE_TEXTS', '/var/www/tesseraev6_flask/texts'), 'grc'))
                   if f.startswith('demosthenes.') and f.endswith('.tess') and '.part.' not in f)
    results, refused = [], []
    for stem in stems:
        if stem in DONE_AT_SECTION_LEVEL or (only and stem not in only):
            continue
        refs, src, _ = load_work('grc', stem)
        if stem in SPECIAL:
            title, tr, vol, keys = SPECIAL[stem]
            rec = perseus_record('Demosthenes', title, tr)
            english = section_text(rec, keys)
            key_of_ref, group = _parts, _first
            comp = ['division' if keys[0] == 'div' else 'letter', 'section']
        else:
            n = speech_number(refs)
            title, tr, vol, = ORATIONS[n]
            rec = perseus_record('Demosthenes', title, tr)
            english = section_text(rec)
            key_of_ref, group, comp = _section, None, ['section']
        v = VOLUMES[vol]
        assert rec['meta']['year'] == v['year'], (stem, rec['meta']['year'], v['year'])
        units, r2u, shared = pair_by_key(refs, key_of_ref, english, group_of_ref=group)
        translator = TRANSLATOR_FULL.get(vol, rec['meta']['translator'])
        rec_out = finish(
            'grc', stem, units, r2u, refs, src, out_dir=out_dir, dry=dry, mode='exact', exact=True,
            attribution=f'{translator}, {v["title"]}; Perseus Digital Library, Tufts University (TEI markup, CC BY-SA 4.0)',
            license=license_for(v['year']),
            sources=[source_dict(translator, v['year'], v['title'], 'https://www.perseus.tufts.edu/', ref_composition=comp,
                                 scan=v['scan'])],
            notes=f'One unit per section, from Perseus "{title}" ({rec["meta"].get("source_file", "")}). '
                  f'{shared} sections whose number Perseus does not mark share the English of the section before.')
        rec_out['perseus_title'] = title
        rec_out['shared'] = shared
        results.append(rec_out)
        if not rec_out['accepted']:
            refused.append(stem)
            if fallback and not dry:
                k = os.path.join(fallback, f'grc__{stem}.json')
                if os.path.exists(k):
                    shutil.copy(k, os.path.join(out_dir, os.path.basename(k)))
                    print(f'  -> {stem}: Kennedy whole-speech file copied from {fallback}')
    print('refused:', refused)
    if not dry:
        with open(os.path.join(out_dir, 'demosthenes_run.json'), 'w') as f:
            json.dump(results, f, indent=1)


if __name__ == '__main__':
    main()
