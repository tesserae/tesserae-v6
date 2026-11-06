#!/usr/bin/env python3
"""Re-measure every aligned file in a staging folder against the current corpus: coverage,
units, source lines per unit, the proper-name check, the length correlation per unit and
the rival-unit test (chapter_common.py). One line per file, plus a TSV for the report.

Run it again on the folder you are about to install (a corpus text may have changed since the
files were built), and run it on the production folder before and after an install to compare.

    measure_staging.py DIR [OUT.tsv]
"""
import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import proper_names as V                                                     # noqa: E402
from chapter_common import load_work, unit_length_correlation, rival_check   # noqa: E402

folder = sys.argv[1]
rows = []
for path in sorted(glob.glob(os.path.join(folder, '*.json'))):
    d = json.load(open(path))
    lang, stem = d['tess_work'].split('/')
    refs, src, _ = load_work(lang, stem)
    if not refs:
        print(f'{os.path.basename(path)}: no such text in the corpus')
        continue
    r2u = {r: u for r, u in d['ref_to_unit'].items() if r in src}
    pairs = [(src[r], d['units'][u]) for r, u in r2u.items()]
    hit, n = V.score(pairs, lang, sample=800)
    corr = unit_length_correlation(d['units'], r2u, src)
    rv, rn = rival_check(lang, d['units'], r2u, src)
    row = [d['tess_work'], f'{len(r2u) / len(refs):.3f}', len(r2u), len(refs), len(d['units']),
           f'{len(r2u) / max(1, len(d["units"])):.1f}', '' if hit is None else f'{hit:.3f}', n,
           '' if corr is None else corr, '' if rv is None else f'{rv:.2f}', rn,
           (d.get('sources') or [{}])[0].get('translator', ''), (d.get('sources') or [{}])[0].get('year', ''),
           d.get('alignment_confidence', ''), d.get('verified_by', '')]
    rows.append(row)
    print('\t'.join(str(x) for x in row[:11]))
if len(sys.argv) > 2:
    with open(sys.argv[2], 'w') as f:
        f.write('work\tcoverage\ttranslated\trefs\tunits\tlines_per_unit\tnames\tnames_n\tlength_corr\trival\trival_n\ttranslator\tyear\tconfidence\tverified_by\n')
        for r in rows:
            f.write('\t'.join(str(x) for x in r) + '\n')
