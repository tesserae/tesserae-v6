#!/usr/bin/env python3
"""Five passages per re-aligned Plato file for reading (Part H, 2026-10-25), as g_readings.py does for Part G,
plus one recovered tail: the unit that grew most against the installed file, with the added words shown.

    h_readings.py INSTALLED_DIR FILE.json [FILE.json ...] > passages_read.txt
"""
import json
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from g_common import load_work   # noqa: E402

inst_dir = sys.argv[1]
for path in sys.argv[2:]:
    d = json.load(open(path))
    lang, stem = d['tess_work'].split('/')
    refs, src, _ = load_work(lang, stem)
    paired = [r for r in refs if r in d['ref_to_unit']]
    pick = random.Random(f'part-h-{stem}').sample(paired, min(5, len(paired)))
    print(f'=== {d["tess_work"]}  ({len(paired)}/{len(refs)} paired, {d["sources"][0].get("translator")} {d["sources"][0].get("year")})')
    for r in pick:
        u = d['ref_to_unit'][r]
        print(f'[{r}] unit {u}')
        print('  GR:', src[r][:170])
        print('  EN:', d['units'][u][:230])
    old = json.load(open(os.path.join(inst_dir, f'{lang}__{stem}.json')))
    best = None
    for r in paired:
        n = d['units'][d['ref_to_unit'][r]]
        o = old['units'][old['ref_to_unit'][r]] if r in old['ref_to_unit'] else ''
        g = len(n.split()) - len(o.split())
        if g > 0 and (best is None or g > best[0]):
            best = (g, r, o, n)
    if best:
        g, r, o, n = best
        print(f'[recovered tail, {r}] +{g} words')
        print('  GR end:', src[r][-170:])
        print('  EN old end:', o[-150:])
        print('  EN new end:', n[-230:])
