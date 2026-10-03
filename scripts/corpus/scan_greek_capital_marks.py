#!/usr/bin/env python3
"""Part 1 scan for issue #580: combining marks stored before the Greek
letter they belong to.

Scans texts/grc/*.tess for a run of combining marks (U+0300-U+036F) that
sits between a space, a tab, or the start of a line, and a Greek letter
that can actually carry a breathing or an accent: a vowel (alpha, epsilon,
eta, iota, omicron, upsilon, omega, capital or lowercase, including their
accented and diaeresis forms), or rho (which takes a rough breathing: ῥ,
Ῥ). A mark before any other letter, a consonant other than rho, is not
this pattern; it is either damage to the word (an OCR-style stray mark) or
something else, and is left for scripts/corpus/scan_greek_stray_marks.py
and a human to look at.

Scope grew to lowercase on 3 October 2026: the original scan only matched a
Greek CAPITAL (U+0391-U+03A9, U+0386, U+0388-U+038F) after the marks, since
that was the issue's reported pattern. The same encoding fault also hits a
lowercase word-initial vowel at a line start (Strabo: marks before "ετι"
for "ἔτι"), so the pattern grew to match lowercase too.

Narrowed to vowels and rho, also on 3 October 2026, after the lowercase
widening briefly matched ANY Greek letter, including consonants: in
Achilles Tatius 2.11.3, ` ̓μέθυστος` (a damaged ἀμέθυστος missing its
alpha) moved the smooth breathing onto the following mu, producing the
nonsense `μ̓έθυστος`. A breathing or accent only ever belongs on a vowel,
or a rough breathing on rho, so that is now the only pattern this script
fixes. A mark before any other consonant is a stray case, left alone and
listed by scan_greek_stray_marks.py.

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

# Vowel capitals plus rho, and their accented/diaeresis forms: Α Ε Η Ι Ο Υ Ω
# Ρ, Ά Έ Ή Ί Ό Ύ Ώ Ϊ Ϋ. No other capital consonant is included: only rho
# ever carries a breathing.
GREEK_VOWEL_RHO_CAPITAL = r'[ΑΕΗΙΟΥΩΡΆΈΉΊΌΎΏΪΫ]'
# The lowercase counterparts: α ε η ι ο υ ω ρ, ά έ ή ί ΐ ϊ ϋ ό ύ ώ.
GREEK_VOWEL_RHO_LOWER = r'[αεηιουωράέήίΐϊϋόύώ]'
GREEK_LETTER = r'(?:' + GREEK_VOWEL_RHO_CAPITAL + '|' + GREEK_VOWEL_RHO_LOWER + ')'

# The original issue scope: ANY capital, not restricted to vowels/rho. Used
# only to size what the vowel/rho restriction excludes (a capital consonant
# with a mark in front of it, which is a stray case, not this pattern).
GREEK_CAPITAL_ANY = r'[Α-ΩΆΈ-Ώ]'

# Matches at line-start, after a space, or after a tab.
PATTERN = re.compile(
    r'(?:(?<=[ \t])|^)(' + COMBINING_RUN + r')(' + GREEK_LETTER + r')',
    re.MULTILINE,
)
CAPITAL_PATTERN = re.compile(
    r'(?:(?<=[ \t])|^)(' + COMBINING_RUN + r')(' + GREEK_VOWEL_RHO_CAPITAL + r')',
    re.MULTILINE,
)
ANY_CAPITAL_PATTERN = re.compile(
    r'(?:(?<=[ \t])|^)(' + COMBINING_RUN + r')(' + GREEK_CAPITAL_ANY + r')',
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
    any_capital_count = 0
    with open(path, encoding='utf-8', errors='surrogateescape') as f:
        for line in f:
            line = line.rstrip('\r\n')
            tag, rest = split_tag(line)
            count += len(PATTERN.findall(rest))
            capital_count += len(CAPITAL_PATTERN.findall(rest))
            any_capital_count += len(ANY_CAPITAL_PATTERN.findall(rest))
    return count, capital_count, any_capital_count


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dir', default='texts/grc')
    ap.add_argument('--top', type=int, default=10)
    args = ap.parse_args()

    files = sorted(glob.glob(os.path.join(args.dir, '*.tess')))
    per_file = {}
    per_file_capital = {}
    per_file_any_capital = {}
    for path in files:
        c, cap, any_cap = scan_file(path)
        if c:
            per_file[path] = c
        if cap:
            per_file_capital[path] = cap
        if any_cap:
            per_file_any_capital[path] = any_cap

    total_files_scanned = len(files)
    files_with_matches = len(per_file)
    total_occurrences = sum(per_file.values())
    total_capital = sum(per_file_capital.values())
    total_lowercase = total_occurrences - total_capital
    total_any_capital = sum(per_file_any_capital.values())
    excluded_capital_consonant = total_any_capital - total_capital
    files_with_excluded = len({
        p for p in per_file_any_capital
        if per_file_any_capital[p] > per_file_capital.get(p, 0)
    })

    print(f"Files scanned: {total_files_scanned}")
    print(f"Files with matches: {files_with_matches}")
    print(f"Total occurrences (vowels and rho only): {total_occurrences}")
    print(f"  of which before a capital: {total_capital}")
    print(f"  of which before a lowercase letter: {total_lowercase}")
    print(f"Capital-consonant cases excluded by the vowel/rho restriction: "
          f"{excluded_capital_consonant} in {files_with_excluded} files")
    print(f"Top {args.top} most-affected files:")
    for path, c in sorted(per_file.items(), key=lambda kv: -kv[1])[:args.top]:
        print(f"  {c:7d}  {os.path.basename(path)}")


if __name__ == '__main__':
    main()
