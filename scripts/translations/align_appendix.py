#!/usr/bin/env python3
"""The Appendix Vergiliana, from Fairclough's Loeb (1916 printing of
Virgil vol. II), by the Claudian self-matching method.

The corpus carries the pseudo-Vergilian poems twice — as individual
works (culex, copa, moretum, dirae, lydia, priapea, catalepton...) and
as one combined file with its own tag strings — with no English at all
(4,780 lines). The 1916 volume contains Copa, Culex, Moretum, Dirae
(with the Lydia attached, as the manuscripts transmit it), Priapea and
Catalepton; Ciris, Aetna and the Elegiae in Maecenatem entered the Loeb
only in the 1934 revision, which is not public domain, so those poems
stay honestly uncovered.

Method is align_claudian.py's: pages are split at the running headers
(Latin pages are headed VIRGIL, English pages by the poem's title), a
Latin page identifies itself by looking its first verse line up in the
corpus, the following English page serves that span, and the span
closes at the next matched Latin page. One Latin line exists in TWO
corpus files (the individual poem and the combined appendix), so the
index maps each line to every ref that carries it and both families are
written in one pass.

Usage:
    python scripts/translations/align_appendix.py \
        --src <workswithenglish02virguoft_djvu.txt> \
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
    'vergil_pseudo.culex', 'vergil_pseudo.ciris', 'vergil_pseudo.copa',
    'vergil_pseudo.moretum', 'vergil_pseudo.dirae', 'vergil_pseudo.lydia',
    'vergil_pseudo.priapea', 'vergil_pseudo.catalepton',
    'vergil_pseudo.aetna', 'vergil_pseudo.elegiae_in_maecenatem',
    'vergil_pseudo.appendix_vergiliana_combined',
]
HEADERS = {'VIRGIL', 'CULEX', 'COPA', 'MORETUM', 'DIRAE', 'LYDIA',
           'PRIAPEA', 'CATALEPTON', 'CIRIS', 'AETNA', 'APPENDIX'}
STOP = {'the', 'of', 'and', 'to', 'that', 'with', 'for', 'her', 'his',
        'thy', 'thou', 'he', 'she', 'not', 'but', 'by', 'was', 'from',
        'all', 'shall', 'thee', 'when', 'their', 'or', 'be', 'now',
        'is', 'have', 'hath', 'will'}


def eng_share(text):
    words = [w.lower().strip('.,;:?!()"’“”') for w in text.split()]
    if len(words) < 8:
        return None
    return sum(1 for w in words if w in STOP) / len(words)


def norm(s):
    s = s.lower().replace('v', 'u').replace('j', 'i')
    return re.sub(r'[^a-z]', '', s)[:24]


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

    # pages split at the running headers
    blocks, cur = [], []
    for ln in open(args.src, encoding='utf-8', errors='replace'):
        s = ln.strip()
        if re.sub(r'[^A-Z]', '', s) in HEADERS and len(s) < 20:
            if cur:
                blocks.append(cur)
            cur = []
            continue
        cur.append(ln.rstrip('\n'))
    if cur:
        blocks.append(cur)

    seq = []
    for block in blocks:
        body = [l for l in block if l.strip()]
        if not body:
            continue
        text = ' '.join(l.strip() for l in body)
        share = eng_share(text)
        if share is None:
            continue
        if share < 0.12:
            hit = None
            for l in body:
                t = re.sub(r'\s+\d+\s*$', '', l.strip())
                key = norm(t)
                if len(key) >= 12 and key in index:
                    hit = index[key]
                    break
            seq.append(('la', hit) if hit else ('la-unmatched',))
        else:
            en = re.sub(r'\[\d+\]', '', text)
            en = re.sub(r'\s+', ' ', en).strip()
            seq.append(('en', en))

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
            # span end: the next Latin page matched to the same work
            i1 = None
            for k2 in la_pos[kidx + 1:]:
                nxt = dict(seq[k2][1]) if seq[k2][0] == 'la' else {}
                if work in nxt:
                    i1 = nxt[work] - 1
                    break
            if i1 is None or i1 < i0 or i1 - i0 > 45:
                i1 = min(i0 + 30, len(order[work]) - 1)
            i1 = min(i1, len(order[work]) - 1)

            def poem_of(ref):
                m = re.search(r'app_ver\. (\d+)\.', ref)
                return m.group(1) if m else None
            p0 = poem_of(order[work][i0])
            for i in range(i0, i1 + 1):
                ref = order[work][i]
                # the combined file runs poem into poem, and a fallback
                # span must never leak one poem's English into the next
                # (Copa's melon was being served for Culex 1)
                if p0 is not None and poem_of(ref) != p0:
                    break
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
        ok = hit is not None and hit >= 0.25 and cov >= 0.5
        print(f'{work:48s} cov {cov:.4f} ({len(mp)}/{len(refs)}) '
              f'units {len(ulist)} names {hit}/{n} '
              + ('ok' if ok else 'REJECTED'))
        if not ok:
            continue
        json.dump({
            'tess_work': f'la/{work}', 'language': 'la',
            'n_tess_refs': len(refs), 'n_translated': len(mp),
            'coverage': round(cov, 4),
            'mean_source_lines_per_translation_unit':
                round(len(mp) / max(1, len(ulist)), 1),
            'alignment_confidence': 'high' if hit >= 0.5 else 'medium',
            'name_check_hit_rate': hit, 'name_check_n': n,
            'verified_by': 'names',
            'sources': [{'translator': 'H. Rushton Fairclough', 'year': 1918,
                         'title': 'Virgil vol. II: Aeneid VII-XII and the '
                                  'Minor Poems (Loeb)',
                         'publisher': 'William Heinemann',
                         'mode': 'page',
                         'ref_composition': ['facing-page line span'],
                         'source_url': 'https://archive.org/details/'
                                       'workswithenglish02virguoft'}],
            'license': 'Public domain in the United States: published '
                       '1918. Text from the Internet Archive scan.',
            'attribution': 'H. R. Fairclough (Loeb, 1918), '
                           'via the Internet Archive',
            'n_units_stored': len(ulist), 'units': ulist,
            'ref_to_unit': ref2u,
        }, open(os.path.join(args.out_dir, f'la__{work}.json'), 'w'),
            ensure_ascii=False)


if __name__ == '__main__':
    main()
