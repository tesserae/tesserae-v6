#!/usr/bin/env python3
"""Boethius, the theological tractates, from the Stewart-Rand Loeb of
1918 (Internet Archive scan) by the self-matching facing-page method of
align_claudian.py / align_ausonius.py.

Five opuscula sacra (~360 corpus lines, reference schemes ranging from
'Incipit' tags to spans like '1-4' -- which is why the method that never
parses references, only exact tag strings in file order, fits). The
commentary on Porphyry is not in the Loeb and stays uncovered. Pages are
split at the short running-header lines and classified Latin/English by
the stopword test; Latin pages self-identify by corpus lookup.

Usage:
    python scripts/translations/align_boethius.py \
        --src <theologicaltrac00testgoog_djvu.txt> \
        --tess-dir texts/la --out-dir <dir>
"""
import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import proper_names as V

WORKS = [
    'boethius.quomodo_trinitas', 'boethius.utrum_pater',
    'boethius.quomodo_substantiae_in_eo_quod_sint_bonae_sint_cum_non_'
    'sint_substantialia_bona',
    'boethius.de_fide_catholica',
    'boethius.liber_de_persona_et_duabus_naturis_contra_eutychen_et_'
    'nestorium',
]
STOP = {'the', 'of', 'and', 'to', 'that', 'with', 'for', 'her', 'his',
        'thy', 'thou', 'he', 'she', 'not', 'but', 'by', 'was', 'from',
        'all', 'shall', 'thee', 'when', 'their', 'or', 'be', 'now',
        'is', 'have', 'hath', 'will', 'my', 'you'}


def eng_share(text):
    words = [w.lower().strip('.,;:?!()"’“”') for w in text.split()]
    if len(words) < 8:
        return None
    return sum(1 for w in words if w in STOP) / len(words)


def norm(s):
    s = s.lower().replace('v', 'u').replace('j', 'i')
    return re.sub(r'[^a-z]', '', s)[:24]


def fuzzy_header(s):
    # any short line set entirely in capitals is a running header here
    t = s.strip()
    return (0 < len(t) < 34 and t.upper() == t
            and len(re.sub(r'[^A-Z]', '', t)) >= 6)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--src', required=True)
    ap.add_argument('--tess-dir', required=True)
    ap.add_argument('--out-dir', required=True)
    args = ap.parse_args()
    os.makedirs(args.out_dir, exist_ok=True)

    index, order, latin_of = {}, {}, {}
    for work in WORKS:
        path = os.path.join(args.tess_dir, work + '.tess')
        if not os.path.exists(path):
            continue
        refs = []
        for line in open(path, encoding='utf-8', errors='replace'):
            m = re.match(r'^<([^>]+)>\s*(.*)', line)
            if not m:
                continue
            ref, latin = m.group(1).strip(), m.group(2).strip()
            refs.append(ref)
            latin_of[(work, ref)] = latin
            key = norm(latin)
            if len(key) >= 12:
                index.setdefault(key, []).append((work, len(refs) - 1))
        order[work] = refs

    seq = []
    for fname in (args.src,):
        cur = []
        for ln in open(fname, encoding='utf-8', errors='replace'):
            s = ln.strip()
            if (len(s) < 26 and fuzzy_header(s)) or re.fullmatch(r'\d+', s):
                if cur:
                    body = [l for l in cur if l.strip()]
                    text = ' '.join(l.strip() for l in body)
                    share = eng_share(text)
                    if share is not None:
                        if share < 0.12:
                            hit = None
                            for l in body:
                                t = re.sub(r'\s+\d+\s*$', '', l.strip())
                                key = norm(t)
                                if len(key) >= 12 and key in index:
                                    hit = index[key]
                                    break
                            seq.append(('la', hit) if hit
                                       else ('la-unmatched',))
                        else:
                            en = re.sub(r'\[\d+\]', '', text)
                            en = re.sub(r'\s+', ' ', en).strip()
                            seq.append(('en', en))
                cur = []
                continue
            cur.append(ln.rstrip('\n'))

    la_pos = [k for k, e in enumerate(seq) if e[0] == 'la']
    mapping = {w: {} for w in WORKS}
    pairs = {w: [] for w in WORKS}
    for kidx, k in enumerate(la_pos):
        hits = seq[k][1]
        if k + 1 >= len(seq) or seq[k + 1][0] != 'en':
            continue
        en = seq[k + 1][1]
        if len(en.split()) < 12:
            continue
        for work, i0 in hits:
            i1 = None
            for k2 in la_pos[kidx + 1:kidx + 12]:
                nxt = dict(seq[k2][1]) if seq[k2][0] == 'la' else {}
                if work in nxt:
                    i1 = nxt[work] - 1
                    break
            if i1 is None or i1 < i0 or i1 - i0 > 45:
                i1 = min(i0 + 30, len(order[work]) - 1)
            i1 = min(i1, len(order[work]) - 1)

            for i in range(i0, i1 + 1):
                ref = order[work][i]
                if ref not in mapping[work]:
                    mapping[work][ref] = en
                    pairs[work].append((latin_of[(work, ref)], en))

    for work in WORKS:
        refs = order.get(work, [])
        if not refs:
            continue
        mp = mapping[work]
        cov = len(mp) / len(refs)
        hit, n = V.score(pairs[work], 'la', sample=500)
        ulist, idx, ref2u = [], {}, {}
        for ref, txt in mp.items():
            if txt not in idx:
                idx[txt] = len(ulist)
                ulist.append(txt)
            ref2u[ref] = idx[txt]
        ok = (hit is None or hit >= 0.25 or n < 10) and cov >= 0.5
        print(f'{work:56s} cov {cov:.4f} ({len(mp)}/{len(refs)}) '
              f'units {len(ulist)} names {hit}/{n} '
              + ('ok' if ok else 'REJECTED'))
        if not ok or not mp:
            continue
        json.dump({
            'tess_work': f'la/{work}', 'language': 'la',
            'n_tess_refs': len(refs), 'n_translated': len(mp),
            'coverage': round(cov, 4),
            'mean_source_lines_per_translation_unit':
                round(len(mp) / max(1, len(ulist)), 1),
            'alignment_confidence': 'high' if (hit or 0) >= 0.5 else 'medium',
            'name_check_hit_rate': hit, 'name_check_n': n,
            'verified_by': 'names',
            'sources': [{'translator': 'H. F. Stewart and E. K. Rand',
                         'year': 1918,
                         'title': 'Boethius: The Theological Tractates '
                                  '(Loeb)',
                         'publisher': 'William Heinemann',
                         'mode': 'page',
                         'ref_composition': ['facing-page span'],
                         'source_url': 'https://archive.org/details/'
                                       'theologicaltrac00testgoog'}],
            'license': 'Public domain in the United States: published '
                       '1918. Text from the Internet Archive scan.',
            'attribution': 'H. F. Stewart and E. K. Rand (Loeb, 1918), '
                           'via the Internet Archive',
            'n_units_stored': len(ulist), 'units': ulist,
            'ref_to_unit': ref2u,
        }, open(os.path.join(args.out_dir, f'la__{work}.json'), 'w'),
            ensure_ascii=False)


if __name__ == '__main__':
    main()
