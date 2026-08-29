"""Re-segment the Silvae translation from the source scan.

The June alignment of the Silvae glued badly: its running headers carry two
roman numerals ("SILVAE, I. II. 42-65"), the OCR mangles them, and every
unreconciled page was fused into the previous unit. The result in
production: 82 of 87 units exceed 500 words (the largest is 3,090 words for
23 Latin lines), each mixing its English page with Latin facing pages,
apparatus, and the English of lines recorded as untranslated. Four whole
poems have no translation at all.

The units themselves are still good anchors: all 87 locate in the scan, in
order. So this pass rebuilds the whole work from those anchors. The scan
between consecutive anchor positions is page-chunked, reduced to its
English pages, and the Latin lines between the anchors' start lines are
distributed across those pages in proportion to page length, the same
within-book fallback the aligners use, on a work already served as
approximate. The stretch before the first anchor and after the last are
bounded by page-count expectation so nothing outside the Silvae leaks in.

Known noise, accepted and logged: the five prose book-prefaces of the
Silvae have no lines in the corpus text, so their English smears into the
pages at book boundaries. Per-poem proper-name checks are printed so the
worst assignments are visible rather than silent.

Usage:
    python scripts/translations/realign_silvae.py \
        --json data/translations/la__statius.silvae.json \
        --tess texts/la/statius.silvae.tess \
        --src  ~/perseus_trans/statius_src/statiusstat01statuoft.txt \
        --out  /tmp/la__statius.silvae.json
"""
import argparse
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from repair_book_openings import (collapse, collapse_with_map, norm,
                                  norm_with_map, find_in, tess_refs,
                                  english_ratio, page_chunks)
import proper_names as V


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--json', required=True)
    ap.add_argument('--tess', required=True)
    ap.add_argument('--src', required=True)
    ap.add_argument('--out', required=True)
    args = ap.parse_args()

    data = json.load(open(args.json))
    lang = data.get('language', 'la')
    refs = tess_refs(args.tess)          # tess order
    ref_pos = {r[0]: i for i, r in enumerate(refs)}

    raw = open(os.path.expanduser(args.src), errors='ignore').read()
    col, omap = collapse_with_map(raw)
    ncol, nmap = norm_with_map(raw)

    def locate(needle):
        i = find_in(col, needle)
        if i != -1:
            return omap[min(i, len(omap) - 1)]
        j = ncol.find(norm(needle)[:24])
        return nmap[min(j, len(nmap) - 1)] if j != -1 else -1

    # Anchors: (tess index of the unit's first covered ref, source position)
    unit_first = {}
    for r, u in data['ref_to_unit'].items():
        if u not in unit_first or ref_pos[r] < ref_pos[unit_first[u]]:
            unit_first[u] = r
    anchors = []
    for u, first_ref in unit_first.items():
        pos = locate(data['units'][u])
        if pos != -1:
            anchors.append((ref_pos[first_ref], pos))
    anchors.sort()
    print(f'{len(anchors)} anchors of {len(data["units"])} units')

    # keep only source-monotonic anchors
    mono = []
    for t, p in anchors:
        if not mono or p > mono[-1][1]:
            mono.append((t, p))
    anchors = mono

    PAGE = 2400                             # rough chars per printed page

    def english_pages(lo, hi):
        return [c for c in page_chunks(raw[lo:hi])
                if english_ratio(c) >= 0.22 and len(c.split()) >= 15]

    new_units, new_map = [], {}

    def assign(line_refs, pages):
        if not line_refs or not pages:
            return
        words = [len(p.split()) for p in pages]
        tot = sum(words)
        bounds, acc = [], 0
        for w in words:
            acc += w
            bounds.append(acc / tot)
        base = len(new_units)
        new_units.extend(pages)
        n = len(line_refs)
        for i, r in enumerate(line_refs):
            share = (i + 0.5) / n
            k = next(j for j, b in enumerate(bounds) if share <= b)
            new_map[r[0]] = base + k

    # before the first anchor
    t0, p0 = anchors[0]
    if t0 > 0:
        lead = refs[:t0]
        span = min((math.ceil(len(lead) / 22) + 1) * PAGE, p0)
        pages = english_pages(p0 - span, p0)
        assign(lead, pages[-(math.ceil(len(lead) / 22) + 1):])

    # between anchors
    for (ta, pa), (tb, pb) in zip(anchors, anchors[1:]):
        assign(refs[ta:tb], english_pages(pa, pb))

    # after the last anchor
    tl, pl = anchors[-1]
    tail = refs[tl:]
    span = (math.ceil(len(tail) / 22) + 2) * PAGE
    pages = english_pages(pl, min(pl + span, len(raw)))
    assign(tail, pages[:math.ceil(len(tail) / 22) + 1])

    # per-poem proper-name report
    import collections
    by_poem = collections.defaultdict(list)
    for r in refs:
        by_poem[r[1][:2]].append(r)
    weak = []
    for poem, prs in sorted(by_poem.items()):
        stems = set()
        for r in prs:
            if r[0] in new_map:
                stems |= V.english_stems(new_units[new_map[r[0]]])
        hits = total = 0
        for _, _, latin in prs:
            for _, c in V.names_in(latin, lang):
                total += 1
                cn = norm(c)
                if c in stems or any(c[:5] == s[:5] or cn[:4] == norm(s)[:4]
                                     for s in stems):
                    hits += 1
        cov = sum(1 for r in prs if r[0] in new_map)
        tag = ''
        if total >= 4 and hits / total < 0.25:
            tag = '  <-- WEAK'
            weak.append(poem)
        print(f'  {poem[0]}.{poem[1]}: {cov}/{len(prs)} lines, '
              f'names {hits}/{total}{tag}')

    data['units'] = new_units
    data['ref_to_unit'] = new_map
    data['n_translated'] = len(new_map)
    data['n_units_stored'] = len(new_units)
    data['coverage'] = round(len(new_map) / data['n_tess_refs'], 4)
    data['realigned'] = {'anchors': len(anchors),
                         'weak_poems': [f'{a}.{b}' for a, b in weak]}
    json.dump(data, open(args.out, 'w'), ensure_ascii=False)
    print(f'coverage now {data["coverage"]}, units {len(new_units)}, '
          f'weak poems: {len(weak)}')


if __name__ == '__main__':
    main()
