#!/usr/bin/env python3
"""Juvenal and Persius, from Evans's literal Bohn prose (PG 50657).

4,509 lines with no English (all sixteen satires of Juvenal, all six of
Persius). The Gutenberg text is clean; each satire is a run of prose
paragraphs under its "SATIRE N." heading, closed by a FOOTNOTES: block.

Evans marks no line numbers, so within each satire the corpus lines are
allocated to his paragraphs by cumulative length -- the engine the
Terence and Cicero-treatise alignments use -- with the satire heading as
the exact anchor. The unit is one paragraph (~15-30 lines). Every satire
must pass its own proper-name check (floor 0.2, min 10 sampled) or it
stays uncovered; the work as a whole then passes the standard gate.

The volume prints the ARGUMENTS of all satires before the translations
and appends Sulpicia and the Lucilius fragments, so the two regions are
sliced by position: Juvenal's translation run is the SECOND run of
SATIRE headings, Persius' follows his PROLOGUE.

Usage:
    python scripts/translations/align_juvenal.py \
        --src <pg50657.txt> --tess-dir texts/la --out-dir <dir>
"""
import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import proper_names as V

ROMAN = {'I': 1, 'V': 5, 'X': 10, 'L': 50}


def roman_to_int(s):
    total, prev = 0, 0
    for ch in reversed(s.strip('. ').upper()):
        v = ROMAN.get(ch)
        if v is None:
            return None
        total += v if v >= prev else -v
        prev = max(prev, v)
    return total or None


def parse_satires(lines):
    """{satire_number: [paragraph texts]} from one author's region."""
    out, cur, buf, para = {}, None, [], []

    def close_para():
        if cur is not None and para:
            text = re.sub(r'\[\d+\]', '', ' '.join(para))
            text = re.sub(r'\s+', ' ', text).strip()
            if len(text.split()) >= 4:
                buf.append(text)
        del para[:]

    def close_sat():
        close_para()
        if cur is not None and buf:
            out[cur] = list(buf)
        del buf[:]
    in_argument = False
    for ln in lines:
        s = ln.strip()
        m = re.match(r'^SATIRE ([IVXL]+)\.?$', s)
        if m and roman_to_int(m.group(1)):
            close_sat()
            cur, in_argument = roman_to_int(m.group(1)), False
            continue
        if re.match(r'^FOOTNOTES:', s):
            close_sat()
            cur = None
            continue
        if re.match(r'^ARGUMENT\.?$', s):
            # Persius' satires carry their ARGUMENT inline, indented;
            # serving Evans's summary as translation is the Medicamina
            # failure, so everything indented after the heading is dropped
            in_argument = True
            continue
        if cur is None:
            continue
        if in_argument:
            if s and not ln.startswith((' ', '\t')):
                in_argument = False
            else:
                continue
        if not s:
            close_para()
            continue
        para.append(s)
    close_sat()
    return out


def allocate(work, tessname, sats, tess_dir, out_dir, translator_note):
    refs = []          # (ref, satire, latin) in order
    for line in open(os.path.join(tess_dir, tessname + '.tess'),
                     encoding='utf-8', errors='replace'):
        m = re.match(r'^<(' + work + r' (\d+)\.(\d+))>\s*(.*)', line)
        if m:
            refs.append((m.group(1), int(m.group(2)), m.group(4)))

    mapping, pairs = {}, []
    from collections import defaultdict
    per_sat = defaultdict(list)
    for ref, s, latin in refs:
        per_sat[s].append((ref, latin))
    for s, lines_ in per_sat.items():
        paras = sats.get(s)
        if not paras:
            print(f'  {tessname}: satire {s} has no English, uncovered')
            continue
        etot = sum(len(p) for p in paras)
        bounds, acc = [], 0.0
        for p in paras:
            acc += len(p) / etot
            bounds.append(acc)
        ltot = sum(len(l) for _, l in lines_) or 1
        cand, accL, ci = {}, 0.0, 0
        for ref, latin in lines_:
            mid = (accL + len(latin) / 2) / ltot
            accL += len(latin)
            while ci < len(bounds) - 1 and mid > bounds[ci]:
                ci += 1
            cand[ref] = paras[ci]
        apairs = [(latin, cand[ref]) for ref, latin in lines_ if ref in cand]
        ahit, an = V.score(apairs, 'la', sample=200)
        if an >= 10 and (ahit is None or ahit < 0.2):
            print(f'  {tessname}: satire {s} REFUSED by names ({ahit}/{an})')
            continue
        for ref, latin in lines_:
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
    ok = hit is not None and hit >= 0.25 and cov >= 0.5
    print(f'{tessname:24s} cov {cov:.4f} ({len(mapping)}/{len(refs)}) '
          f'units {len(ulist)} names {hit}/{n} ' + ('ok' if ok else 'REJECTED'))
    if not ok:
        return
    json.dump({
        'tess_work': f'la/{tessname}', 'language': 'la',
        'n_tess_refs': len(refs), 'n_translated': len(mapping),
        'coverage': round(cov, 4),
        'mean_source_lines_per_translation_unit':
            round(len(mapping) / max(1, len(ulist)), 1),
        'alignment_confidence': 'medium', 'approximate': True,
        'name_check_hit_rate': hit, 'name_check_n': n,
        'verified_by': 'names',
        'sources': [{'translator': translator_note, 'year': 1861,
                     'title': 'The Satires of Juvenal, Persius, Sulpicia '
                              'and Lucilius (Bohn)',
                     'publisher': 'Project Gutenberg 50657',
                     'mode': 'proportional',
                     'ref_composition': ['satire', 'paragraph'],
                     'source_url': 'https://www.gutenberg.org/ebooks/50657'}],
        'license': 'Public domain: Bohn edition, 1861. '
                   'Text from Project Gutenberg.',
        'attribution': translator_note + ' (Bohn), via Project Gutenberg',
        'n_units_stored': len(ulist), 'units': ulist, 'ref_to_unit': ref2u,
    }, open(os.path.join(out_dir, f'la__{tessname}.json'), 'w'),
        ensure_ascii=False)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--src', required=True)
    ap.add_argument('--tess-dir', required=True)
    ap.add_argument('--out-dir', required=True)
    args = ap.parse_args()
    os.makedirs(args.out_dir, exist_ok=True)
    lines = open(args.src, encoding='utf-8', errors='replace').read().split('\n')

    # region boundaries: the translation runs, not the ARGUMENTS block
    sat1 = [i for i, l in enumerate(lines) if l.strip() == 'SATIRE I.']
    prol = next(i for i, l in enumerate(lines) if l.strip() == 'PROLOGUE.')
    sulp = next(i for i, l in enumerate(lines) if l.strip() == 'SULPICIA.')
    juv_start = next(i for i in sat1 if i > 2900)   # after the ARGUMENTS
    juvenal = lines[juv_start:prol]
    persius = lines[prol:sulp]

    allocate(r'juv\.', 'juvenal.satires', parse_satires(juvenal),
             args.tess_dir, args.out_dir, 'Lewis Evans')
    allocate(r'pers\. sati\.', 'persius.saturae', parse_satires(persius),
             args.tess_dir, args.out_dir, 'Lewis Evans')


if __name__ == '__main__':
    main()
