#!/usr/bin/env python3
"""Ausonius (both Loeb volumes, Evelyn-White 1919/1921), plus the
Paulinus of Nola verse letters the second volume carries in its
appendix -- the only public-domain English Paulinus there is.

~3,100 uncovered Ausonius lines across two dozen small works, plus
carmina 10-11 of Paulinus. Same self-matching method as align_claudian:
pages are split at the running headers (both sides are headed AUSONIUS,
so the split is on the header line and the LANGUAGE of a page comes from
the pure-English stopword test alone); each Latin page finds its work
and position by looking its first verse line up in the corpus of every
registered work at once, the following English page serves that span,
and spans close at the next matched page of the same work. Work identity
therefore never depends on parsing Evelyn-White's titles or numbering.

Usage:
    python scripts/translations/align_ausonius.py \
        --src-dir <dir with ausonius1.txt ausonius2.txt> \
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
    'ausonius.mosella', 'ausonius.eclogarum_liber', 'ausonius.parentalia',
    'ausonius.ephemeris_id_est_totius_diei_negotium',
    'ausonius.ludus_septem_sapientum', 'ausonius.technopaegnion',
    'ausonius.epitaphia_heroum_qui_bello_troico_interfuerunt',
    'ausonius.ordo_urbium_nobilium', 'ausonius.cento_nuptialis',
    'ausonius.cupido_cruciatus', 'ausonius.griphus_ternarii_numeri',
    'ausonius.precationes', 'ausonius.praefatiunculae',
    'ausonius.epicedion_in_patrem',
    'ausonius.oratio_consulis_ausonii_versibus_rhopalicis',
    'ausonius.de_herediolo', 'ausonius.versus_paschales_pro_augusto_dicti',
    'ausonius.de_xii_caesaribus',
    'ausonius.commemoratio_professorum_burdigalensium',
    'ausonius.libri_de_fastis_conclusio', 'ausonius.de_bissula',
    'paulinus_of_nola.carmina',
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
    t = re.sub(r'[^A-Z]', '', s.upper())
    for w in ('AUSONIUS', 'AVSONIUS', 'APPENDIX', 'PAULINUS'):
        for i in range(len(t) - len(w) + 1 if len(t) >= len(w) else 0):
            if sum(a != b for a, b in zip(t[i:i + len(w)], w)) <= 2:
                return True
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--src-dir', required=True)
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
    for fname in ('ausonius1.txt', 'ausonius2.txt'):
        cur = []
        for ln in open(os.path.join(args.src_dir, fname),
                       encoding='utf-8', errors='replace'):
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

            def poem_of(ref):
                m = re.search(r'carmina\. (\d+)\.', ref)
                return m.group(1) if m else None
            p0 = poem_of(order[work][i0])
            for i in range(i0, i1 + 1):
                ref = order[work][i]
                # Paulinus' long poems must not leak into one another on
                # a fallback span, and only the pieces Evelyn-White
                # actually prints (the Oratio = carm. 4-5, the verse
                # epistles 10-11) may be served at all
                if work == 'paulinus_of_nola.carmina':
                    pp = poem_of(ref)
                    if pp != p0 or pp not in ('4', '5', '10', '11'):
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
        floor = 0.5 if work != 'paulinus_of_nola.carmina' else 0.02
        ok = (hit is None or hit >= 0.25 or n < 10) and cov >= floor
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
            'sources': [{'translator': 'Hugh G. Evelyn-White',
                         'year': 1921,
                         'title': 'Ausonius, with an English translation '
                                  '(Loeb, 2 vols, 1919-21)',
                         'publisher': 'William Heinemann',
                         'mode': 'page',
                         'ref_composition': ['facing-page line span'],
                         'source_url': 'https://archive.org/details/'
                                       'deciausonius01ausouoft'}],
            'license': 'Public domain in the United States: published '
                       '1919-1921. Text from the Internet Archive scans.',
            'attribution': 'H. G. Evelyn-White (Loeb, 1919-21), '
                           'via the Internet Archive',
            'n_units_stored': len(ulist), 'units': ulist,
            'ref_to_unit': ref2u,
        }, open(os.path.join(args.out_dir, f'la__{work}.json'), 'w'),
            ensure_ascii=False)


if __name__ == '__main__':
    main()
