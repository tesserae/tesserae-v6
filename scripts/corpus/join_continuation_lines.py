#!/usr/bin/env python3
"""Join untagged continuation lines onto the tagged line they belong to.

A .tess line is '<ref> text'. Some imports wrapped a long heading or paragraph
onto following lines that carry no tag, and the parser drops those lines. This
script appends each untagged non-blank line to the preceding tagged line with
one space (trailing tabs and spaces stripped), so no reference changes.

Usage: join_continuation_lines.py FILE [FILE ...] [--dry-run]
Prints, per file, tagged-line count before and after and the number joined.
Refuses a file whose first non-blank line is untagged.
"""
import sys

TAGGED = '<'


def fix(path, dry):
    out = []
    joined = 0
    before = after = 0
    with open(path, encoding='utf-8') as fh:
        lines = fh.read().split('\n')
    for ln in lines:
        s = ln.rstrip()
        if not s.strip():
            out.append('')
            continue
        if s.startswith(TAGGED):
            out.append(s)
            before += 1
            continue
        if not any(o.startswith(TAGGED) for o in out):
            raise SystemExit(f'{path}: untagged text before the first tag')
        # attach to the last tagged line
        for i in range(len(out) - 1, -1, -1):
            if out[i].startswith(TAGGED):
                out[i] = out[i] + ' ' + s.strip()
                break
        joined += 1
    after = sum(1 for o in out if o.startswith(TAGGED))
    print(f'{path}: tagged lines {before} -> {after}, continuation lines joined {joined}')
    if not dry:
        with open(path, 'w', encoding='utf-8') as fh:
            fh.write('\n'.join(out))


if __name__ == '__main__':
    dry = '--dry-run' in sys.argv
    for p in [a for a in sys.argv[1:] if not a.startswith('--')]:
        fix(p, dry)
