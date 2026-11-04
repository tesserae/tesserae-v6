#!/usr/bin/env python3
"""
Fix stray Greek breathings and accents across all texts/grc/*.tess files.

This is a broader follow-up to fix_stray_marks.py (issue #580 / PR #1133),
which fixed 1,347 specific entries from a catalogued CSV.  This script fixes
the remaining stray Greek breathing and accent marks found across the corpus
that were not in the original catalogue.

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
  its marks.  The capital is emitted as a single NFC-composed character so
  it matches the polytonic precomposed forms (U+1F08 etc.).

Each line is edited in-place: only the stray marks and their replacement
characters change; the rest of the line is returned exactly as it was read,
preserving the file's existing normalization form.

Run with --dry-run to print diffs without writing.
Run with --apply to write changes.
"""

import argparse
import os
import sys
import unicodedata

TEXTS_DIR = os.path.join(os.path.dirname(__file__), '..', 'texts', 'grc')

# Plain base characters (NFC decomposition's first character must be one of these)
PLAIN_VOWELS_RHO = frozenset('αεηιουωΑΕΗΙΟΥΩρΡ')

# Bare capital vowels (no diacritics).  Rule B fires when the next non-Mn
# character is one of these.
GREEK_CAP_VOWELS = frozenset('ΑΕΗΙΟΥΩ')

# Short vowels that cannot take perispomeni
SHORT_NO_PERIS = frozenset('εοΕΟ')

TARGET_MARKS = frozenset({
    '̓',  # COMBINING COMMA ABOVE       (smooth breathing)
    '̔',  # COMBINING REVERSED COMMA ABOVE (rough breathing)
    '̀',  # COMBINING GRAVE ACCENT
    '́',  # COMBINING ACUTE ACCENT
    '͂',  # COMBINING GREEK PERISPOMENI
    '̈',  # COMBINING DIAERESIS
    'ͅ',  # COMBINING GREEK YPOGEGRAMMENI (iota subscript)
})

BREATHING_SET = frozenset({'̓', '̔'})
ACCENT_SET    = frozenset({'̀', '́', '͂'})
DIAERESIS_SET = frozenset({'̈'})
IOTA_SUB_SET  = frozenset({'ͅ'})


def _is_valid_base(ch: str) -> bool:
    """True if ch can bear a Greek diacritic (is a Greek vowel or rho).

    Works for both plain (NFD) and precomposed (NFC) characters: NFD of a
    precomposed vowel like ἀ (U+1F00) starts with α, which is in the set.
    """
    if not ch:
        return False
    return unicodedata.normalize('NFD', ch)[0] in PLAIN_VOWELS_RHO


def _mark_category(ch: str) -> str:
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
    """Return the corrected form of a text line.

    Edits only the stray-mark positions; every other character is copied
    unchanged so the line's existing Unicode normalisation form is preserved.
    """
    chars = list(line)   # work on the ORIGINAL encoding, not NFD
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

        # ch is a target combining mark.
        # Find the most recent non-combining character in result (the "base").
        j = len(result) - 1
        while j >= 0 and unicodedata.category(result[j]) == 'Mn':
            j -= 1

        # Collect the full run of consecutive target marks starting at i.
        mark_run_start = i
        while (i < len(chars)
               and unicodedata.category(chars[i]) == 'Mn'
               and chars[i] in TARGET_MARKS):
            i += 1
        marks = chars[mark_run_start:i]

        # Find the next non-combining character after the full mark run
        # (skipping any non-target Mn chars that may also be present).
        k = i
        while k < len(chars) and unicodedata.category(chars[k]) == 'Mn':
            k += 1
        next_base_char = chars[k] if k < len(chars) else ''

        base_ok = _is_valid_base(result[j]) if j >= 0 else False

        if not base_ok and next_base_char in GREEK_CAP_VOWELS:
            # Rule B: compose marks with the following capital vowel.
            # Emit a single NFC-composed character (e.g. Α + ̓ → Ἀ U+1F08).
            # Non-target Mn chars between i and k had no valid base; drop them.
            composed = unicodedata.normalize('NFC', next_base_char + ''.join(marks))
            result.append(composed)
            cur_base_idx = len(result) - 1
            cur_base_cats = set()
            i = k + 1

        elif base_ok:
            # Base is a valid vowel or rho; keep marks (applying de-dup).
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

        # else: Rule A — base is invalid and no capital vowel follows; drop marks.

    return ''.join(result)


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
            fixed = fix_line(line)
            new_lines.append(fixed)
            if fixed != line:
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
