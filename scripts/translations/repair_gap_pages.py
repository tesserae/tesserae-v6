"""Fill every translation gap from the dropped pages of the source scan.

repair_book_openings.py recovers the headerless first page of each book.
The Silvae lost far more than openings: its running headers carry two
roman numerals ("SILVAE, I. II. 42-65"), the OCR mangles them beyond the
contiguity repair, and the aligner rightly dropped what it could not
reconcile, leaving mid-poem holes and four whole poems untranslated. The
English of every dropped page is still in the scan, between pages that did
align.

So this pass works gap by gap. For each maximal run of untranslated lines,
the region between the surrounding aligned units is cut from the source,
split at page boundaries, and reduced to its English pages (the boundary
units' own pages, recognized by normalized containment, are excluded; so
are Latin facing pages, by stopword ratio). A one-page gap gets that page.
A multi-page gap distributes its lines across the pages in proportion to
their length, which is the same within-book fallback the aligners
themselves use, and the served work is already marked approximate. Proper
names shared between the gap's Latin and the recovered English are checked
before anything is written, and a gap that fails is skipped and printed.

Usage:
    python scripts/translations/repair_gap_pages.py \
        --json data/translations/la__statius.silvae.json \
        --tess texts/la/statius.silvae.tess \
        --src  ~/perseus_trans/statius_src/statiusstat01statuoft.txt \
        --out  /tmp/la__statius.silvae.json
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from repair_book_openings import (collapse, collapse_with_map, norm,
                                  norm_with_map, find_in, tess_refs,
                                  english_ratio, page_chunks)
import proper_names as V

MAX_REGION = 60000


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--json', required=True)
    ap.add_argument('--tess', required=True)
    ap.add_argument('--src', action='append', required=True)
    ap.add_argument('--out', required=True)
    args = ap.parse_args()

    data = json.load(open(args.json))
    lang = data.get('language', 'la')
    refs = tess_refs(args.tess)
    covered = set(data['ref_to_unit'])

    sources = []
    for s in args.src:
        raw = open(os.path.expanduser(s), errors='ignore').read()
        col, omap = collapse_with_map(raw)
        ncol, nmap = norm_with_map(raw)
        sources.append((raw, col, omap, ncol, nmap))

    def locate(needle):
        for raw, col, omap, ncol, nmap in sources:
            i = find_in(col, needle)
            if i != -1:
                return raw, omap[min(i, len(omap) - 1)]
            jj = ncol.find(norm(needle)[:24])
            if jj != -1:
                return raw, nmap[min(jj, len(nmap) - 1)]
        return None, -1

    # maximal gaps in tess order
    gaps, cur = [], []
    for r in refs:
        if r[0] in covered:
            if cur:
                gaps.append(cur)
                cur = []
        else:
            cur.append(r)
    if cur:
        gaps.append(cur)

    repaired = skipped = new_lines = 0
    for gap in gaps:
        label = f"{'.'.join(str(n) for n in gap[0][1])}-{gap[-1][1][-1]}"
        # boundary units
        first_pos = refs.index(gap[0])
        prev_unit = next_unit = None
        for j in range(first_pos - 1, -1, -1):
            if refs[j][0] in covered:
                prev_unit = data['units'][data['ref_to_unit'][refs[j][0]]]
                break
        last_pos = refs.index(gap[-1])
        for j in range(last_pos + 1, len(refs)):
            if refs[j][0] in covered:
                next_unit = data['units'][data['ref_to_unit'][refs[j][0]]]
                break
        if next_unit is None and prev_unit is None:
            skipped += 1
            print(f'  skip {label}: no aligned neighbours')
            continue
        raw_r, right = (None, -1) if next_unit is None else locate(next_unit)
        raw_l, left = (None, -1) if prev_unit is None else locate(prev_unit)
        if right == -1 and left == -1:
            skipped += 1
            print(f'  skip {label}: neighbours not found in source')
            continue
        if right == -1:
            raw, start, end = raw_l, left, min(left + MAX_REGION, len(raw_l))
        elif left == -1:
            raw, start, end = raw_r, max(0, right - MAX_REGION), right
        elif raw_l is not raw_r or left >= right:
            skipped += 1
            print(f'  skip {label}: neighbours disagree on location')
            continue
        else:
            raw, start, end = raw_l, left, right
        if end - start > MAX_REGION:
            skipped += 1
            print(f'  skip {label}: region too large ({end - start} chars)')
            continue
        chunks = page_chunks(raw[start:end])
        pages = []
        nprev = norm(prev_unit) if prev_unit else ''
        for c in chunks:
            if english_ratio(c) < 0.22 or len(c.split()) < 15:
                continue
            if nprev and norm(c)[:40] and norm(c)[:40] in nprev:
                continue                     # the boundary unit's own page
            pages.append(c)
        if not pages:
            skipped += 1
            print(f'  skip {label}: no English pages in region')
            continue
        # proper-name check across the whole gap
        stems = set()
        for p in pages:
            stems |= V.english_stems(p)
        hits = total = 0
        for _, _, latin in gap:
            for _, c in V.names_in(latin, lang):
                total += 1
                cn = norm(c)
                if c in stems or any(c[:5] == s[:5] or cn[:4] == norm(s)[:4]
                                     for s in stems):
                    hits += 1
        if total >= 3 and hits == 0:
            skipped += 1
            print(f'  skip {label}: 0/{total} proper names matched')
            continue
        # distribute gap lines across pages by cumulative word share
        words = [len(p.split()) for p in pages]
        tot_w = sum(words)
        bounds, acc = [], 0
        for w in words:
            acc += w
            bounds.append(acc / tot_w)
        base = len(data['units'])
        for p in pages:
            data['units'].append(p)
        n = len(gap)
        for i, r in enumerate(gap):
            share = (i + 0.5) / n
            page_i = next(k for k, b in enumerate(bounds) if share <= b)
            data['ref_to_unit'][r[0]] = base + page_i
        repaired += 1
        new_lines += n
        print(f'  {label}: {n} lines <- {len(pages)} page(s), '
              f'{tot_w} words (names {hits}/{total})')

    data['n_translated'] = len(data['ref_to_unit'])
    data['n_units_stored'] = len(data['units'])
    if data.get('n_tess_refs'):
        data['coverage'] = round(data['n_translated'] / data['n_tess_refs'], 4)
    data.setdefault('opening_repair', {})
    data['gap_repair'] = {'gaps_filled': repaired, 'gaps_skipped': skipped,
                          'lines_recovered': new_lines}
    json.dump(data, open(args.out, 'w'), ensure_ascii=False)
    print(f'{os.path.basename(args.json)}: {repaired} gaps filled '
          f'({new_lines} lines), {skipped} skipped, '
          f'coverage now {data["coverage"]}')


if __name__ == '__main__':
    main()
