#!/usr/bin/env python3
"""Second check of an aligned translation file: length correlation.

Do longer source lines get longer English? Computes Pearson r between the
character lengths of each source line and of the English unit it is assigned
(units shared by several source lines are compared with the summed length of
those lines). Needs no proper names.

Usage: length_check.py TRANSLATION.json TESS_FILE
"""
import json
import math
import re
import sys


def main():
    doc = json.load(open(sys.argv[1], encoding='utf-8'))
    lat = {}
    for line in open(sys.argv[2], encoding='utf-8'):
        m = re.match(r'^<([^>]+)>\s*(.*)', line.rstrip('\n'))
        if m:
            lat[m.group(1)] = len(m.group(2))
    by_unit = {}
    for ref, u in doc['ref_to_unit'].items():
        if ref in lat:
            by_unit.setdefault(u, []).append(lat[ref])
    xs = [sum(v) for v in by_unit.values()]
    ys = [len(doc['units'][u]) for u in by_unit]
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    r = sxy / math.sqrt(sxx * syy) if sxx and syy else float('nan')
    print(f'{sys.argv[1].split("/")[-1]}: {n} units, length correlation r = {r:.3f}')


if __name__ == '__main__':
    main()
