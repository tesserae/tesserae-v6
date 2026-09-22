#!/usr/bin/env python3
"""Rebuild a work's whole file from its book files, which are canonical.

NC's decision, 2026-09-21: "Make the book files for the canonical copy."
Where a work exists twice, as `X.tess` and as `X.part.*.tess`, and the two
copies disagree, the book files are the text and the whole file is rebuilt
from them.

THE DECISION IS NOT AUTOMATIC. Read both copies before running this. On the
Georgics the book files hold mojibake where the whole file is sound
("Lenaeeâtuis" for "Lenaee—tuis", 42 lines), so regenerating there would
have written corruption into the canonical copy; those book files are
repaired from the whole file instead, by
scripts/corpus/repair_part_file_defects_2026-09-21.py. This script is for
the other direction, where the book files are demonstrably the better text:

    arnobius.adversus_nationes     whole file has an OCR digit, "cur erg6"
    prudentius.peristephanon       whole file has a running header glued into
                                   a line, "uellere.'<prud. peristeph."
    apuleius.metamorphoses         two lines split differently
    ovid.metamorphoses             curly quotation marks
    paulus_orosius.historiae       em dashes and spacing before punctuation

Part order is the order the book files sort in by their part label, numbers
numerically and names after them, which is the order they are read in.

Line endings are preserved exactly: the files are read and written with
newline='' so a book file's own endings survive into the whole file.

Usage:
    python scripts/corpus/regenerate_whole_from_parts.py --root . la/ovid.metamorphoses
    python scripts/corpus/regenerate_whole_from_parts.py --root . la/ovid.metamorphoses --apply
"""
import argparse
import os
import re

PART_RE = re.compile(r'^(?P<base>.+)\.part\.(?P<label>[0-9]+[a-z]?|[a-z_]+)(?:\.(?P<rest>[^.]+))*\.tess$')


def sort_key(label):
    """Numbers first and numerically, then named parts alphabetically."""
    m = re.match(r'^(\d+)([a-z]?)$', label)
    if m:
        return (0, int(m.group(1)), m.group(2))
    return (1, 0, label)


def book_files(texts_root, lang, base):
    out = []
    for name in os.listdir(os.path.join(texts_root, lang)):
        m = PART_RE.match(name)
        if m and m.group('base') == base:
            out.append((sort_key(m.group('label')), name))
    return [name for _, name in sorted(out)]


def read(path):
    with open(path, encoding='utf-8', newline='') as fh:
        return fh.read()


def regenerate(root, work, apply_):
    texts_root = os.path.join(root, 'texts')
    lang, base = work.split('/', 1)
    base = base[:-5] if base.endswith('.tess') else base
    whole_path = os.path.join(texts_root, lang, f'{base}.tess')
    parts = book_files(texts_root, lang, base)
    if not parts:
        return f'{work}: no book files, nothing to do', 0

    before = read(whole_path)
    pieces = []
    for name in parts:
        text = read(os.path.join(texts_root, lang, name))
        if text and not text.endswith(('\n', '\r')):
            text += '\n'
        pieces.append(text)
    after = ''.join(pieces)

    def count(s):
        return len([l for l in s.splitlines() if l.strip()])

    report = (f'{work}: {len(parts)} book files, '
              f'{count(before)} lines -> {count(after)}, '
              f'{"unchanged" if before == after else "rewritten"}')
    if apply_ and before != after:
        tmp = whole_path + '.new'
        with open(tmp, 'w', encoding='utf-8', newline='') as fh:
            fh.write(after)
        os.replace(tmp, whole_path)
    return report, (0 if before == after else 1)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('works', nargs='+', help='e.g. la/ovid.metamorphoses')
    ap.add_argument('--root', default='.')
    ap.add_argument('--apply', action='store_true', help='write (default: dry run)')
    args = ap.parse_args()
    print('APPLY' if args.apply else 'DRY RUN')
    changed = 0
    for work in args.works:
        report, n = regenerate(args.root, work, args.apply)
        print('  ' + report)
        changed += n
    print(f'  {changed} whole file(s) {"rewritten" if args.apply else "would be rewritten"}')


if __name__ == '__main__':
    main()
