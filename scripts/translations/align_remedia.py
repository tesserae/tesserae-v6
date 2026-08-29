#!/usr/bin/env python3
"""Ovid, Remedia Amoris, from Riley's Bohn prose (PG 47678, clean text).

814 lines. Riley's paragraphs carry no verse numbers, but his footnotes
do: each inline anchor [1202] resolves, in the footnote block, to
"--Ver. 17", so every anchored paragraph is dated by the verses its
notes annotate -- the same trick align_ovid.py used for the Fasti, minus
the OCR. A paragraph's span runs from the end of the previous one to its
last-anchored verse (or to the next paragraph's first anchor); the tail
paragraph runs to the poem's end. Verse numbers must be monotonic or the
offending anchor is ignored.

Usage:
    python scripts/translations/align_remedia.py \
        --src <pg47678.txt> --tess texts/la/ovid.remedia_amoris.tess \
        --out <la__ovid.remedia_amoris.json>
"""
import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import proper_names as V


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--src', required=True)
    ap.add_argument('--tess', required=True)
    ap.add_argument('--out', required=True)
    args = ap.parse_args()

    text = open(args.src, encoding='utf-8', errors='replace').read()
    # footnote block: anchor id -> verse
    verse_of = {}
    for m in re.finditer(r'\[Footnote (\d+):.*?--Ver\.\s*(\d+)', text, re.S):
        verse_of[m.group(1)] = int(m.group(2))

    body = text.split('*** START', 1)[-1].split('[Footnote', 1)[0]
    paras_raw = re.split(r'\n\s*\n', body)
    paras = []
    for p in paras_raw:
        t = re.sub(r'\s+', ' ', p).strip()
        if len(t.split()) < 15 or t.isupper():
            continue
        anchors = [verse_of[a] for a in re.findall(r'\[(\d+)\]', t)
                   if a in verse_of]
        mono = []
        for v in anchors:
            if not mono or v >= mono[-1]:
                mono.append(v)
        paras.append((mono, re.sub(r'\[\d+\]', '', t)))

    refs, lat = [], {}
    for line in open(args.tess, encoding='utf-8', errors='replace'):
        m = re.match(r'^<(ov\. red\. am\. (\d+))>\s*(.*)', line)
        if m:
            refs.append((m.group(1), int(m.group(2))))
            lat[m.group(1)] = m.group(3)
    maxv = max(n for _, n in refs)

    # spans: paragraph k covers (prev_end+1 .. its last anchor), except
    # the last covers to the end; a paragraph with no anchors extends to
    # the next paragraph's first anchor - 1
    # Gutenberg boilerplate and Riley's own preface precede the poem and
    # carry no verse anchors: nothing is served until the first anchored
    # paragraph (whose first note is Ver. 5)
    while paras and not paras[0][0]:
        paras.pop(0)
    spans = []
    prev_end = 0
    for k, (mono, t) in enumerate(paras):
        start = prev_end + 1
        if mono:
            end = mono[-1]
        else:
            nxt = next((mm[0] for mm, _ in paras[k + 1:] if mm), maxv)
            end = max(start, nxt - 1)
        if k == len(paras) - 1:
            end = maxv
        if end < start:
            continue
        spans.append((start, end, t))
        prev_end = end

    mapping, pairs = {}, []
    for start, end, t in spans:
        for ref, n in refs:
            if start <= n <= end and ref not in mapping:
                mapping[ref] = t
                pairs.append((lat[ref], t))
    cov = len(mapping) / len(refs)
    hit, n = V.score(pairs, 'la', sample=500)
    ulist, idx, ref2u = [], {}, {}
    for ref, txt in mapping.items():
        if txt not in idx:
            idx[txt] = len(ulist)
            ulist.append(txt)
        ref2u[ref] = idx[txt]
    print(f'remedia: cov {cov:.4f} ({len(mapping)}/{len(refs)}) units '
          f'{len(ulist)} names {hit}/{n}')
    if hit is None or hit < 0.25:
        print('REJECTED')
        return
    json.dump({
        'tess_work': 'la/ovid.remedia_amoris', 'language': 'la',
        'n_tess_refs': len(refs), 'n_translated': len(mapping),
        'coverage': round(cov, 4),
        'mean_source_lines_per_translation_unit':
            round(len(mapping) / max(1, len(ulist)), 1),
        'alignment_confidence': 'medium', 'approximate': True,
        'name_check_hit_rate': hit, 'name_check_n': n,
        'verified_by': 'names',
        'sources': [{'translator': 'Henry T. Riley', 'year': 1852,
                     'title': 'Remedia Amoris, literally translated (Bohn)',
                     'publisher': 'Project Gutenberg 47678',
                     'mode': 'footnote-anchored paragraphs',
                     'ref_composition': ['verse span'],
                     'source_url': 'https://www.gutenberg.org/ebooks/47678'}],
        'license': 'Public domain: Bohn translation, 1852. '
                   'Text from Project Gutenberg.',
        'attribution': 'H. T. Riley (Bohn), via Project Gutenberg',
        'n_units_stored': len(ulist), 'units': ulist, 'ref_to_unit': ref2u,
    }, open(args.out, 'w'), ensure_ascii=False)


if __name__ == '__main__':
    main()
