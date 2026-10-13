#!/usr/bin/env python3
"""Read-only duplicate scan: group whole-file texts by their opening words.

Method of the 2026-09-10 duplicate-text memo. For each language folder, every
.tess file without '.part.' in its name is read for its first --words
normalized words (diacritics stripped, lower case, punctuation removed, the
line tags ignored); files with the same opening are grouped. A group is a
candidate duplicate: two editions of one work under two names, or a shared
prologue. The scan changes nothing.

Usage: scan_opening_lines.py [--texts texts] [--words 40] [--min-words 12]
"""
import argparse
import glob
import os
import re
import unicodedata
from collections import defaultdict


def norm(text):
    text = unicodedata.normalize('NFD', text.lower())
    text = ''.join(c for c in text if not unicodedata.combining(c))
    return re.sub(r'[^\w\s]|_', ' ', text).split()


def opening(path, nwords):
    words = []
    with open(path, encoding='utf-8', errors='replace') as fh:
        for raw in fh:
            raw = raw.strip()
            if not raw.startswith('<'):
                continue
            words += norm(raw[raw.find('>') + 1:])
            if len(words) >= nwords:
                break
    return tuple(words[:nwords]), len(words)


def lines_of(path):
    with open(path, encoding='utf-8', errors='replace') as fh:
        return sum(1 for r in fh if r.startswith('<'))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--texts', default='texts')
    ap.add_argument('--words', type=int, default=40)
    ap.add_argument('--min-words', type=int, default=12,
                    help='ignore files whose text is shorter than this')
    a = ap.parse_args()
    total = groups = 0
    for lang_dir in sorted(glob.glob(os.path.join(a.texts, '*'))):
        found = defaultdict(list)
        for path in glob.glob(os.path.join(lang_dir, '*.tess')):
            if '.part.' in os.path.basename(path):
                continue
            key, n = opening(path, a.words)
            if n >= a.min_words:
                found[key].append(path)
                total += 1
        for key, paths in sorted(found.items(), key=lambda kv: kv[1][0]):
            if len(paths) > 1:
                groups += 1
                print(f'[{os.path.basename(lang_dir)}] {" ".join(key[:14])} ...')
                for p in sorted(paths):
                    print(f'    {os.path.basename(p)}  ({lines_of(p)} lines)')
    print(f'\n{total} whole-file texts scanned, {groups} opening groups with more than one file')


if __name__ == '__main__':
    main()
