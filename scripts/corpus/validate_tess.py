#!/usr/bin/env python3
"""Validate staged .tess files before they enter the corpus.

Checks per file:
  - every line matches '<ref>\\ttext' with non-empty text
  - refs unique
  - refs monotonic within their numeric prefix ordering (book, then chapter,
    then section, comparing number parts numerically; 'pr'/'pref' sort first)
  - no HTML tag or entity residue in the text
  - line count and average line length printed for a plausibility read

Usage: python validate_tess.py [--edition-order] <file.tess> [...]
Exits non-zero if any check fails.

--edition-order is for texts cited by the edition's own numbers (the CLLG Freed Corpus: pages and lines of the
printed edition, fragments such as 3b,469,F or 5col14, verses an editor has transposed). The order check then compares
only the leading numeric components of a reference (the book or the page), never the last (the line or verse within
it, which an edition may print out of order), compares references of different depth on their shared leading components, and skips a pair whose leading components are not plain numbers.
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


def comparable_prefix(ref):
    """The leading components of a reference when all are plain numbers or preface labels, else None."""
    tail = ref.split()[-1].split('.')[:-1]
    if not tail or not all(p.isdigit() or p in ('pr', 'pref', 'praef', 'arg') for p in tail):
        return None
    return [(1, int(p)) if p.isdigit() else (0, p) for p in tail]


def check(path, edition_order=False):
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
        if edition_order:
            ka, kb = comparable_prefix(a), comparable_prefix(b)
            if ka is not None and kb is not None and a.split()[:-1] == b.split()[:-1] and kb[:len(ka)] < ka[:len(kb)]:
                errs.append(f'non-monotonic: <{a}> -> <{b}>')
            continue
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
    args = [a for a in sys.argv[1:] if a != '--edition-order']
    ok = all([check(p, '--edition-order' in sys.argv[1:]) for p in args])
    sys.exit(0 if ok else 1)
