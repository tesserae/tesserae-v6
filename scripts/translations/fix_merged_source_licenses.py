#!/usr/bin/env python3
"""Give every source of a merged translation file its own license line.

A merged file (one with ``unit_sources``) serves units from two or more
translations. The translation endpoint shows, for the units served, each
source's own ``license`` when it has one and the file-level ``license``
otherwise. The 2026-10-24 merges (Pausanias, Josephus, Pliny the Elder,
Silius) wrote a license only on the Loeb sources, so a Shilleto unit of
Pausanias was shown with the Loeb's "published 1931 to 1963, not renewed"
text. This script writes the missing per-source lines and a file-level
sentence that covers every source, keeping a dated backup beside each file.

Usage: fix_merged_source_licenses.py --dir data/translations [--apply]
"""
import argparse
import json
import os
import shutil

PER_SOURCE = {
    'grc__pausanias.description_of_greece.json': {
        1: 'Public domain (published 1886)',
    },
    'grc__flavius_josephus.antiquitates_judaicae.json': {
        0: 'Public domain (Whiston, 1737; this printing 1856); Perseus Digital Library TEI, CC BY-SA 4.0',
    },
    'la__pliny_the_elder.naturalis_historia.json': {
        0: 'Public domain (published 1855); Perseus Digital Library TEI, CC BY-SA 4.0',
    },
    'la__silius_italicus.punica.json': {
        0: 'Public domain in the United States (published 1927)',
    },
}

FILE_LEVEL = {
    'grc__pausanias.description_of_greece.json':
        'Public domain: Shilleto (1886) for most of the work; the units from the Loeb volume of Jones and Ormerod (1933, books 6 to 8.21) are public domain in the United States, copyright not renewed (renewal check 2026-10-24).',
    'grc__flavius_josephus.antiquitates_judaicae.json':
        'Public domain: Whiston (1737, Perseus Digital Library TEI under CC BY-SA 4.0) where the Loeb volumes do not cover a passage; the Loeb units (Thackeray, Marcus, Wikgren, 1934 to 1963) are public domain in the United States, copyright not renewed (renewal check 2026-10-24).',
    'la__pliny_the_elder.naturalis_historia.json':
        'Public domain: Bostock and Riley (1855, Perseus Digital Library TEI under CC BY-SA 4.0) where the Loeb volumes do not cover a passage; the Loeb units (Rackham, Jones, Eichholz, 1938 to 1963) are public domain in the United States, copyright not renewed (renewal check 2026-10-24).',
    'la__silius_italicus.punica.json':
        'Public domain in the United States: Duff (Loeb, 1927 and 1934; the 1934 volume with no renewal of copyright, renewal check 2026-10-24). The few lines served from A. S. Kline (2018) carry his own noncommercial terms, shown with those lines.',
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dir', required=True)
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--stamp', default='20261025-srclicense')
    a = ap.parse_args()
    for name, fixes in PER_SOURCE.items():
        path = os.path.join(a.dir, name)
        with open(path, encoding='utf-8') as fh:
            d = json.load(fh)
        srcs = d.get('sources') or []
        changes = []
        for idx, lic in fixes.items():
            if idx >= len(srcs):
                raise SystemExit(f'{name}: source {idx} missing')
            if srcs[idx].get('license'):
                changes.append(f'source {idx} already has a license, left as is')
                continue
            srcs[idx]['license'] = lic
            changes.append(f'source {idx} ({srcs[idx].get("translator")}) <- {lic}')
        if d.get('license') != FILE_LEVEL[name]:
            d['license'] = FILE_LEVEL[name]
            changes.append('file-level license rewritten')
        print(name)
        for c in changes:
            print('  ', c)
        if a.apply:
            bak = f'{path}.bak-{a.stamp}'
            if not os.path.exists(bak):
                shutil.copy2(path, bak)
            tmp = path + '.new'
            with open(tmp, 'w', encoding='utf-8') as fh:
                json.dump(d, fh, ensure_ascii=False)
            os.chmod(tmp, 0o664)
            os.replace(tmp, path)
            print('   written, backup', os.path.basename(bak))


if __name__ == '__main__':
    main()
