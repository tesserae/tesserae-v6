#!/usr/bin/env python3
"""
Fix stray Greek breathings and accents across all texts/grc/*.tess files.

This is a broader follow-up to fix_stray_marks.py (issue #580 / PR #1133),
which fixed 1,347 specific entries from a catalogued CSV.  This script fixes
the remaining ~12,000 stray Greek breathing and accent marks found across
446 files that were not in the original catalogue.

Targeted mark types (combining diacritics with no valid use on consonants
or non-Greek characters):

  U+0313  COMBINING COMMA ABOVE       (smooth breathing)
  U+0314  COMBINING REVERSED COMMA ABOVE (rough breathing)
  U+0300  COMBINING GRAVE ACCENT
  U+0301  COMBINING ACUTE ACCENT
  U+0342  COMBINING GREEK PERISPOMENI
  U+0308  COMBINING DIAERESIS
  U+0345  COMBINING GREEK YPOGEGRAMMENI (iota subscript)

NOT targeted (intentional scholarly notation preserved):
  U+0304  COMBINING MACRON        — prosody notation (Herodianus, etc.)
  U+0305  COMBINING OVERLINE      — prosody notation
  U+0323  COMBINING DOT BELOW     — editorial uncertain-reading marks (Sappho, etc.)
  U+035E  COMBINING DOUBLE MACRON — prosody notation
  U+0302  COMBINING CIRCUMFLEX ACCENT

Two rules:

  Rule A (Strip): a target mark is attached to a consonant, space, punctuation,
  or other character that is not a valid base (Greek vowel or rho).  Remove it.

  Rule B (Move): one or more target marks appear immediately before a Greek
  capital vowel (the marks' base is a non-valid character and the very next
  non-combining character is a capital vowel).  Reorder: capital first, then
  its marks, applying de-dup as usual.

Run with --dry-run to print diffs without writing.
Run with --apply to write changes.
"""

import argparse
import os
import sys
import unicodedata

TEXTS_DIR = os.path.join(os.path.dirname(__file__), '..', 'texts', 'grc')

GREEK_VOWELS     = set('αεηιουωΑΕΗΙΟΥΩ')
GREEK_RHO        = set('ρΡ')
VALID_BASES      = GREEK_VOWELS | GREEK_RHO
GREEK_CAP_VOWELS = set('ΑΕΗΙΟΥΩ')
SHORT_NO_PERIS   = set('εοΕΟ')

TARGET_MARKS = frozenset({
    '̓',  # smooth breathing
    '̔',  # rough breathing
    '̀',  # grave accent
    '́',  # acute accent
    '͂',  # perispomeni
    '̈',  # diaeresis
    'ͅ',  # iota subscript
})

BREATHING_SET = frozenset({'̓', '̔'})
ACCENT_SET    = frozenset({'̀', '́', '͂'})
DIAERESIS_SET = frozenset({'̈'})
IOTA_SUB_SET  = frozenset({'ͅ'})


def _mark_category(ch):
    if ch in BREATHING_SET:
        return 'breathing'
    if ch in ACCENT_SET:
        return 'accent'
    if ch in DIAERESIS_SET:
        return 'diaeresis'
    if ch in IOTA_SUB_SET:
        return 'iota_sub'
    return 'other'


def fix_line(line: str) -> str:
    """Return the corrected form of a full text line, preserving NFD normalisation.

    The .tess corpus is stored in NFD (decomposed) form.  This function works
    in NFD and returns NFD so only the stray marks change — no recomposition
    side-effects that would otherwise touch every line.
    """
    nfd = unicodedata.normalize('NFD', line)
    chars = list(nfd)
    result: list[str] = []
    cur_base_idx = -1
    cur_base_cats: set[str] = set()

    i = 0
    while i < len(chars):
        ch = chars[i]

        if unicodedata.category(ch) != 'Mn' or ch not in TARGET_MARKS:
            result.append(ch)
            if unicodedata.category(ch) != 'Mn':
                cur_base_idx = len(result) - 1
                cur_base_cats = set()
            i += 1
            continue

        # ch is a target combining mark — find base in result
        j = len(result) - 1
        while j >= 0 and unicodedata.category(result[j]) == 'Mn':
            j -= 1

        # Collect the full run of consecutive target marks starting at i
        mark_run_start = i
        while i < len(chars) and unicodedata.category(chars[i]) == 'Mn' and chars[i] in TARGET_MARKS:
            i += 1
        marks = chars[mark_run_start:i]

        # What is the next non-combining character after the mark run?
        k = i
        while k < len(chars) and unicodedata.category(chars[k]) == 'Mn':
            k += 1
        next_base_char = chars[k] if k < len(chars) else ''

        base_ok = j >= 0 and result[j] in VALID_BASES

        if not base_ok and next_base_char in GREEK_CAP_VOWELS:
            # Rule B: move marks to the following capital vowel.
            # chars[i:k] are any non-target combining marks between our target run and
            # the capital — they sit on a non-valid base so they are also dropped.
            capital = chars[k]

            result.append(capital)
            new_base_idx = len(result) - 1
            new_base_cats: set[str] = set()

            for m in marks:
                if m == '͂' and capital in SHORT_NO_PERIS:
                    continue
                cat = _mark_category(m)
                if cat in new_base_cats:
                    continue
                new_base_cats.add(cat)
                result.append(m)

            cur_base_idx = new_base_idx
            cur_base_cats = new_base_cats
            i = k + 1
            # (non-target marks between our run and capital are also dropped)

        elif base_ok:
            # Base is a valid vowel or rho — keep marks (applying de-dup + Rule C)
            if j != cur_base_idx:
                cur_base_idx = j
                cur_base_cats = set()

            for m in marks:
                if m == '͂' and result[j] in SHORT_NO_PERIS:
                    continue
                cat = _mark_category(m)
                if cat in cur_base_cats:
                    continue
                cur_base_cats.add(cat)
                result.append(m)

        # else: Rule A — base is invalid and no capital vowel follows; drop the marks

    return unicodedata.normalize('NFD', ''.join(result))


def process_files(dry_run: bool) -> tuple[int, int]:
    total_lines = 0
    total_files = 0

    for fname in sorted(os.listdir(TEXTS_DIR)):
        if not fname.endswith('.tess'):
            continue
        fpath = os.path.join(TEXTS_DIR, fname)
        with open(fpath, encoding='utf-8') as fh:
            lines = fh.readlines()

        new_lines = []
        file_changed = False
        for line in lines:
            line_nfd = unicodedata.normalize('NFD', line)
            fixed = fix_line(line)
            new_lines.append(fixed)
            if fixed != line_nfd:
                total_lines += 1
                file_changed = True
                if dry_run:
                    print(f'--- {fname}')
                    print(f'-   {line.rstrip()}')
                    print(f'+   {fixed.rstrip()}')
                    print()

        if file_changed:
            total_files += 1
            if not dry_run:
                with open(fpath, 'w', encoding='utf-8') as fh:
                    fh.writelines(new_lines)

    return total_files, total_lines


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--dry-run', action='store_true',
                    help='Print proposed changes without writing files')
    ap.add_argument('--apply', action='store_true',
                    help='Write changes to disk')
    args = ap.parse_args()

    if not args.apply and not args.dry_run:
        print('Pass --dry-run or --apply', file=sys.stderr)
        sys.exit(1)

    dry = not args.apply
    files, lines = process_files(dry_run=dry)

    if dry:
        print(f'DRY RUN: {lines} lines changed across {files} files.')
    else:
        print(f'Applied: {lines} lines changed across {files} files.')


if __name__ == '__main__':
    main()
