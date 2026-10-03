#!/usr/bin/env python3
"""Issue #580, part A: move combining breathing/accent marks that are
stored before the Greek letter they belong to onto that letter, then apply
NFC so the result is the precomposed letter where one exists.

A run of combining marks (U+0300-U+036F) that sits between a space, a tab,
or the start of a line, and a Greek letter that can actually carry a
breathing or an accent, a vowel (alpha, epsilon, eta, iota, omicron,
upsilon, omega, capital or lowercase, including accented and diaeresis
forms) or rho (ῥ, Ῥ, the one consonant that takes a rough breathing), is
moved onto that letter, preserving the marks' own relative order (which is
already the canonical order: it is the same order Unicode decomposition
uses for the precomposed letter). Where a precomposed letter exists, NFC
produces it. Where none exists (a rough breathing on an upper-case rho that
has no precomposed single-codepoint form, say), the marks are left after
the letter as combining characters, in that same canonical order.

A mark before any other consonant is not this pattern. It is either damage
to the word or something else, and is left alone, for a human to check in
data/proposals/greek_stray_marks_2026-10-03.csv.

Scope history:
- Original (issue #580, part A): a run of marks before a Greek CAPITAL
  (U+0391-U+03A9, U+0386, U+0388-U+038F).
- Grew to lowercase on 3 October 2026: the same fault also hits a lowercase
  word-initial vowel (Strabo: marks before "ετι" for "ἔτι").
- Narrowed to vowels and rho, also on 3 October 2026, after the lowercase
  widening briefly matched ANY Greek letter, including consonants: in
  Achilles Tatius 2.11.3, ` ̓μέθυστος` (a damaged ἀμέθυστος missing its
  alpha) moved the smooth breathing onto the following mu, producing the
  nonsense `μ̓έθυστος`. A breathing or accent only ever belongs on a
  vowel, or a rough breathing on rho, and that restriction applies to
  capitals as much as lowercase: a capital consonant with a mark in front
  of it is exactly as wrong to move as a lowercase one.

The line tag inside <...> is never touched; only the text after it is
scanned and changed.

Usage:
    fix_greek_capital_marks.py --dry-run [--dir texts/grc]
    fix_greek_capital_marks.py --apply   [--dir texts/grc]

--dry-run prints per-file counts and writes a unified diff of the first 200
changed lines to data/proposals/greek_capital_marks_dryrun_2026-10-03.diff.
--apply rewrites the files in place.

Either mode checks an invariant on every changed line: with all combining
marks and precomposed-letter decompositions normalised away (NFD, then
strip U+0300-U+036F), the line before and after must be byte-identical.
If that check ever fails, the script stops and reports the line instead of
writing anything for it.
"""
import argparse
import difflib
import glob
import os
import re
import sys
import unicodedata

COMBINING_RUN = r'[̀-ͯ]+'
# Vowel capitals plus rho, and their accented/diaeresis forms, together with
# the lowercase counterparts. No other consonant is included: only rho ever
# carries a breathing.
GREEK_VOWEL_RHO_CAPITAL = r'[ΑΕΗΙΟΥΩΡΆΈΉΊΌΎΏΪΫ]'
GREEK_VOWEL_RHO_LOWER = r'[αεηιουωράέήίΐϊϋόύώ]'
GREEK_LETTER = r'(?:' + GREEK_VOWEL_RHO_CAPITAL + '|' + GREEK_VOWEL_RHO_LOWER + ')'
PATTERN = re.compile(
    r'(?:(?<=[ \t])|^)(' + COMBINING_RUN + r')(' + GREEK_LETTER + r')',
    re.MULTILINE,
)

TAG_RE = re.compile(r'^(<[^>]*>)([ \t]*)')

DIFF_LINE_CAP = 200
DEFAULT_DIFF_PATH = 'data/proposals/greek_capital_marks_dryrun_2026-10-03.diff'


def split_tag(line):
    m = TAG_RE.match(line)
    if m:
        return m.group(0), line[m.end():]
    return '', line


def invariant_key(s):
    """NFD, then strip all combining marks U+0300-U+036F. Used to check
    that a fix only ever moved marks around and never changed a letter."""
    nfd = unicodedata.normalize('NFD', s)
    return re.sub(r'[̀-ͯ]', '', nfd)


def fix_rest(rest):
    def repl(m):
        marks, letter = m.group(1), m.group(2)
        return unicodedata.normalize('NFC', letter + marks)
    return PATTERN.sub(repl, rest)


def process_line(raw_line):
    """Returns (new_raw_line, changed, invariant_ok)."""
    # Split off the line terminator so the regex and tag logic work on
    # content only; the terminator (whatever it is: \n, \r\n, or none on
    # the last line) is reattached unchanged.
    m = re.search(r'(\r\n|\r|\n)$', raw_line)
    if m:
        body, terminator = raw_line[:m.start()], m.group(1)
    else:
        body, terminator = raw_line, ''

    tag, rest = split_tag(body)
    if not PATTERN.search(rest):
        return raw_line, False, True

    new_rest = fix_rest(rest)
    new_body = tag + new_rest
    changed = new_body != body
    ok = invariant_key(body) == invariant_key(new_body)
    return new_body + terminator, changed, ok


def process_file(path):
    with open(path, encoding='utf-8', newline='') as f:
        content = f.read()
    lines = content.splitlines(keepends=True)

    new_lines = []
    changed_count = 0
    invariant_failures = []
    for i, line in enumerate(lines):
        new_line, changed, ok = process_line(line)
        if not ok:
            invariant_failures.append((i + 1, line, new_line))
        new_lines.append(new_line)
        if changed:
            changed_count += 1

    return lines, new_lines, changed_count, invariant_failures


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dir', default='texts/grc')
    group = ap.add_mutually_exclusive_group(required=True)
    group.add_argument('--dry-run', action='store_true')
    group.add_argument('--apply', action='store_true')
    ap.add_argument('--diff-out', default=DEFAULT_DIFF_PATH)
    args = ap.parse_args()

    files = sorted(glob.glob(os.path.join(args.dir, '*.tess')))

    total_changed_lines = 0
    files_changed = 0
    all_invariant_failures = []
    diff_chunks = []
    diff_lines_used = 0

    for path in files:
        lines, new_lines, changed_count, invariant_failures = process_file(path)
        if invariant_failures:
            all_invariant_failures.append((path, invariant_failures))
            continue  # do not touch this file's output at all

        if changed_count:
            files_changed += 1
            total_changed_lines += changed_count
            print(f"  {changed_count:6d}  {os.path.basename(path)}")

            if args.dry_run and diff_lines_used < DIFF_LINE_CAP:
                diff = difflib.unified_diff(
                    lines, new_lines,
                    fromfile=f'a/{path}', tofile=f'b/{path}',
                    lineterm='',
                )
                diff_text = list(diff)
                if diff_text:
                    diff_chunks.append('\n'.join(diff_text))
                    diff_lines_used += changed_count

            if args.apply:
                with open(path, 'w', encoding='utf-8', newline='') as f:
                    f.write(''.join(new_lines))

    if all_invariant_failures:
        print("\nINVARIANT CHECK FAILED -- stopping without writing these files:")
        for path, failures in all_invariant_failures:
            for lineno, old, new in failures[:5]:
                print(f"  {path}:{lineno}")
                print(f"    before: {old!r}")
                print(f"    after:  {new!r}")
        print(f"\n{len(all_invariant_failures)} file(s) with invariant failures. "
              f"No changes were written for these files.")
        sys.exit(1)

    print(f"\nFiles scanned: {len(files)}")
    print(f"Files changed: {files_changed}")
    print(f"Total changed lines: {total_changed_lines}")

    if args.dry_run:
        os.makedirs(os.path.dirname(args.diff_out), exist_ok=True)
        with open(args.diff_out, 'w', encoding='utf-8') as f:
            f.write('\n'.join(diff_chunks))
            f.write('\n')
        print(f"Dry-run diff (first {DIFF_LINE_CAP} changed lines) written to {args.diff_out}")
    elif args.apply:
        print("Applied.")


if __name__ == '__main__':
    main()
