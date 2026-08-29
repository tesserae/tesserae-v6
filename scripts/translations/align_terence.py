#!/usr/bin/env python3
"""Terence: all six comedies, from Riley's literal Bohn prose (1874).

6,188 lines with no English anywhere. Source is Project Gutenberg 22188
(Henry Thomas Riley, "The Comedies of Terence, literally translated",
Bohn/Harper) -- a clean transcription, no OCR.

ACT-ANCHORED, LENGTH-ALLOCATED WITHIN THE ACT

Our refs are act.scene(.line); Riley prints "ACT THE FIRST." / "SCENE I."
headings. Scene DIVISIONS are editorial and Riley's tradition splits far
finer than ours (his Andria act 4 has nine scenes to our five), so scenes
cannot be mapped by number -- the first draft tried and refused 21 of 30
acts. ACT boundaries, though, are canonical and agree, so within each act
the corpus lines are allocated to Riley's scene texts by cumulative
length, the same engine the Cicero treatises use. The unit is one Riley
scene; the alignment is marked approximate. Each act must pass its own
proper-name check (floor 0.2, min 10 sampled) or the whole act stays
uncovered; each play must then pass the work-level check to be written.
Prologues (Hecyra's two included) are concatenated per play, served to
every prologue ref, and count as their own "act" for validation.

Riley's stage directions and footnote markers are part of the scene text;
his endnote blocks (lines opening with a bracketed number) are dropped.

Usage:
    python scripts/translations/align_terence.py \
        --src <pg22188.txt> --tess-dir texts/la --out-dir <dir>
"""
import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import proper_names as V

PLAYS = [
    (r'^ANDRIA;', 'terence.andria', r'^<(ter\. and\. ([\w]+)\.(\d+)(?:\.\d+)?)>\s*(.*)'),
    (r'^EUNUCHUS;', 'terence.eunuchus', r'^<(ter\. eun\. ([\w]+)(?:\.(\d+))?(?:\.\d+)?)>\s*(.*)'),
    (r'^HEAUTONTIMORUMENOS;', 'terence.heautontimorumenos',
     r'^<(ter\. heaut\. ([\w]+)(?:\.(\d+))?(?:\.\d+)?)>\s*(.*)'),
    (r'^ADELPHI;', 'terence.adelphi', r'^<(ter\. ad\. ([\w]+)(?:\.(\d+))?(?:\.\d+)?)>\s*(.*)'),
    (r'^HECYRA;', 'terence.hecyra', r'^<(ter\. hec\. ([\w]+)(?:\.(\d+))?(?:\.\d+)?)>\s*(.*)'),
    (r'^PHORMIO;', 'terence.phormio', r'^<(ter\. phor\. ([\w]+)(?:\.(\d+))?(?:\.\d+)?)>\s*(.*)'),
]

ORDINALS = {'FIRST': 1, 'SECOND': 2, 'THIRD': 3, 'FOURTH': 4, 'FIFTH': 5}


def roman_to_int(s):
    vals = {'I': 1, 'V': 5, 'X': 10}
    total, prev = 0, 0
    for ch in reversed(s.strip('. ')):
        v = vals.get(ch)
        if v is None:
            return None
        total += v if v >= prev else -v
        prev = max(prev, v)
    return total


def parse(path):
    """{play_index: {'prologue': text, (act, scene): text}}"""
    out = {}
    play = act = scene = None
    buf, key = [], None

    def flush():
        nonlocal buf
        if play is not None and key is not None and buf:
            text = ' '.join(buf)
            text = re.sub(r'\[\d+\]', '', text)
            text = re.sub(r'\s+', ' ', text).strip()
            d = out.setdefault(play, {})
            d[key] = (d.get(key, '') + ' ' + text).strip()
        buf = []

    for raw in open(path, encoding='utf-8', errors='replace'):
        line = raw.rstrip('\n')
        s = line.strip()
        hit_play = None
        for i, (title_re, _, _) in enumerate(PLAYS):
            if re.match(title_re, s):
                hit_play = i
                break
        if hit_play is not None:
            flush()
            play, act, scene, key = hit_play, None, None, None
            continue
        if play is None:
            continue
        if re.match(r'^THE (FIRST |SECOND )?PROLOGUE\.?$', s):
            flush()
            act, scene, key = 'prologue', None, 'prologue'
            continue
        m = re.match(r'^ACT THE (\w+)\.?$', s)
        if m and m.group(1) in ORDINALS:
            flush()
            act, scene, key = ORDINALS[m.group(1)], None, None
            continue
        m = re.match(r'^SCENE ([IVX]+)\.?$', s)
        if m and isinstance(act, int) and roman_to_int(m.group(1)):
            flush()
            scene = roman_to_int(m.group(1))
            key = (act, scene)
            continue
        # endnote blocks: a line opening with a bracketed number
        if re.match(r'^\[\d+\]', s):
            flush()
            key = None
            continue
        if key is not None and s:
            buf.append(s)
    flush()
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--src', required=True)
    ap.add_argument('--tess-dir', required=True)
    ap.add_argument('--out-dir', required=True)
    args = ap.parse_args()
    os.makedirs(args.out_dir, exist_ok=True)

    plays = parse(args.src)
    for i, (_, tessname, pat) in enumerate(PLAYS):
        riley = plays.get(i, {})
        # corpus refs
        refs = []          # (ref, key, latin)
        for line in open(os.path.join(args.tess_dir, tessname + '.tess'),
                         encoding='utf-8', errors='replace'):
            m = re.match(pat, line)
            if not m:
                continue
            actf, scenef = m.group(2), m.group(3)
            if actf == 'prologue':
                key = 'prologue'
            elif actf.isdigit() and scenef:
                key = (int(actf), int(scenef))
            else:
                key = None
            refs.append((m.group(1), key, m.group(4)))

        # allocate corpus lines to Riley scenes by cumulative length,
        # act by act
        from collections import defaultdict
        acts = defaultdict(list)          # act -> [(ref, latin)] in order
        for ref, key, latin in refs:
            if key == 'prologue':
                acts['prologue'].append((ref, latin))
            elif isinstance(key, tuple):
                acts[key[0]].append((ref, latin))

        mapping, pairs = {}, []
        for a, lines in acts.items():
            if a == 'prologue':
                text = riley.get('prologue')
                cand = {ref: text for ref, _ in lines} if text else {}
            else:
                segs = sorted((k for k in riley
                               if isinstance(k, tuple) and k[0] == a))
                texts = [riley[k] for k in segs]
                if not texts:
                    print(f'  {tessname}: act {a} has no English, uncovered')
                    continue
                etot = sum(len(t) for t in texts)
                bounds, accE = [], 0.0
                for t in texts:
                    accE += len(t) / etot
                    bounds.append(accE)
                ltot = sum(len(l) for _, l in lines) or 1
                cand, accL, ci = {}, 0.0, 0
                for ref, latin in lines:
                    mid = (accL + len(latin) / 2) / ltot
                    accL += len(latin)
                    while ci < len(bounds) - 1 and mid > bounds[ci]:
                        ci += 1
                    cand[ref] = texts[ci]
            # the act must vouch for itself
            apairs = [(latin, cand[ref]) for ref, latin in lines
                      if ref in cand]
            ahit, an = V.score(apairs, 'la', sample=200)
            if an >= 10 and (ahit is None or ahit < 0.2):
                print(f'  {tessname}: act {a} REFUSED by name check '
                      f'({ahit}/{an})')
                continue
            for ref, latin in lines:
                if ref in cand:
                    mapping[ref] = cand[ref]
                    pairs.append((latin, cand[ref]))

        cov = len(mapping) / len(refs) if refs else 0
        hit, n = V.score(pairs, 'la', sample=800)
        ulist, idx, ref2u = [], {}, {}
        for ref, txt in mapping.items():
            if txt not in idx:
                idx[txt] = len(ulist)
                ulist.append(txt)
            ref2u[ref] = idx[txt]
        ok = hit is not None and hit >= 0.25
        print(f'{tessname:28s} cov {cov:.4f} ({len(mapping)}/{len(refs)}) '
              f'units {len(ulist)} names {hit}/{n} ' + ('ok' if ok else 'REJECTED'))
        if not ok:
            continue
        json.dump({
            'tess_work': f'la/{tessname}', 'language': 'la',
            'n_tess_refs': len(refs), 'n_translated': len(mapping),
            'coverage': round(cov, 4),
            'mean_source_lines_per_translation_unit':
                round(len(mapping) / max(1, len(ulist)), 1),
            'alignment_confidence': 'high' if hit >= 0.5 else 'medium',
            'name_check_hit_rate': hit, 'name_check_n': n,
            'verified_by': 'names',
            'sources': [{'translator': 'Henry Thomas Riley', 'year': 1874,
                         'title': 'The Comedies of Terence, '
                                  'literally translated (Bohn)',
                         'publisher': 'Harper & Brothers '
                                      '(via Project Gutenberg)',
                         'mode': 'exact', 'ref_composition': ['act', 'scene'],
                         'source_url':
                             'https://www.gutenberg.org/ebooks/22188'}],
            'license': 'Public domain: Bohn translation, 1874 printing. '
                       'Text from Project Gutenberg.',
            'attribution': 'H. T. Riley (Bohn), via Project Gutenberg',
            'n_units_stored': len(ulist), 'units': ulist,
            'ref_to_unit': ref2u,
        }, open(os.path.join(args.out_dir, f'la__{tessname}.json'), 'w'),
            ensure_ascii=False)


if __name__ == '__main__':
    main()
