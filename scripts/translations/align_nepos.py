#!/usr/bin/env python3
"""Cornelius Nepos, the Lives, from Watson's Bohn prose in the
tertullian.org transcription (clean HTML, the Martial source's sibling).

837 corpus lines, no English. Corpus refs are life.chapter.section with
abbreviated life names; Watson's page gives each life its own heading
("VII. ALCIBIADES.") followed by an ARGUMENT (chapter summary whose
entries end ", III.----") and then the chapters, the first opening
"I. AT the time..." with the first word in capitals. So: lives are cut
at the headings and mapped to the corpus abbreviations by name; the
chapter chain is anchored at the "I. <CAPS>" opening (which steps past
the argument), and later markers join by the expected-successor window.
Chapter-keyed exact; all sections of a chapter serve its English.

Usage:
    python scripts/translations/align_nepos.py \
        --src <nepos.htm> --tess texts/la/nepos.vitae.tess --out <json>
"""
import argparse
import html as htmllib
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import proper_names as V

LIVES = {
    'MILTIADES': 'milt', 'THEMISTOCLES': 'them', 'ARISTIDES': 'ar',
    'PAUSANIAS': 'paus', 'CIMON': 'cim', 'LYSANDER': 'lys',
    'ALCIBIADES': 'alc', 'THRASYBULUS': 'thr', 'CONON': 'con',
    'DION': 'di', 'IPHICRATES': 'iph', 'CHABRIAS': 'cha',
    'TIMOTHEUS': 'timoth', 'DATAMES': 'dat', 'EPAMINONDAS': 'ep',
    'PELOPIDAS': 'pel', 'AGESILAUS': 'ag', 'EUMENES': 'eum',
    'PHOCION': 'phoc', 'TIMOLEON': 'timol', 'OF KINGS': 'reg',
    'HAMILCAR': 'ham', 'HANNIBAL': 'han', 'CATO': 'ca', 'ATTICUS': 'att',
    'PREFACE': 'praef',
}
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--src', required=True)
    ap.add_argument('--tess', required=True)
    ap.add_argument('--out', required=True)
    args = ap.parse_args()

    t = open(args.src, encoding='utf-8', errors='replace').read()
    segs = re.split(r'<h[234][^>]*>(.*?)</h[234]>', t, flags=re.S)
    english = {}
    for k in range(1, len(segs), 2):
        head = re.sub(r'<[^>]+>', '', segs[k]).strip().upper()
        tag = next((v for name, v in LIVES.items() if name in head), None)
        if tag is None or k + 1 >= len(segs):
            continue
        body = re.sub(r'<[^>]+>', ' ', segs[k + 1])
        body = re.sub(r'\|+\d*', '', htmllib.unescape(body))
        body = re.sub(r'\s+', ' ', body).strip()
        if tag == 'praef':
            english[('praef', 1)] = body
            continue
        # anchor: the first chapter opens "I. " + a fully capitalised word
        m = re.search(r'\bI\.\s+[A-Z]{2,}', body)
        if not m:
            english[(tag, 1)] = body      # single-chapter lives
            continue
        body = body[m.start():]
        marks, cur = [], 0
        for mm in re.finditer(r'\b([IVXL]+)\.\s', body):
            n = roman_to_int(mm.group(1))
            if n is not None and cur + 1 <= n <= cur + 2:
                marks.append((n, mm))
                cur = n
        for i, (n, mm) in enumerate(marks):
            end = marks[i + 1][1].start() if i + 1 < len(marks) else len(body)
            chunk = body[mm.end():end].strip()
            chunk = re.sub(r'\s*\d+\s*$', '', chunk)
            if len(chunk.split()) >= 5:
                english[(tag, n)] = chunk

    refs, lat = [], {}
    for line in open(args.tess, encoding='utf-8', errors='replace'):
        m = re.match(r'^<(nep\. vitae\. (\w+)\.(\d+)(?:\.\d+)?)>\s*(.*)',
                     line)
        if m:
            refs.append((m.group(1), m.group(2), int(m.group(3))))
            lat[m.group(1)] = m.group(4)

    mapping, pairs = {}, []
    for ref, tag, c in refs:
        txt = english.get((tag, c))
        if txt:
            mapping[ref] = txt
            pairs.append((lat[ref], txt))
    cov = len(mapping) / len(refs)
    hit, n = V.score(pairs, 'la', sample=500)
    ulist, idx, ref2u = [], {}, {}
    for ref, txt in mapping.items():
        if txt not in idx:
            idx[txt] = len(ulist)
            ulist.append(txt)
        ref2u[ref] = idx[txt]
    print(f'nepos: cov {cov:.4f} ({len(mapping)}/{len(refs)}) units '
          f'{len(ulist)} names {hit}/{n}')
    if hit is None or hit < 0.25:
        print('REJECTED')
        return
    json.dump({
        'tess_work': 'la/nepos.vitae', 'language': 'la',
        'n_tess_refs': len(refs), 'n_translated': len(mapping),
        'coverage': round(cov, 4),
        'mean_source_lines_per_translation_unit':
            round(len(mapping) / max(1, len(ulist)), 1),
        'alignment_confidence': 'high' if hit >= 0.5 else 'medium',
        'name_check_hit_rate': hit, 'name_check_n': n,
        'verified_by': 'names',
        'sources': [{'translator': 'John Selby Watson', 'year': 1886,
                     'title': 'Lives of Eminent Commanders (Bohn)',
                     'publisher': 'George Bell and Sons '
                                  '(tertullian.org transcription)',
                     'mode': 'exact', 'ref_composition': ['life', 'chapter'],
                     'source_url': 'https://www.tertullian.org/fathers/'
                                   'nepos.htm'}],
        'license': 'Public domain: Watson (Bohn), 1886 printing. '
                   'Transcription by Roger Pearse (public domain).',
        'attribution': 'J. S. Watson (Bohn), via tertullian.org',
        'n_units_stored': len(ulist), 'units': ulist, 'ref_to_unit': ref2u,
    }, open(args.out, 'w'), ensure_ascii=False)


if __name__ == '__main__':
    main()
