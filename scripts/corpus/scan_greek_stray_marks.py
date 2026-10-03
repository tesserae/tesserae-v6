#!/usr/bin/env python3
"""Part 1 step 3 for issue #580, part B: find combining accent/breathing
marks that sit on something other than a vowel (or rho, for rough
breathing) -- a consonant, a space, a Latin letter, punctuation. These look
like OCR or typing errors and are listed for a human to check against an
edition. Nothing is changed.

Excludes the convention covered by part A (a run of marks between a space,
a tab or line start and a Greek capital) -- that is handled by
fix_greek_capital_marks.py, not here.

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

# Greek vowel base letters (all case/accent-bearing forms are covered by
# walking back past already-applied combining marks to the true base
# character, so this list only needs the plain forms NFD decomposition
# exposes: alpha, epsilon, eta, iota, omicron, upsilon, omega, both cases).
VOWELS = set('αεηιουωΑΕΗΙΟΥΩ')
# Rho takes rough breathing in its own right (ῥ, ῤ).
RHO = set('ρΡ')

TAG_RE = re.compile(r'^(<[^>]*>)([ \t]*)')

GREEK_LETTER_ANY = re.compile(r'[Ͱ-Ͽἀ-῿]')

# Characters after which a new word can reasonably start (so marks landing
# on the following letter, in the wrong order, are the known conversion
# convention rather than a stray mark on an unrelated character). Limited
# to actual word-boundary punctuation; an odd character like an inserted
# underscore or digit is NOT treated as a boundary, so a mark that lands
# next to one of those still gets listed as a stray case for a human to
# look at.
BOUNDARY_CHARS = set(' \t"\'“‘(«‘’[{—–:;,.!?《「')


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
            if base is not None and (base in VOWELS or base in RHO):
                continue

            j_after = skip_combining_fwd(rest, m.end())
            following = rest[j_after] if j_after < len(rest) else None

            # The systematic conversion bug (issue part A): a run of marks
            # between a space/tab/line-start and the Greek letter they
            # belong to, whether that letter is a capital (the bulk fix's
            # scope) or, less often, a lowercase word-initial vowel (seen
            # at line starts, e.g. Strabo). Either way this is the same
            # known convention, not an OCR-style stray mark, so it is left
            # out of this list.
            if preceded_by_boundary and following is not None and GREEK_LETTER_ANY.match(following):
                continue

            # Stray: mark sits on a consonant, punctuation, a Latin
            # letter, or is floating between non-letters, and is not the
            # mark-before-letter conversion pattern above.
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
