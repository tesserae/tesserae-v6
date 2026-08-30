#!/usr/bin/env python3
"""Validate staged .tess files before they enter the corpus.

Checks per file:
  - every line matches '<ref>\\ttext' with non-empty text
  - refs unique
  - refs monotonic within their numeric prefix ordering (book, then chapter,
    then section, comparing number parts numerically; 'pr'/'pref' sort first)
  - no HTML tag or entity residue in the text
  - line count and average line length printed for a plausibility read

Usage: python validate_tess.py <file.tess> [...]
Exits non-zero if any check fails.
"""
import re
import sys

LINE = re.compile(r'^<([^>]+)>\t(.+)$')
RESIDUE = re.compile(r'(?i)</?(p|b|i|a|div|font|br|span|table|td|tr|center|h\d)\b'
                     r'|&(nbsp|amp|lt|gt|quot|#\d+|[a-z]+acute|[a-z]+grave|uml|circ);')


def ref_key(ref):
    """Numeric sort key for the trailing dotted reference."""
    tail = ref.split()[-1]
    parts = []
    for p in tail.split('.'):
        if p.isdigit():
            parts.append((1, int(p)))
        else:
            parts.append((0, p))  # 'pr', 'pref' etc. sort before numbers
    return parts


def check(path):
    errs = []
    refs = []
    lens = []
    for n, raw in enumerate(open(path, encoding='utf-8'), 1):
        raw = raw.rstrip('\n')
        if not raw:
            errs.append(f'line {n}: empty line')
            continue
        m = LINE.match(raw)
        if not m:
            errs.append(f'line {n}: malformed: {raw[:80]!r}')
            continue
        ref, text = m.groups()
        if not text.strip():
            errs.append(f'line {n}: empty text for <{ref}>')
        if RESIDUE.search(text):
            errs.append(f'line {n}: HTML residue: {text[:100]!r}')
        refs.append(ref)
        lens.append(len(text))
    if len(set(refs)) != len(refs):
        seen = set()
        for r in refs:
            if r in seen:
                errs.append(f'duplicate ref <{r}>')
            seen.add(r)
    # monotonicity within the same non-numeric prefix run
    for a, b in zip(refs, refs[1:]):
        if a.rsplit('.', 1)[0].split()[0] == b.rsplit('.', 1)[0].split()[0]:
            try:
                if ref_key(b) < ref_key(a) and ref_key(b)[0] == ref_key(a)[0]:
                    errs.append(f'non-monotonic: <{a}> -> <{b}>')
            except TypeError:
                pass
    avg = sum(lens) // max(len(lens), 1)
    status = 'FAIL' if errs else 'ok'
    print(f'{path}: {len(refs)} lines, avg {avg} chars [{status}]')
    for e in errs[:12]:
        print(f'  {e}')
    if len(errs) > 12:
        print(f'  ... {len(errs) - 12} more')
    return not errs


if __name__ == '__main__':
    ok = all([check(p) for p in sys.argv[1:]])
    sys.exit(0 if ok else 1)
