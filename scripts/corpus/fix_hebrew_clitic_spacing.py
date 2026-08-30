#!/usr/bin/env python3
"""Rejoin clitic prefixes split as free-standing tokens in three Hebrew books.

hebrew_bible.1_samuel, 2_samuel, and 1_kings shipped with clitic prefixes
(vav, the article, bet/kaf/lamed/mem, relative shin) as their own
space-delimited tokens ("VA YEHI" for "vayehi"), while the other 36 books
keep joined Masoretic orthography. Every token-matching channel (lemma,
exact, sound, quotation) then mismatches across book pairs for reasons of
spacing, not text. Found 2026-08-30 by the external-baselines run
(research/languages/hebrew/EXTERNAL_BASELINES_2026-08-30.md).

The fold: a token whose consonantal skeleton is a single Hebrew letter is
joined to the following token, repeatedly, so chains (vav + article) fold
too. There are no legitimate free-standing one-consonant words in Biblical
Hebrew. Letters, points, and accents are preserved exactly: the ONLY
characters removed are the spaces between a clitic and its host.

Validation, per file, all hard-fail:
  - references unchanged, line count unchanged
  - each line's non-space character sequence unchanged
  - no single-consonant token remains
Running it on an already-joined book is a verified no-op.
"""
import re
import sys
import unicodedata

# Hebrew consonants; points/accents (Mn marks) ride along with their letter.
HEB = r'א-ת'


def skeleton(tok):
    return ''.join(c for c in tok if 'א' <= c <= 'ת')


def fold_line(text):
    toks = text.split(' ')
    out = []
    i = 0
    while i < len(toks):
        t = toks[i]
        # join forward while this token is a one-consonant clitic and a
        # following token exists to host it
        while i + 1 < len(toks) and len(skeleton(t)) == 1 and skeleton(t):
            i += 1
            t = t + toks[i]
        out.append(t)
        i += 1
    return ' '.join(out)


def fix_file(path, write=True):
    lines = open(path, encoding='utf-8').read().splitlines(keepends=False)
    fixed, changed = [], 0
    for line in lines:
        m = re.match(r'(<[^>]+>\t?)(.*)$', line)
        if not m:
            fixed.append(line)
            continue
        ref, text = m.group(1), m.group(2)
        new = fold_line(text)
        if new != text:
            changed += 1
        # validation: non-space chars identical
        assert new.replace(' ', '') == text.replace(' ', ''), ref
        for tok in new.split(' '):
            sk = skeleton(tok)
            assert len(sk) != 1, (ref, tok)
        fixed.append(ref + new)
    if write:
        open(path, 'w', encoding='utf-8').write('\n'.join(fixed) + '\n')
    # refs unchanged by construction (ref group re-emitted verbatim)
    return changed, len(lines)


if __name__ == '__main__':
    for path in sys.argv[1:]:
        changed, total = fix_file(path)
        print(f'{path}: {changed}/{total} lines changed')
