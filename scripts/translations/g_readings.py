#!/usr/bin/env python3
"""Five passages per aligned file for reading (Part G, 2026-10-25): a seeded random draw of our references, each
printed with the start of the Greek line and the start of its unit's English, so a reader can check the pairing
against the Greek. For a merged file two extra references are drawn from the units of the first source.

    g_readings.py FILE.json [FILE.json ...] > passages_read.txt
"""
import json
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from g_common import load_work   # noqa: E402

for path in sys.argv[1:]:
    d = json.load(open(path))
    lang, stem = d['tess_work'].split('/')
    refs, src, _ = load_work(lang, stem)
    paired = [r for r in refs if r in d['ref_to_unit']]
    rnd = random.Random(f'part-g-{stem}')
    pick = rnd.sample(paired, min(5, len(paired)))
    us = d.get('unit_sources')
    if us:
        first = [r for r in paired if us[d['ref_to_unit'][r]] == 0]
        pick += rnd.sample(first, min(2, len(first)))
    print(f'=== {d["tess_work"]}  ({len(paired)}/{len(refs)} paired, source(s): ' + '; '.join(f"{s.get('translator')} {s.get('year')}" for s in d['sources']) + ')')
    for r in pick:
        u = d['ref_to_unit'][r]
        print(f'[{r}] unit {u}' + (f' (source {us[u]})' if us else ''))
        print('  GR:', src[r][:170])
        print('  EN:', d['units'][u][:230])
