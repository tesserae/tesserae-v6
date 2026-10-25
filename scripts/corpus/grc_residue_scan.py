#!/usr/bin/env python3
"""Scan Greek .tess files for apparatus and heading residue.

    grc_residue_scan.py TESS_DIR --files FILELIST [--out REPORT.tsv] [--summary SUMMARY.tsv]

Five kinds of finding, one row per line of text per kind:
  latin   the text holds a Latin-alphabet word of three or more letters
  lead    the text begins with a run of digits or a Roman numeral ("VIII, 19.", "12.")
  digit   an ASCII or superscript digit anywhere in the text (a page, section or footnote number left in the line)
  caps    a token of four or more capital Greek letters inside a line (a running page header)
  siglum  a siglum or apparatus abbreviation stands as a token (Phot., Par., cod., corr., om., add., or a lone A/B/C)
The summary gives the count per work and kind. Greek letters only are never reported.
"""
import argparse
import collections
import os
import re

LATIN_WORD = re.compile(r'[A-Za-z]{3,}')
LEAD = re.compile(r'^(?:\d+[a-z]?[.,]?|[IVXLC]+[.,]\s*\d+|[IVXLC]+\.)(?:\s|$)')
DIGIT = re.compile(r'[\d⁰-⁹₀-₉]')
CAPS = re.compile(r'(?<![Ͱ-Ͽἀ-῿])[Α-ΩἈ-Ὧ]{4,}(?![Ͱ-Ͽἀ-῿])')
SIGLUM = re.compile(r'(?<![A-Za-z])(?:Phot|Par|cod|corr|om|add|Vgl|vgl|vor|nach|cf|Cf|fol|ed|Migne|Bidez|Hist|Suid)\.|(?<![\w])(?:[A-C]|[A-C][0-9]?)(?![\w])(?=[\s,.;]|$)(?<![Ͱ-Ͽἀ-῿])')


def split_line(line):
    ref, _, text = line.rstrip('\n').partition('\t')
    return ref.strip('<>'), text


def work_of(fn):
    return fn[:-5].split('.part.')[0]


def scan_text(text):
    kinds = []
    if LATIN_WORD.search(text):
        kinds.append('latin')
    if LEAD.match(text):
        kinds.append('lead')
    if SIGLUM.search(text):
        kinds.append('siglum')
    if DIGIT.search(text):
        kinds.append('digit')
    if CAPS.search(text):
        kinds.append('caps')
    return kinds


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('dir')
    ap.add_argument('--files', help='file with one .tess name (or path) per line; default every .tess in DIR')
    ap.add_argument('--out')
    ap.add_argument('--summary')
    a = ap.parse_args()
    if a.files:
        names = sorted(os.path.basename(line.strip()) for line in open(a.files) if line.strip())
    else:
        names = sorted(f for f in os.listdir(a.dir) if f.endswith('.tess'))
    rows, count, lines_in = [], collections.defaultdict(collections.Counter), collections.Counter()
    seen_lines = collections.defaultdict(set)
    for fn in names:
        w = work_of(fn)
        for line in open(os.path.join(a.dir, fn), encoding='utf-8'):
            if not line.startswith('<'):
                continue
            ref, text = split_line(line)
            lines_in[w] += 1
            kinds = scan_text(text)
            for k in kinds:
                count[w][k] += 1
                rows.append((w, fn, ref, k, text[:200]))
            if kinds:
                seen_lines[w].add((fn, ref))
    works = sorted(lines_in)
    out = ['work\tlines\tflagged lines\tlatin\tlead\tsiglum\tdigit\tcaps']
    for w in works:
        c = count[w]
        out.append(f"{w}\t{lines_in[w]}\t{len(seen_lines[w])}\t{c['latin']}\t{c['lead']}\t{c['siglum']}\t{c['digit']}\t{c['caps']}")
    flagged = sum(len(v) for v in seen_lines.values())
    out.append(f"TOTAL\t{sum(lines_in.values())}\t{flagged}\t{sum(c['latin'] for c in count.values())}\t"
               f"{sum(c['lead'] for c in count.values())}\t{sum(c['siglum'] for c in count.values())}\t"
               f"{sum(c['digit'] for c in count.values())}\t{sum(c['caps'] for c in count.values())}")
    text = '\n'.join(out)
    print(text)
    if a.summary:
        open(a.summary, 'w').write(text + '\n')
    if a.out:
        with open(a.out, 'w', encoding='utf-8') as fh:
            fh.write('work\tfile\tref\tkind\ttext\n')
            for r in rows:
                fh.write('\t'.join(r) + '\n')


if __name__ == '__main__':
    main()
