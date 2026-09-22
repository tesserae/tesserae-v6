#!/usr/bin/env python3
"""Repair six defects in book (.part.N) files, found by comparing every
whole-file work with its book files (2026-09-21; see
scripts/corpus/check_whole_vs_parts.py, added in PR #432, and the four works
that batch fixed).

Each repair takes the whole file's own line as the correction, so nothing is
invented here: the whole file and the book files are two copies of the same
work, and in every case below the whole file's copy is demonstrably the
sound one.

  1. Pliny, Naturalis Historia, all seven book files: 77 lines whose Greek
     words are mojibake, UTF-8 bytes read as Latin-1. The whole file has
     "ὀρνιθογονίαν" where the book file has "Î¿ÌÏÎ½Î¹Î¸Î¿Î³Î¿Î½Î¹ÌÎ±Î½".
  2. Claudian, De Consulatu Stilichonis: 2 lines, same corruption
     ("probastiâ" for "probasti—").
  3. Claudian, De Raptu Proserpinae: 3 lines, same corruption.
  4. Cicero, Philippics book 7: the file's first line begins
     "cic. phil. 7.1>", with no opening "<", so the line does not parse as a
     tagged line and was never indexed from that file. Same class as the
     doubled bracket in Isocrates fixed on 2026-09-20.
  5. Orosius, Historiae: three references carry a doubled author prefix,
     "paulus_paulus_orosius." for "paulus_orosius.".
  6. Galen, De Naturalibus Facultatibus, book 1: the file starts at 1.2; the
     whole file's 1.1 is missing.

Everything else the comparison found is deliberately NOT touched here: whole
sections missing from a work's book files, and transcription differences
(curly quotes in Ovid, diaereses in the Georgics, stray section numbers in
Arrian). Those need a decision about which copy is canonical, and are
written up in research/corpus/WHOLE_VS_PARTS_2026-09-21.md.

Usage:
    python scripts/corpus/repair_part_file_defects_2026-09-21.py [--root .] [--apply]

Dry run by default: reports every line it would change, and changes nothing.
"""
import argparse
import os
import re

TAG = re.compile(r'^<+([^>]*)>')
# The signature of UTF-8 bytes decoded as Latin-1 or Windows-1252.
MOJIBAKE = re.compile(r'[ÂÃÎÏÐâ€“”˜™œž]')

# (language, work base name) whose book files hold mojibake lines to replace
# with the whole file's text for the same reference.
MOJIBAKE_WORKS = [
    ('la', 'pliny_the_elder.naturalis_historia'),
    ('la', 'claudian.de_consulatu_stilichonis'),
    ('la', 'claudian.de_raptu_proserpinae'),
    # Added 2026-09-21 evening. NC's rule is that book files are canonical,
    # and for the Georgics they are not fit to be: 42 of their 43 differences
    # from the whole file are mojibake ("Lenaeeâtuis" for "Lenaee—tuis"),
    # so the whole file repairs them rather than the other way about. The
    # 43rd is a diaeresis, aëre against aere, which this leaves alone.
    ('la', 'vergil.georgics'),
]

OROSIUS = ('la', 'paulus_orosius.historiae_adversum_paganos')
OROSIUS_BAD_PREFIX = 'paulus_paulus_orosius.'
OROSIUS_GOOD_PREFIX = 'paulus_orosius.'

CICERO_PART7 = ('la', 'cicero.philippicae.part.7.tess')
GALEN_PART1 = ('grc', 'galen.natural_faculties.part.1.tess')
GALEN_WHOLE = ('grc', 'galen.natural_faculties.tess')


def part_files(texts, lang, base):
    pat = re.compile(re.escape(base) + r'\.part\.\d+(\.[^.]+)?\.tess$')
    d = os.path.join(texts, lang)
    return sorted(f for f in os.listdir(d) if pat.match(f))


def read_lines(path):
    """Lines with their own endings kept exactly as they are on disk.

    newline='' turns off Python's universal-newline translation. Without it
    a file written back would silently lose its Windows line endings: the
    first run of this script rewrote every line of four Pliny book files and
    of Philippic 7 that way, which the PR review caught.
    """
    with open(path, encoding='utf-8-sig', newline='') as fh:
        return fh.readlines()


def split_eol(line):
    for end in ('\r\n', '\n', '\r'):
        if line.endswith(end):
            return line[:-len(end)], end
    return line, ''


def tagged(line):
    """(reference, text without its line ending, line ending)."""
    m = TAG.match(line)
    if not m:
        return (None, None, None)
    text, end = split_eol(line[m.end():])
    return (m.group(1).strip(), text, end)


def whole_text_by_ref(texts, lang, base):
    out = {}
    for line in read_lines(os.path.join(texts, lang, f'{base}.tess')):
        ref, text, _ = tagged(line)
        if ref is not None:
            out[ref] = text
    return out


def write(path, lines, apply_):
    if not apply_:
        return
    tmp = path + '.new'
    with open(tmp, 'w', encoding='utf-8', newline='') as fh:
        fh.writelines(lines)
    os.replace(tmp, path)


def repair(root, apply_):
    texts = os.path.join(root, 'texts')
    report = []
    changed = 0

    for lang, base in MOJIBAKE_WORKS:
        whole = whole_text_by_ref(texts, lang, base)
        for name in part_files(texts, lang, base):
            path = os.path.join(texts, lang, name)
            lines = read_lines(path)
            hits = 0
            for i, line in enumerate(lines):
                ref, text, end = tagged(line)
                if ref is None or ref not in whole:
                    continue
                if text != whole[ref] and MOJIBAKE.search(text):
                    # the whole file's text, this file's own line ending
                    lines[i] = line[:TAG.match(line).end()] + whole[ref] + end
                    hits += 1
            if hits:
                report.append(f'  {lang}/{name}: {hits} corrupted line(s) taken from the whole file')
                changed += hits
                write(path, lines, apply_)

    lang, base = OROSIUS
    for name in part_files(texts, lang, base):
        path = os.path.join(texts, lang, name)
        lines = read_lines(path)
        hits = 0
        for i, line in enumerate(lines):
            ref = tagged(line)[0]
            if ref and ref.startswith(OROSIUS_BAD_PREFIX):
                lines[i] = line.replace(OROSIUS_BAD_PREFIX, OROSIUS_GOOD_PREFIX, 1)
                hits += 1
        if hits:
            report.append(f'  {lang}/{name}: {hits} doubled author prefix in the reference')
            changed += hits
            write(path, lines, apply_)

    lang, name = CICERO_PART7
    path = os.path.join(texts, lang, name)
    lines = read_lines(path)
    if lines and not lines[0].startswith('<') and lines[0].startswith('cic. phil.'):
        lines[0] = '<' + lines[0]
        report.append(f'  {lang}/{name}: restored the opening "<" on line 1')
        changed += 1
        write(path, lines, apply_)

    lang, name = GALEN_PART1
    path = os.path.join(texts, lang, name)
    lines = read_lines(path)
    have = {tagged(l)[0] for l in lines}
    whole = read_lines(os.path.join(texts, *GALEN_WHOLE))
    missing = [l for l in whole if tagged(l)[0] == 'gal. nat.fac. 1.1']
    if missing and 'gal. nat.fac. 1.1' not in have:
        # the inserted line takes THIS file's line ending, not the whole
        # file's, so the book file stays internally consistent
        end = split_eol(lines[0])[1] if lines else '\n'
        body, _ = split_eol(missing[0])
        lines = [body + end] + lines
        report.append(f'  {lang}/{name}: inserted the missing first line, gal. nat.fac. 1.1')
        changed += 1
        write(path, lines, apply_)

    return changed, report


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--root', default='.', help='repository root (default: .)')
    ap.add_argument('--apply', action='store_true', help='write the changes (default: dry run)')
    args = ap.parse_args()
    changed, report = repair(args.root, args.apply)
    print(('APPLY' if args.apply else 'DRY RUN') + f' on {os.path.abspath(args.root)}')
    print('\n'.join(report) if report else '  nothing to repair')
    print(f'  {changed} line(s) {"changed" if args.apply else "would change"}')


if __name__ == '__main__':
    main()
