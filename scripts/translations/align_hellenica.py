#!/usr/bin/env python3
"""Xenophon, Hellenica: Brownson's Loeb translation (1918 to 1921) aligned to
texts/grc/xenophon.hellenica.tess.

Source: PerseusDL/canonical-greekLit, tlg0032.tlg001.perseus-eng2.xml (CC BY-SA
4.0 TEI over a translation published before 1931). Perseus cites the English by
book.chapter.section exactly as it cites the Greek, so the alignment is exact:
section n of the English belongs to section n of the Greek, with no search.
The script refuses to write unless every Greek reference is matched, then runs
the two independent checks the other aligners report (proper names, and the
correlation of Greek and English lengths).

    align_hellenica.py ENG.xml TESS OUT_DIR
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import proper_names as V                       # noqa: E402
import tei_extract_base as E                   # noqa: E402
from align_perseus import length_correlation   # noqa: E402
from write_aligned import tess_refs, write_aligned   # noqa: E402

eng_path, tess_path, out_dir = sys.argv[1:4]
meta, chunks = E.extract(eng_path)
assert meta['ref_labels'] == ['book', 'chapter', 'section'], meta['ref_labels']
by_ref = {}
for c in chunks:
    a = c['anchors']
    ref = f"{a['book']}.{a['chapter']}.{a['section']}"
    by_ref[ref] = by_ref.get(ref, '') + (' ' if ref in by_ref else '') + c['text']

src = {}
for line in open(tess_path, encoding='utf-8'):
    ref, text = line.rstrip('\n').split('\t', 1)
    src[ref[1:-1]] = text
refs = tess_refs(tess_path)
units, ref_to_unit, pairs, missing = [], {}, [], []
for r in refs:
    tail = r.split()[-1]
    if tail not in by_ref:
        missing.append(r)
        continue
    ref_to_unit[r] = len(units)
    units.append(by_ref[tail])
    pairs.append((src[r], by_ref[tail]))
extra = set(by_ref) - {r.split()[-1] for r in refs}
hit, n = V.score(pairs, 'grc')
corr = length_correlation(pairs)
print(f'refs {len(refs)}  translated {len(ref_to_unit)}  missing {len(missing)}  '
      f'English sections not in Greek {len(extra)}')
print(f'name check {hit} on {n}; length correlation {corr}')
if missing or extra:
    sys.exit(f'refuse to write: missing {missing[:5]} extra {sorted(extra)[:5]}')

path = write_aligned(
    out_dir, 'grc', 'xenophon.hellenica', units, ref_to_unit,
    attribution='Perseus Digital Library, Tufts University',
    license='CC BY-SA 4.0 (Perseus Digital Library TEI); underlying translation '
            'is US public domain (published before 1931)',
    sources=[{
        'cts_urn': 'urn:cts:greekLit:tlg0032.tlg001.perseus-eng2',
        'translator': 'Carleton L. Brownson', 'year': 1921,
        'publisher': 'Harvard University Press', 'title': 'Hellenica',
        'mode': 'exact', 'ref_composition': ['book', 'chapter', 'section'],
        'mean_span_source_lines': 1.0, 'our_ref_truncation': 0,
        'their_ref_aggregation': 0,
        'pd_reason': 'Loeb volumes 1918 to 1921, US public domain',
        'source_file': 'canonical-greekLit/data/tlg0032/tlg001/'
                       'tlg0032.tlg001.perseus-eng2.xml'}],
    confidence='high', approximate=False, tess_refs=refs,
    name_check={'name_check_hit_rate': hit, 'name_check_n': n},
    verified_by='exact citation match; proper names; length correlation '
                f'{corr:.3f}' if corr is not None else 'exact citation match')
print('wrote', path)
