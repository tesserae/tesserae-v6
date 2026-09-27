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
their bytes otherwise, line endings included. Dry run by default; --apply
writes.

    python scripts/corpus/restore_coptic_letters.py FILE [FILE ...] [--apply]

The Coptic lemma caches (cache/lemmas/cop) are not derived data but the
SCRIPTORIUM annotations themselves, one file per text, and json.dump wrote
their letters partly as backslash-u escapes, so this script handles both forms
and is the way to correct them. The Coptic index is then rebuilt from the
corrected caches, the operation recorded in docs/DATA_OPERATIONS.md for the
day this shipped.
"""
import argparse
import sys

import re

WRONG_TO_RIGHT = {0x2CB2 + k: 0x03E2 + k for k in range(14)}
# JSON files written by json.dump carry non-ASCII as backslash-u escapes. The
# Coptic annotation caches hold the wrong letters both raw and escaped.
_ESCAPED = re.compile(r'\\u2[cC][bB]([2-9a-fA-F])')


def _fix_escape(m):
    return '\\u%04x' % (0x03E2 + int(m.group(1), 16) - 2)


def restore(text):
    return _ESCAPED.sub(_fix_escape, text.translate(WRONG_TO_RIGHT))


def count_wrong(text):
    return sum(1 for ch in text if ord(ch) in WRONG_TO_RIGHT) + len(_ESCAPED.findall(text))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('files', nargs='+')
    ap.add_argument('--apply', action='store_true', help='write the files; the default only reports')
    args = ap.parse_args(argv)
    total = 0
    for path in args.files:
        # newline='' keeps the file's own line endings, so the only bytes that
        # change are the letters.
        text = open(path, encoding='utf-8', newline='').read()
        n = count_wrong(text)
        total += n
        fixed = restore(text)
        assert count_wrong(fixed) == 0
        print(f'{path}: {n} characters to move back' + ('' if args.apply else ' (dry run)'))
        if args.apply and n:
            open(path, 'w', encoding='utf-8', newline='').write(fixed)
    print(f'{total} characters in {len(args.files)} files' + (' rewritten' if args.apply else ', nothing written'))
    return 0


if __name__ == '__main__':
    sys.exit(main())
