#!/usr/bin/env python3
"""Rumi, Masnavi, Book I opening ("Song of the Reed"), from R. A. Nicholson's
translation.

Nicholson's English translation of Masnavi Books I-II (Persian text and
translation, Luzac & Co. for the Trustees of the "E. J. W. Gibb Memorial",
1925/1926) numbers each English couplet continuously through the book. Our
corpus holds only the opening eighteen Persian lines of Book I
(`texts/fa/rumi.masnavi.part.1.tess`, the reed-flute prologue, one line per
couplet), which line up one to one with Nicholson's couplets 1-18. No
offset, no section structure, and no proportional blocks are needed here:
this is the simplest case the pipeline handles, by design, since the
corpus text is itself only the opening fragment.

The source file is a small plain-text list, one couplet per line, each
line starting with "N. " (the number printed in Nicholson's own text) and
giving the couplet's English in full, e.g.:

    1. Listen to this reed how it complains: it is telling a tale of separations.
    2. Saying, "Ever since I was parted from the reed-bed, ...

The numbers are checked to run 1..N with no gaps before anything is
written: a missing or duplicated number means the source list was copied
wrong, and the script refuses rather than guess.

Usage:
    python scripts/translations/align_rumi_masnavi_nicholson.py \
        --src /path/nicholson_reed_1-18.txt \
        --tess texts/fa/rumi.masnavi.part.1.tess \
        --out-dir data/translations
"""
import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from write_aligned import write_aligned, tess_refs  # noqa: E402

LINE = re.compile(r'^(\d+)\.\s+(.*\S)\s*$')


def read_couplets(path):
    """[(number, english_text), ...] in file order."""
    out = []
    with open(path, encoding='utf-8') as f:
        for raw in f:
            line = raw.rstrip('\n')
            if not line.strip():
                continue
            m = LINE.match(line)
            if not m:
                raise ValueError(f'unrecognized source line: {line!r}')
            out.append((int(m.group(1)), m.group(2)))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--src', required=True)
    ap.add_argument('--tess', required=True)
    ap.add_argument('--out-dir', required=True)
    a = ap.parse_args()

    couplets = read_couplets(a.src)
    numbers = [n for n, _ in couplets]
    expected = list(range(1, len(couplets) + 1))
    if numbers != expected:
        sys.exit(f'source numbering is not a clean 1..{len(couplets)} run: got {numbers}')
    print(f'{len(couplets)} numbered English couplets read from {a.src}', flush=True)

    refs = tess_refs(a.tess)
    print(f'{len(refs)} refs in {a.tess}', flush=True)
    if len(refs) != len(couplets):
        sys.exit(f'refusing to write: {len(refs)} tess refs but {len(couplets)} English '
                  f'couplets (one-to-one alignment needs equal counts here)')

    units = [text for _, text in couplets]
    ref_to_unit = {ref: i for i, ref in enumerate(refs)}

    write_aligned(
        a.out_dir, 'fa', os.path.basename(a.tess)[:-5], units, ref_to_unit,
        attribution=('Reynold A. Nicholson, The Mathnawi of Jalalu\'ddin Rumi, '
                     'Book I (Luzac & Co. for the Trustees of the "E. J. W. Gibb '
                     'Memorial", 1925/1926)'),
        license=('Public domain (English translation published 1925/1926, more '
                  'than 95 years before this file was built; under the US rule in '
                  'force at the time of acquisition, anything published in 1931 or '
                  'earlier is public domain). Text of couplets 1-18 checked against '
                  'the transcription at dar-al-masnavi.org/reedsong.html, itself '
                  'quoting Nicholson\'s 1926 Cambridge University Press translation; '
                  'the scanned volume is at archive.org/details/mathnawinicholsonvol2 '
                  '(Vol. 2, 1925, "the translation of the first & second books").'),
        sources=[{'translator': 'Reynold A. Nicholson', 'year': 1926,
                  'title': "The Mathnawi of Jalalu'ddin Rumi, Book I "
                           '(the "Song of the Reed")',
                  'url': 'https://archive.org/details/mathnawinicholsonvol2'}],
        confidence='exact', approximate=False, tess_refs=refs,
        verified_by=('one-to-one couplet correspondence: our corpus holds only the '
                     'eighteen-line reed-flute prologue, and Nicholson numbers his '
                     'English couplets continuously from 1, so ref k maps to '
                     'couplet k with no offset or proportional block.'),
        notes=('Nicholson revised several of these lines in 1930, 1937 and 1940 after '
               'consulting the earliest known manuscript (lines 1, 2, 8, 17, 22, 23, '
               'and the placement of line 35 relative to the next heading, per '
               'dar-al-masnavi.org/reedsong.html); this file carries his original '
               '1925/1926 wording throughout for one consistent citation rather than '
               'mixing two printings.'),
    )
    print(f'[done] {len(units)} units, {len(ref_to_unit)} refs, confidence exact', flush=True)


if __name__ == '__main__':
    main()
