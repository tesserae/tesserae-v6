#!/usr/bin/env python3
"""Part 1 scan for issue #580: combining marks stored before the Greek
letter they belong to.

Scans texts/grc/*.tess for a run of combining marks (U+0300-U+036F) that
sits between a space, a tab, or the start of a line, and a Greek letter.

Scope grew to lowercase on 3 October 2026: the original scan only matched a
Greek CAPITAL (U+0391-U+03A9, U+0386, U+0388-U+038F) after the marks, since
that was the issue's reported pattern. The same encoding fault also hits a
lowercase word-initial vowel at a line start (Strabo: marks before "ετι"
for "ἔτι"), so the pattern now matches any Greek letter in the basic block
and its accented forms, capital or lowercase.

Only scans the text AFTER the line tag (the part after the first tab, or
after the first '>' plus following space/tab if no literal tab is present),
so a tag's own content is never touched or counted.

Usage:
    scan_greek_capital_marks.py [--dir texts/grc] [--top N]

Prints: total files scanned, files with matches, total occurrences (split
into the capital and lowercase cases), and the top N most-affected files.
"""
import argparse
import glob
import os
import re
import sys

COMBINING_RUN = r'[̀-ͯ]+'
GREEK_CAPITAL = r'[Α-ΩΆΈ-Ώ]'
# Basic Greek block letters and their accented forms, capital or lowercase:
# capitals Α-Ρ, Σ-Ω plus Ϊ Ϋ, the accented capitals Ά Έ Ή Ί Ό Ύ Ώ, lowercase
# α-ω, and the accented/diaeresis lowercase forms ά έ ή ί ΐ ϊ ϋ ό ύ ώ. Skips
# U+03A2, which is unassigned.
GREEK_LETTER = r'[ΆΈ-ΊΌΎ-ΡΣ-ώ]'

# Matches at line-start, after a space, or after a tab.
PATTERN = re.compile(
    r'(?:(?<=[ \t])|^)(' + COMBINING_RUN + r')(' + GREEK_LETTER + r')',
    re.MULTILINE,
)
CAPITAL_PATTERN = re.compile(
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
    capital_count = 0
    with open(path, encoding='utf-8', errors='surrogateescape') as f:
        for line in f:
            line = line.rstrip('\r\n')
            tag, rest = split_tag(line)
            count += len(PATTERN.findall(rest))
            capital_count += len(CAPITAL_PATTERN.findall(rest))
    return count, capital_count


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dir', default='texts/grc')
    ap.add_argument('--top', type=int, default=10)
    args = ap.parse_args()

    files = sorted(glob.glob(os.path.join(args.dir, '*.tess')))
    per_file = {}
    per_file_capital = {}
    for path in files:
        c, cap = scan_file(path)
        if c:
            per_file[path] = c
        if cap:
            per_file_capital[path] = cap

    total_files_scanned = len(files)
    files_with_matches = len(per_file)
    total_occurrences = sum(per_file.values())
    total_capital = sum(per_file_capital.values())
    total_lowercase = total_occurrences - total_capital
    files_lowercase_only = len(set(per_file) - set(per_file_capital))

    print(f"Files scanned: {total_files_scanned}")
    print(f"Files with matches: {files_with_matches}")
    print(f"Total occurrences: {total_occurrences}")
    print(f"  of which before a capital: {total_capital}")
    print(f"  of which before a lowercase letter: {total_lowercase}")
    print(f"Files with a lowercase-only case (no capital case in the file): {files_lowercase_only}")
    print(f"Top {args.top} most-affected files:")
    for path, c in sorted(per_file.items(), key=lambda kv: -kv[1])[:args.top]:
        print(f"  {c:7d}  {os.path.basename(path)}")


if __name__ == '__main__':
    main()
