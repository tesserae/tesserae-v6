#!/usr/bin/env python3
"""Run cllg_tei_to_tess.py over every row of scripts/corpus/cllg_tier1_works.json (CLLG Freed Corpus, group one).

    cllg_tier1_convert.py SRC_DIR OUT_DIR [--range A:B] [--only STEM ...] [--report FILE] [--force]

SRC_DIR is the freed-corpus data folder (the rows' `file` is relative to it). Writes OUT_DIR/<stem>.tess and, where
the row says parts, OUT_DIR/<stem>.part.N.tess beside it (the whole file is kept too, as Herodotus is filed).
A file already written is skipped unless --force. --report appends one tab-separated line per text:
stem, exit code, mode, lines, tokens, ratio, duplicates, parts. The exit code is 0 when every text passed,
1 if any had a duplicate citation, 2 if any failed the letter check.
"""
import argparse
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('src')
    ap.add_argument('out')
    ap.add_argument('--range', default='')
    ap.add_argument('--only', nargs='*', default=[])
    ap.add_argument('--report')
    ap.add_argument('--force', action='store_true')
    a = ap.parse_args()
    rows = json.load(open(os.path.join(HERE, 'cllg_tier1_works.json'), encoding='utf-8'))
    if a.range:
        lo, hi = a.range.split(':')
        rows = rows[int(lo or 0):int(hi or len(rows))]
    if a.only:
        rows = [r for r in rows if r['stem'] in a.only]
    os.makedirs(a.out, exist_ok=True)
    worst = 0
    for r in rows:
        dest = os.path.join(a.out, r['stem'] + '.tess')
        if os.path.exists(dest) and not a.force:
            continue
        cmd = [sys.executable, os.path.join(HERE, 'cllg_tei_to_tess.py'), os.path.join(a.src, r['file']), dest,
               '--tag', r['tag']]
        if r['parts']:
            cmd += ['--parts-dir', a.out]
        p = subprocess.run(cmd, capture_output=True, text=True)
        m = re.search(r'RESULT mode=(\S+) lines=(\d+) tokens=(\d+) src_letters=\d+ out_letters=\d+ ratio=(\S+) dups=(\d+) parts=(\d+)',
                      p.stdout)
        fields = [r['stem'], str(p.returncode)] + (list(m.groups()) if m else ['-', '0', '0', '0', '0', '0'])
        print('\t'.join(fields), (p.stderr.strip().splitlines() or [''])[-1][:120], flush=True)
        if a.report:
            with open(a.report, 'a', encoding='utf-8') as fh:
                fh.write('\t'.join(fields) + '\n')
        worst = max(worst, p.returncode if p.returncode in (1, 2) else (1 if p.returncode else 0))
    sys.exit(worst)


if __name__ == '__main__':
    main()
