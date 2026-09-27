#!/usr/bin/env python3
"""Put the seven Coptic letters back where Unicode keeps them.

The Coptic normaliser used to move shei, fei, khei, hori, gangia, shima and
dei from U+03E2-03EF, the only code points Unicode assigns them, to
U+2CB2-2CBF, which are seven different letters (Dialect-P alef, Old Coptic
ain, and so on). Matching was unaffected, because both sides of every
comparison were moved the same way, but every stored normalised form
carried the wrong letters: three dictionary files, the stoplist, the lemma
table, the lemma caches and the Coptic index (issue #493).

This script reverses the move in the files that hold stored forms, one
code point to one code point, U+2CB2+k to U+03E2+k for k in 0..13. It is
a text substitution: it touches nothing else in the files and preserves
their bytes otherwise. Dry run by default; --apply writes.

    python scripts/corpus/restore_coptic_letters.py FILE [FILE ...] [--apply]

The caches and the index are not files to edit but to rebuild with the
corrected normaliser, which is the operation recorded in
docs/DATA_OPERATIONS.md for the day this shipped.
"""
import argparse
import sys

WRONG_TO_RIGHT = {0x2CB2 + k: 0x03E2 + k for k in range(14)}


def restore(text):
    return text.translate(WRONG_TO_RIGHT)


def count_wrong(text):
    return sum(1 for ch in text if ord(ch) in WRONG_TO_RIGHT)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('files', nargs='+')
    ap.add_argument('--apply', action='store_true', help='write the files; the default only reports')
    args = ap.parse_args(argv)
    total = 0
    for path in args.files:
        text = open(path, encoding='utf-8').read()
        n = count_wrong(text)
        total += n
        fixed = restore(text)
        assert count_wrong(fixed) == 0
        assert len(fixed) == len(text), 'one code point maps to one code point'
        print(f'{path}: {n} characters to move back' + ('' if args.apply else ' (dry run)'))
        if args.apply and n:
            open(path, 'w', encoding='utf-8').write(fixed)
    print(f'{total} characters in {len(args.files)} files' + (' rewritten' if args.apply else ', nothing written'))
    return 0


if __name__ == '__main__':
    sys.exit(main())
