#!/usr/bin/env python3
"""Part 1 scan for issue #580: combining marks stored before the Greek
capital letter they belong to.

Scans texts/grc/*.tess for a run of combining marks (U+0300-U+036F) that
sits between a space, a tab, or the start of a line, and a Greek capital
letter (U+0391-U+03A9, U+0386, U+0388-U+038F).

Only scans the text AFTER the line tag (the part after the first tab, or
after the first '>' plus following space/tab if no literal tab is present),
so a tag's own content is never touched or counted.

Usage:
    scan_greek_capital_marks.py [--dir texts/grc] [--top N]

Prints: total files scanned, files with matches, total occurrences, and the
top N most-affected files.
"""
import argparse
import glob
import os
import re
import sys

COMBINING_RUN = r'[̀-ͯ]+'
GREEK_CAPITAL = r'[Α-ΩΆΈ-Ώ]'

# Matches at line-start, after a space, or after a tab.
PATTERN = re.compile(
    r'(?:(?<=[ \t])|^)(' + COMBINING_RUN + r')(' + GREEK_CAPITAL + r')',
    re.MULTILINE,
)

TAG_RE = re.compile(r'^(<[^>]*>)([ \t]*)')


def split_tag(line):
    """Return (tag_and_sep, rest) so the scan never looks inside the tag."""
    m = TAG_RE.match(line)
    if m:
        return m.group(0), line[m.end():]
    return '', line


def scan_file(path):
    count = 0
    with open(path, encoding='utf-8', errors='surrogateescape') as f:
        for line in f:
            line = line.rstrip('\r\n')
            tag, rest = split_tag(line)
            count += len(PATTERN.findall(rest))
    return count


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dir', default='texts/grc')
    ap.add_argument('--top', type=int, default=10)
    args = ap.parse_args()

    files = sorted(glob.glob(os.path.join(args.dir, '*.tess')))
    per_file = {}
    for path in files:
        c = scan_file(path)
        if c:
            per_file[path] = c

    total_files_scanned = len(files)
    files_with_matches = len(per_file)
    total_occurrences = sum(per_file.values())

    print(f"Files scanned: {total_files_scanned}")
    print(f"Files with matches: {files_with_matches}")
    print(f"Total occurrences: {total_occurrences}")
    print(f"Top {args.top} most-affected files:")
    for path, c in sorted(per_file.items(), key=lambda kv: -kv[1])[:args.top]:
        print(f"  {c:7d}  {os.path.basename(path)}")


if __name__ == '__main__':
    main()
