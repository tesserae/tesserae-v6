#!/usr/bin/env python3
"""Part 1 step 3 for issue #580, part B: find combining accent/breathing
marks that do not belong where they are stored: on something other than a
vowel or rho (which is handled, when it precedes the letter, by
fix_greek_capital_marks.py), or floating free with no letter to attach to.
These look like OCR or typing errors, or other damage, and are listed for a
human to check against an edition. Nothing is changed.

Excludes the convention covered by part A: a run of marks between a space,
a tab or line start and a Greek VOWEL OR RHO, capital or lowercase -- that
is handled by fix_greek_capital_marks.py, not here. Narrowed alongside that
script on 3 October 2026: a mark before any other consonant (capital or
lowercase) is NOT part A's pattern. A breathing or accent only ever belongs
on a vowel, or a rough breathing on rho, so a mark before a consonant stays
in this list (Achilles Tatius 2.11.3, ` ̓μέθυστος`, a damaged ἀμέθυστος
missing its alpha, is the case that found this).

Writes data/proposals/greek_stray_marks_2026-10-03.csv with columns:
file, reference, stored_string, context.
"""
import csv
import glob
import os
import re
import sys
import unicodedata

# Only accent-type marks: grave, acute, circumflex, iota subscript. The
# breathings U+0313/U+0314 are excluded here because they are legitimately
# reused, attached to a consonant, as the elision apostrophe (δ᾽, ἀλλ᾽,
# κατ᾽): thousands of genuine instances, not errors. Breathings on a
# consonant other than rho, or on a space, would still be a real error, but
# telling an elision apostrophe from a misplaced breathing needs more care
# than this scan gives it; the issue's part B examples are all grave,
# acute, circumflex or iota subscript, so this scan matches that scope.
COMBINING = re.compile(r'[̀́͂ͅ]+')
ANY_COMBINING = re.compile(r'[̀-ͯ]')
# Any run of combining marks at all (breathings included), used for the
# mark-before-consonant detector below: a breathing run before a
# word-initial consonant cannot be the elision apostrophe (that convention
# puts the breathing AFTER a word-final consonant, not before a
# word-initial one), so it is safe to look at breathings here without
# pulling in the thousands of genuine elisions.
ANY_COMBINING_RUN = re.compile(r'[̀-ͯ]+')

# Vowels (capital and lowercase, including accented/diaeresis forms) and
# rho: the only letters a breathing or accent can actually belong to. Kept
# in sync with fix_greek_capital_marks.py's GREEK_LETTER.
VOWELS = set('αεηιουωΑΕΗΙΟΥΩάέήίΐϊϋόύώΆΈΉΊΌΎΏΪΫ')
RHO = set('ρΡ')
VOWEL_OR_RHO = VOWELS | RHO

# Any basic-Greek-block letter, capital or lowercase, accented or not
# (mirrors fix_greek_capital_marks.py's old "any letter" scope before it was
# narrowed). A character in this set that is not in VOWEL_OR_RHO is a
# consonant that the fix script now leaves alone.
GREEK_BASIC_LETTER_RE = re.compile(r'[ΆΈ-ΊΌΎ-ΡΣ-ώ]')


def is_greek_consonant(ch):
    return ch is not None and GREEK_BASIC_LETTER_RE.match(ch) and ch not in VOWEL_OR_RHO

TAG_RE = re.compile(r'^(<[^>]*>)([ \t]*)')


def split_tag(line):
    m = TAG_RE.match(line)
    if m:
        return m.group(0), line[m.end():]
    return '', line


def skip_combining_back(rest, idx):
    """Index just past the last non-combining character before rest[idx]."""
    j = idx - 1
    while j >= 0 and ANY_COMBINING.match(rest[j]):
        j -= 1
    return j


def skip_combining_fwd(rest, idx):
    """Index of the first non-combining character at or after rest[idx]."""
    j = idx
    while j < len(rest) and ANY_COMBINING.match(rest[j]):
        j += 1
    return j


# Characters after which a new word can reasonably start (so marks landing
# on the following letter, in the wrong order, are the known conversion
# convention rather than a stray mark on an unrelated character). Limited
# to actual word-boundary punctuation; an odd character like an inserted
# underscore or digit is NOT treated as a boundary, so a mark that lands
# next to one of those still gets listed as a stray case for a human to
# look at.
BOUNDARY_CHARS = set(' \t"\'“‘(«‘’[{—–:;,.!?《「')


def scan_file(path):
    results = []
    with open(path, encoding='utf-8', errors='surrogateescape') as f:
        lines = f.readlines()
    for line in lines:
        line = line.rstrip('\r\n')
        tag, rest = split_tag(line)
        ref = tag.strip('<> \t')
        for m in COMBINING.finditer(rest):
            idx = m.start()

            j_before = skip_combining_back(rest, idx)
            base = rest[j_before] if j_before >= 0 else None
            preceded_by_boundary = base is None or base in BOUNDARY_CHARS

            # Normal accent placement: the mark sits right after the vowel
            # (or rho, for rough breathing) it belongs to.
            if base is not None and base in VOWEL_OR_RHO:
                continue

            j_after = skip_combining_fwd(rest, m.end())
            following = rest[j_after] if j_after < len(rest) else None

            # The systematic conversion bug (issue part A, narrowed to
            # vowels and rho on 3 October 2026): a run of marks between a
            # space/tab/line-start and the vowel or rho it belongs to.
            # Fixed by fix_greek_capital_marks.py, so left out of this
            # list. A mark before any OTHER letter (a consonant) is not
            # this pattern and stays in the stray list below.
            if preceded_by_boundary and following is not None and following in VOWEL_OR_RHO:
                continue

            # Stray: mark sits on a consonant, punctuation, a Latin
            # letter, or is floating between non-letters, and is not the
            # mark-before-vowel-or-rho conversion pattern above.
            start = max(0, idx - 15)
            end = min(len(rest), m.end() + 15)
            context = rest[start:end]
            stored = rest[max(0, idx - 1):m.end() + 1]
            results.append((ref, stored, context))

        # Second pass: a run of marks before a word-initial CONSONANT,
        # narrowed out of fix_greek_capital_marks.py's scope on 3 October
        # 2026 (Achilles Tatius 2.11.3: ` ̓μέθυστος`). The first pass above
        # only matches accent-type marks, so it misses a pure breathing run
        # (the common case: a converted breathing landed on the wrong,
        # consonant letter). Looking at breathings here is safe because
        # this position, before a word-initial letter, is never the
        # elision apostrophe, which always follows a word-final consonant.
        for m in ANY_COMBINING_RUN.finditer(rest):
            idx = m.start()
            j_before = skip_combining_back(rest, idx)
            base = rest[j_before] if j_before >= 0 else None
            preceded_by_boundary = base is None or base in BOUNDARY_CHARS
            if not preceded_by_boundary:
                continue
            following = rest[m.end()] if m.end() < len(rest) else None
            if not is_greek_consonant(following):
                continue
            if COMBINING.search(m.group(0)):
                continue  # already listed by the first pass above
            start = max(0, idx - 15)
            end = min(len(rest), m.end() + 15)
            context = rest[start:end]
            stored = rest[max(0, idx - 1):m.end() + 1]
            results.append((ref, stored, context))
    return results


def main():
    directory = 'texts/grc'
    files = sorted(glob.glob(os.path.join(directory, '*.tess')))
    out_path = 'data/proposals/greek_stray_marks_2026-10-03.csv'
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    total = 0
    files_with = 0
    with open(out_path, 'w', newline='', encoding='utf-8') as out:
        writer = csv.writer(out)
        writer.writerow(['file', 'reference', 'stored_string', 'context'])
        for path in files:
            hits = scan_file(path)
            if hits:
                files_with += 1
            for ref, stored, context in hits:
                writer.writerow([os.path.basename(path), ref, stored, context])
                total += 1

    print(f"Stray-mark cases written: {total}")
    print(f"Files with stray marks: {files_with}")
    print(f"CSV: {out_path}")


if __name__ == '__main__':
    main()
