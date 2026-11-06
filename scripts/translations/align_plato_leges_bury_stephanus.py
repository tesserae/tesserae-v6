#!/usr/bin/env python3
"""Plato, Laws, by Stephanus page, from Bury's Loeb (1926) in the Perseus TEI (Part H, 2026-10-25).

Our references are `pl. leges B.PPP` (book, Stephanus page, no section letter: 327 of them). The installed file
has 12 units, one per book. Perseus anchors the English by (book, lettered section 'PPPa'), with bare page
numbers for the Loeb's page breaks. The page-break rule of `stephanus_text` assigns every chunk to a lettered
section; the sections of one page are then joined, so each of our references takes the English of its own page.

    align_plato_leges_bury_stephanus.py OUT_DIR [--dry] [--installed FILE]
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from g_common import load_work, tail, finish, perseus_record, stephanus_text, pair_by_key, source_dict, license_for   # noqa: E402

STEM = 'plato.leges'
INSTALLED = '/var/www/tesseraev6_flask/data/translations/grc__plato.leges.json'


def page_text(sections):
    """{(book, 'PPPa'): English} -> {(book, 'PPP'): English}, sections of a page joined in order."""
    out = {}
    for (b, s), t in sections.items():
        k = (str(b), re.match(r'\d+', s).group(0))
        out[k] = (out.get(k, '') + ' ' + t).strip()
    return out


def main():
    out_dir = sys.argv[1]
    dry = '--dry' in sys.argv
    inst_path = sys.argv[sys.argv.index('--installed') + 1] if '--installed' in sys.argv else INSTALLED
    rec = perseus_record('Plato', 'Laws', 'Bury')
    year = rec['meta']['year']
    if year >= 1931:
        raise SystemExit(f'Laws volume dated {year}; renewal check needed')
    english = page_text(stephanus_text(rec, group=lambda a: a.get('book')))
    refs, src, _ = load_work('grc', STEM)
    key = lambda r: tuple(tail(r).split('.', 1))                                    # noqa: E731
    units, r2u, _ = pair_by_key(refs, key, english, share_previous=False)
    missing = [r for r in refs if r not in r2u]
    inst = json.load(open(inst_path))
    s0 = inst['sources'][0]
    title = 'Plato, Laws (Loeb Classical Library, Plato in Twelve Volumes)'
    sd = source_dict(s0['translator'], year, title, 'https://www.perseus.tufts.edu/', ref_composition=['book', 'stephanus page'],
                     scan=f'by date (published {year}), no title page read')
    sd['cts_urn'] = s0['cts_urn']
    sd['source_file'] = rec['meta'].get('source_file')
    res = finish('grc', STEM, units, r2u, refs, src, out_dir=out_dir, dry=dry, mode='exact', exact=True,
                 attribution=f'{s0["translator"]}, {title}; Perseus Digital Library, Tufts University (TEI markup, CC BY-SA 4.0)',
                 license=license_for(year), sources=[sd],
                 notes='One unit per Stephanus page of a book (our references carry the page, not the section letter), '
                       'the lettered sections of the page joined, with the page-break rule. The installed file had one unit per book. '
                       f'{len(missing)} references unpaired: {" ".join(missing[:10])}')
    # compare with the installed file: words of each reference's English, old (book unit) against new (page)
    old_words = sum(len(inst['units'][i].split()) for i in set(inst['ref_to_unit'].values()))
    new_words = sum(len(u.split()) for u in units)
    print(f'references paired {len(r2u)}/{len(refs)}; missing {missing}')
    print(f'English words: installed {old_words} in {len(inst["units"])} units, new {new_words} in {len(units)} units; '
          f'accepted {res["accepted"]}')


if __name__ == '__main__':
    main()
