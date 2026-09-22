#!/usr/bin/env python3
"""Check that a work's whole .tess file agrees with its book/part files.

Tesserae's Reader shows some works one book at a time: a whole file
`<work>.tess` plus book files `<work>.part.<N>.tess` (sometimes
`<work>.part.<N>.<suffix>.tess`, e.g. a part spanning several books). This
script finds every such whole+parts group under a texts root and checks
that the two views of the work agree:

  - the refs (the `<...>` tag on each line) in the whole file must equal
    the refs across all its part files as MULTISETS (no missing ref, no
    extra ref, and a ref repeated more than once -- e.g. a refrain or an
    apparatus variant given twice under the same locus -- must repeat the
    same number of times on both sides);
  - the text lines, with tags stripped and whitespace normalised (runs of
    whitespace collapsed to one space, leading/trailing stripped), must be
    equal as MULTISETS between the whole file and the concatenation of its
    parts (catches a line duplicated in a part, or one whose wording
    drifted from the whole file, even when the ref sets happen to match).

A whole+parts group is any `<work>.tess` for which at least one
`<work>.part.<N>...tess` file exists alongside it (same directory). Parts
are discovered by the pattern `<work>.part.<digits>` at the start of the
part's filename (a suffix like `.books_12-20` after the digits is allowed
and ignored for grouping).

Usage:
    python check_whole_vs_parts.py [--root TEXTS_ROOT] [WORK ...]

TEXTS_ROOT defaults to "texts" under the current directory. WORK names
(the part before ".tess", e.g. "isocrates.letters") restrict the check to
just those works; with none given, every whole+parts group found under the
root is checked. Prints one PASS/FAIL line per work, a summary line, and
exits 1 if any checked work fails (0 otherwise, including when no
whole+parts groups exist at all).
"""
import argparse
import glob
import os
import re
import sys

# A part's label is not always a number. The corpus names a preface
# `.part.pr`, `.part.praef` or `.part.preface`, fragments `.part.fragments`,
# and the Vulgate's second psalter `.part.21a.old_latin_psalms`. A pattern
# that insisted on digits reported eleven such files, across eight works, as
# missing content when the content was there all along, and that is what sent
# the 2026-09-21 analysis looking for book files to generate that already
# existed (found while acting on it).
PART_RE = re.compile(r'^(?P<base>.+)\.part\.(?P<n>[0-9]+[a-z]?|[a-z_]+)(?:\.[^.]+)*\.tess$')
LINE_RE = re.compile(r'^\s*<([^>]+)>\s?(.*)$')


def parse_tess(path):
    """Return list of (ref, normalised_text) for a .tess file's non-blank
    lines. A line that doesn't match the '<ref> text' shape is reported to
    stderr and skipped (this script is a checker, not a validator -- use
    validate_tess.py for line-shape problems)."""
    out = []
    with open(path, encoding='utf-8-sig') as fh:
        for n, raw in enumerate(fh, 1):
            raw = raw.rstrip('\n')
            if not raw.strip():
                continue
            m = LINE_RE.match(raw)
            if not m:
                print(f'  WARNING: {path}:{n}: unparsed line, skipped: {raw[:80]!r}',
                      file=sys.stderr)
                continue
            ref, text = m.group(1).strip(), m.group(2)
            norm_text = ' '.join(text.split())
            out.append((ref, norm_text))
    return out


def find_groups(root, only_works=None):
    """{work_base: {'whole': path, 'parts': [path, ...]}} for every whole
    file under root that has at least one matching part file. If
    only_works is given, restrict to those base names (still requiring the
    whole file and at least one part to exist)."""
    whole_by_base = {}
    for path in glob.glob(os.path.join(root, '**', '*.tess'), recursive=True):
        fname = os.path.basename(path)
        if fname.endswith('.tess') and '.part.' not in fname:
            base = fname[:-len('.tess')]
            whole_by_base.setdefault(base, {}).setdefault('candidates', []).append(path)

    groups = {}
    for path in glob.glob(os.path.join(root, '**', '*.part.*.tess'), recursive=True):
        fname = os.path.basename(path)
        m = PART_RE.match(fname)
        if not m:
            continue
        base = m.group('base')
        groups.setdefault(base, {'whole': None, 'parts': []})
        groups[base]['parts'].append(path)

    for base, info in list(groups.items()):
        cand = whole_by_base.get(base, {}).get('candidates', [])
        if not cand:
            print(f'  WARNING: {base}: part files found but no whole file {base}.tess',
                  file=sys.stderr)
            del groups[base]
            continue
        if len(cand) > 1:
            print(f'  WARNING: {base}: multiple whole-file candidates {cand}, using first',
                  file=sys.stderr)
        info['whole'] = cand[0]
        info['parts'].sort()

    if only_works:
        groups = {b: g for b, g in groups.items() if b in only_works}
        missing = set(only_works) - set(groups)
        for m in missing:
            print(f'  WARNING: no whole+parts group found for {m!r}', file=sys.stderr)

    return groups


def check_work(base, info):
    whole = parse_tess(info['whole'])
    parts = []
    for p in info['parts']:
        parts.extend(parse_tess(p))

    whole_refs = [r for r, _ in whole]
    parts_refs = [r for r, _ in parts]

    problems = []

    # Compare refs as MULTISETS, not sets: some works legitimately repeat a
    # ref (a refrain, an apparatus variant given twice under the same
    # locus), and that is fine as long as the whole file and its parts
    # repeat it the SAME number of times. Only an actual count mismatch --
    # missing entirely, extra entirely, or duplicated a different number of
    # times on the two sides -- is a real problem.
    whole_ref_counts = _counter(whole_refs)
    parts_ref_counts = _counter(parts_refs)
    if whole_ref_counts != parts_ref_counts:
        only_whole = _subtract(whole_ref_counts, parts_ref_counts)
        only_parts = _subtract(parts_ref_counts, whole_ref_counts)
        if only_whole:
            items = sorted(only_whole)
            problems.append(f'{sum(only_whole.values())} ref occurrence(s) in whole file '
                             f'with no matching count in the parts: {items[:10]}'
                             f'{" ..." if len(items) > 10 else ""}')
        if only_parts:
            items = sorted(only_parts)
            problems.append(f'{sum(only_parts.values())} ref occurrence(s) in the parts '
                             f'with no matching count in the whole file: {items[:10]}'
                             f'{" ..." if len(items) > 10 else ""}')

    whole_texts = _counter(t for _, t in whole)
    parts_texts = _counter(t for _, t in parts)
    if whole_texts != parts_texts:
        only_w = _subtract(whole_texts, parts_texts)
        only_p = _subtract(parts_texts, whole_texts)
        if only_w:
            problems.append(f'{sum(only_w.values())} text line(s) in whole file with no match '
                             f'(by count) in the parts, e.g. {list(only_w)[:3]!r}')
        if only_p:
            problems.append(f'{sum(only_p.values())} text line(s) in the parts with no match '
                             f'(by count) in the whole file, e.g. {list(only_p)[:3]!r}')

    return problems


def _counter(items):
    d = {}
    for x in items:
        d[x] = d.get(x, 0) + 1
    return d


def _subtract(a, b):
    out = {}
    for k, v in a.items():
        diff = v - b.get(k, 0)
        if diff > 0:
            out[k] = diff
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                  formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--root', default='texts', help='texts root to scan (default: texts)')
    ap.add_argument('works', nargs='*', help='restrict to these work base names')
    args = ap.parse_args()

    groups = find_groups(args.root, set(args.works) if args.works else None)
    if not groups:
        print('No whole+parts groups found.')
        return 0

    n_pass = 0
    n_fail = 0
    for base in sorted(groups):
        problems = check_work(base, groups[base])
        if problems:
            n_fail += 1
            print(f'[FAIL] {base} ({len(groups[base]["parts"])} part file(s))')
            for p in problems:
                print(f'    - {p}')
        else:
            n_pass += 1
            print(f'[PASS] {base} ({len(groups[base]["parts"])} part file(s))')

    print(f'\n{n_pass} passed, {n_fail} failed, {n_pass + n_fail} whole+parts work(s) checked.')
    return 1 if n_fail else 0


if __name__ == '__main__':
    sys.exit(main())
