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

Safety (2026-09-21, code audit finding #2): dry run by default, reporting
the lines/file that would change; --apply writes, after a dated backup of
each file via scripts/corpus/corpus_safety.py. Previously this overwrote
its argument files unconditionally with no flag and no backup at all.
"""
import argparse
import os
import re
import sys
import unicodedata

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from corpus_safety import add_apply_argument, backup, atomic_write  # noqa: E402

# Hebrew consonants; points/accents (Mn marks) ride along with their letter.
HEB = r'א-ת'


def skeleton(tok):
    return ''.join(c for c in tok if 'א' <= c <= 'ת')


# Two-consonant vav-initial clitic clusters (vav + a second prefix), which the
# source also emitted free-standing, and which folding a chain of singles can
# produce. All 886 corpus occurrences were in the seven split books and none
# in the thirty-two clean ones, so no real word is caught. ומה ("and what")
# IS a real word, occurs only in clean books, and is deliberately absent here.
CLUSTERS = {'ול', 'וה', 'וב', 'ומ', 'וכ', 'וש'}


def foldable(t):
    sk = skeleton(t)
    return bool(sk) and (len(sk) == 1 or sk in CLUSTERS)


def fold_line(text):
    toks = text.split(' ')
    out = []
    i = 0
    while i < len(toks):
        t = toks[i]
        # join forward while this token is a clitic (or clitic cluster) and a
        # following token exists to host it
        while i + 1 < len(toks) and foldable(t):
            i += 1
            t = t + toks[i]
        out.append(t)
        i += 1
    return ' '.join(out)


def fix_file(path, apply_=False, tag=None):
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
            assert sk not in CLUSTERS, (ref, tok)
        fixed.append(ref + new)
    if apply_:
        backup(path, tag=tag or 'hebrew-clitic')
        atomic_write(path, '\n'.join(fixed) + '\n')
    # refs unchanged by construction (ref group re-emitted verbatim)
    return changed, len(lines)


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    add_apply_argument(ap)
    ap.add_argument('--tag', default=None, help='backup suffix (default: a timestamp)')
    ap.add_argument('paths', nargs='+', help='.tess files to fold clitic spacing in')
    args = ap.parse_args()
    for path in args.paths:
        changed, total = fix_file(path, apply_=args.apply, tag=args.tag)
        verb = 'changed' if args.apply else 'would change'
        print(f'{path}: {changed}/{total} lines {verb}')
    if not args.apply:
        print('dry run; pass --apply to write (a dated backup is made first)')


if __name__ == '__main__':
    main()
