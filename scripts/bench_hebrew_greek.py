#!/usr/bin/env python3
"""Hebrew->Greek (Septuagint) cross-lingual benchmark.

For each Hebrew book paired with its Septuagint counterpart, rank all LXX verses for
each Hebrew verse by an IDF-weighted shared-dictionary score (via the Hebrew-Greek
dictionary), and measure how often the TRUE same-reference LXX verse is retrieved at
rank 1 and within the top 5. Reports per-book and overall recall.

Books use aligned chapter:verse numbering (Torah + Former Prophets); Psalms are skipped
because Hebrew/LXX psalm numbering is offset.
"""
import os, sys, re, math, glob, unicodedata
from collections import defaultdict, Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from backend.text_processor import TextProcessor
from backend.hebrew import register as reg_he
reg_he()
from backend.synonym_dict import CROSSLINGUAL_STOPLIST_GREEK

PAIRS = [
    ('genesis', 'septuaginta.genesis'),
    ('deuteronomy', 'septuaginta.deuteronomion'),
    ('1_samuel', 'septuaginta.basileion_a'),
    ('2_samuel', 'septuaginta.basileion_b'),
    ('1_kings', 'septuaginta.basileion_g'),
    ('2_kings', 'septuaginta.basileion_d'),
]
# Exodus if present under any name
ex = glob.glob(os.path.join(ROOT, 'texts/grc/septuaginta.exod*.tess'))
if ex:
    PAIRS.insert(1, ('exodus', os.path.basename(ex[0])[:-5]))

def norm_gr(s):
    s = unicodedata.normalize('NFD', str(s).strip().lower())
    s = ''.join(c for c in s if unicodedata.category(c) != 'Mn')
    return s.replace('ς', 'σ')

def load_he_greek():
    d = defaultdict(set)
    with open(os.path.join(ROOT, 'backend/synonymy/v6_additions/hebrew_greek.csv'), encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'): continue
            p = line.split(',')
            if len(p) < 2: continue
            g = norm_gr(p[1])
            if len(g) >= 3 and g not in CROSSLINGUAL_STOPLIST_GREEK:
                d[p[0].strip()].add(g)
    return d

def chv(ref):
    m = re.search(r'(\d+)[.:](\d+)\s*$', str(ref))
    return f'{m.group(1)}.{m.group(2)}' if m else None

def main():
    tp = TextProcessor()
    he_greek = load_he_greek()
    print(f'Hebrew-Greek dict: {len(he_greek)} Hebrew words', flush=True)
    tot_r1 = tot_r5 = tot_n = 0
    print(f'\n{"book":<14}{"verses":>8}{"R@1":>8}{"R@5":>8}', flush=True)
    for he_book, lxx_base in PAIRS:
        he_fp = os.path.join(ROOT, 'texts/he', f'hebrew_bible.{he_book}.tess')
        lxx_fp = os.path.join(ROOT, 'texts/grc', f'{lxx_base}.tess')
        if not (os.path.exists(he_fp) and os.path.exists(lxx_fp)):
            print(f'{he_book:<14} (missing file, skip)', flush=True); continue
        he = tp.process_file(he_fp, 'he', 'line')
        lxx = tp.process_file(lxx_fp, 'grc', 'line')
        # LXX verses: greek lemma sets + ref index
        lxx_greek = []      # list of set(norm greek), filtered by stoplist
        lxx_ref = {}        # chv -> index
        for i, u in enumerate(lxx):
            gs = {norm_gr(l) for l in u.get('lemmas', []) if l}
            gs = {g for g in gs if len(g) >= 3 and g not in CROSSLINGUAL_STOPLIST_GREEK}
            lxx_greek.append(gs)
            r = chv(u.get('ref'))
            if r and r not in lxx_ref:
                lxx_ref[r] = i
        N = len(lxx)
        df = Counter()
        for gs in lxx_greek:
            for g in gs: df[g] += 1
        idf = {g: math.log(N / c) for g, c in df.items()}
        # for each Hebrew verse whose same-ref LXX verse exists, rank LXX verses
        r1 = r5 = n = 0
        for u in he:
            r = chv(u.get('ref'))
            if r is None or r not in lxx_ref: continue
            true_i = lxx_ref[r]
            he_g = set()
            for lem in u.get('lemmas', []):
                he_g |= he_greek.get(lem, set())
            if not he_g: continue
            scores = []
            for i, gs in enumerate(lxx_greek):
                shared = he_g & gs
                if shared:
                    scores.append((sum(idf.get(g, 0.0) for g in shared), i))
            if not scores: continue
            scores.sort(reverse=True)
            n += 1
            if scores[0][1] == true_i: r1 += 1
            if any(i == true_i for _, i in scores[:5]): r5 += 1
        tot_r1 += r1; tot_r5 += r5; tot_n += n
        print(f'{he_book:<14}{n:>8}{(r1/n if n else 0):>8.2f}{(r5/n if n else 0):>8.2f}', flush=True)
    print(f'\n{"OVERALL":<14}{tot_n:>8}{(tot_r1/tot_n if tot_n else 0):>8.2f}{(tot_r5/tot_n if tot_n else 0):>8.2f}', flush=True)
    print(f'\nR@1 = true LXX verse ranks first; R@5 = within top 5. IDF-weighted shared-dictionary score.', flush=True)
    print('BENCH DONE', flush=True)

if __name__ == '__main__':
    main()
