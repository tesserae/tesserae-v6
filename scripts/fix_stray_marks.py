#!/usr/bin/env python3
"""
Fix stray Greek diacritics from data/proposals/greek_stray_marks_2026-10-03.csv.

Each CSV row supplies the .tess file, the line reference, the problematic
substring (stored_string), and surrounding context.  For every row we:

  1. Find the exact line in texts/grc/<file>.
  2. Compute the corrected substring.
  3. Replace the first occurrence of stored_string on that line.

Three kinds of fix:
  A. Strip: combining mark is attached to a consonant, space, punctuation, or
     other character that cannot bear a Greek diacritic.
  B. Move: stored_string starts with combining marks followed immediately by a
     Greek capital vowel; move the marks to compose with the capital.
  C. De-duplicate: a vowel already has a breathing/accent and receives an extra
     one of the same category (or a perispomeni on a short vowel ε/ο).

Run with --dry-run to print a diff without writing files.
"""

import argparse
import csv
import os
import sys
import unicodedata
from collections import defaultdict

TEXTS_DIR = os.path.join(os.path.dirname(__file__), '..', 'texts', 'grc')
CSV_PATH  = os.path.join(os.path.dirname(__file__), '..', 'data', 'proposals',
                         'greek_stray_marks_2026-10-03.csv')

# ── diacritic universe ────────────────────────────────────────────────────────
GREEK_VOWELS_NFD     = set('αεηιουωΑΕΗΙΟΥΩ')
GREEK_RHO_NFD        = set('ρΡ')
VALID_BASES          = GREEK_VOWELS_NFD | GREEK_RHO_NFD
GREEK_CAPITAL_VOWELS = set('ΑΕΗΙΟΥΩ')
SHORT_VOWELS_NO_PERIS = set('εοΕΟ')   # never take perispomeni

BREATHING  = {'̓', '̔', '̓'}  # smooth, rough, koronis
ACCENT     = {'̀', '́', '͂'}  # grave, acute, perispomeni
DIAERESIS  = {'̈'}
IOTA_SUB   = {'ͅ'}
MACRON_BR  = {'̄', '̆', '͞'}  # macron, breve, double-inverted


def _mark_category(ch):
    if ch in BREATHING:
        return 'breathing'
    if ch in ACCENT:
        return 'accent'
    if ch in DIAERESIS:
        return 'diaeresis'
    if ch in IOTA_SUB:
        return 'iota_sub'
    if ch in MACRON_BR:
        return 'macron_br'
    return 'other'


def fix_stored_string(s: str) -> str:
    """Return the corrected form of a stored_string."""
    nfd   = unicodedata.normalize('NFD', s)
    chars = list(nfd)

    # ── Rule B: leading combining marks + Greek capital vowel ────────────────
    lead_end = 0
    while lead_end < len(chars) and unicodedata.category(chars[lead_end]) == 'Mn':
        lead_end += 1

    if lead_end > 0 and lead_end < len(chars):
        next_base = chars[lead_end]
        if next_base in GREEK_CAPITAL_VOWELS:
            # Reorder: capital first, then its marks, then the rest
            new_nfd = [next_base] + chars[:lead_end] + chars[lead_end + 1:]
            return unicodedata.normalize('NFC', ''.join(new_nfd))
        # Leading marks before a non-vowel: strip them and process the rest
        chars = chars[lead_end:]

    # ── Rules A + C: per-character filtering ─────────────────────────────────
    result: list[str] = []
    cur_base_idx  = -1
    cur_base_cats: set[str] = set()

    for ch in chars:
        if unicodedata.category(ch) == 'Mn':
            # Find the nearest non-combining base in result
            j = len(result) - 1
            while j >= 0 and unicodedata.category(result[j]) == 'Mn':
                j -= 1
            if j < 0:
                continue                          # bare leading mark – drop

            base = result[j]
            if base not in VALID_BASES:
                continue                          # Rule A: consonant/punct – drop

            # Rule C-special: perispomeni never on short vowels ε / ο
            if ch == '͂' and base in SHORT_VOWELS_NO_PERIS:
                continue

            # Refresh category-tracking when the base changes
            if j != cur_base_idx:
                cur_base_idx  = j
                cur_base_cats = set()

            cat = _mark_category(ch)
            if cat in cur_base_cats:
                continue                          # Rule C: duplicate category – drop
            cur_base_cats.add(cat)
            result.append(ch)

        else:
            result.append(ch)
            if unicodedata.category(ch) != 'Mn':
                cur_base_idx  = len(result) - 1
                cur_base_cats = set()

    return unicodedata.normalize('NFC', ''.join(result))


def _ref_tag(reference: str) -> str:
    """Build the <...> tag prefix from the CSV reference field."""
    ref = reference.strip()
    # Stale CSV naming: libanius. orations_1-11. → libanius. orations.
    #                   libanius. orations_26-50. → libanius. orations.
    ref = ref.replace('orations_1-11. ', 'orations. ')
    ref = ref.replace('orations_26-50. ', 'orations. ')
    return '<' + ref + '>'


def apply_fixes(dry_run: bool = True) -> int:
    with open(CSV_PATH, encoding='utf-8', newline='') as fh:
        rows = list(csv.DictReader(fh))

    # Group by file; within each file group by reference
    by_file: dict[str, list] = defaultdict(list)
    for row in rows:
        by_file[row['file']].append(row)

    total_files   = 0
    total_changes = 0
    total_skipped = 0

    FILENAME_MAP = {
        'thucydides.peleponnesian_war.tess': 'thucydides.peloponnesian_war.tess',
        'thucydides.peleponnesian_war.part.8.tess': 'thucydides.peloponnesian_war.part.8.tess',
        'libanius.orations_1-11.part.1.tess': 'libanius.orations.part.1.tess',
        'libanius.orations_26-50.part.2.tess': 'libanius.orations.part.2.tess',
    }

    for filename, file_rows in sorted(by_file.items()):
        actual_filename = FILENAME_MAP.get(filename, filename)
        fpath = os.path.join(TEXTS_DIR, actual_filename)
        if not os.path.exists(fpath):
            print(f'WARN  file not found: {fpath}', file=sys.stderr)
            total_skipped += len(file_rows)
            continue

        with open(fpath, encoding='utf-8', newline='') as fh:
            lines = fh.readlines()

        # Build index: reference tag → list of line indices (some files have duplicate tags)
        ref_index: dict[str, list[int]] = defaultdict(list)
        for i, line in enumerate(lines):
            if line.startswith('<'):
                end = line.find('>')
                if end > 0:
                    ref_index[line[:end + 1]].append(i)

        new_lines = list(lines)
        file_changed = False

        for row in file_rows:
            tag = _ref_tag(row['reference'])
            stored = row['stored_string']
            fixed  = fix_stored_string(stored)

            if fixed == stored:
                total_skipped += 1
                continue

            if tag not in ref_index:
                print(f'WARN  ref not found: {tag} in {filename}', file=sys.stderr)
                total_skipped += 1
                continue

            # Search all lines with this tag for the stored_string
            found_idx = None
            for idx in ref_index[tag]:
                if stored in new_lines[idx]:
                    found_idx = idx
                    break

            if found_idx is None:
                print(f'WARN  stored_string not in line: {stored!r} @ {tag} in {filename}',
                      file=sys.stderr)
                total_skipped += 1
                continue

            line     = new_lines[found_idx]
            new_line = line.replace(stored, fixed, 1)
            if dry_run:
                print(f'--- {filename}:{found_idx + 1}  {tag}')
                print(f'-   {line.rstrip()}')
                print(f'+   {new_line.rstrip()}')
                print()
            new_lines[found_idx] = new_line
            file_changed = True
            total_changes += 1

        if file_changed and not dry_run:
            with open(fpath, 'w', encoding='utf-8', newline='') as fh:
                fh.writelines(new_lines)
            total_files += 1

    if dry_run:
        print(f'DRY RUN: {total_changes} substitutions across rows; '
              f'{total_skipped} skipped.')
    else:
        print(f'Applied {total_changes} substitutions across {total_files} files; '
              f'{total_skipped} skipped.')

    return total_changes


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--dry-run', action='store_true',
                    help='Print proposed changes without writing files')
    ap.add_argument('--apply', action='store_true',
                    help='Write changes to disk')
    args = ap.parse_args()

    if args.apply:
        apply_fixes(dry_run=False)
    else:
        apply_fixes(dry_run=True)


if __name__ == '__main__':
    main()
