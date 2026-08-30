#!/usr/bin/env python3
"""Fronto's correspondence: Haines' Loeb English (1919-20 scans) keyed to
the Latin Library text by HAINES PAGE NUMBERS.

The LL page (our corpus source) tags every letter with its Loeb location:
"ad M. Caesarem 1.2 [1 Hout; 1.80 Haines]" -> volume 1, page 80. The scan
OCR yields pages separated by standalone page-number lines (the number
prints at the END of its page). Loebs put Latin on the even page and the
facing English on the odd, so a letter at Haines page P is served by the
ENGLISH-classified pages P..P'-1 (P' = the next letter's page), where
"English-classified" is a stopword-density test (the only reliable
language separator in OCR; names pass Latin perfectly).

Letter-keyed: every corpus section of a letter carries the letter's whole
English. The name check guards the mapping.

Usage: align_fronto.py --ll <ll_fronto_epistulae.html> --ocr1 <vol1.txt>
       --ocr2 <vol2.txt> --tess <fronto.epistulae.tess> --out <json>
"""
import argparse
import html as htmllib
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import proper_names as V

STOP = set('''the and of to in that is was for with as his he not be at by
this have from or which but they their so it on all а you we our are were
than then when who him her them will would may can shall should more most
'''.split())

FRONTO_COLL = {
    'mcaes': 'mcaes', 'antimp': 'antimp', 'verimp': 'verimp',
    'amic': 'amic', 'antpium': 'antpium', 'addit': 'addit',
    'de_eloqu': 'eloq', 'de_orat': 'orat',
}


def english_score(text):
    words = re.findall(r"[a-zA-Z']+", text.lower())
    if len(words) < 20:
        return 0.0
    return sum(1 for w in words if w in STOP) / len(words)


def ocr_pages(path):
    """{page_number: text} from the djvu OCR; the number ends its page."""
    t = open(path, encoding='utf-8', errors='replace').read()
    parts = re.split(r'\n\s*(\d{1,3})\s*\n', t)
    pages = {}
    # parts = [text0, num0, text1, num1, ...]. In these scans the page
    # number prints at the TOP of its page (verified: '6' is immediately
    # followed by the Latin running head M. CORNELIUS FRONTO, and 6 is an
    # even = Latin page), so the text AFTER num_i is page num_i.
    for i in range(1, len(parts), 2):
        num = int(parts[i])
        body = parts[i + 1] if i + 1 < len(parts) else ''
        pages.setdefault(num, '')
        pages[num] += ' ' + body
    return pages


def clean_english(txt):
    txt = re.sub(r'^.{0,70}(TO +[A-Z. ,]{3,50}|M\. +CORNELIUS +FRONTO).{0,20}$',
                 ' ', txt, flags=re.M)
    # footnote blocks: lines starting with a digit-marker or containing
    # apparatus sigla are dropped
    keep = []
    for line in txt.split('\n'):
        s = line.strip()
        if re.match(r'^[0-9*]\s', s):
            continue
        keep.append(line)
    txt = ' '.join(keep)
    txt = re.sub(r'(\w)-\s+', r'\1', txt)
    txt = re.sub(r'\s+', ' ', txt).strip()
    return txt


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--ll', required=True)
    ap.add_argument('--ocr1', required=True)
    ap.add_argument('--ocr2', required=True)
    ap.add_argument('--tess', required=True)
    ap.add_argument('--out', required=True)
    args = ap.parse_args()

    ll = open(args.ll, encoding='utf-8', errors='replace').read()
    # letter anchors with their Haines locations
    pat = re.compile(
        r'name="(mcaes|antimp|verimp|amic|antpium|addit|de_eloqu|de_orat)'
        r'(?:_(\d+))?(?:_(\d+))?"[^>]*>.{0,200}?\[[^]]*?'
        r'(\d)\.(\d+)\s*Haines\]', re.S)
    letters = []
    for m in pat.finditer(ll):
        coll, a, b, vol, page = m.groups()
        if coll in ('mcaes', 'antimp', 'verimp', 'amic'):
            if b is None:
                continue
            tag = (f'{FRONTO_COLL[coll]}{a}', int(b))
        elif a is not None:
            tag = (FRONTO_COLL[coll], int(a))
        else:
            tag = (FRONTO_COLL[coll], 1)
        letters.append((tag, int(vol), int(page)))
    print(f'{len(letters)} letters with Haines locations')

    pages = {1: ocr_pages(args.ocr1), 2: ocr_pages(args.ocr2)}
    for vol in (1, 2):
        eng = {n for n, txt in pages[vol].items() if english_score(txt) > 0.18}
        print(f'vol {vol}: {len(pages[vol])} pages, {len(eng)} classified English')

    # order letters by (vol, page) to know each letter's page range
    order = sorted(range(len(letters)), key=lambda i: (letters[i][1],
                                                       letters[i][2]))
    english = {}
    for oi, i in enumerate(order):
        tag, vol, page = letters[i]
        if oi + 1 < len(order):
            nvol, npage = letters[order[oi + 1]][1], letters[order[oi + 1]][2]
            end = npage if nvol == vol else max(pages[vol]) + 1
        else:
            end = max(pages[vol]) + 1
        chunks = []
        for p in range(page, min(end + 1, max(pages[vol]) + 2)):
            txt = pages[vol].get(p)
            if txt and english_score(txt) > 0.18:
                if p == end and chunks:
                    break   # next letter starts on this page; stop unless
                            # we have nothing yet (letter within one page)
                chunks.append(clean_english(txt))
        if chunks:
            english[tag] = ' '.join(chunks)

    refs, lat = [], {}
    for line in open(args.tess, encoding='utf-8', errors='replace'):
        m = re.match(r'^<(front\. epist\. ([a-z0-9]+)\.(\d+)\.\d+)>\s*(.*)',
                     line)
        if m:
            refs.append((m.group(1), (m.group(2), int(m.group(3)))))
            lat[m.group(1)] = m.group(4)
    mapping = {r: english[k] for r, k in refs if k in english}
    cov = len(mapping) / len(refs)
    hit, n = V.score([(lat[r], t) for r, t in mapping.items()], 'la',
                     sample=500)
    ulist, idx, ref2u = [], {}, {}
    for ref, txt in mapping.items():
        if txt not in idx:
            idx[txt] = len(ulist)
            ulist.append(txt)
        ref2u[ref] = idx[txt]
    print(f'fronto: cov {cov:.4f} ({len(mapping)}/{len(refs)}) '
          f'units {len(ulist)} names {hit}/{n}')
    if hit is None or hit < 0.25:
        print('REFUSED')
        sys.exit(1)
    json.dump({
        'tess_work': 'la/fronto.epistulae', 'language': 'la',
        'n_tess_refs': len(refs), 'n_translated': len(mapping),
        'coverage': round(cov, 4),
        'mean_source_lines_per_translation_unit':
            round(len(mapping) / max(1, len(ulist)), 1),
        'alignment_confidence': 'medium' if hit < 0.5 else 'high',
        'name_check_hit_rate': hit, 'name_check_n': n,
        'verified_by': 'names',
        'sources': [{'translator': 'C. R. Haines', 'year': 1919,
                     'title': 'The Correspondence of Marcus Cornelius '
                              'Fronto (Loeb, 2 vols 1919-20)',
                     'publisher': 'Heinemann (archive.org OCR)',
                     'mode': 'letter-page-range',
                     'ref_composition': ['collection', 'letter'],
                     'source_url': 'https://archive.org/details/'
                                   'correspondenceof01fronuoft'}],
        'license': 'Public domain: Haines (Loeb), 1919-1920.',
        'attribution': 'C. R. Haines (Loeb), via archive.org',
        'n_units_stored': len(ulist), 'units': ulist, 'ref_to_unit': ref2u,
    }, open(args.out, 'w', encoding='utf-8'), ensure_ascii=False)


if __name__ == '__main__':
    main()
