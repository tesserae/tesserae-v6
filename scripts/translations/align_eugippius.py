#!/usr/bin/env python3
"""Eugippius, Vita sancti Severini, from Robinson's Harvard translation
of 1914 (Internet Archive scan) — chapter-keyed exact.

179 corpus lines, refs chapter.section; Robinson prints CHAPTER N
headings (OCR romans read through the usual substitutions). Sections
within a chapter serve the chapter's English. The strict-successor chain
with a two-step resync guards against page-furniture numerals.

Usage:
    python scripts/translations/align_eugippius.py \
        --src <lifeofsaintsever00eugi_djvu.txt> \
        --tess texts/la/eugippius.vita_sancti_severini.tess --out <json>
"""
import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import proper_names as V


def roman_to_int(s):
    s = (s.upper().replace('1', 'I').replace('L', 'I').replace('N', 'II')
         .replace('T', 'I').replace('U', 'V').replace('Y', 'V'))
    s = re.sub(r'[^IVX]', '', s)
    vals = {'I': 1, 'V': 5, 'X': 10}
    total, prev = 0, 0
    for ch in reversed(s):
        v = vals[ch]
        total += v if v >= prev else -v
        prev = max(prev, v)
    return total or None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--src', required=True)
    ap.add_argument('--tess', required=True)
    ap.add_argument('--out', required=True)
    args = ap.parse_args()

    chapters, cur, buf = {}, None, []

    def flush():
        if cur and buf:
            t = ' '.join(buf)
            t = re.sub(r'\s+', ' ', re.sub(r'[|/*^]+', '', t)).strip()
            if len(t.split()) >= 10:
                chapters[cur] = t
    for ln in open(args.src, encoding='utf-8', errors='replace'):
        s = ln.strip()
        m = re.match(r'^CHAPTER\s+(\S{1,6})\s*$', s)
        if m:
            n = roman_to_int(m.group(1))
            expect = 1 if cur is None else cur + 1
            if n is not None and expect <= n <= expect + 2:
                flush()
                cur, buf = n, []
                continue
        if re.match(r'^(NOTES|THE LETTER OF|INDEX)', s):
            flush()
            cur = None
            continue
        if cur is not None and s and not re.fullmatch(r'\d+', s):
            buf.append(s)
    flush()

    refs, lat = [], {}
    for line in open(args.tess, encoding='utf-8', errors='replace'):
        m = re.match(r'^<(eugippius\. vita_s_severini (\d+)\.\d+)>\s*(.*)',
                     line)
        if m:
            refs.append((m.group(1), int(m.group(2))))
            lat[m.group(1)] = m.group(3)
    mapping, pairs = {}, []
    for ref, c in refs:
        t = chapters.get(c)
        if t:
            mapping[ref] = t
            pairs.append((lat[ref], t))
    cov = len(mapping) / len(refs) if refs else 0
    hit, n = V.score(pairs, 'la', sample=300)
    ulist, idx, ref2u = [], {}, {}
    for ref, txt in mapping.items():
        if txt not in idx:
            idx[txt] = len(ulist)
            ulist.append(txt)
        ref2u[ref] = idx[txt]
    print(f'eugippius vita: cov {cov:.4f} ({len(mapping)}/{len(refs)}) '
          f'units {len(ulist)} names {hit}/{n}')
    if hit is None or hit < 0.25:
        print('REJECTED')
        return
    json.dump({
        'tess_work': 'la/eugippius.vita_sancti_severini', 'language': 'la',
        'n_tess_refs': len(refs), 'n_translated': len(mapping),
        'coverage': round(cov, 4),
        'mean_source_lines_per_translation_unit':
            round(len(mapping) / max(1, len(ulist)), 1),
        'alignment_confidence': 'high' if hit >= 0.5 else 'medium',
        'name_check_hit_rate': hit, 'name_check_n': n,
        'verified_by': 'names',
        'sources': [{'translator': 'George W. Robinson', 'year': 1914,
                     'title': 'The Life of Saint Severinus',
                     'publisher': 'Harvard University Press',
                     'mode': 'exact', 'ref_composition': ['chapter'],
                     'source_url': 'https://archive.org/details/'
                                   'lifeofsaintsever00eugi'}],
        'license': 'Public domain: published 1914. '
                   'Text from the Internet Archive scan.',
        'attribution': 'G. W. Robinson (1914), via the Internet Archive',
        'n_units_stored': len(ulist), 'units': ulist, 'ref_to_unit': ref2u,
    }, open(args.out, 'w'), ensure_ascii=False)


if __name__ == '__main__':
    main()
