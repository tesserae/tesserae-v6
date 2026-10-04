#!/usr/bin/env python3
"""Rewrite the line tags of texts/grc/aelius_herodianus.on_enclitics.tess,
the one Greek file (besides the 21 Septuagint files fixed by #578) that the
2026-10-02 scan found still carrying a CTS-URN line tag instead of the
plain form every other file uses.

The 26 lines currently read:
  <aelius_herodianus. urn:cts:greekLit:tlg0087.tlg002.1st1K-grc1.N>
and are rewritten to the plain form, keeping the locus number N exactly:
  <aelius_herodianus.on_enclitics N>

This script only touches the text file in this repository. The reference
string is also stored in the passage index's window_texts.db and
descriptions.jsonl and in the two connections-map caches on production;
rewriting those is a data operation the maintainer runs after merge with
`scripts/corpus/retag_septuagint_refs.py --work herodian --apply` (that
script was generalised from the single-work form #578 used for the
Septuagint retag). See the pull request body for the full command list.

Usage:
  python scripts/corpus/retag_herodian_refs.py              # dry run, prints every change
  python scripts/corpus/retag_herodian_refs.py --apply      # rewrite the file
"""
import argparse
import re
import sys

PATH = 'texts/grc/aelius_herodianus.on_enclitics.tess'
_OLD = re.compile(
    r'<aelius_herodianus\. urn:cts:greekLit:tlg0087\.tlg002\.1st1K-grc1\.(\d+)>'
)


def new_tag(old_tag):
    """The plain tag for an old CTS-URN tag, or None if it does not match."""
    m = _OLD.fullmatch(old_tag)
    if not m:
        return None
    return f'<aelius_herodianus.on_enclitics {m.group(1)}>'


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--path', default=PATH, help='the .tess file to rewrite (default: the Herodian file)')
    ap.add_argument('--apply', action='store_true', help='rewrite the file (default: dry run only)')
    a = ap.parse_args()

    with open(a.path, encoding='utf-8') as fh:
        raw_lines = fh.readlines()

    out_lines = []
    changes = []
    for i, line in enumerate(raw_lines, start=1):
        ending = ''
        body = line
        if body.endswith('\n'):
            body = body[:-1]
            ending = '\n'
        if '\t' not in body:
            out_lines.append(line)
            continue
        tag, text = body.split('\t', 1)
        replacement = new_tag(tag)
        if replacement is None:
            out_lines.append(line)
            continue
        changes.append((i, tag, replacement, text))
        out_lines.append(replacement + '\t' + text + ending)

    if not changes:
        print('no CTS-URN tags found; nothing to do')
        return

    for i, old, new, _text in changes:
        print(f'  line {i}: {old} -> {new}')

    # The text after the tab must not change at all. Verify byte for byte
    # against the original before writing anything.
    old_texts = [c[3] for c in changes]
    new_texts = []
    for i, line in enumerate(out_lines, start=1):
        body = line[:-1] if line.endswith('\n') else line
        if '\t' not in body:
            continue
        tag, text = body.split('\t', 1)
        if tag.startswith('<aelius_herodianus.on_enclitics '):
            new_texts.append(text)
    assert old_texts == new_texts, 'text after the tab changed; refusing to write'

    if a.apply:
        with open(a.path, 'w', encoding='utf-8') as fh:
            fh.writelines(out_lines)
        print(f'{len(changes)} tags rewritten in {a.path}')
    else:
        print(f'{len(changes)} tags to rewrite; add --apply to rewrite')


if __name__ == '__main__':
    sys.exit(main())
