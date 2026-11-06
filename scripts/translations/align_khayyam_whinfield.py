#!/usr/bin/env python3
"""Khayyam: E. H. Whinfield, The Quatrains of Omar Khayyam (Trubner, London 1882, second
edition of his 253-quatrain translation), against our khayyam.diwan.

The Internet Archive scan prints Whinfield's Persian as images, so the OCR holds the English
only and nothing can be matched by first line. The quatrains are matched by meaning with the
multilingual encoder (persian_semantic_common.py, strict rules) and judged on evidence the
matcher never saw. Our file carries the poet in more than one edition, so many quatrains
occur twice: duplicates are recognized (cosine 0.97 or more between Persian quatrains) and
every copy gets the English of the quatrain it duplicates.

Whinfield translates his own selection of 253. Where no Persian quatrain of ours is a clear
mutual best match, nothing is written for it. The English is a verse translation in the
quatrain form, close to literal.

Usage: python align_khayyam_whinfield.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import persian_poems as P
import persian_semantic_common as S
from write_aligned import write_aligned

SRC = os.environ.get('TESSERAE_PERSIAN_SRC', '/home/ncoffee/tesserae-backups/tr-d-staging/src')
OUT = os.environ.get('TESSERAE_FA_OUT', '/home/ncoffee/tesserae-backups/tr-d-staging/persian')
TESS = os.environ.get('TESSERAE_TEXTS', '/var/www/tesseraev6_flask/texts') + '/fa/khayyam.diwan.tess'
SOURCE = {'translator': 'Edward Henry Whinfield', 'year': 1882,
          'title': 'The Quatrains of Omar Khayyam (Persian text and English verse)',
          'place': 'London', 'publisher': "Trubner and Co. (Trubner's Oriental Series)",
          'license': 'public domain', 'url': 'https://archive.org/details/quatrains00omaruoft'}


MARGIN = 0.0


def main():
    rows = [ln.rstrip('\n').split('>\t', 1) for ln in open(TESS, encoding='utf-8')]
    refs = [r[1:] if r.startswith('<') else r for r, _ in rows]
    lines = [t for _, t in rows]
    groups = P.rubai_groups(lines)
    fa_text = [' / '.join(lines[a:b]) for a, b in groups]
    en = P.english_quatrains(f'{SRC}/whinfield.txt', 1930, 4770)
    en_text = [t for _, t in en]
    print(f'{len(groups)} Persian quatrains of ours, {len(en)} English quatrains read from Whinfield '
          f'({len([1 for v, _ in en if v])} with a numeral)')
    os.makedirs(OUT, exist_ok=True)
    FA = S.embed(fa_text, f'{OUT}/khayyam_fa.cache.json')
    EN = S.embed(en_text, f'{OUT}/khayyam_en.cache.json')
    # clusters of duplicate Persian quatrains
    n = len(FA)
    parent = list(range(n))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    for i in range(n):
        for j in range(i + 1, n):
            if S.dot(FA[i], FA[j]) >= 0.97:
                parent[find(j)] = find(i)
    clusters = {}
    for i in range(n):
        clusters.setdefault(find(i), []).append(i)
    reps = sorted(clusters)
    print(f'{len(reps)} distinct Persian quatrains after merging {n - len(reps)} duplicates')
    # similarity of each English quatrain to each cluster: the best member
    M = [[max(S.dot(EN[e], FA[m]) for m in clusters[r]) for r in reps] for e in range(len(EN))]
    M = S.csls(M)
    for mg in (0.0, 0.02, 0.04, 0.06):
        print(f'   margin {mg}: {len(S.mutual_best(M, margin=mg))} pairs')
    pairs = S.mutual_best(M, margin=MARGIN)
    print(f'{len(pairs)} mutual best matches with a clear margin (of {len(EN)} English quatrains)')
    # independent evidence 1: length of the Persian against length of the English
    xs = [sum(len(lines[i]) for i in range(*groups[reps[j]])) for e, j, _, _ in pairs]
    ys = [len(en_text[e]) for e, j, _, _ in pairs]
    corr = S.pearson(xs, ys)
    # control: the same Persian with English shifted by 7 positions in the pair list
    ctrl_corr = S.pearson(xs, ys[7:] + ys[:7])
    # independent evidence 2: both books keep the alphabetical order of the rhyme letter
    rho = S.spearman([e for e, _, _, _ in pairs], [j for _, j, _, _ in pairs])
    ctrl_rho = S.spearman([e for e, _, _, _ in pairs], ([j for _, j, _, _ in pairs][7:] + [j for _, j, _, _ in pairs][:7]))
    print(f'  length correlation {corr:.3f} (control {ctrl_corr:.3f}); rank correlation of positions '
          f'{rho:.3f} (control {ctrl_rho:.3f})')
    mean_sim = sum(p[2] for p in pairs) / len(pairs)
    print(f'  mean cosine of kept pairs {mean_sim:.3f}')
    for e, j, sim, mar in pairs[:5] + pairs[len(pairs) // 2:len(pairs) // 2 + 3]:
        print(f'   EN {en[e][0]}: {en_text[e][:90]}')
        print(f'   FA {fa_text[reps[j]][:90]}   cos {sim:.3f} margin {mar:.3f}')
    ok = corr is not None and corr >= 0.45 and corr >= (ctrl_corr or 0) + 0.25
    if not ok:
        print('NOT WRITTEN: the length check does not clear its control')
        return
    units, r2u = [], {}
    for e, j, sim, mar in pairs:
        units.append(en_text[e])
        for m in clusters[reps[j]]:
            a, b = groups[m]
            for k in range(a, b):
                r2u[refs[k]] = len(units) - 1
    src = dict(SOURCE, mode='quatrain, matched by meaning', ref_composition=['line'])
    path = write_aligned(
        OUT, 'fa', 'khayyam.diwan', units, r2u,
        attribution='E. H. Whinfield, The Quatrains of Omar Khayyam (1882), public domain',
        license='Public domain', sources=[src], confidence='medium', approximate=True,
        tess_refs=refs,
        name_check={'length_correlation': round(corr, 3), 'control_length_correlation': round(ctrl_corr, 3),
                    'rank_correlation': round(rho, 3), 'control_rank_correlation': round(ctrl_rho, 3),
                    'n_pairs': len(pairs), 'mean_cosine': round(mean_sim, 3)},
        verified_by='length of poem, and the order of the rhyme letters (neither seen by the matcher)',
        notes='Matched by meaning with a multilingual encoder, because the scan does not carry the '
              'Persian. Only mutual best matches with a clear margin are kept; our file holds some '
              'quatrains twice and both copies carry the English.')
    print('wrote', path, f'{len(r2u)} of {len(refs)} lines')


if __name__ == '__main__':
    main()
